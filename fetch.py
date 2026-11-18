"""Download NSE's official end-of-day files (equity bhavcopy with delivery + all index closes) into nse/.

Runs in GitHub Actions every weekday evening. Only standard library. Keeps the last 45 days.
Files kept for a date only when BOTH files download and pass sanity checks.
"""
import os, sys, time, datetime as dt, urllib.request

HOSTS = ['https://nsearchives.nseindia.com', 'https://archives.nseindia.com']
PATHS = {'sec': '/products/content/sec_bhavdata_full_{d}.csv', 'ind': '/content/indices/ind_close_all_{d}.csv'}
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nse')
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def get(path):
    for h in HOSTS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(h + path, headers={'User-Agent': UA, 'Accept': '*/*', 'Referer': 'https://www.nseindia.com/'})
                with urllib.request.urlopen(req, timeout=60) as r:
                    if r.status == 200: return r.read().decode('utf-8', 'ignore')
            except Exception as e:
                if getattr(e, 'code', None) == 404: break      # not published (holiday / too early)
                time.sleep(3)
    return None


def ok_sec(t): return t is not None and t.lstrip().startswith('SYMBOL') and t.count('\n') > 2000
def ok_ind(t): return t is not None and '\nNifty 500,' in t


def main():
    os.makedirs(OUT, exist_ok=True)
    today = dt.datetime.now(IST).date(); added = []
    for k in range(0, 12):
        day = today - dt.timedelta(days=k)
        if day.weekday() >= 5: continue
        d = day.strftime('%d%m%Y')
        fs, fi = os.path.join(OUT, f'sec_bhavdata_full_{d}.csv'), os.path.join(OUT, f'ind_close_all_{d}.csv')
        if os.path.exists(fs) and os.path.exists(fi): continue
        s = get(PATHS['sec'].format(d=d)); i = get(PATHS['ind'].format(d=d)) if ok_sec(s) else None
        if ok_sec(s) and ok_ind(i):
            open(fs, 'w').write(s); open(fi, 'w').write(i); added.append(day.isoformat())
    cutoff = today - dt.timedelta(days=45)
    for f in os.listdir(OUT):
        try:
            d = f.rsplit('_', 1)[1][:8]; day = dt.date(int(d[4:]), int(d[2:4]), int(d[:2]))
            if day < cutoff: os.remove(os.path.join(OUT, f))
        except Exception: pass
    print('added', added or 'nothing')


if __name__ == '__main__':
    main()
