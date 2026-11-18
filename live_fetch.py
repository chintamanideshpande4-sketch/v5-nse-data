"""Live (intraday) snapshot for the V5 Friday check: NSE index constituents' last prices.

Writes live/snapshot.json: {fetched_ist, sources:{...status...}, index:{name,last,time}, stocks:{SYMBOL:{last,prev_close,time}}}
Tries NSE's own live API first (needs a cookie from the home page), then Yahoo Finance for the index level.
Standard library only.
"""
import os, json, time, datetime as dt, urllib.request, urllib.parse, http.cookiejar

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live')
INDICES = ['NIFTY 500', 'NIFTY TOTAL MARKET', 'NIFTY MICROCAP 250', 'SECURITIES IN F&O']

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
H = {'User-Agent': UA, 'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-US,en;q=0.9', 'Referer': 'https://www.nseindia.com/market-data/live-equity-market'}


def get(url, headers=H, timeout=30):
    req = urllib.request.Request(url, headers=headers)
    with op.open(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', 'ignore')


def main():
    os.makedirs(OUT, exist_ok=True)
    snap = {'fetched_ist': dt.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'), 'sources': {}, 'index': None, 'stocks': {}}
    try:
        st, _ = get('https://www.nseindia.com/', headers={'User-Agent': UA, 'Accept': 'text/html'})
        snap['sources']['nse_home'] = st
        time.sleep(1)
        get('https://www.nseindia.com/market-data/live-equity-market', headers={'User-Agent': UA, 'Accept': 'text/html'})
    except Exception as e:
        snap['sources']['nse_home'] = f'ERR {e}'
    for ix in INDICES:
        try:
            st, body = get('https://www.nseindia.com/api/equity-stockIndices?index=' + urllib.parse.quote(ix))
            d = json.loads(body); rows = d.get('data', [])
            n = 0
            for r in rows:
                sym = r.get('symbol')
                if sym == ix:
                    if ix == 'NIFTY 500':
                        snap['index'] = {'name': ix, 'last': r.get('lastPrice'), 'prev_close': r.get('previousClose'), 'time': r.get('lastUpdateTime') or d.get('timestamp')}
                    continue
                if sym and r.get('lastPrice') is not None:
                    snap['stocks'][sym] = {'last': r.get('lastPrice'), 'prev_close': r.get('previousClose'), 'time': r.get('lastUpdateTime')}
                    n += 1
            snap['sources']['nse_' + ix] = f'{st} rows={n} ts={d.get("timestamp")}'
        except Exception as e:
            snap['sources']['nse_' + ix] = f'ERR {str(e)[:120]}'
        time.sleep(1.5)
    try:
        st, body = get('https://query1.finance.yahoo.com/v8/finance/chart/%5ECRSLDX?interval=5m&range=1d', headers={'User-Agent': UA})
        m = json.loads(body)['chart']['result'][0]['meta']
        snap['sources']['yahoo_nifty500'] = f"{st} last={m.get('regularMarketPrice')} t={m.get('regularMarketTime')}"
        if snap['index'] is None:
            snap['index'] = {'name': 'NIFTY 500 (Yahoo)', 'last': m.get('regularMarketPrice'), 'prev_close': m.get('chartPreviousClose'),
                             'time': dt.datetime.fromtimestamp(m.get('regularMarketTime'), IST).strftime('%Y-%m-%d %H:%M:%S')}
    except Exception as e:
        snap['sources']['yahoo_nifty500'] = f'ERR {str(e)[:120]}'
    snap['n_stocks'] = len(snap['stocks'])
    json.dump(snap, open(os.path.join(OUT, 'snapshot.json'), 'w'), separators=(',', ':'))
    print(json.dumps({k: v for k, v in snap.items() if k != 'stocks'}, indent=1))


if __name__ == '__main__':
    main()
