"""Calendar-driven issuer actuals for recurring ABS CPI and BEA GDP/PCE.
Research only: no forecast, causal reaction, historical PIT or Core claim.
"""
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import re
import math

QUALITY = "OFFICIAL_RECURRING_RELEASE_OBSERVED_NOT_EVENT_REACTION"
ROME = ZoneInfo("Europe/Rome")
HOSTS = {"bea.gov", "www.bea.gov", "www.abs.gov.au"}
MONTHS = "January February March April May June July August September October November December".split()
NUM = r"(-?\d+(?:\.\d+)?)"
MOVE = r"(increased|decreased)"
SEP = r"\s*"

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

def plain(markup):
    p=Page()
    p.feed(markup)
    return re.sub(r"\s+", " ", " ".join(p.parts)).replace("−","-").strip()

def identity(e):
    title, period=e.get("title",""), e.get("reference_period","")
    family=e.get("source_family")
    if family=="ABS" and e.get("ccy")=="AUD" and title=="Consumer Price Index, Australia":
        kind="ABS_CPI"
    elif family=="BEA" and e.get("ccy")=="USD":
        if title=="Personal Income and Outlays":
            kind="BEA_PCE"
        elif re.match(r"^GDP \((Advance|Second|Third) Estimate\)",title):
            kind="BEA_GDP"
        else:
            return None
    else:
        return None
    year=e["date"][:4]
    if kind=="BEA_GDP":
        q,y=re.fullmatch(r"Q([1-4]) (20\d{2})",period).groups()
        ordinal={"1":"1st","2":"2nd","3":"3rd","4":"4th"}[q]
        stage=re.match(r"^GDP \((Advance|Second|Third) Estimate\)",title)[1].lower()
        suffix="-and-corporate-profits" if "Corporate Profits" in title and stage=="second" else ""
        base=f"https://www.bea.gov/news/{year}/gdp-{stage}-estimate"
        return kind,base+suffix+f"-{ordinal}-quarter-{y}",f"{ordinal} quarter {y}",stage
    m,y=re.fullmatch(r"([A-Za-z]+) (20\d{2})",period).groups()
    if m not in MONTHS:
        raise ValueError("unsupported month")
    url=("https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/"+m[:3].lower()+"-"+y if kind=="ABS_CPI" else f"https://www.bea.gov/news/{year}/personal-income-and-outlays-{m.lower()}-{y}")
    return kind,url,period,None

def match(pattern,text):
    m=re.search(pattern,text,re.I)
    if not m:
        raise ValueError("exact metric or release identity not found")
    return m

def numeric(raw, direction=None):
    v=float(raw)
    if not math.isfinite(v) or abs(v)>=100:
        raise ValueError("invalid percentage")
    return -abs(v) if direction and direction.lower()=="decreased" else v

def metrics(e,markup):
    kind,url,period,stage=identity(e)
    t=plain(markup)
    day=date.fromisoformat(e["date"])
    if kind=="ABS_CPI":
        match(r"Reference period\s+"+re.escape(period)+r"\s+Released\s+"+day.strftime("%d/%m/%Y"),t)
        key=match(r"Key statistics\s+(.*?)(?:Important release updates|Quarterly data available|Data downloads)",t)[1]
        a=match(r"Consumer Price Index \(CPI\) rose "+NUM+r"\s*%,\s*(?:up|down) from "+NUM+r"\s*%",key)
        b=match(r"Trimmed mean inflation was "+NUM+r"\s*%,\s*(?:up|down) from "+NUM+r"\s*%",key)
        return [("AU_CPI_HEADLINE_YOY","CPI Australia a/a",numeric(a[1]),numeric(a[2])),("AU_CPI_TRIMMED_MEAN_YOY","Trimmed mean Australia a/a",numeric(b[1]),numeric(b[2]))]
    match(r"\b"+MONTHS[day.month-1]+rf" {day.day}, {day.year}\b",t)
    if kind=="BEA_GDP":
        match(r"GDP \("+stage+r" Estimate\).*?"+re.escape(period),t)
        a=match(r"Real gross domestic product \(GDP\) "+MOVE+r" at an annual rate of "+NUM+r" percent",t)
        b=match(r"In the (?:first|second|third|fourth) quarter, real GDP "+MOVE+r" "+NUM+r" percent",t)
        return [("US_REAL_GDP_SAAR","PIL reale USA annualizzato",numeric(a[2],a[1]),numeric(b[2],b[1]))]
    match(r"Personal Income and Outlays,\s*"+re.escape(period),t)
    m=period.split()[0]
    a=match(r"From the preceding month, the PCE price index for "+m+" "+MOVE+" "+NUM+r" percent\s*\.\s*Excluding food and energy, the PCE price index (?:also )?"+MOVE+" "+NUM+r" percent",t)
    b=match(r"From the same month one year ago, the PCE price index for "+m+" "+MOVE+" "+NUM+r" percent\s*\.\s*Excluding food and energy, the PCE price index (?:also )?"+MOVE+" "+NUM+r" percent",t)
    return [(mid,label,numeric(x[j+1],x[j]),None) for mid,label,x,j in [("US_PCE_MOM","PCE USA m/m",a,1),("US_CORE_PCE_MOM","Core PCE USA m/m",a,3),("US_PCE_YOY","PCE USA a/a",b,1),("US_CORE_PCE_YOY","Core PCE USA a/a",b,3)]]

