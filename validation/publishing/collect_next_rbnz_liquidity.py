"""Collect the official monthly NZD liquidity research release."""
import argparse
import io
from hashlib import sha256
from datetime import date, datetime
from html import unescape
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen

BASE = "https://www.rbnz.govt.nz/statistics/series/"
C60 = BASE + "lending-and-monetary/credit-conditions"
SOURCES = {
    "d10": BASE + "reserve-bank/influences-on-settlement-cash",
    "c50": BASE + "lending-and-monetary/depository-corporations-money-and-credit-aggregates",
}
LABELS = {
    "d10": {"liquidity": "average settlement cash"},
    "c50": {"money": "broad money (a+b)", "credit": "d. private sector credit"},
}
AGENT = "RBNZ-Automated-Agent/GlobalMacroFXQuant/LiquidityResearch"
PREFIX = "window.FXQuantNZDRBNZLiquidity = "
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
SEED = {
    "2026-08": {"liquidity": 26460, "money": 454671, "credit": 624663},
    "2026-09": {"liquidity": 27036, "money": 459840, "credit": 630847},
}


def plain(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def month(cell):
    match = re.fullmatch(r"([a-z]{3})[a-z]*\.?\s+(20\d{2})", cell.lower())
    if match and match[1] in MONTHS:
        return f"{match[2]}-{MONTHS.index(match[1]) + 1:02}"
    return None


def read_table(html, labels):
    page = plain(html)

    def release_date(label):
        match = re.search(r"\b" + label + r"\s*:?\s*(\d{1,2} [A-Za-z]+ 20\d{2})", page, re.I)
        if not match:
            raise ValueError(f"Missing {label}")
        return datetime.strptime(match[1], "%d %B %Y").date().isoformat()

    for table in re.findall(r"<table\b[^>]*>(.*?)</table>", html, re.I | re.S):
        rows = [
            [plain(cell) for cell in re.split(r"<t[hd]\b[^>]*>", row, flags=re.I)[1:]]
            for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.I | re.S)
        ]
        for header in rows:
            dates = [period for cell in header if (period := month(cell))]
            if len(dates) < 3 or dates != sorted(set(dates)):
                continue
            found = {}
            for key, label in labels.items():
                matches = [r for r in rows if len(r) > len(dates)
                           and " ".join(r[:-len(dates)]).casefold().strip() in
                           {label, "9. " + label, "9 " + label}]
                if len(matches) != 1:
                    break
                cells = matches[0][-len(dates):]
                if not all(re.fullmatch(r"(?:[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*)", c) for c in cells):
                    raise ValueError(f"Invalid value for {key}")
                found[key] = dict(zip(dates, (int(c.replace(",", "")) for c in cells)))
            if len(found) == len(labels):
                return release_date("Released"), release_date("Next release"), dates[-1], found
    raise ValueError(f"Missing matching dated table for {', '.join(labels)}")


def fetch(url):
    request = Request(url, headers={"User-Agent": AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=25) as response:
        if response.geturl() != url or response.status != 200:
            raise ValueError(f"Unexpected response from {url}")
        return response.read(5_000_000).decode("utf-8")


def read_c60(html, today):
    page = plain(html)
    def release_date(label):
        m = re.search(r"\b" + label + r"\s*:?\s*(\d{1,2} [A-Za-z]+ 20\d{2})", page, re.I)
        if not m:
            raise ValueError("C60 missing " + label)
        return datetime.strptime(m[1], "%d %B %Y").date().isoformat()
    released, upcoming = release_date("Released"), release_date("Next release")
    if not released <= today < upcoming or "six-monthly" not in page.lower():
        raise ValueError("C60 release chronology/frequency")
    sections = {"loan demand - observed change over the past six months (index)": "demand",
                "credit availability - observed change over the past six months (index)": "availability"}
    targets = {"corporate/institutional loans": "corporate", "sme business loans": "sme"}
    hits = []
    for table in re.findall(r"<table\b[^>]*>(.*?)</table>", html, re.I | re.S):
        rows = [[plain(cell) for cell in re.split(r"<t[hd]\b[^>]*>", row, flags=re.I)[1:]]
                for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.I | re.S)]
        dates = None
        active = None
        found = {}
        for row in rows:
            if not row:
                continue
            stamps = []
            for cell in row:
                m = re.fullmatch(r"(Mar|Sep)\s+(20\d{2}|\d{2})", cell, re.I)
                if m:
                    stamps.append(f"{int(m[2]) + (2000 if len(m[2]) == 2 else 0):04d}-" + ("03" if m[1].lower() == "mar" else "09"))
            if len(stamps) >= 4:
                if dates is not None and stamps != dates:
                    raise ValueError("C60 conflicting dates")
                dates = stamps
                continue
            label = row[0].casefold()
            if " (index)" in label:
                active = sections.get(label)
                continue
            if dates and active and label in targets:
                key = active + "_" + targets[label]
                cells = row[1:]
                if key in found or len(cells) != len(dates):
                    raise ValueError("C60 duplicate/column mismatch")
                values = [float(v.replace("−", "-")) for v in cells]
                if not all(math.isfinite(v) and -100 <= v <= 100 for v in values):
                    raise ValueError("C60 index out of range")
                found[key] = values
        if dates and len(found) == 4:
            hits.append((dates, found))
    if len(hits) != 1:
        raise ValueError("C60 actual survey table missing or ambiguous")
    dates, found = hits[0]
    serial = [int(d[:4])*12+int(d[5:]) for d in dates]
    if any(b-a != 6 for a,b in zip(serial,serial[1:])):
        raise ValueError("C60 nonconsecutive half-years")
    period = dates[-1]
    release = date.fromisoformat(released)
    if release.year*12+release.month-serial[-1] != 1:
        raise ValueError("C60 release period mismatch")
    return {"source_url": C60, "series_id": "RBNZ_C60_ACTUAL_CREDIT_AVAILABILITY",
            "frequency": "H", "unit": "index_points", "positive_means": "easing",
            "dates": dates, **found, "latest_observation": period, "released": released, "next": upcoming,
            "first_release_pit_verified": False, "eligible_for_fx_core": False, "eligible_for_backtest": False}


