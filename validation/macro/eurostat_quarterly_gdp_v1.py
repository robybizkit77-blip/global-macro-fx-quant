"""Eurostat dated GDP releases, including subsequent revisions; descriptive only."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
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
ORDINALS = ("first","second","third","fourth")
MONTHS = "January February March April May June July August September October November December".split()
LOOKBACK_DAYS = 7


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
    return data


def latest_growth(as_of, *, path=ARCHIVE):
    day=date.fromisoformat(as_of)
    rows=[r for r in archive_for(path)["editions"] if
          date.fromisoformat(r["publisher_release_day"])<day and
          datetime.fromisoformat(r["first_observed_at_utc"]).astimezone(ROME).date()<=day]
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


def collect(now,*,path=ARCHIVE,fetch=retrieve,apply=False):
    data=archive_for(path)
    today=now.astimezone(ROME).date()
    last=date.fromisoformat(data["editions"][-1]["publisher_release_day"]) if data["editions"] else None
    start=max(FIRST_DAY,today-timedelta(days=LOOKBACK_DAYS),last+timedelta(days=1) if last else FIRST_DAY)
    days=[start+timedelta(days=i) for i in range(max(0,(today-start).days+1))]
    if last is None and FIRST_DAY<=today and FIRST_DAY not in days:
        days.insert(0,FIRST_DAY)
    additions=[]; checks=[]
    for day in days:
        try:
            row=read_day(day,today,fetch)
        except HTTPError as exc:
            if exc.code!=404:
                checks.append({"day":day.isoformat(),"error":str(exc)})
            continue
        except (OSError,ValueError,Pending) as exc:
            if str(exc) not in ("EUROSTAT_NOT_IDENTIFIED_GDP_EDITION","EUROSTAT_RELEASE_DATE_NOT_VERIFIED"):
                checks.append({"day":day.isoformat(),"error":str(exc)})
            continue
        if day==FIRST_DAY and (row["quarter"],row["reported_value"],row["prior_qoq"]) != (FIRST_QUARTER,0.4,0.6):
            checks.append({"day":day.isoformat(),"error":"EUROSTAT_SEED_MISMATCH"})
            continue
        additions.append(row)
        if apply:
            append_edition(path,data,row,now)
    return {"status":"ARCHIVED" if additions and apply else "VERIFIED_PREVIEW" if additions else
            "SOURCE_UNAVAILABLE_ARCHIVE_RETAINED" if checks else "NO_NEW_GDP_EDITION",
            "additions":additions,"source_warnings":checks,"lookback_days":LOOKBACK_DAYS}


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
