#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import json
import re
from pathlib import Path

BASE_PATH=Path('validation/materialize_jpy_wages_cpi_pit_v1.py')
SPEC=importlib.util.spec_from_file_location('jpy_pit_v1',BASE_PATH)
base=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def direct_yoy(block: str):
    """Parse only the YoY statement inside one numbered overview item."""
    # Official CPI releases sometimes express exactly 0.0% as 'same level as previous year'
    # instead of printing a numeric YoY percentage (e.g. 2020-07 ex-fresh-food core).
    if re.search(r'前年同月と同水準',block) or re.search(r'前年同月比[^。]{0,40}(?:変わらず|同水準)',block):
        return 0.0
    m=re.search(r'前年同月比(?:は|が|、)?(-?[0-9]+(?:\.[0-9]+)?)%(?:の)?(上昇|下落)?',block)
    if not m:
        return None
    val=float(m.group(1))
    direction=m.group(2)
    if direction=='下落':
        val=-abs(val)
    return val


def numbered_overview(seg: str):
    # NFKC performed by base.norm turns full-width parentheses/numbers into ASCII.
    # The official first-page overview defines (1)=headline and (2)=ex-fresh-food core.
    m1=re.search(r'\(1\)(.*?)(?=\(2\))',seg)
    m2=re.search(r'\(2\)(.*?)(?=\(3\)|表1|表１)',seg)
    h=direct_yoy(m1.group(1)) if m1 else None
    c=direct_yoy(m2.group(1)) if m2 else None
    return h,c


def narrative_current_month(seg: str,label: str,current_month: int,headline: bool=False):
    """Fallback only when the authoritative numbered item cannot be parsed."""
    if headline:
        pat=r'(?<!く)総合の前年同月比[^。]{0,220}'
    else:
        pat=r'生鮮食品を除く総合の前年同月比[^。]{0,220}'
    for sm in re.finditer(pat,seg):
        sentence=sm.group(0)
        am=re.search(r'\([^)]*?→'+str(current_month)+r'月(-?[0-9]+(?:\.[0-9]+)?)%\)',sentence)
        if am:
            return float(am.group(1))
        if '変わらず' in sentence or '同水準' in sentence:
            return 0.0
        dm=re.search(r'前年同月比(?:は|が|、)?(-?[0-9]+(?:\.[0-9]+)?)%(?:の)?(上昇|下落)?',sentence)
        if dm and '上昇幅' not in sentence[:dm.end()] and '下落幅' not in sentence[:dm.end()] and 'ポイント' not in sentence[:dm.end()]:
            val=float(dm.group(1))
            if dm.group(2)=='下落':
                val=-abs(val)
            return val
    return None


def parse_cpi_v2(txt: str, ym: str):
    seg=base.norm(txt[:18000]).replace(' ','')
    current_month=int(ym.split('-')[1])
    oh,oc=numbered_overview(seg)

    # Authoritative primary: when both official numbered overview items parse,
    # use them directly. Do not let later narrative/table prose veto them.
    if oh is not None and oc is not None:
        return oh,oc,'OVERVIEW_NUMBERED_ITEM','OVERVIEW_NUMBERED_ITEM'

    # Component-wise fallback only for the numbered item that is missing/unparseable.
    nh=None if oh is not None else narrative_current_month(seg,'総合',current_month,headline=True)
    nc=None if oc is not None else narrative_current_month(seg,'生鮮食品を除く総合',current_month,headline=False)
    h=oh if oh is not None else nh
    c=oc if oc is not None else nc
    hm='OVERVIEW_NUMBERED_ITEM' if oh is not None else ('SCOPED_NARRATIVE_SENTENCE' if nh is not None else None)
    cm='OVERVIEW_NUMBERED_ITEM' if oc is not None else ('SCOPED_NARRATIVE_SENTENCE' if nc is not None else None)
    return h,c,hm,cm


base.parse_cpi=parse_cpi_v2

if __name__=='__main__':
    base.main()
    ev_path=base.EVID
    ev=json.loads(ev_path.read_text(encoding='utf-8'))
    ev['materializer_revision']='2.2'
    ev['cpi_extraction_policy']='Authoritative primary = official first-page numbered overview items (1=headline, 2=ex-fresh-food core). Official unchanged/same-level wording maps mechanically to 0.0% YoY. Scoped narrative is used only component-by-component when the corresponding numbered item is absent or unparseable; later prose cannot veto a successfully parsed numbered overview item. No cross-component regex traversal.'
    ev['semantic_crosscheck']='NUMBERED_OVERVIEW_AUTHORITATIVE_NARRATIVE_FALLBACK_ONLY'
    ev_path.write_text(json.dumps(ev,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
