"""StatCan expenditure GDP: archive dated bulletin and its quarterly table."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
from urllib.parse import urljoin
import argparse
import json
import re
from urllib.error import HTTPError

from validation.macro.capture_official_postrelease_actuals_v1 import Pending, retrieve
from validation.macro.capture_uk_ch_gdp_official_firstseen_v11 import source_text
from validation.macro.ons_quarterly_gdp_v1 import (
    ROOT, ROME, append_edition, archived_growth, previous_quarter, quarter_parts,
)
from validation.macro.abs_quarterly_gdp_v1 import next_quarter

HOST = "www150.statcan.gc.ca"
BASE = f"https://{HOST}/n1/daily-quotidien/"
ARCHIVE = ROOT / "validation/macro/STATCAN_QUARTERLY_GDP_V1.json"
SCHEMA = "GMFQ_STATCAN_QUARTERLY_GDP_V1"
FIRST = "2026Q3"
MAX_SCAN_DAYS = 10
SETTLEMENT_DAYS = 2
SEED_URL = BASE + "260828/dq260828a-eng.htm"
ORDINALS = ("first", "second", "third", "fourth")
MONTHS = "January February March April May June July August September October November December".split()


def label(quarter):
    y, q = quarter_parts(quarter)
    return f"{ORDINALS[q-1]} quarter {y}"


def daily_prefix(day):
    code = day.strftime("%y%m%d")
    return BASE + code + "/"


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(v for k, v in attrs if k == "href" and v)


def bulletin(raw, url, quarter, today):
    text = source_text(raw)
    heading = r"Gross domestic product,\s*income and expenditure,\s*" + label(quarter)
    if not re.search(heading, text, re.I):
        raise Pending("STATCAN_GDP_BULLETIN_IDENTITY")
    hit = re.search(r"Released:\s*(20\d{2}-\d{2}-\d{2})", text)
    if not hit:
        raise Pending("STATCAN_GDP_RELEASE_DATE")
    day = date.fromisoformat(hit[1])
    y, q = quarter_parts(next_quarter(quarter))
    if not date(y, 3*q-2, 1) <= day <= today:
        raise Pending("STATCAN_GDP_RELEASE_DATE_RANGE")
    prefix = daily_prefix(day)
    if not re.fullmatch(re.escape(prefix) + r"dq\d{6}[a-z]-eng\.htm", url):
        raise Pending("STATCAN_GDP_DATED_URL")
    parser = Links()
    parser.feed(raw.decode("utf-8", errors="replace"))
    links = {urljoin(url, h) for h in parser.hrefs}
    tables = [x for x in links if re.fullmatch(re.escape(prefix) + r"t002[a-z]-eng\.htm", x)]
    if len(tables) != 1:
        raise Pending("STATCAN_QUARTERLY_TABLE_LINK_NOT_UNIQUE")
    nxt = next_quarter(quarter)
    m = re.search(r"Data on GDP by income and expenditure for the " +
                  re.escape(label(nxt).replace(" quarter ", " quarter of ")) +
                  r"\s+will be released on\s+(" + "|".join(MONTHS) +
                  r")\s+(\d{1,2})(?:,\s*(20\d{2}))?", text, re.I)
    # The next release is only a discovery hint; actual bulletin verifies period and date.
    next_day = None
    if m:
        mo = MONTHS.index(m[1].title()) + 1
        yy = int(m[3]) if m[3] else day.year + (mo < day.month)
        next_day = date(yy, mo, int(m[2]))
        if next_day <= day:
            raise Pending("STATCAN_NEXT_RELEASE_DATE_INVALID")
    return day, tables[0], next_day


def parse_table(raw, quarter):
    text = source_text(raw).replace("\u2212", "-")
    if not re.search(r"Real gross domestic product by expenditure account,\s*quarterly change\s*[–—-]\s*Seasonally adjusted at annual rates,\s*chained\s*\(\d{4}\)\s*dollars", text, re.I):
        raise Pending("STATCAN_REAL_QUARTERLY_TABLE_IDENTITY")
    if not re.search(r"quarter-to-quarter\s*%\s*change", text, re.I):
        raise Pending("STATCAN_QOQ_UNIT_MISSING")
    # The table has six consecutive percent columns then two monetary columns.
    # Validate header sequence and the exact market-price aggregate row.
    head = text[:text.lower().find("final consumption expenditure")]
    periods = re.findall(r"(?:first|second|third|fourth) quarter 20\d{2}", head, re.I)
    expected = [quarter]
    for _ in range(5):
        expected.insert(0, previous_quarter(expected[0]))
    if [x.lower() for x in periods[-8:]] != [label(k) for k in expected + expected[-2:]]:
        raise Pending("STATCAN_QUARTER_COLUMNS_MISMATCH")
    num = r"[+-]?\d+(?:\.\d+)?"
    money = r"[+-]?\d[\d,]*(?:\.\d+)?"
    matches = re.findall(r"\bGross domestic product at market prices\s+" +
                         r"\s+".join(["("+num+")"]*6 + [money]*2) +
                         r"(?=\s|$)", text, re.I)
    if len(matches) != 1:
        raise Pending("STATCAN_GDP_MARKET_PRICE_ROW_NOT_UNIQUE")
    prior, current = map(float, matches[0][-2:])
    if not all(-30 < x < 30 for x in (prior, current)):
        raise Pending("STATCAN_REAL_GDP_OUT_OF_RANGE")
    return current, prior


def archive_for(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or not isinstance(data.get("editions"), list):
        raise ValueError("invalid StatCan archive")
    last = None
    for r in data["editions"]:
        day = date.fromisoformat(r["publisher_release_day"])
        q = r["quarter"]
        quarter_parts(q)
        prefix = daily_prefix(day)
        seen = datetime.fromisoformat(r["first_observed_at_utc"])
        if (q < FIRST or (last and (q != next_quarter(last["quarter"]) or day.isoformat() <= last["publisher_release_day"]))
                or not re.fullmatch(re.escape(prefix)+r"dq\d{6}[a-z]-eng\.htm", r["source_url"])
                or not re.fullmatch(re.escape(prefix)+r"t002[a-z]-eng\.htm", r["table_url"])
                or any(type(r[k]) not in (int,float) or not -30 < r[k] < 30 for k in ("reported_value","prior_qoq"))
                or seen.utcoffset() is None or seen.astimezone(ROME).date() < day
                or not all(re.fullmatch(r"[0-9a-f]{64}",r[k]) for k in ("source_html_sha256","table_sha256"))):
            raise ValueError("StatCan archive integrity")
        if r["next_release_day"] is not None and date.fromisoformat(r["next_release_day"]) <= day:
            raise ValueError("StatCan next release date invalid")
        last = r
    cursor = data.get("discovery")
    if cursor is not None:
        expected = next_quarter(last["quarter"]) if last else FIRST
        if (not isinstance(cursor,dict) or cursor.get("quarter") != expected
                or not isinstance(cursor.get("checked_through"),str)):
            raise ValueError("StatCan discovery cursor invalid")
        checked = date.fromisoformat(cursor["checked_through"])
        if last and checked <= date.fromisoformat(last["publisher_release_day"]):
            raise ValueError("StatCan discovery cursor precedes latest edition")
    return data


def latest_growth(as_of, *, path=ARCHIVE):
    rows = archive_for(path)["editions"]
    result = archived_growth(as_of, rows, stage="QUARTERLY_NATIONAL_ACCOUNTS",
                              same_edition_field="prior_value_from_same_publisher_edition")
    if result:
        row = next(r for r in rows if r["quarter"] == result["reference_quarter"])
        result["publisher_table_source"] = row["table_url"]
    return result


def exact_fetch(url, fetch):
    raw, final = fetch(url, HOST)
    if final != url:
        raise Pending("STATCAN_REDIRECT")
    return raw


def read_edition(url, quarter, today, fetch):
    raw = exact_fetch(url, fetch)
    day, table, nxt = bulletin(raw, url, quarter, today)
    table_raw = exact_fetch(table, fetch)
    current, prior = parse_table(table_raw, quarter)
    return {"quarter":quarter,"publisher_release_day":day.isoformat(),
            "reported_value":current,"prior_qoq":prior,"source_url":url,
            "table_url":table,"next_release_day":nxt.isoformat() if nxt else None,
            "source_html_sha256":sha256(raw).hexdigest(),"table_sha256":sha256(table_raw).hexdigest()}


def issue_url(day):
    return daily_prefix(day) + f"dq{day.strftime('%y%m%d')}-eng.htm"


def find_edition_on_day(day, quarter, today, fetch):
    # Inspect the official daily index, not a guessed article suffix.
    url = issue_url(day)
    try:
        raw = exact_fetch(url, fetch)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    parser = Links()
    parser.feed(raw.decode("utf-8", errors="replace"))
    prefix = daily_prefix(day)
    pattern = re.escape(prefix) + r"dq" + day.strftime("%y%m%d") + r"[a-z]-eng\.htm"
    candidates = sorted({urljoin(url,h) for h in parser.hrefs
                         if re.fullmatch(pattern,urljoin(url,h))})
    if not candidates:
        raise Pending("STATCAN_DAILY_INDEX_ARTICLES_NOT_IDENTIFIED")
    for article in candidates:
        try:
            return read_edition(article,quarter,today,fetch)
        except Pending as exc:
            if str(exc) != "STATCAN_GDP_BULLETIN_IDENTITY":
                raise
    return None


def save_cursor(path,data,quarter,day):
    data["discovery"] = {"quarter":quarter,"checked_through":day.isoformat()}
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    tmp.replace(path)


def collect(now, *, path=ARCHIVE, fetch=retrieve, apply=False):
    data = archive_for(path)
    last = data["editions"][-1] if data["editions"] else None
    quarter = next_quarter(last["quarter"]) if last else FIRST
    today = now.astimezone(ROME).date()
    cursor = data.get("discovery")
    checked = date.fromisoformat(cursor["checked_through"]) if cursor else None
    if checked and checked > today:
        raise ValueError("StatCan discovery cursor from future")
    progressed=checked
    try:
        if last is None:
            seed = read_edition(SEED_URL, "2026Q2", today, fetch)
            if (seed["reported_value"], seed["prior_qoq"]) != (0.8,0.1):
                raise Pending("STATCAN_SEED_MISMATCH")
            hint = seed["next_release_day"]
        else:
            hint = last["next_release_day"]
        if hint is None:
            # No calendar hint: search from the first day after quarter close.
            ny,nq = quarter_parts(next_quarter(quarter))
            hint = date(ny,3*nq-2,1).isoformat()
        expected = date.fromisoformat(hint)
        if today < expected:
            return {"status":"AWAITING_STATCAN_RELEASE","next_quarter":quarter,"expected_release_day":hint}
        start=max(expected,checked+timedelta(days=1) if checked else expected)
        end=min(today,start+timedelta(days=MAX_SCAN_DAYS-1))
        for i in range(max(0,(end-start).days+1)):
            day=start+timedelta(days=i)
            row=find_edition_on_day(day,quarter,today,fetch)
            if row is not None:
                if apply:
                    data.pop("discovery",None)
                    append_edition(path,data,row,now)
                return {"status":"ARCHIVED" if apply else "VERIFIED_PREVIEW",**row}
            if day<=today-timedelta(days=SETTLEMENT_DAYS):
                progressed=day
        if apply and progressed and progressed!=checked:
            save_cursor(path,data,quarter,progressed)
        return {"status":"AWAITING_STATCAN_RELEASE","next_quarter":quarter,
                "expected_release_day":hint,"checked_through":progressed.isoformat() if progressed else None,
                "catchup_pending":end<today}
    except (OSError, ValueError, Pending) as exc:
        if apply and progressed and progressed!=checked:
            save_cursor(path,data,quarter,progressed)
        return {"status":"SOURCE_UNAVAILABLE_ARCHIVE_RETAINED","next_quarter":quarter,
                "reason":str(exc),"checked_through":progressed.isoformat() if progressed else None}




def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--verify-q2",action="store_true")
    p.add_argument("--verify-index",action="store_true")
    a=p.parse_args()
    now=datetime.now(timezone.utc)
    if a.verify_q2 or a.verify_index:
        if a.apply:
            p.error("verification is read-only")
        if a.verify_index:
            row=find_edition_on_day(date(2026,8,28),"2026Q2",now.astimezone(ROME).date(),retrieve)
        else:
            row=read_edition(SEED_URL,"2026Q2",now.astimezone(ROME).date(),retrieve)
        print(json.dumps(row,sort_keys=True))
    else:
        print(json.dumps(collect(now,apply=a.apply),sort_keys=True))


if __name__ == "__main__":
    main()
