/* CHF/USD futures indicative, EUR unsynchronised, NZD explicit hypothetical basis.
   Read-only Rates-page supplement. Never promotes official OIS or pair signals. */
(function(){
'use strict';
const fx=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'],tenors=['3m','6m','12m'];
const flags={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',AUD:'🇦🇺',CAD:'🇨🇦',NZD:'🇳🇿',CHF:'🇨🇭'};
const labels={OFFICIAL:'CERTIFICATA',PROXY:'FUTURES INDICATIVI',MIXED:'DATE NON SINCRONIZZATE',SCENARIO:'SCENARIO BB − 50 bp',WITHHELD:'NON DISPONIBILE'};
const number=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const fmt=x=>number(x)===null?'—':x.toFixed(2);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function fresh(date,today){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date||'')||!/^\d{4}-\d{2}-\d{2}$/.test(today||''))return false;
 const d=(Date.parse(today+'T00:00:00Z')-Date.parse(date+'T00:00:00Z'))/86400000;
 return Number.isInteger(d)&&d>=0&&d<=5;
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
    for(const t of tenors){const p=bb.horizons?.[t]||{},raw=number(p.implied_bank_bill_rate);
     if(raw!==null&&raw>=-5&&raw<=25&&/^\d{4}-\d{2}-\d{2}$/.test(p.expiration||'')){
      points[t]={value:Math.round((raw-0.50)*100)/100,date:bb.as_of,
       range:[Math.round((raw-0.75)*100)/100,Math.round((raw-0.25)*100)/100]};}}
    if(Object.keys(points).length){tier='SCENARIO';source=bb.source||'';}
  }
  return {ccy,tier,points,source,official_ois:ccy==='GBP'&&tier==='OFFICIAL',
    allow_official_promotion:false,allow_repricing:false,
    core_score_effect:'NONE',bias_effect:'NONE',pair_effect:'NONE',backtest_official:false};
 });
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
 '<p class="gmfq-est-note"><b>Metodo:</b> GBP OIS BoE; AUD/CAD/JPY futures monetari ufficiali; USD/CHF futures indicativi. EUR usa giorni diversi e non forma una curva sincronizzata. NZD: scenario non calibrato = futures Bank Bill meno 50 bp ipotetici, con fascia 25–75 bp di differenziale, <b>non intervallo statistico</b>. Nessuna stima produce variazioni OIS 1D/1W, segnali FX o backtest.</p></div>';
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
if(typeof module!=='undefined'&&module.exports)module.exports={matrix,view,fresh};
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