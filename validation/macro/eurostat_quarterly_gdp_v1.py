"""Eurostat dated GDP releases, including subsequent revisions; descriptive only."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, parse_qs
from urllib.error import HTTPError
import argparse
import json
import re

from validation.macro.capture_official_postrelease_actuals_v1 import Pending, retrieve
from validation.macro.capture_uk_ch_gdp_official_firstseen_v11 import source_text
from validation.macro.ons_quarterly_gdp_v1 import ROOT, ROME, quarter_parts, previous_quarter, append_edition
from validation.macro.abs_quarterly_gdp_v1 import next_quarter

HOST = "ec.europa.eu"
BASE = f"https://{HOST}/eurostat/en/web/products-euro-indicators/w/2-"
ARCHIVE = ROOT / "validation/macro/EUROSTAT_QUARTERLY_GDP_V1.json"
SCHEMA = "GMFQ_EUROSTAT_QUARTERLY_GDP_V1"
UNIT = "PERCENT_QOQ_SA_CALENDAR"
FIRST_DAY = date(2026,11,13)
FIRST_QUARTER = "2026Q3"
RELEASE_INDEX = f"https://{HOST}/eurostat/news/euro-indicators"
ORDINALS = ("first","second","third","fourth")
MONTHS = "January February March April May June July August September October November December".split()
MAX_SCAN_DAYS = 14
# Recheck recent negative responses before advancing the durable cursor.
SETTLEMENT_DAYS = 2


def edition_url(day):
    return BASE + day.strftime("%d%m%Y") + "-ap"


def quarter_label(q):
    y,n = quarter_parts(q)
    return f"{ORDINALS[n-1]} quarter of {y}"


def parse_bulletin(raw, day, today):
    text = source_text(raw).replace("\u2212","-")
    # Publication date and GDP-specific subtitle, not another dated indicator.
    header = re.search(r"Euro indicators\s+" + str(day.day) + r"\s+" +
                       MONTHS[day.month-1] + r"\s+" + str(day.year) + r"\b",text,re.I)
    if not header or day > today:
        raise Pending("EUROSTAT_RELEASE_DATE_NOT_VERIFIED")
    subtitle = re.search(r"\b(GDP(?: and employment)? (?:preliminary flash estimates?|flash estimates?|estimates?)|"
                         r"Main aggregates of GDP(?: and employment)?|GDP and main aggregates(?: including employment)?)"
                         r"\s+for the\s+(first|second|third|fourth) quarter(?: of)? (20\d{2})\b",text,re.I)
    if not subtitle:
        raise Pending("EUROSTAT_NOT_IDENTIFIED_GDP_EDITION")
    q = f"{subtitle[3]}Q{ORDINALS.index(subtitle[2].lower())+1}"
    ny,nq = quarter_parts(next_quarter(q))
    if day < date(ny,3*nq-2,1):
        raise Pending("EUROSTAT_QUARTER_NOT_CLOSED")
    stage = ("PRELIMINARY_FLASH" if "preliminary" in subtitle[1].lower() else
             "FLASH_ESTIMATE" if "flash" in subtitle[1].lower() else "REGULAR_ESTIMATE")
    num = r"[+-]?\d+(?:\.\d+)?"
    # Exact volume table, not the employment table or GDP annual rates.
    table = re.search(r"Growth rates of GDP in volume\s*\(?based on seasonally adjusted\*?\s*data\)?"
                      r"\s+Percentage change compared with the previous quarter\s+"
                      r"Percentage change compared with the same quarter of the previous year",text,re.I)
    if not table:
        raise Pending("EUROSTAT_REAL_GDP_TABLE_IDENTITY")
    tail = text[table.end():]
    expected=[q]
    for _ in range(3):
        expected.insert(0,previous_quarter(expected[0]))
    match = re.search(r"\s*"+r"\s+".join(map(re.escape,expected+expected))+
                      r"\s+Euro area\s+"+r"\s+".join(["("+num+")"]*8)+
                      r"\s+EU\b",tail,re.I)
    if not match:
        raise Pending("EUROSTAT_GDP_QUARTER_COLUMNS_OR_EA_ROW")
    values = list(map(float,match.groups()))
    prior,current=values[2:4]
    if not all(-30 < x < 30 for x in (prior,current)):
        raise Pending("EUROSTAT_GDP_OUT_OF_RANGE")
    return {"quarter":q,"publisher_release_day":day.isoformat(),
            "reported_value":current,"prior_qoq":prior,"source_url":edition_url(day),
            "publication_stage":stage,"source_html_sha256":sha256(raw).hexdigest()}


def archive_for(path):
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema")!=SCHEMA or not isinstance(data.get("editions"),list):
        raise ValueError("Eurostat archive schema")
    prior_day=None
    for r in data["editions"]:
        day=date.fromisoformat(r["publisher_release_day"])
        quarter_parts(r["quarter"])
        seen=datetime.fromisoformat(r["first_observed_at_utc"])
        if (day<FIRST_DAY or (prior_day and day<=prior_day) or r["quarter"]<FIRST_QUARTER
            or r["source_url"]!=edition_url(day)
            or r["publication_stage"] not in ("PRELIMINARY_FLASH","FLASH_ESTIMATE","REGULAR_ESTIMATE")
            or not re.fullmatch(r"[0-9a-f]{64}",r["source_html_sha256"])
            or seen.utcoffset() is None or seen.astimezone(ROME).date()<day
            or any(type(r[k]) not in (int,float) or not -30<r[k]<30 for k in ("reported_value","prior_qoq"))):
            raise ValueError("Eurostat archive provenance")
        prior_day=day
    cursor = data.get("checked_through")
    if cursor is not None:
        if not isinstance(cursor, str) or date.fromisoformat(cursor) < FIRST_DAY:
            raise ValueError("Eurostat discovery cursor invalid")
    return data


def latest_growth(as_of, *, path=ARCHIVE, live_cutoff=None):
    from validation.macro.ons_quarterly_gdp_v1 import edition_available
    rows=[r for r in archive_for(path)["editions"] if
          edition_available(r, as_of, live_cutoff)]
    if not rows:
        return None
    r=max(rows,key=lambda x:(x["quarter"],x["publisher_release_day"]))
    def obs(q,v):
        return {"reference_quarter":q,"publisher_release_day":r["publisher_release_day"],
                "publisher_source":r["source_url"],"reported_value":v,"reported_unit":UNIT,
                "nonannualized_qoq_descriptive_pct":v,"is_growth_strength_score":False,
                "national_definitions_are_not_fully_cross_country_equivalent":True,
                "later_revisions_not_identical_to_first_release":True,
                "historical_pit_training_vintages_certified":False}
    return {**obs(r["quarter"],r["reported_value"]),
            "publication_stage":r["publication_stage"],
            "prior_documented_quarter":obs(previous_quarter(r["quarter"]),r["prior_qoq"]),
            "prior_value_from_same_publisher_edition":True,
            "source_first_observed_at_utc":r["first_observed_at_utc"]}


def read_day(day,today,fetch):
    url=edition_url(day)
    raw,final=fetch(url,HOST)
    if final!=url:
        raise Pending("EUROSTAT_DATED_RELEASE_REDIRECT")
    return parse_bulletin(raw,day,today)


class ReleaseIndexLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=set()
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            for key,value in attrs:
                if key=="href" and value:
                    url=urlsplit(urljoin(RELEASE_INDEX,value))
                    if url.scheme=="https" and url.hostname==HOST:
                        match=re.search(r"/products-euro-indicators/w/(\d+)-(\d{8})-ap/?$",url.path)
                        if not match and url.path.rstrip("/")=="/eurostat/product":
                            codes=parse_qs(url.query).get("code",[])
                            if len(codes)==1:
                                match=re.fullmatch(r"(\d+)-(\d{8})-ap",codes[0])
                        if match:
                            self.links.add((match[1],datetime.strptime(match[2],"%d%m%Y").date()))


def release_index(raw,today):
    text=source_text(raw)
    if not re.search(r"\bEuro indicators\b",text,re.I) or not re.search(r"Showing\s+1\s*[-–]\s*\d+\s+out of\s+[\d,.\s]+\s+results",text,re.I):
        raise Pending("EUROSTAT_PUBLIC_INDEX_NOT_IDENTIFIED")
    parser=ReleaseIndexLinks()
    parser.feed(raw.decode("utf-8",errors="replace"))
    published=re.findall(r"PUBLISHED:\s*(\d{1,2})\s+("+"|".join(MONTHS)+r")\s+(20\d{2})",text,re.I)
    dates={date(int(y),MONTHS.index(m.title())+1,int(d)) for d,m,y in published}
    # Only a genuine populated first page may establish date coverage.
    if len(dates)<3 or len(parser.links)<3 or any(d>today for d in dates):
        raise Pending(f"EUROSTAT_PUBLIC_INDEX_COVERAGE_UNVERIFIED: dates={len(dates)} links={len(parser.links)}")
    # URL dates must correspond to dated published results. Ignore unrelated links.
    links={pair for pair in parser.links if pair[1] in dates}
    if len(links)<3:
        raise Pending("EUROSTAT_PUBLIC_INDEX_RELEASE_LINKS_UNVERIFIED")
    return min(dates),links


def collect(now,*,path=ARCHIVE,fetch=retrieve,apply=False):
    data=archive_for(path)
    today=now.astimezone(ROME).date()
    last=date.fromisoformat(data["editions"][-1]["publisher_release_day"]) if data["editions"] else None
    cursor=date.fromisoformat(data["checked_through"]) if data.get("checked_through") else None
    if cursor and cursor > today:
        raise ValueError("Eurostat discovery cursor from the future")
    # Resume from the last durable checkpoint, not a sliding seven-day window.
    # Existing archives without a cursor start after the last accepted edition.
    start=max(FIRST_DAY, (cursor+timedelta(days=1)) if cursor else FIRST_DAY,
              (last+timedelta(days=1)) if last else FIRST_DAY)
    end=min(today,start+timedelta(days=MAX_SCAN_DAYS-1))
    additions=[]; checks=[]; progressed=cursor
    index=None
    def confirm(day):
        nonlocal progressed
        if day <= today-timedelta(days=SETTLEMENT_DAYS):
            progressed=day
    for i in range(max(0,(end-start).days+1)):
        day=start+timedelta(days=i)
        # Reuse the independently verified listing for settled negative days.
        # Recent days are rechecked on subsequent runs; never skip a listed GDP.
        if index is not None and day>index[0] and ("2",day) not in index[1] and day<=today-timedelta(days=SETTLEMENT_DAYS):
            confirm(day)
            continue
        try:
            row=read_day(day,today,fetch)
        except HTTPError as exc:
            if exc.code==404:
                confirm(day)
                continue
            checks.append({"day":day.isoformat(),"error":str(exc)})
            break
        except (Pending, ValueError) as exc:
            # An identified non-GDP release is a negative, not a source error.
            if str(exc)=="EUROSTAT_NOT_IDENTIFIED_GDP_EDITION":
                confirm(day)
                continue
            # Missing dated articles may redirect to EU Login. Do not read
            # authentication pages or classify an unverified redirect as absent.
            # Independently consult the public list of recent official releases.
            if "redirect" in str(exc).lower():
                try:
                    if index is None:
                        raw,final=fetch(RELEASE_INDEX,HOST)
                        if final!=RELEASE_INDEX:
                            raise Pending("EUROSTAT_PUBLIC_INDEX_REDIRECT")
                        index=release_index(raw,today)
                    oldest,links=index
                    if day<=oldest or ("2",day) in links:
                        raise Pending("EUROSTAT_PUBLIC_INDEX_CANNOT_EXCLUDE_GDP")
                    confirm(day)
                    continue
                except (OSError,ValueError,Pending) as index_exc:
                    checks.append({"day":day.isoformat(),"error":str(index_exc)})
                    break
            checks.append({"day":day.isoformat(),"error":str(exc)})
            break
        except OSError as exc:
            checks.append({"day":day.isoformat(),"error":str(exc)})
            break
        if day==FIRST_DAY and (row["quarter"],row["reported_value"],row["prior_qoq"]) != (FIRST_QUARTER,0.4,0.6):
            checks.append({"day":day.isoformat(),"error":"EUROSTAT_SEED_MISMATCH"})
            break
        additions.append(row)
        # A validated edition itself is conclusive even before settlement.
        progressed=day
        if apply:
            append_edition(path,data,row,now)
    if apply and progressed and progressed!=cursor:
        data["checked_through"]=progressed.isoformat()
        temporary=path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        temporary.replace(path)
    return {"status":"ARCHIVED" if additions and apply else "VERIFIED_PREVIEW" if additions else
            "SOURCE_UNAVAILABLE_ARCHIVE_RETAINED" if checks else "NO_NEW_GDP_EDITION",
            "additions":additions,"source_warnings":checks,
            "checked_through":progressed.isoformat() if progressed else None,
            "scan_start":start.isoformat(),"scan_end":end.isoformat(),
            "catchup_pending":bool(checks) or end<today,"max_scan_days":MAX_SCAN_DAYS}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--verify-day")
    a=p.parse_args()
    now=datetime.now(timezone.utc)
    if a.verify_day:
        if a.apply:
            p.error("verification is read-only")
        print(json.dumps(read_day(date.fromisoformat(a.verify_day),now.astimezone(ROME).date(),retrieve),sort_keys=True))
    else:
        print(json.dumps(collect(now,apply=a.apply),sort_keys=True))


if __name__=="__main__":
    main()
