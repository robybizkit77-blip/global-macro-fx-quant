"""Stats NZ official monthly seasonally adjusted new dwelling consents."""
import calendar,re,math
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
from validation.macro.capture_official_postrelease_actuals_v1 import Pending,retrieve
from validation.macro.capture_uk_ch_gdp_official_firstseen_v11 import source_text
ID="NZ_NEW_DWELLINGS_CONSENTED_SA"
HOST="www.stats.govt.nz"
BASE="https://"+HOST+"/information-releases/building-consents-issued-"
def require(ok,msg):
    if not ok:raise ValueError(msg)
class Tables(HTMLParser):
    def __init__(self):
        super().__init__();self.tables=[];self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="table":self.table=[]
        elif tag=="tr" and self.table is not None:self.row=[]
        elif tag in ("th","td") and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("th","td") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()));self.cell=None
        elif tag=="tr" and self.row is not None:
            self.table.append(self.row);self.row=None
        elif tag=="table" and self.table is not None:
            self.tables.append(self.table);self.table=None
def parse(raw,period,today,url):
    text=source_text(raw)
    y,m=map(int,period.split("-"));month=calendar.month_name[m]
    title=f"Building consents issued: {month} {y}"
    hit=re.search(re.escape(title)+r".{0,350}?\b(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\s*,?\s+\d{1,2}:\d{2}",text,re.I)
    require(hit is not None,"Stats NZ dated release heading missing")
    names={calendar.month_name[i].lower():i for i in range(1,13)}
    released=date(int(hit[3]),names[hit[2].lower()],int(hit[1]))
    require(date(y,m,calendar.monthrange(y,m)[1])<released<=today,"Stats NZ release date invalid")
    require(re.search(r"New dwellings consented, monthly, January 1995",text,re.I) is not None,"Stats NZ chart identity missing")
    parser=Tables();parser.feed(raw.decode("utf-8"))
    candidates=[]
    for table in parser.tables:
        for n,row in enumerate(table):
            normalized=[x.casefold() for x in row]
            if normalized != ["category","actual","seasonally adjusted","trend"]:continue
            obs={}
            for cells in table[n+1:]:
                if len(cells)!=4 or not re.fullmatch(r"\d{4}-\d{2}-01",cells[0]):continue
                d=date.fromisoformat(cells[0]).isoformat()[:7]
                if d<"2019-10":continue
                v=float(cells[2].replace(",",""))
                require(d not in obs and d<=period and math.isfinite(v) and v>0 and v.is_integer(),"Stats NZ invalid dwelling count")
                obs[d]=int(v)
            ds=sorted(obs)
            if len(ds)<36 or ds[-1]!=period:continue
            idx=[int(d[:4])*12+int(d[5:]) for d in ds]
            require(all(b-a==1 for a,b in zip(idx,idx[1:])),"Stats NZ dwelling history gap")
            candidates.append((ds,[obs[d] for d in ds]))
    require(len(candidates)==1,"Stats NZ unique SA dwelling chart missing")
    ds,vs=candidates[0]
    if period=="2026-09":require(vs[-1]==3218 and vs[-2]==3495,"Stats NZ September official anchor mismatch")
    return dict(series_id=ID,currency="NZD",pillar="housing",measurement="QUANTITY",
        label="Nuove abitazioni autorizzate — destagionalizzate",frequency="M",unit="abitazioni (SA)",
        source_url=url,source_series_id="BLDM.SFTZ1100A1S",source_sha256=sha256(raw).hexdigest(),
        dates=ds,values=vs,latest_period=period,released=released.isoformat(),
        source_series_first_release_PIT_certified=False,quality="STATSNZ_CURRENT_REVISED_HISTORY_NOT_PIT")
def browser(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True)
        try:
            page=b.new_page(locale="en-NZ")
            response=page.goto(url,wait_until="domcontentloaded",timeout=20000)
            require(response and response.status==200 and page.url==url,"Stats NZ browser edition mismatch")
            page.get_by_text("New dwellings consented, monthly, January 1995",exact=False).first.wait_for(state="attached",timeout=15000)
            # A chart heading can appear before its data table is populated.
            # Wait for a candidate table, then let parse() enforce identity,
            # exact seasonally adjusted columns, chronology and release anchors.
            page.wait_for_function(r"""() => Array.from(document.querySelectorAll('table')).some(table => {
                const rows=Array.from(table.querySelectorAll('tr'));
                const header=rows.findIndex(row => Array.from(row.querySelectorAll('th,td')).map(cell =>
                    cell.textContent.trim().replace(/\\s+/g,' ').toLowerCase()).join('|') ===
                    'category|actual|seasonally adjusted|trend');
                return header>=0 && rows.slice(header+1).filter(row =>
                    /^\\d{4}-\\d{2}-01$/.test(row.querySelector('th,td')?.textContent.trim()||'')).length>=36;
            })""",timeout=20000)
            return page.content().encode("utf-8")
        finally:b.close()
def collect(today,fetcher=retrieve,renderer=browser):
    errors=[]
    for offset in (1,2,3):
        serial=today.year*12+today.month-1-offset;y,k=divmod(serial,12);m=k+1
        period=f"{y}-{m:02d}"
        url=BASE+calendar.month_name[m].lower()+f"-{y}/"
        try:
            raw,final=fetcher(url,HOST)
            require(final==url,"Stats NZ redirected edition")
            try:return parse(raw,period,today,url)
            except (ValueError,Pending):return parse(renderer(url),period,today,url)
        except Exception as exc:
            errors.append(period+": "+str(exc))
    raise ValueError("No validated Stats NZ monthly release: "+"; ".join(errors))
