"""Narrow incident recovery: restore only exact corrupt Nov 26 CAD values."""
import json
from pathlib import Path
from validation.cb_pricing.cad_corra_plausibility_v1 import validate_changes,TENORS
from validation.cb_pricing.apply_cad_mx_corra_candidate import extract,replace,OM,NM
ROOT=Path(__file__).resolve().parents[2]
SEC=ROOT/"live_data/sections"
BAD=(-286,-762,-864)
def rates(row):
    return tuple(row["horizons"][t]["rate"] for t in TENORS)
def restore(o,n,op,fixture):
    cad=o["currencies"]["CAD"]
    if cad.get("as_of")!="2026-11-26" or rates(cad)!=BAD:
        return False
    good=fixture["OIS_DATA"]
    assert fixture["source_day"]==good["as_of"]=="2026-11-25"
    assert good["policy_rate"]==cad["policy_rate"]==n["CAD"]["rate"]
    validate_changes(good["provenance"]["observations"],
        {t:good["horizons"][t]["change_1d_bp"] for t in TENORS},
        {t:good["horizons"][t]["change_1w_bp"] for t in TENORS})
    assert n["CAD"]["market_pricing"]["as_of"]=="2026-11-26"
    assert tuple(n["CAD"]["market_pricing"]["h"+t] for t in TENORS)==BAD
    assert op["currencies"]["CAD"]["as_of"] in ("2026-11-25","2026-11-26")
    assert rates(op["currencies"]["CAD"]) in (BAD,rates(good))
    assert rates(fixture["OIS_OPERATIONAL_VIEW"])==rates(good)
    o["currencies"]["CAD"]=good
    n["CAD"].update(fixture["NATIVE_CB_DATA"])
    op["currencies"]["CAD"]=fixture["OIS_OPERATIONAL_VIEW"]
    return True
def main():
    names=["OIS_DATA","NATIVE_CB_DATA","OIS_OPERATIONAL_VIEW"]
    paths=[SEC/(k+".json") for k in names]
    o,n,op=[json.loads(p.read_text()) for p in paths]
    raw=(ROOT/"payload/part-00.txt").read_bytes()
    assert extract(raw,OM)[0]==o and extract(raw,NM)[0]==n,"payload/source mismatch"
    fixture=json.loads((ROOT/"validation/cb_pricing/CAD_CORRA_LAST_GOOD_2026-11-25.json").read_text())
    if not restore(o,n,op,fixture):
        print("CAD_CORRA_INCIDENT_NO_CHANGE")
        return
    encoded=replace(replace(raw,OM,o),NM,n)
    for p,d in zip(paths,(o,n,op)):
        p.write_text(json.dumps(d,ensure_ascii=False,separators=(",",":")))
    (ROOT/"payload/part-00.txt").write_bytes(encoded)
    print("CAD_CORRA_INCIDENT_RESTORED_2026_11_25_NOT_CURRENT_26")
if __name__=="__main__":main()
