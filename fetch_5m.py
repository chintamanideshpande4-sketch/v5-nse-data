"""One-off research download: last ~59 days of 5-minute bars from Yahoo Finance for the same
300 most-traded NSE stocks as fetch_hourly.py, plus Nifty 50. Writes fivemin/bars_5m.csv.gz."""
import os, csv, json, time, gzip, urllib.parse
from fetch_hourly import yget, universe, HERE

def main():
    os.makedirs(os.path.join(HERE, 'fivemin'), exist_ok=True)
    now = int(time.time()); p1 = now - 59 * 86400
    syms = ['^NSEI'] + [s + '.NS' for s in universe()]
    ok = bad = rows = 0
    with gzip.open(os.path.join(HERE, 'fivemin', 'bars_5m.csv.gz'), 'wt', newline='') as out:
        w = csv.writer(out); w.writerow(['sym', 'ts', 'o', 'h', 'l', 'c', 'v'])
        for s in syms:
            try:
                d = yget('/v8/finance/chart/' + urllib.parse.quote(s) + f'?interval=5m&period1={p1}&period2={now}')
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
