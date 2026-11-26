"""One-off research download: current constituent lists of NSE sectoral indices (official CSVs).
Writes sectors/sectors.csv (index,symbol,industry,company) and sectors/log.json. Standard library only."""
import os, csv, io, json, time, urllib.request
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
HOSTS = ['https://nsearchives.nseindia.com/content/indices/', 'https://archives.nseindia.com/content/indices/', 'https://www.niftyindices.com/IndexConstituent/']
IDX = {'auto': ['ind_niftyautolist.csv'], 'bank': ['ind_niftybanklist.csv'], 'it': ['ind_niftyitlist.csv'], 'pharma': ['ind_niftypharmalist.csv'],
       'fmcg': ['ind_niftyfmcglist.csv'], 'metal': ['ind_niftymetallist.csv'], 'realty': ['ind_niftyrealtylist.csv'], 'energy': ['ind_niftyenergylist.csv'],
       'media': ['ind_niftymedialist.csv'], 'psu bank': ['ind_niftypsubanklist.csv'], 'private bank': ['ind_nifty_privatebanklist.csv', 'ind_niftyprivatebanklist.csv'],
       'financial services': ['ind_niftyfinancelist.csv'], 'infrastructure': ['ind_niftyinfralist.csv'], 'commodities': ['ind_niftycommoditieslist.csv'],
       'india consumption': ['ind_niftyconsumptionlist.csv'], 'cpse': ['ind_niftycpselist.csv'], 'mnc': ['ind_niftymnclist.csv'],
       'services sector': ['ind_niftyservicelist.csv'], 'healthcare index': ['ind_niftyhealthcarelist.csv'], 'consumer durables': ['ind_niftyconsumerdurableslist.csv'],
       'oil & gas': ['ind_niftyoilgaslist.csv'], 'capital markets': ['ind_niftycapitalmarkets_list.csv', 'ind_niftycapitalmarketslist.csv'],
       'chemicals': ['ind_niftychemicals_list.csv', 'ind_niftychemicalslist.csv'], 'india defence': ['ind_niftyindiadefence_list.csv'],
       'housing finance': ['ind_niftyhousingfinance_list.csv'], 'cement': ['ind_niftycement_list.csv'], 'capital goods': ['ind_niftycapitalgoods_list.csv']}
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*', 'Referer': 'https://www.nseindia.com/'})
    with urllib.request.urlopen(req, timeout=30) as r: return r.read().decode('utf-8', 'ignore')
os.makedirs('sectors', exist_ok=True); rows = []; log = {}
for name, files in IDX.items():
    got = None
    for f in files:
        for h in HOSTS:
            try:
                t = get(h + f)
                if 'Symbol' in t[:300]: got = (h + f, t); break
            except Exception as e: pass
            time.sleep(0.5)
        if got: break
    if not got: log[name] = 'not found'; continue
    rd = csv.DictReader(io.StringIO(got[1])); n = 0
    for r in rd:
        r = {k.strip(): (v or '').strip() for k, v in r.items() if k}
        if r.get('Symbol'): rows.append([name, r['Symbol'], r.get('Industry', ''), r.get('Company Name', '')]); n += 1
    log[name] = f'{n} stocks from {got[0]}'
with open('sectors/sectors.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['index', 'symbol', 'industry', 'company']); w.writerows(rows)
json.dump(log, open('sectors/log.json', 'w'), indent=1); print(json.dumps(log, indent=1))