def retrieve(url):
    with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0 (macro research)"}),timeout=12) as response:
        if urlsplit(response.geturl()).hostname not in HOSTS:
            raise ValueError("unexpected issuer redirect")
        return response.read(4_000_000).decode("utf-8",errors="replace")

def build(seed,now,previous=(),fetch=retrieve,clock=None):
    if now.utcoffset() is None:
        raise ValueError("aware clock required")
    today=now.astimezone(ROME).date()
    items,checks=[],[]
    for e in seed.get("events",[]):
        key="|".join(str(e.get(k,"")) for k in ("ccy","date","event_type","title"))
        try:
            d=date.fromisoformat(e["date"])
            if not 0<=(today-d).days<=7:
                continue
            target=identity(e)
            if not target:
                continue
            scheduled=datetime.fromisoformat(e["date"]+"T"+e["time_local"]).replace(tzinfo=ZoneInfo(e["timezone"]))
            if scheduled>now:
                continue
            kind,url,period,stage=target
            old=next((r for r in previous if r.get("quality")==QUALITY and r.get("event_key")==key and r.get("source_url")==url and r.get("as_of")==e["date"]),None)
            if old and scheduled<=datetime.fromisoformat(old["first_runner_observed_at_utc"].replace("Z","+00:00"))<=now:
                items.append({**old,"_date":d})
                checks.append({"event_key":key,"status":"VERIFIED","source_url":url})
                continue
            parsed=metrics(e,fetch(url))
            seen=(clock or (lambda:datetime.now(timezone.utc)))()
            if seen<now or seen<scheduled:
                raise ValueError("invalid observation clock")
            fmt=lambda v:f"{v:.1f}".replace(".",",")+"%"
            parts=[label+": "+fmt(v)+(f" (periodo precedente {fmt(p)})" if p is not None else "") for _,label,v,p in parsed]
            items.append({"category":"MACRO_OFFICIAL_ACTUAL","event_key":key,"event_type":e["event_type"],"ccy":e["ccy"],"as_of":e["date"],"title":parts[0],"detail":"; ".join(parts)+". Periodo: "+period+". Nessuna sorpresa senza consenso pre-evento; reazione FX non misurata.","source":"ABS" if kind=="ABS_CPI" else "BEA","source_url":url,"first_runner_observed_at_utc":seen.astimezone(timezone.utc).isoformat().replace("+00:00","Z"),"quality":QUALITY,"confidence":"A","importance":"HIGH","metrics":[{"id":mid,"value_percent":v,"previous_period_percent":p} for mid,_,v,p in parsed],"_date":d})
            checks.append({"event_key":key,"status":"VERIFIED","source_url":url})
        except Exception as exc:
            checks.append({"event_key":key,"status":"SOURCE_UNVERIFIED","reason":str(exc)[:160]})
    known={r["event_key"] for r in items}
    failed={r["event_key"] for r in checks if r["status"]=="SOURCE_UNVERIFIED"}
    for r in previous:
        if r.get("quality")!=QUALITY or r.get("event_key") in known|failed:
            continue
        try:
            d=date.fromisoformat(r["as_of"])
            seen=datetime.fromisoformat(r["first_runner_observed_at_utc"].replace("Z","+00:00"))
            if 0<=(today-d).days<=7 and seen<=now and urlsplit(r["source_url"]).hostname in HOSTS:
                items.append({**r,"_date":d})
                known.add(r["event_key"])
        except (ValueError,TypeError,KeyError):
            pass
    return items,checks
