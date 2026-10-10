#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import re
from urllib.parse import urlencode

import materialize_jpy_inflation_strict_pit_v1 as base


y, m = 2019, 3
route_name, tstat, tclass1 = base.route_for(y, m)
params = {
    "cycle": "1",
    "layout": "datalist",
    "month": base.month_code(m),
    "page": "1",
    "result_back": "1",
    "tclass1": tclass1,
    "tclass2val": "0",
    "toukei": "00200573",
    "tstat": tstat,
    "year": f"{y}0",
}
search_url = base.BASE + "/stat-search/files?" + urlencode(params)
raw, _, _ = base.get(search_url)
page = html.unescape(raw.decode("utf-8", "replace"))
ids = []
for hit in re.finditer(r"(?:stat_infid|statInfId)=(\d+)", page, re.I):
    window = html.unescape(page[max(0, hit.start() - 1400): hit.end() + 1400])
    if "結果の概要（全国）" in window or "結果の概要(全国)" in window:
        ids.append(hit.group(1))
ids = list(dict.fromkeys(ids))
print("route=", route_name, "ids=", ids)
for sid in ids:
    meta_url = base.BASE + "/stat-search/files?" + urlencode({"stat_infid": sid})
    mraw, _, mfinal = base.get(meta_url)
    meta = html.unescape(mraw.decode("utf-8", "replace"))
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", meta))
    if "消費者物価指数" not in plain or not re.search(rf"調査年月\s*{y}年\s*{m}月", plain):
        continue
    pub = re.search(r"公開年月日時分\s*(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})", plain)
    print("sid=", sid, "metadata_url=", mfinal, "pub=", pub.groups() if pub else None)
    durl = base.BASE + "/stat-search/file-download?" + urlencode({"fileKind": "2", "statInfId": sid})
    draw, _, dfinal = base.get(durl)
    if not draw.startswith(b"%PDF"):
        continue
    text = base.pdf_text(draw)
    print("source_url=", dfinal)
    print("sha256=", hashlib.sha256(draw).hexdigest())
    print("TEXT_BEGIN")
    print(text[:5000])
    print("TEXT_END")
    compact = re.sub(r"\s+", "", text)
    for token in ("平成", "令和", "2019", "4月", "19日", "公表", "総務省"):
        pos = compact.find(token)
        if pos >= 0:
            print("SNIP", token, compact[max(0, pos-160):pos+240])
