#!/usr/bin/env python3
"""Inspect captured BLS CPI XLSX XML, describe structure without imputing values.

Only reads source bytes already acquired by opt-in one-shot probe.
The printed content is a technical inspection, not original-vintage certification.
"""
from __future__ import annotations
import json
import re
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

NS = {"s":"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
X = "{"+NS["s"]+"}"
R = "{"+NS["r"]+"}"

def value(c,strings):
    inline=c.find(X+"is")
    if inline is not None:
        return "".join(x.text or "" for x in inline.iter(X+"t"))
    v=c.find(X+"v")
    if v is None or v.text is None:
        return ""
    if c.get("t")=="s":
        try: return strings[int(v.text)]
        except (ValueError, IndexError): return "BAD_SHARED_STRING"
    return v.text

def inspect(path:Path):
    with ZipFile(path) as f:
        strings=[]
        if "xl/sharedStrings.xml" in f.namelist():
            root=ET.fromstring(f.read("xl/sharedStrings.xml"))
            strings=["".join(t.text or "" for t in item.iter(X+"t")) for item in root]
        workbook=ET.fromstring(f.read("xl/workbook.xml"))
        sheets=[(s.get("name"),s.get(R+"id")) for s in workbook.findall(".//"+X+"sheet")]
        output=[]
        for idx,(name,rel) in enumerate(sheets):
            target=f"xl/worksheets/sheet{idx+1}.xml"
            if target not in f.namelist():continue
            root=ET.fromstring(f.read(target))
            found=[]
            preview=[]
            allitems=[]
            totalrows=0
            for row in root.iter(X+"row"):
                totalrows+=1
                cells=[(c.get("r",""),value(c,strings)) for c in row.findall(X+"c") if value(c,strings)!=""]
                sample=" | ".join(f"{a}:{v}" for a,v in cells[:50])
                if totalrows <= 9:
                    preview.append(sample[:380])
                if re.search(r"all\s*items|seasonally\s*adjusted|CUSR0000SA0|1982-84",sample,re.I):
                    if len(found)<18:
                        found.append(sample[:800])
                if re.search(r"all\s*items",sample,re.I):
                    if len(allitems)<4: allitems.append({"row": row.get("r"),"first":cells[:6],"last":cells[-14:]})
            output.append({"sheet":name,"rows":totalrows,"first_rows":preview,
                           "keyword_rows":found,"all_items_row_slices":allitems})
        return {"file":path.name,"sheets":output}

def main():
    root=Path("/tmp/bls_cpi_research_probe/raw_research_sources")
    sources=list(root.glob("*.xlsx"))
    if not sources: print("NO_VALID_SOURCE_WORKBOOKS")
    for path in sources:
        o=inspect(path)
        print("XLSX_LAYOUT: "+json.dumps(o,ensure_ascii=False,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