WORKBOOKS = {
    "d10": "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/d-f-r/d10/hd10.xlsx",
    "c50": "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/c/c50/hc50.xlsx",
}
BACKFILL_MONTHS = 36

def workbook(url):
    from openpyxl import load_workbook
    request = Request(url, headers={"User-Agent": AGENT})
    with urlopen(request, timeout=25) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("unexpected RBNZ workbook response")
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000 or not raw.startswith(b"PK"):
        raise ValueError("invalid RBNZ workbook")
    return load_workbook(io.BytesIO(raw), read_only=True, data_only=True), sha256(raw).hexdigest()

def workbook_series(rows, kind):
    def cell(row,col):
        return row[col-1] if len(row)>=col else None
    def label(row,col):
        return " ".join(str(cell(row,col)).casefold().split())
    if kind=="d10":
        if label(rows[0],1)!="d10 influences on settlement cash" or label(rows[1],2)!="($nz million)" or label(rows[3],1)!="date" or label(rows[3],24)!="9. average settlement cash":
            raise ValueError("D10 workbook identity or unit mismatch")
        specs={"liquidity":24}; start=6
    elif kind=="c50":
        if label(rows[3],1)!="unit" or label(rows[4],1)!="series id":
            raise ValueError("C50 workbook header mismatch")
        specs={"money":2,"credit":13}; start=5
        for key,col,expected,title in (("money",2,"mca.mdb.bm","broad money (a+b)"),("credit",13,"mca.mdc.psc","d. private sector credit")):
            if label(rows[4],col)!=expected or label(rows[1],col)!=title or label(rows[3],col)!="nzdm":
                raise ValueError("C50 series identity or unit mismatch: "+key)
    else:
        raise ValueError("unknown workbook kind")
    out={}
    for row in rows[start:]:
        d=cell(row,1)
        if d is None: continue
        if not isinstance(d,(date,datetime)):
            raise ValueError("unexpected RBNZ workbook period")
        stamp=d.strftime("%Y-%m")
        if stamp in out: raise ValueError("duplicate RBNZ workbook month")
        vals={}
        for key,col in specs.items():
            v=cell(row,col)
            if type(v) not in (int,float) or not math.isfinite(v) or v<=0:
                raise ValueError("invalid RBNZ workbook value")
            # Match the public table's NZD-million display precision.
            vals[key]=int(math.floor(v+0.5))
        out[stamp]=vals
    return out

def backfill_monthly(payload, sources):
    h=payload["history"]
    latest=payload["period"]
    end=int(latest[:4])*12+int(latest[5:])-1
    required=[f"{i//12:04d}-{i%12+1:02d}" for i in range(end-BACKFILL_MONTHS+1,end+1)]
    d10,c50=sources
    if max(d10)!=latest or max(c50)!=latest:
        raise ValueError("workbook and published table reference period mismatch")
    if any(k not in d10 or k not in c50 for k in required):
        raise ValueError("incomplete RBNZ workbook history")
    for k in set(h)&set(required):
        if h[k]!={**d10[k],**c50[k]}:
            raise ValueError("RBNZ workbook overlap mismatch "+k)
    if len(set(h)&set(required))<2:
        raise ValueError("insufficient RBNZ workbook overlap")
    return {**{k:{**d10[k],**c50[k]} for k in required},**h}

