/* CHF/USD futures indicative, EUR unsynchronised, NZD explicit hypothetical basis.
   Read-only Rates-page supplement. Never promotes official OIS or pair signals. */
(function(){
'use strict';
const fx=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'],tenors=['3m','6m','12m'];
const flags={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',AUD:'🇦🇺',CAD:'🇨🇦',NZD:'🇳🇿',CHF:'🇨🇭'};
const labels={OFFICIAL:'CERTIFICATA',PROXY:'FUTURES INDICATIVI',MIXED:'DATE NON SINCRONIZZATE',SCENARIO:'SCENARIO · RBNZ B2',WITHHELD:'NON DISPONIBILE'};
const number=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const fmt=x=>number(x)===null?'—':x.toFixed(2);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function fresh(date,today){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date||'')||!/^\d{4}-\d{2}-\d{2}$/.test(today||''))return false;
 const d=(Date.parse(today+'T00:00:00Z')-Date.parse(date+'T00:00:00Z'))/86400000;
 return Number.isInteger(d)&&d>=0&&d<=5;
}
/* Research empirical NZD bank-bill cash-carry calibration, NOT NZBO/OIS quotes.
   Arrays must match validation/cb_pricing/NZD_BB_CASH_RESEARCH_CALIBRATION_V1_2026-10-21.json.
   Public RBNZ monthly averages / month-end OCR manually pinned 2026-10-21. */
const NZD_REFERENCE_ROWS=[["2023-06",5.5,5.68],["2023-07",5.5,5.67],["2023-08",5.5,5.64],["2023-09",5.5,5.68],["2023-10",5.5,5.68],["2023-11",5.5,5.63],["2023-12",5.5,5.63],["2024-01",5.5,5.64],["2024-02",5.5,5.71],["2024-03",5.5,5.64],["2024-04",5.5,5.63],["2024-05",5.5,5.62],["2024-06",5.5,5.62]];
const NZD_RECENT_ROWS=[["2026-01",2.25,2.5],["2026-02",2.25,2.49],["2026-03",2.25,2.51],["2026-04",2.25,2.56],["2026-05",2.25,2.63],["2026-06",2.25,2.68]];
function empiricalMedian(values){
 const s=[...values].sort((a,b)=>a-b),k=Math.floor(s.length/2);
 return s.length%2?s[k]:(s[k-1]+s[k])/2;
}
function calibratedNzdCarry(){
 const basis=(input,expectedOCR)=>{
  if(!Array.isArray(input)||input.length<5)return null;
  const out=[];
  for(const [month,ocr,bill] of input){
   if(!/^\d{4}-\d{2}$/.test(month)||number(ocr)===null||
      number(bill)===null||ocr!==expectedOCR||bill<0||bill>25)return null;
   out.push(Math.round((bill-ocr)*10000)/100);
  }
  return out;
 };
 const old=basis(NZD_REFERENCE_ROWS,5.50),recent=basis(NZD_RECENT_ROWS,2.25);
 if(!old||!recent)return null;
 const all=old.concat(recent),mOld=empiricalMedian(old),mRecent=empiricalMedian(recent);
 const estimated=Math.round(0.30*mOld+0.70*mRecent);
 const lo=Math.floor(Math.min(...all)-2),hi=Math.ceil(Math.max(...all)+2);
 if(!Number.isFinite(estimated)||estimated<=0||estimated>=100||lo<0||hi>100||
    !(lo<estimated&&estimated<hi))return null;
 return {schema:'GMFQ_NZD_EMPIRICAL_CASH_CARRY_SCENARIO_V1',
  basis_bp:estimated,low_bp:lo,high_bp:hi,observations:all.length,
  reference_median_bp:mOld,recent_median_bp:mRecent,
  source:'RBNZ B2 monthly 90-day bills and OCR',reviewed_as_of:'2026-10-21',
  direct_nzbo_ois_quote:false,statistical_confidence_interval:false,
  forward_ois_curve:false,policy_delta_allowed:false,core_effect:'NONE'};
}
function matrix(ois,bb,today){
 return fx.map(ccy=>{
  const x=ois?.currencies?.[ccy]||{},points={};let tier='WITHHELD',source='';
  if(x.operational_status==='GREEN_OFFICIAL'&&x.official_status==='ACTIVE'&&
     x.quality==='OFFICIAL_CERTIFIED'&&x.backtest_eligible_as_official===true&&fresh(x.as_of,today)){
    if(tenors.every(t=>number(x.horizons?.[t]?.rate)!==null)){
     for(const t of tenors)points[t]={value:x.horizons[t].rate,date:x.as_of};
     tier='OFFICIAL';source=x.source||'';
    }
  }else if(['USD','CHF'].includes(ccy)&&x.operational_status==='GREEN_ESTIMATED'&&
    x.official_status==='WITHHELD'&&x.quality==='ESTIMATED_INFORMATIONAL'&&
    x.backtest_eligible_as_official===false&&x.method_id==='TRADINGVIEW_DATED_FUTURES_SSR_V2'){
    for(const t of tenors){const p=x.horizons?.[t]||{};
     if(number(p.rate)!==null&&fresh(p.quote_as_of,today)&&p.quote_timestamp_verified===true&&
        p.quote_timestamp_source==='SSR_DAILY_BAR_DATA_UPDATE_TIME'&&/^[A-Z0-9]+$/.test(p.contract||''))
      points[t]={value:p.rate,date:p.quote_as_of};}
    if(Object.keys(points).length){tier='PROXY';source=x.source||'';}
  }else if(ccy==='EUR'&&x.operational_status==='WITHHELD'){
    const q=x.secondary_quote_context||{};
    if(q.status==='INDICATIVE_OBSERVATIONS_NON_OIS'&&q.full_curve_usable===false&&
       q.cross_date_join_allowed===false&&q.policy_delta_allowed===false&&
       q.repricing_signal_allowed===false&&q.backtest_eligible_as_official===false){
      for(const t of tenors){const p=q.horizons?.[t]||{};
       if(number(p.rate_indicative)!==null&&fresh(p.quote_as_of,today)&&
          p.source_quality==='SECONDARY_VERIFIED_DAILY_BAR'&&/^[A-Z0-9]+$/.test(p.contract||''))
        points[t]={value:p.rate_indicative,date:p.quote_as_of};}
      if(Object.keys(points).length){tier='MIXED';source=q.source||'';}
    }
  }else if(ccy==='NZD'&&x.official_status==='WITHHELD'&&
    bb?.schema==='GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1'&&
    bb.currency==='NZD'&&bb.status==='LIVE_DIRECTIONAL_PROXY_READY'&&
    bb.governance?.substitutes_for_ois_level===false&&
    bb.governance?.policy_delta_from_proxy_allowed===false&&fresh(bb.as_of,today)){
    const calibration=calibratedNzdCarry();
    if(calibration&&bb.governance?.backtest_eligible_as_official_ois===false){
     for(const t of tenors){
      const p=bb.horizons?.[t]||{},raw=number(p.implied_bank_bill_rate);
      if(raw!==null&&raw>=-5&&raw<=25&&
         /^\d{4}-\d{2}-\d{2}$/.test(p.expiration||'')&&
         typeof p.mapping==='string'&&p.mapping.includes('nearest listed expiry')){
       points[t]={
        value:Math.round((raw-calibration.basis_bp/100)*100)/100,date:bb.as_of,
        range:[Math.round((raw-calibration.high_bp/100)*100)/100,
               Math.round((raw-calibration.low_bp/100)*100)/100]
       };
      }
     }
     if(Object.keys(points).length){
      tier='SCENARIO';source=(bb.source||'')+
        ' · '+calibration.source+' ('+calibration.observations+
        ' mesi; sconto empirico '+calibration.basis_bp+' bp)';
     }
    }
  }
  return {ccy,tier,points,source,official_ois:ccy==='GBP'&&tier==='OFFICIAL',
    allow_official_promotion:false,allow_repricing:false,
    core_score_effect:'NONE',bias_effect:'NONE',pair_effect:'NONE',backtest_official:false};
 });
}
/* A full G8 research row requires three valid dated levels. A single
   observed contract must NOT count as complete 3M/6M/12M coverage. */
function coverage(ois,bb,today){
 const rows=matrix(ois,bb,today);
 const complete=rows.filter(x=>x.tier!=='WITHHELD'&&
   tenors.every(t=>number(x.points[t]?.value)!==null&&fresh(x.points[t]?.date,today)));
 const official=complete.filter(x=>x.tier==='OFFICIAL');
 const context=complete.filter(x=>x.tier!=='OFFICIAL');
 return {
  schema:'GMFQ_OIS_G8_RESEARCH_COVERAGE_V1',
  date:today,total:8,official_count:official.length,
  context_count:context.length,covered_count:complete.length,
  official_codes:official.map(x=>x.ccy),
  context_codes:context.map(x=>x.ccy),
  incomplete_codes:rows.filter(x=>!complete.includes(x)).map(x=>x.ccy),
  currency_tiers:Object.fromEntries(rows.map(x=>[x.ccy,
   complete.includes(x)?x.tier:'INCOMPLETE_OR_STALE'])),
  unverified_are_not_official:true,
  no_ois_official_promotion:true,core_effect:'NONE',
  pair_effect:'NONE',backtest_estimated_as_official:false
 };
}
function view(rows){
 const cell=(r,t)=>{const x=r.points[t];return x?
  '<b>'+(r.tier==='OFFICIAL'?'':'≈')+fmt(x.value)+'%</b><small>'+esc(x.date)+'</small>'+
   (x.range?'<small>'+fmt(x.range[0])+'–'+fmt(x.range[1])+'%</small>':''):
  '<b>—</b><small>n.d.</small>';};
 return '<h2 class="desk-panel-title">G8 · Pricing monetario 3M / 6M / 12M</h2>'+
 '<div class="gmfq-est-body"><p>Valori <b>certificati, indicativi e scenari</b> distinti. Date per singola scadenza; non tutte le serie sono OIS.</p>'+
 '<div role="table" class="gmfq-est-table"><div class="gmfq-est-row gmfq-est-head" role="row"><span>Valuta</span><span>3M</span><span>6M</span><span>12M</span></div>'+
 rows.map(r=>'<div role="row" class="gmfq-est-row" data-ccy="'+r.ccy+'" data-estimate-type="'+r.tier+'">'+
 '<div><strong>'+flags[r.ccy]+' '+r.ccy+'</strong><small>'+labels[r.tier]+'</small></div>'+
 tenors.map(t=>'<div>'+cell(r,t)+'</div>').join('')+
 '<div class="gmfq-est-source">'+esc(r.source||'Fonte non corrente')+'</div></div>').join('')+'</div>'+
 '<p class="gmfq-est-note"><b>Metodo:</b> GBP OIS BoE; AUD/CAD/JPY futures monetari ufficiali; USD/CHF futures indicativi. EUR usa giorni diversi e non forma una curva sincronizzata. NZD: scenario empirico su Bank Bill 90 giorni − OCR RBNZ (19 mesi, due regimi): sconto stimato 24 bp, fascia prudenziale 10–45 bp. <b>Non è il vero spread Bills/OIS né un intervallo statistico</b>. Sono futures trimestrali, non una curva OIS spot. Nessuna stima produce variazioni OIS 1D/1W, segnali FX o backtest.</p></div>';
}
const css=[
 '#gmfq-ois-research-estimates{margin:12px 0;min-width:0}',
 '#gmfq-ois-research-estimates .gmfq-est-body{padding:12px 15px;color:#bacedd;font:12px/1.5 Arial,sans-serif}',
 '#gmfq-ois-research-estimates .gmfq-est-table{border:1px solid #2c495a;background:#0a2132;border-radius:6px;overflow:hidden}',
 '#gmfq-ois-research-estimates .gmfq-est-row{display:grid;grid-template-columns:minmax(115px,1.3fr) repeat(3,minmax(75px,1fr));border-bottom:1px solid #254153}',
 '#gmfq-ois-research-estimates .gmfq-est-row>div,#gmfq-ois-research-estimates .gmfq-est-row>span{padding:7px 7px;min-width:0;overflow-wrap:anywhere}',
 '#gmfq-ois-research-estimates .gmfq-est-row b{display:block;color:#e6eff5;font:600 14px/1.3 Arial,sans-serif;font-variant-numeric:tabular-nums}',
 '#gmfq-ois-research-estimates .gmfq-est-row small{display:block;color:#a4bccc;font:10px/1.35 Arial,sans-serif}',
 '#gmfq-ois-research-estimates .gmfq-est-source{grid-column:1/-1;color:#9aafbd;font-size:10px;padding-top:0!important}',
 '#gmfq-ois-research-estimates .gmfq-est-head{color:#adbecc;background:#142c3d;font:600 10px Arial,sans-serif}',
 '#gmfq-ois-research-estimates [data-estimate-type="SCENARIO"] b,#gmfq-ois-research-estimates [data-estimate-type="MIXED"] b{color:#e3c681}',
 '#gmfq-ois-research-estimates .gmfq-est-note{margin-top:12px;color:#b1c5d2}',
 '@media(max-width:600px){#gmfq-ois-research-estimates .gmfq-est-body{padding:9px}#gmfq-ois-research-estimates .gmfq-est-row{grid-template-columns:minmax(78px,1.1fr) repeat(3,minmax(0,1fr))}#gmfq-ois-research-estimates .gmfq-est-row>div,#gmfq-ois-research-estimates .gmfq-est-row>span{padding:6px 4px}#gmfq-ois-research-estimates .gmfq-est-row b{font-size:12px}#gmfq-ois-research-estimates .gmfq-est-row small{font-size:9px}}'
].join('');
if(typeof module!=='undefined'&&module.exports)module.exports={matrix,view,fresh,coverage,calibratedNzdCarry,NZD_REFERENCE_ROWS,NZD_RECENT_ROWS};
if(typeof window!=='undefined')window.GMFQ_OIS_RESEARCH_V1=Object.freeze({coverage});
if(typeof document==='undefined')return;
const frame=document.getElementById('gmfq-page');if(!frame)return;
const ROOT='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/';
let mounted=null;
function active(){return(location.hash||'#/home').split('?')[0]==='#/tassi';}
async function get(p){const r=await fetch(ROOT+p,{cache:'no-store'});if(!r.ok)throw Error('feed '+p);return r.json();}
async function mount(doc){
 if(!active()||frame.contentDocument!==doc||mounted===doc)return;
 const anchor=doc.getElementById('ois-rows')?.closest('.desk-panel');if(!anchor)return;
 mounted=doc;
 const box=doc.createElement('section');box.id='gmfq-ois-research-estimates';box.className='desk-panel';
 box.dataset.coreEffect='NONE';box.dataset.officialPromotion='false';box.dataset.status='LOADING';
 box.innerHTML='<h2 class="desk-panel-title">G8 · tassi monetari</h2>';
 anchor.insertAdjacentElement('afterend',box);
 const st=doc.createElement('style');st.textContent=css;doc.head.appendChild(st);
 try{const [a,b]=await Promise.allSettled([get('OIS_OPERATIONAL_VIEW.json'),get('NZD_CB_PRICING_DIRECTIONAL_PROXY.json')]);
  if(frame.contentDocument!==doc||!active())return;
  const o=a.status==='fulfilled'?a.value:null,p=b.status==='fulfilled'?b.value:null;
  if(o?.schema!=='GMFQ_OIS_OPERATIONAL_VIEW_V1'||!o.currencies)throw Error('invalid feed');
  const rows=matrix(o,p,new Date().toISOString().slice(0,10));
  box.dataset.status='RESEARCH_ONLY';box.dataset.officalSources=''+rows.filter(r=>r.tier==='OFFICIAL').length;
  box.innerHTML=view(rows);
 }catch(e){box.dataset.status='WITHHELD';box.innerHTML='<h2 class="desk-panel-title">G8 · dati non disponibili</h2>';
  console.warn('[GMFQ OIS research withheld]',String(e));}
}
function loaded(){let doc;try{doc=frame.contentDocument}catch(_){return}
 if(doc?.body)mount(doc).catch(e=>console.warn('[GMFQ OIS research withheld]',e));}
frame.addEventListener('load',loaded);
try{if(frame.contentDocument?.readyState==='complete')loaded()}catch(_){}
})();