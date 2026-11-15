"""Collect the official monthly NZD liquidity research release."""
import argparse
from datetime import date, datetime
from html import unescape
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

BASE = "https://www.rbnz.govt.nz/statistics/series/"
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


def main(output, today):
    sources = [read_table(fetch(url), LABELS[key]) for key, url in SOURCES.items()]
    released, upcoming, period, _ = sources[0]
    release_month = date.fromisoformat(released)
    period_date = date.fromisoformat(period + "-01")
    if (sources[1][:3] != (released, upcoming, period) or released > today
            or upcoming <= released or
            (release_month.year - period_date.year) * 12 + release_month.month - period_date.month != 1):
        raise ValueError("D10 and C50 require a common, published monthly release")

    history = dict(SEED)
    if output.exists():
        previous = json.loads(output.read_text().removeprefix(PREFIX).strip().removesuffix(";"))
        history.update(previous["history"])
        if period < previous["period"] or released < previous["released"]:
            raise ValueError("The source predates the last published release")

    observed = {k: v for source in sources for k, v in source[3].items()}
    overlap = set.intersection(*(set(values) for values in observed.values()))
    last_known = max(history)
    if last_known not in overlap:
        raise ValueError("No matching recent overlap with the last published release")
    anchors = set(SEED) & overlap if not output.exists() else {last_known}
    if any(observed[key][stamp] != value for stamp in anchors for key, value in history[stamp].items()):
        raise ValueError("Last published observation was revised; review before extending history")
    for stamp in sorted(overlap):
        if stamp > last_known:
            prior = date.fromisoformat(max(history) + "-01")
            following = date.fromisoformat(stamp + "-01")
            if (following.year - prior.year) * 12 + following.month - prior.month != 1:
                raise ValueError("Gap in published monthly history")
            history[stamp] = {key: values[stamp] for key, values in observed.items()}
    if max(history) != period:
        raise ValueError("Latest reference period is absent from the common history")
    payload = {"period": period, "released": released, "next": upcoming, "history": history}
    pending = output.with_suffix(".tmp")
    pending.write_text(PREFIX + json.dumps(payload, indent=2) + ";\n")
    pending.replace(output)
    print(f"RBNZ D10/C50 {period} released {released}: {history[period]}, next {upcoming}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    main(args.output, date.today().isoformat())
