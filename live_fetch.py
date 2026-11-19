"""Live (intraday) snapshot for the V5 Friday check.

Writes live/snapshot.json:
  {fetched_ist, sources, index:{name,last,prev_close,time,source}, index_checks:{...}, stocks:{SYMBOL:{last,prev_close,time}}, n_stocks}
Index level: Yahoo Finance (query1, then query2), with Moneycontrol's public price feed as backup and cross-check.
Stock prices: Yahoo Finance spark batches (query1, then query2), per-symbol chart fallback.
Stock universe = NSE symbols that traded >= Rs 3 Cr on any of the last 5 days in nse/ (official bhavcopy files).
Standard library only. Never fails hard: whatever was fetched is written, and the V5 agent decides if it is usable.
"""
import os, glob, csv, json, time, datetime as dt, urllib.request, urllib.parse

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'live')
YHOSTS = ['https://query1.finance.yahoo.com', 'https://query2.finance.yahoo.com']


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', 'ignore')


def yget(path):
    err = None
    for h in YHOSTS:
        try:
            return get(h + path)
        except Exception as e:
            err = e
    raise err


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
    st, body = yget('/v8/finance/chart/' + urllib.parse.quote(sym) + '?interval=5m&range=1d')
    m = json.loads(body)['chart']['result'][0]['meta']
    return m.get('regularMarketPrice'), m.get('chartPreviousClose'), m.get('regularMarketTime')


def moneycontrol_index():
    st, body = get('https://priceapi.moneycontrol.com/pricefeed/notapplicable/inidicesindia/in%3Bncx')
    d = json.loads(body)['data']
    if not d or 'NIFTY 500' not in str(d.get('company', '')).upper():
        raise ValueError('unexpected moneycontrol answer')
    return float(str(d['pricecurrent']).replace(',', '')), float(str(d['priceprevclose']).replace(',', '')), d.get('lastupd')


def fresh(t, now):
    """index time is from today and within 40 minutes of now (IST strings)"""
    if not t or t[:10] != now[:10]: return False
    a = dt.datetime.strptime(t, '%Y-%m-%d %H:%M:%S'); b = dt.datetime.strptime(now, '%Y-%m-%d %H:%M:%S')
    return abs((b - a).total_seconds()) <= 2400 or t[11:16] >= '15:29'


def main():
    os.makedirs(OUT, exist_ok=True)
    now = dt.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
    snap = {'fetched_ist': now, 'sources': {}, 'index': None, 'index_checks': {}, 'stocks': {}}
    cand = []
    try:
        last, prev, t = chart('^CRSLDX')
        snap['index_checks']['yahoo'] = {'last': last, 'prev_close': prev, 'time': ist(t)}
        snap['sources']['yahoo_index'] = 'ok'
        if last: cand.append({'name': 'NIFTY 500', 'last': last, 'prev_close': prev, 'time': ist(t), 'source': 'yahoo'})
    except Exception as e:
        snap['sources']['yahoo_index'] = f'ERR {str(e)[:120]}'
    try:
        last, prev, t = moneycontrol_index()
        snap['index_checks']['moneycontrol'] = {'last': last, 'prev_close': prev, 'time': t}
        snap['sources']['moneycontrol_index'] = 'ok'
        cand.append({'name': 'NIFTY 500', 'last': last, 'prev_close': prev, 'time': t, 'source': 'moneycontrol'})
    except Exception as e:
        snap['sources']['moneycontrol_index'] = f'ERR {str(e)[:120]}'
    # prefer a fresh Yahoo value, else a fresh Moneycontrol value, else whatever exists
    good = [c for c in cand if fresh(c['time'], now)]
    snap['index'] = (good or cand or [None])[0]
    if len(cand) == 2 and cand[0]['last'] and cand[1]['last']:
        snap['index_checks']['diff_pct'] = round((cand[0]['last'] / cand[1]['last'] - 1) * 100, 3)
    syms = universe(); snap['sources']['universe'] = len(syms)
    ok = 0
    for i in range(0, len(syms), 20):
        part = syms[i:i + 20]
        try:
            st, body = yget('/v8/finance/spark?interval=5m&range=1d&symbols=' + urllib.parse.quote(','.join(s + '.NS' for s in part)))
            d = json.loads(body)
            for s in part:
                v = d.get(s + '.NS')
                if not v: continue
                closes = [c for c in (v.get('close') or []) if c is not None]; ts = v.get('timestamp') or []
                if closes:
                    snap['stocks'][s] = {'last': closes[-1], 'prev_close': v.get('chartPreviousClose') or v.get('previousClose'), 'time': ist(ts[-1] if ts else None)}
                    ok += 1
        except Exception:
            snap['sources']['spark_errors'] = snap['sources'].get('spark_errors', 0) + 1
        time.sleep(0.3)
    snap['sources']['spark_ok'] = ok
    missing = [s for s in syms if s not in snap['stocks']]
    t0 = time.time(); ok2 = 0
    for s in missing:
        if time.time() - t0 > 300: break
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
