#!/usr/bin/env python3
"""Create a read-only, self-contained preview of the independent FX Quant NEXT site.

This is a dated offline snapshot of the same published local source JSON. It is not
a replacement for GitHub Pages or a live data service.
"""
from __future__ import annotations
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "fx-quant-v2" / "next"
DEST = ROOT / "fxquant-next-offline" / "FX_Quant_NEXT_Anteprima_Offline.html"

SOURCES = {
    "rates": "live_data/sections/NATIVE_RATES_DATA.json",
    "dxy": "live_data/sections/DXY_SYNTHETIC_ECB.json",
    "pairs": "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
    "macro": "live_data/sections/MACRO_THERMOMETER_DATA.json",
    "cb": "live_data/sections/NATIVE_CB_DATA.json",
    "cot": "live_data/sections/V247_COT_STORIES.json",
    "cotHistory": "live_data/sections/V250_COT_CHART_DATA.json",
    "cotPrice": "site/fx-quant-v2/design-studio-cot-v1-data.json",
    "risk": "site/fx-quant-v2/cross-asset-live-data.json",
    "ois": "site/fx-quant-v2/ois-pricing-snapshot.json",
    "news": "live_data/sections/NEWS_PULSE_OPERATIONAL.json",
    "themes": "live_data/sections/TOP_THEMES.json",
}

def main() -> None:
    contents = (SITE / "index.html").read_text(encoding="utf-8")
    css = (SITE / "theme.css").read_text(encoding="utf-8")
    js = (SITE / "app.js").read_text(encoding="utf-8")
    cot_js = (SITE / "cot-studio.js").read_text(encoding="utf-8")
    cot_css = (SITE / "cot-studio.css").read_text(encoding="utf-8")
    docs = {k: json.loads((ROOT / path).read_text(encoding="utf-8")) for k, path in SOURCES.items()}
    assert len(docs) == 12
    assert docs["pairs"].get("pair_count") == 28
    assert docs["dxy"].get("not_official_ice") is True

    css = css.replace("@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;450;500;550;600;650;700;750;800&family=Manrope:wght@400;500;600;650;700;800&display=swap');", "")
    contents = contents.replace('<link rel="stylesheet" href="./theme.css?v=2">', "<style>"+css+"</style>")
    contents = contents.replace('<link rel="stylesheet" href="./cot-studio.css?v=1">', "<style>"+cot_css+"</style>")
    contents = contents.replace('<script src="./cot-studio.js?v=1" defer></script>', "<script>"+cot_js+"</script>")
    contents = contents.replace('<script src="./app.js?v=2" defer></script>', "")
    contents = contents.replace('<span class="live-dot"></span> NEXT / DESIGN LAB', '<span class="live-dot"></span> NEXT / DESIGN LAB')
    contents = contents.replace('NEXT / DESIGN LAB <span class="edition-sep">', 'NEXT / OFFLINE PREVIEW <span class="edition-sep">')
    contents = contents.replace('FX QUANT / NEXT · Concept di prodotto', 'FX QUANT / NEXT · Copia autonoma con dati fotografati al 06/11/2026')
    snapshot=json.dumps(docs,ensure_ascii=False,separators=(",",":")).replace("</","<\\/")
    script_intro="""<script id="fxquant-next-offline-data" type="application/json">"""+snapshot+"""</script>
<script>
/* Snapshot-only fetch interceptor for this standalone review file. */
(function(){
 const captured=JSON.parse(document.getElementById('fxquant-next-offline-data').textContent);
 const targets={
 'NATIVE_RATES_DATA.json':'rates','DXY_SYNTHETIC_ECB.json':'dxy',
 'PAIR_SETUP_OPERATIONAL_VIEW.json':'pairs','MACRO_THERMOMETER_DATA.json':'macro',
 'NATIVE_CB_DATA.json':'cb','V247_COT_STORIES.json':'cot',
 'V250_COT_CHART_DATA.json':'cotHistory',
 'design-studio-cot-v1-data.json':'cotPrice',
 'cross-asset-live-data.json':'risk','ois-pricing-snapshot.json':'ois',
 'NEWS_PULSE_OPERATIONAL.json':'news','TOP_THEMES.json':'themes'};
 const original=window.fetch?window.fetch.bind(window):null;
 window.fetch=function(input,options){
   const key=Object.entries(targets).find(([name])=>String(input).includes(name))?.[1];
   if(key)return Promise.resolve({ok:true,status:200,json:async()=>captured[key]});
   return original?original(input,options):Promise.reject(Error('Offline snapshot: external fetch disabled'));
 };
})();
</script>
<script id="fxquant-next-offline-app">
"""+js.replace("</script>","<\\/script>")+"""
</script>
"""
    contents=contents.replace("</body>",script_intro+"</body>")
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(contents,encoding="utf-8")
    assert 'fxquant-next-offline-data' in contents
    assert 'function rates()' in contents
    assert '<style>' in contents
    print(json.dumps({"status":"PASS","output":str(DEST),"bytes":DEST.stat().st_size,
      "snapshot_sources":list(docs),"pairs":docs["pairs"]["pair_count"],
      "rate_usd_asof":docs["rates"]["USD"]["date"],"live_updates":False},ensure_ascii=False))
if __name__=="__main__":
    main()
