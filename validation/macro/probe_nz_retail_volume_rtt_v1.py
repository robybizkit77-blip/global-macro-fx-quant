"""Read-only Stats NZ RTT retail volume source identity and full-history proof."""
import csv, io, json, math, re, statistics
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zipfile import ZipFile
from bs4 import BeautifulSoup
from validation.macro.collect_us_nz_household_firm_sources_v1 import fetch

ROOT=Path(__file__).resolve().parents[2]
PAGE="https://www.stats.govt.nz/information-releases/retail-trade-survey-september-2026-quarter/"
ID="RTTQS1S9K"
TARGET="NZ_RETAIL_VOLUME_Q_history_value"

def need(ok, reason):
    if not ok: raise ValueError(reason)

def norm(s):
    return " ".join(str(s).casefold().split())

def zip_link(raw, page):
    soup=BeautifulSoup(raw,"html.parser")
    need("retail trade survey" in norm(soup.get_text(" ",strip=True)), "wrong release")
    links=set()
    for a in soup.find_all("a",href=True):
        u=urljoin(page,a["href"])
        p=urlsplit(u)
        label=norm(a.get_text(" ",strip=True))
        if p.scheme=="https" and p.hostname in ("www.stats.govt.nz","stats.govt.nz") and p.path.lower().endswith(".zip") and ("retail" in label or "retail" in p.path.lower()):
            links.add(u)
    need(len(links)==1, "missing or ambiguous retail ZIP link: "+str(sorted(links)))
    return links.pop()

def inspect_zip(raw, row, today):
    need(row["id"]==TARGET and row["unit"]=="NZD million, deflated Sep 2010 quarter prices, SA" and row["frequency"]=="Q","canonical identity changed")
    need(len(row["dates"])==len(row["values"])>=24 and row["dates"]==sorted(set(row["dates"])),"bad canonical history")
    prior=dict(zip(row["dates"],row["values"]))
    hits=[]; schemas=[]
    with ZipFile(io.BytesIO(raw)) as z:
        entries=[x for x in z.infolist() if not x.is_dir() and x.filename.lower().endswith(".csv")]
        need(entries and len(entries)<=30 and sum(x.file_size for x in entries)<=20_000_000,"unexpected archive")
        for ent in entries:
            reader=csv.DictReader(io.StringIO(z.read(ent).decode("utf-8-sig")))
            headers=reader.fieldnames or []
            schemas.append({"name":ent.filename,"headers":headers})
            for r in reader:
                if r.get("Series_reference")==ID: hits.append(r)
    print("NZ_RETAIL_ZIP_SCHEMA",json.dumps(schemas))
    need(hits,"candidate series not present")
    meta={k:sorted({str(r.get(k,"")) for r in hits}) for k in hits[0] if k not in ("Period","Data_value","STATUS","Suppressed")}
    print("NZ_RETAIL_EXACT_SERIES_METADATA",json.dumps(meta))
    obs={}
    for r in hits:
        m=re.fullmatch(r"(\d{4})[.-](03|06|09|12)",r["Period"])
        need(m is not None,"unexpected quarterly period")
        p=m[1]+"-"+m[2]
        need(p not in obs and p<=today.strftime("%Y-%m"),"duplicate or future period")
        if not r["Data_value"].strip(): continue
        v=float(r["Data_value"])
        need(math.isfinite(v) and v>0,"invalid value")
        obs[p]=v
    need(set(prior)<=set(obs),"incomplete full historical overlap")
    # Test possible explicit scaling to NZD millions. Never choose per period.
    fits=[]
    for factor in (1, .001, .000001, 1000):
        err=[abs(obs[p]*factor-v)/abs(v) for p,v in prior.items()]
        fits.append({"factor":factor,"median":statistics.median(err),"max":max(err)})
    print("NZ_RETAIL_FULL_HISTORY_SCALE_PROOF",json.dumps(fits))
    match=[x for x in fits if x["median"]<=.005 and x["max"]<=.025]
    need(len(match)==1,"no unique comparable full history")
    factor=match[0]["factor"]
    dates=sorted(p for p in obs if p>=min(prior))
    need(all((int(b[:4])-int(a[:4]))*12+int(b[5:])-int(a[5:])==3 for a,b in zip(dates,dates[1:])),"quarterly history gap")
    # Independent exact anchor published on the issuer's release chart, NZD millions.
    need("2026-09" in obs and abs(obs["2026-09"]*factor-26487.973)<=.1,"September chart level mismatch")
    return {"series_id":ID,"metadata":meta,"overlap":len(prior),"scale":match[0],"first":dates[0],"last":dates[-1],"latest_nzd_million":obs[dates[-1]]*factor,"source_sha256":sha256(raw).hexdigest(),"first_release_PIT_certified":False,"research_only":True,"canonical_mutated":False}

if __name__=="__main__":
    row=next(x for x in json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text())["NZD"] if x["id"]==TARGET)
    raw,final=fetch(PAGE)
    try:
        url=zip_link(raw,final)
    except ValueError as exc:
        print("NZ_RETAIL_RELEASE_LINK_UNRESOLVED",str(exc))
        index="https://www.stats.govt.nz/large-datasets/csv-files-for-download/"
        listing,listing_final=fetch(index)
        soup=BeautifulSoup(listing,"html.parser")
        links=set()
        for a in soup.find_all("a",href=True):
            u=urljoin(listing_final,a["href"])
            p=urlsplit(u)
            label=norm(a.get_text(" ",strip=True))
            if p.scheme=="https" and p.hostname in ("www.stats.govt.nz","stats.govt.nz") and "retail trade survey" in label and "september 2026 quarter" in label and "csv" in label:
                links.add(u)
        print("NZ_RETAIL_INDEX_EXACT_LINKS",sorted(links))
        # File cards may place the link on an icon, with the title in a sibling.
        # Inspect the release card itself, not the entire parent page.
        for origin,body in ((final,raw),(listing_final,listing)):
            doc=BeautifulSoup(body,"html.parser")
            for h in doc.find_all(["h2","h3","h4","h5"]):
                title=norm(h.get_text(" ",strip=True))
                if "retail trade survey" not in title or "september 2026 quarter" not in title or "csv" not in title:continue
                for card in (h,h.parent,h.parent.parent):
                    urls=set()
                    for a in card.find_all("a",href=True):
                        u=urljoin(origin,a["href"]);p=urlsplit(u)
                        if p.scheme=="https" and p.hostname in ("www.stats.govt.nz","stats.govt.nz") and p.path.lower().endswith(".zip"):urls.add(u)
                    if len(urls)==1:links.update(urls);break
                print("NZ_RETAIL_RELEASE_CARD",str(h.parent)[:1600])
            print("NZ_RETAIL_LINK_DIAGNOSTICS",json.dumps([{"href":a["href"],"label":norm(a.get_text(" ",strip=True))} for a in doc.find_all("a",href=True) if "retail" in a["href"].lower() or ".zip" in a["href"].lower()][:30]))
        need(len(links)==1,"missing or ambiguous exact release CSV link on issuer pages")
        url=links.pop()
    print("NZ_RETAIL_ISSUER_ZIP",url)
    blob,returned=fetch(url)
    receipt=inspect_zip(blob,row,datetime.now(timezone.utc).date())
    receipt["source_url"]=returned
    print("NZ_RETAIL_SOURCE_PROOF",json.dumps(receipt,sort_keys=True))
