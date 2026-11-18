"""Live (intraday) snapshot for the V5 Friday check.

Writes live/snapshot.json:
  {fetched_ist, sources, index:{name,last,prev_close,time}, stocks:{SYMBOL:{last,prev_close,time}}, n_stocks}
Index level and stock prices come from Yahoo Finance (NSE's own live API refuses GitHub's servers).
Stock universe = NSE symbols that traded >= Rs 3 Cr on any of the last 5 days in nse/ (official bhavcopy files).
Standard library only.
"""
import os, glob, csv, json, time, datetime as dt, urllib.request, urllib.parse

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'live')


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', 'ignore')


def ist(ts):
    return dt.datetime.fromtimestamp(ts, IST).strftime('%Y-%m-%d %H:%M:%S') if ts else None


def universe():
    files = sorted(glob.glob(os.path.join(HERE, 'nse', 'sec_bhavdata_full_*.csv')),
                   key=lambda p: os.path.basename(p)[-8:-4] + os.path.basename(p)[-10:-8] + os.path.basename(p)[-12:-10])[-5:]
    syms = set()
    for p in files:
        with open(p, newline='') as fh:
            rd = csv.reader(fh); hdr = [h.strip() for h in next(rd)]; ix = {h: i for i, h in enumerate(hdr)}
            for r in rd:
                if len(r) < len(hdr) - 1: continue
                r = [c.strip() for c in r]
                if r[ix['SERIES']] not in ('EQ', 'BE', 'BZ'): continue
                try:
                    if float(r[ix['TURNOVER_LACS']]) >= 300: syms.add(r[ix['SYMBOL']])
                except ValueError:
                    pass
    return sorted(syms)


def chart(sym):
    st, body = get('https://query1.finance.yahoo.com/v8/finance/chart/' + urllib.parse.quote(sym) + '?interval=5m&range=1d')
    m = json.loads(body)['chart']['result'][0]['meta']
    return m.get('regularMarketPrice'), m.get('chartPreviousClose'), m.get('regularMarketTime')


def main():
    os.makedirs(OUT, exist_ok=True)
    snap = {'fetched_ist': dt.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'), 'sources': {}, 'index': None, 'stocks': {}}
    try:
        last, prev, t = chart('^CRSLDX')
        snap['index'] = {'name': 'NIFTY 500', 'last': last, 'prev_close': prev, 'time': ist(t)}
        snap['sources']['yahoo_index'] = 'ok'
    except Exception as e:
        snap['sources']['yahoo_index'] = f'ERR {str(e)[:120]}'
    syms = universe(); snap['sources']['universe'] = len(syms)
    # batch first (fast), per-symbol chart as fallback
    left = list(syms); ok = 0
    for i in range(0, len(left), 20):
        part = left[i:i + 20]
        try:
            st, body = get('https://query1.finance.yahoo.com/v8/finance/spark?interval=5m&range=1d&symbols=' +
                           urllib.parse.quote(','.join(s + '.NS' for s in part)))
            d = json.loads(body)
            for s in part:
                v = d.get(s + '.NS')
                if not v: continue
                closes = [c for c in (v.get('close') or []) if c is not None]; ts = v.get('timestamp') or []
                if closes:
                    snap['stocks'][s] = {'last': closes[-1], 'prev_close': v.get('chartPreviousClose') or v.get('previousClose'), 'time': ist(ts[-1] if ts else None)}
                    ok += 1
        except Exception as e:
            snap['sources'].setdefault('spark_errors', 0); snap['sources']['spark_errors'] += 1
        time.sleep(0.3)
    snap['sources']['spark_ok'] = ok
    missing = [s for s in syms if s not in snap['stocks']]
    t0 = time.time(); ok2 = 0
    for s in missing:
        if time.time() - t0 > 360: break
        try:
            last, prev, t = chart(s + '.NS')
            if last is not None:
                snap['stocks'][s] = {'last': last, 'prev_close': prev, 'time': ist(t)}; ok2 += 1
        except Exception:
            pass
        time.sleep(0.15)
    snap['sources']['chart_ok'] = ok2
    snap['n_stocks'] = len(snap['stocks'])
    json.dump(snap, open(os.path.join(OUT, 'snapshot.json'), 'w'), separators=(',', ':'))
    print(json.dumps({k: v for k, v in snap.items() if k != 'stocks'}, indent=1))


if __name__ == '__main__':
    main()
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
