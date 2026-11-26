"""Read-only audit of OECD amplitude-adjusted Australia CLI against local history."""
import csv,io,json,math,statistics
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
ID="AU_OECD_CLI_LEAD_INDICATOR_history_OECD_CLI_AUS"
BASE="https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,4.1/AUS.M.LI...AA...H"
def fetch(url):
    with urlopen(Request(url,headers={"User-Agent":"GMFQ-official-research/1.0","Accept":"text/csv"}),timeout=45) as r:
        assert urlsplit(r.geturl()).hostname=="sdmx.oecd.org"
        raw=r.read(3_000_001)
    assert 0<len(raw)<=3_000_000
    return raw
def main():
    row=next(r for r in json.loads(Path("live_data/sections/MACRO_SERIES.json").read_text())["AUD"] if r["id"]==ID)
    old={d[:7]:v for d,v in zip(row["dates"],row["values"])}
    url=BASE+"?"+urlencode({"startPeriod":min(old),"dimensionAtObservation":"AllDimensions","format":"csvfile"})
    raw=fetch(url);reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    print("CLI_FIELDS",reader.fieldnames)
    groups={}
    for rec in reader:
        key=tuple((k,v) for k,v in rec.items() if k not in ("TIME_PERIOD","OBS_VALUE","OBS_STATUS","OBS_STATUS_LABEL","DECIMALS","TIME_PERIOD_LABEL","CONF_STATUS","CONF_STATUS_LABEL"))
        try:v=float(rec["OBS_VALUE"])
        except (ValueError,TypeError):continue
        assert math.isfinite(v)
        d=rec["TIME_PERIOD"];obs=groups.setdefault(key,{})
        assert d not in obs
        obs[d]=v
    for key,obs in groups.items():
        if not set(old)<=set(obs):print("CLI_COVERAGE",dict(key),len(set(old)&set(obs)),max(obs));continue
        err=[abs(obs[d]-v) for d,v in old.items()]
        print("CLI_CANDIDATE",json.dumps({"metadata":dict(key),"overlap":len(err),"median_abs":statistics.median(err),"max_abs":max(err),"exact":sum(e<1e-8 for e in err),"latest":{d:v for d,v in obs.items() if d>max(old)}},ensure_ascii=False))
    print("DIAGNOSTIC_ONLY_NO_WRITES")
if __name__=="__main__":main()
