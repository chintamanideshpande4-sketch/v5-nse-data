"""One-off research download: ~2 years of 60-minute bars from Yahoo Finance for the
300 most-traded NSE stocks (by turnover in the last 5 official bhavcopy files in nse/),
plus Nifty 50 and Nifty 500. Writes hourly/hourly_60m.csv.gz (sym,ts,o,h,l,c,v). Standard library only."""
import os, glob, csv, json, time, gzip, urllib.request, urllib.parse
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
HOSTS = ['https://query1.finance.yahoo.com', 'https://query2.finance.yahoo.com']
HERE = os.path.dirname(os.path.abspath(__file__))

def yget(path):
    err = None
    for h in HOSTS:
        for k in range(2):
            try:
                req = urllib.request.Request(h + path, headers={'User-Agent': UA, 'Accept': 'application/json'})
                with urllib.request.urlopen(req, timeout=40) as r:
                    return json.loads(r.read().decode('utf-8', 'ignore'))
            except Exception as e:
                err = e; time.sleep(1.5)
    raise err

def universe(n=300):
    files = sorted(glob.glob(os.path.join(HERE, 'nse', 'sec_bhavdata_full_*.csv')),
                   key=lambda p: os.path.basename(p)[-8:-4] + os.path.basename(p)[-10:-8] + os.path.basename(p)[-12:-10])[-5:]
    tot = {}
    for p in files:
        with open(p, newline='') as fh:
            rd = csv.reader(fh); hdr = [h.strip() for h in next(rd)]; ix = {h: i for i, h in enumerate(hdr)}
            for r in rd:
                if len(r) < len(hdr) - 1: continue
                r = [c.strip() for c in r]
                if r[ix['SERIES']] != 'EQ': continue
                try: tot[r[ix['SYMBOL']]] = tot.get(r[ix['SYMBOL']], 0) + float(r[ix['TURNOVER_LACS']])
                except ValueError: pass
    skip = ('BEES', 'ETF', 'IETF', 'LIQUID', 'GOLD', 'SILVER', 'NIFTY', 'SENSEX')
    syms = [s for s, _ in sorted(tot.items(), key=lambda x: -x[1]) if not any(k in s for k in skip)]
    return syms[:n]

def main():
    os.makedirs(os.path.join(HERE, 'hourly'), exist_ok=True)
    now = int(time.time()); p1 = now - 729 * 86400
    syms = ['^NSEI', '^CRSLDX'] + [s + '.NS' for s in universe()]
    ok = bad = rows = 0
    with gzip.open(os.path.join(HERE, 'hourly', 'hourly_60m.csv.gz'), 'wt', newline='') as out:
        w = csv.writer(out); w.writerow(['sym', 'ts', 'o', 'h', 'l', 'c', 'v'])
        for s in syms:
            try:
                d = yget('/v8/finance/chart/' + urllib.parse.quote(s) + f'?interval=60m&period1={p1}&period2={now}')
                r = d['chart']['result'][0]; q = r['indicators']['quote'][0]
                for i, t in enumerate(r.get('timestamp') or []):
                    if q['close'][i] is None: continue
                    w.writerow([s, t, q['open'][i], q['high'][i], q['low'][i], q['close'][i], q['volume'][i]]); rows += 1
                ok += 1
            except Exception as e:
                bad += 1; print('fail', s, str(e)[:80])
            time.sleep(0.25)
    print(json.dumps({'symbols_ok': ok, 'failed': bad, 'rows': rows}))

if __name__ == '__main__':
    main()