def extend_monthly_history(payload):
    results=[]; hashes={}
    for key,sheet in (("d10","History_D10 (Jan 08 onwards)"),("c50","Data")):
        wb,hashes[key]=workbook(WORKBOOKS[key])
        try:
            ws=wb[sheet]
            ws.reset_dimensions()
            results.append(workbook_series(list(ws.values),key))
        finally:
            wb.close()
    history=backfill_monthly(payload,results)
    payload["history"]=history
    payload["history_backfill"]={
        "source_urls":WORKBOOKS,"source_sha256":hashes,"first_period":min(history),
        "last_period":payload["period"],"overlap_display_precision_nzd_million":True,
        "first_release_pit_verified":False,
    }
    print("RBNZ_WORKBOOK_BACKFILL_PASS",min(history),max(history),len(history),hashes)

def main(output, today, *, require_c60=False):
    previous = json.loads(output.read_text().removeprefix(PREFIX).strip().removesuffix(";")) if output.exists() else {}
    old_survey = previous.get("credit_conditions")
    survey = old_survey
    try:
        candidate = read_c60(fetch(C60), today)
        if old_survey and candidate["latest_observation"] < old_survey["latest_observation"]:
            raise ValueError("C60 source rolled back")
        survey = candidate
        print("NZD_C60_LIVE_SOURCE_PASS", survey["latest_observation"], survey["availability_corporate"][-1], survey["availability_sme"][-1], len(survey["dates"]))
    except (OSError, ValueError, TypeError) as error:
        print("NZD_C60_WITHHELD", str(error)[:250])
        if require_c60:
            raise
    try:
        payload = collect_monthly(previous, today)
    except (OSError, ValueError, KeyError) as error:
        if not previous or survey == old_survey:
            raise
        payload = {k:previous[k] for k in ("period", "released", "next", "history")}
        print("NZD_MONTHLY_RETAINED", str(error)[:250])
    if len(payload["history"]) < BACKFILL_MONTHS:
        try:
            extend_monthly_history(payload)
        except (OSError, ValueError, KeyError, TypeError) as error:
            print("RBNZ_WORKBOOK_BACKFILL_WITHHELD", str(error)[:250])
            if require_c60:
                raise
    elif previous.get("history_backfill"):
        payload["history_backfill"] = previous["history_backfill"]
    if survey is not None:
        payload["credit_conditions"] = survey
    if payload != previous:
        pending = output.with_suffix(".tmp")
        pending.write_text(PREFIX + json.dumps(payload, indent=2) + ";\n")
        pending.replace(output)
    print("NZD_SOURCE_UPDATE", "NO_CHANGE" if payload == previous else "UPDATED")


def collect_monthly(previous, today):
    sources = [read_table(fetch(url), LABELS[key]) for key, url in SOURCES.items()]
    released, upcoming, period, _ = sources[0]
    release_month = date.fromisoformat(released)
    period_date = date.fromisoformat(period + "-01")
    if (sources[1][:3] != (released, upcoming, period) or released > today
            or upcoming <= released or
            (release_month.year - period_date.year) * 12 + release_month.month - period_date.month != 1):
        raise ValueError("D10 and C50 require a common, published monthly release")

    history = dict(SEED)
    if previous:
        history.update(previous["history"])
        if period < previous["period"] or released < previous["released"]:
            raise ValueError("The source predates the last published release")

    observed = {k: v for source in sources for k, v in source[3].items()}
    overlap = set.intersection(*(set(values) for values in observed.values()))
    last_known = max(history)
    if last_known not in overlap:
        raise ValueError("No matching recent overlap with the last published release")
    # Reconcile every common published observation, including older periods.
    # Do not invent missing months or silently accept historical revisions.
    anchors = set(history) & overlap
    if any(observed[key][stamp] != value for stamp in anchors for key, value in history[stamp].items()):
        raise ValueError("A published observation was revised; review before extending history")
    for stamp in sorted(overlap):
        if stamp not in history:
            history[stamp] = {key: values[stamp] for key, values in observed.items()}
    dates = [date.fromisoformat(stamp + "-01") for stamp in sorted(history)]
    if any((b.year-a.year)*12+b.month-a.month != 1 for a,b in zip(dates,dates[1:])):
        raise ValueError("Gap in published monthly history")
    if max(history) != period:
        raise ValueError("Latest reference period is absent from the common history")
    print(f"RBNZ D10/C50 {period} released {released}: {history[period]}, next {upcoming}; history {min(history)}–{max(history)} ({len(history)} months)")
    return {"period": period, "released": released, "next": upcoming, "history": history}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--require-c60", action="store_true")
    args = parser.parse_args()
    main(args.output, date.today().isoformat(), require_c60=args.require_c60)
