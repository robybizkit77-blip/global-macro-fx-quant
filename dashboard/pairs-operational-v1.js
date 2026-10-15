(()=>{
  'use strict';
  const PAIRS=['AUD/CAD','AUD/CHF','AUD/JPY','AUD/NZD','AUD/USD','CAD/CHF','CAD/JPY','CHF/JPY','EUR/AUD','EUR/CAD','EUR/CHF','EUR/GBP','EUR/JPY','EUR/NZD','EUR/USD','GBP/AUD','GBP/CAD','GBP/CHF','GBP/JPY','GBP/NZD','GBP/USD','NZD/CAD','NZD/CHF','NZD/JPY','NZD/USD','USD/CAD','USD/CHF','USD/JPY'];
  const QUALITY_LABEL={
    'CONTRASTO STRUTTURALE FORTE':'Segnale più chiaro',
    'VANTAGGIO RELATIVO PARZIALE':'Vantaggio parziale',
    'PILASTRI DIVISI':'Macro e tassi in conflitto',
    'NESSUN CONTRASTO':'Nessun vantaggio chiaro',
    'SEPARAZIONE RATES MATERIALE':'Differenziale tassi rilevante'
  };
  const QUALITY_SCORE={
    'CONTRASTO STRUTTURALE FORTE':4,
    'VANTAGGIO RELATIVO PARZIALE':3,
    'SEPARAZIONE RATES MATERIALE':2,
    'PILASTRI DIVISI':1,
    'NESSUN CONTRASTO':0
  };
  const css=`
  #pairs .poWrap{display:grid;gap:18px}
  #pairs .poHero{padding:18px;border:1px solid rgba(255,255,255,.10);border-radius:16px;background:linear-gradient(135deg,rgba(36,73,125,.20),rgba(10,18,32,.15))}
  #pairs .poHero h2{margin:0 0 6px;font-size:clamp(20px,2.5vw,30px)}
  #pairs .poSub{opacity:.78;line-height:1.5}
  #pairs .poMeta{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
  #pairs .poChip{font-size:12px;padding:6px 9px;border-radius:999px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.08)}
  #pairs .poTop{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
  #pairs .poCard{padding:14px;border-radius:14px;border:1px solid rgba(255,255,255,.09);background:rgba(255,255,255,.035)}
  #pairs .poPair{font-weight:800;font-size:17px;letter-spacing:.2px}
  #pairs .poDir{margin-top:7px;font-size:13px;font-weight:700}
  #pairs .poWhy{margin-top:5px;font-size:12px;opacity:.72;line-height:1.4}
  #pairs .poPx{margin-top:10px;font-variant-numeric:tabular-nums;font-size:13px}
  #pairs .poTableWrap{overflow:auto;border:1px solid rgba(255,255,255,.08);border-radius:14px}
  #pairs table.poTable{width:100%;border-collapse:collapse;min-width:760px}
  #pairs .poTable th,#pairs .poTable td{padding:10px 12px;text-align:left;border-bottom:1px solid rgba(255,255,255,.06);font-size:12px;vertical-align:top}
  #pairs .poTable th{position:sticky;top:0;background:#101827;z-index:1;opacity:.9}
  #pairs .poTable tr:last-child td{border-bottom:0}
  #pairs .pos{color:#62d69b}.neg{color:#ff7f8a}.neu{color:#a9b4c6}.warn{color:#f0b35a}
  @media(max-width:900px){#pairs .poTop{grid-template-columns:1fr 1fr}}
  @media(max-width:560px){#pairs .poTop{grid-template-columns:1fr}#pairs .poHero{padding:14px}}
  `;

  function latestPriceRow(){
    if(typeof D==='undefined'||!Array.isArray(D.prices)||!D.prices.length) return null;
    return [...D.prices].filter(x=>x&&x.Date).sort((a,b)=>String(a.Date).localeCompare(String(b.Date))).at(-1)||null;
  }
  function crossPrice(pair,row){
    if(!row) return null;
    const [a,b]=pair.split('/');
    const ra=Number(row[a]), rb=Number(row[b]);
    if(!(ra>0)||!(rb>0)) return null;
    return rb/ra;
  }
  function fmtPrice(pair,x){
    if(!Number.isFinite(x)) return '—';
    return x.toFixed(pair.includes('JPY')?3:5);
  }
  function frame(pair){
    try{return window.derivePairDecisionFrame?.(pair)||null;}catch(e){return null;}
  }
  function direction(pair,f){
    const [a,b]=pair.split('/');
    if(!f||!f.fav||f.fav==='—') return {text:'Nessun lato favorito',cls:'neu',side:'NEUTRAL'};
    if(f.fav===a) return {text:`Favorisce ${a}`,cls:'pos',side:'BASE'};
    if(f.fav===b) return {text:`Favorisce ${b}`,cls:'neg',side:'QUOTE'};
    return {text:'Nessun lato favorito',cls:'neu',side:'NEUTRAL'};
  }
  function sideText(side){return side==='A'?'prima valuta':side==='B'?'seconda valuta':'pari';}
  function details(f){
    if(!f) return 'Motore non disponibile';
    const m=sideText(f.structural?.macro?.side);
    const p=sideText(f.structural?.policy?.side);
    const r=f.structural?.ratesGap?.material?` · tassi: ${sideText(f.structural?.ratesGap?.side)}`:'';
    return `Macro: ${m} · Banca centrale: ${p}${r}`;
  }
  function quality(f){return QUALITY_LABEL[f?.quality]||String(f?.quality||'Da verificare');}
  function rankValue(f){return (QUALITY_SCORE[f?.quality]??-1)+(f?.structural?.ratesGap?.material?0.25:0);}

  function buildRows(row){
    return PAIRS.map(pair=>{
      const f=frame(pair), d=direction(pair,f), price=crossPrice(pair,row);
      return {pair,f,d,price,quality:quality(f),rank:rankValue(f)};
    });
  }
  function card(x){return `<div class="poCard" data-pair="${x.pair}"><div class="poPair">${x.pair}</div><div class="poDir ${x.d.cls}">${x.d.text}</div><div class="poWhy">${x.quality}<br>${details(x.f)}</div><div class="poPx">Prezzo fixing: <b>${fmtPrice(x.pair,x.price)}</b></div></div>`;}
  function tableRow(x){return `<tr data-pair="${x.pair}"><td><b>${x.pair}</b></td><td class="${x.d.cls}">${x.d.text}</td><td>${x.quality}</td><td>${details(x.f)}</td><td>${fmtPrice(x.pair,x.price)}</td></tr>`;}

  function render(){
    const root=document.getElementById('pairs');
    if(!root) throw new Error('PAIRS_VIEW_MISSING');
    if(typeof window.derivePairDecisionFrame!=='function') throw new Error('PAIR_ENGINE_MISSING');
    const row=latestPriceRow();
    if(!row) throw new Error('PRICE_ROW_MISSING');
    const rows=buildRows(row);
    if(rows.length!==28||rows.some(x=>!x.f||!Number.isFinite(x.price))) throw new Error('PAIR_COVERAGE_INCOMPLETE');
    const top=rows.filter(x=>x.d.side!=='NEUTRAL').sort((a,b)=>b.rank-a.rank||a.pair.localeCompare(b.pair)).slice(0,6);
    root.innerHTML=`<style>${css}</style><div class="poWrap" data-gmfq-operational="pairs"><section class="poHero"><h2>Coppie FX</h2><div class="poSub">Le 28 coppie G8 ricalcolate dal motore corrente. Qui vedi quale valuta è favorita da Macro, banca centrale e differenziale tassi. Il prezzo è derivato dall’ultimo fixing ECB disponibile.</div><div class="poMeta"><span class="poChip">28/28 coppie</span><span class="poChip">Prezzi aggiornati al ${row.Date}</span><span class="poChip">Motore: stato corrente</span></div></section><section><h3>Contrasti più chiari adesso</h3><div class="poTop">${top.map(card).join('')}</div></section><section><h3>Tutte le coppie</h3><div class="poTableWrap"><table class="poTable"><thead><tr><th>Coppia</th><th>Lato favorito</th><th>Qualità</th><th>Perché</th><th>Fixing</th></tr></thead><tbody>${rows.map(tableRow).join('')}</tbody></table></div></section></div>`;
    root.dataset.gmfqPairPriceAsOf=String(row.Date);
    window.GMFQ_PAIRS_OPERATIONAL={status:'ACTIVE',schema:'GMFQ_PAIRS_OPERATIONAL_UI_V1',core_effect:'NONE',pair_count:28,directional_count:rows.filter(x=>x.d.side!=='NEUTRAL').length,price_as_of:String(row.Date),source:'derivePairDecisionFrame + D.prices latest official ECB fixing',legacy_owner:'NON_OWNER'};
    return window.GMFQ_PAIRS_OPERATIONAL;
  }
  function boot(){
    let n=0;
    const tick=()=>{
      n++;
      try{
        if(window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true&&typeof window.derivePairDecisionFrame==='function'&&typeof D!=='undefined'&&Array.isArray(D.prices)){
          render();return;
        }
      }catch(e){window.GMFQ_PAIRS_OPERATIONAL={status:'WAITING',error:String(e?.message||e),core_effect:'NONE'};}
      if(n<240) setTimeout(tick,250); else window.GMFQ_PAIRS_OPERATIONAL={status:'FAIL',error:'PAIR_OPERATIONAL_BOOT_TIMEOUT',core_effect:'NONE'};
    };
    tick();
  }
  window.gmfqRenderOperationalPairs=render;
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();
