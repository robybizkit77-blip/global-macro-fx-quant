(()=>{
'use strict';
const MONTHS={gennaio:0,febbraio:1,marzo:2,aprile:3,maggio:4,giugno:5,luglio:6,agosto:7,settembre:8,ottobre:9,novembre:10,dicembre:11};
const SPECS={
  overview:{maxAgeDays:7,label:'OVERVIEW',kind:'overview'},
  wow:{maxAgeDays:2,label:'WHAT CHANGED',kind:'news'},
  themes:{maxAgeDays:2,label:'TOP THEMES',kind:'news'},
  calendar:{maxAgeDays:1,label:'CALENDARIO',kind:'calendar'},
  news:{maxAgeDays:2,label:'NEWS PULSE',kind:'news'},
  risk:{maxAgeDays:3,label:'RISK',kind:'risk'}
};
const operational={calendar:null,news:null,risk:null,loaded:false,errors:[]};
const state={
  schema:'GMFQ_EDITORIAL_FRESHNESS_GUARD_V3_OPERATIONAL_AUTHORITY',
  status:'INIT',sections:{},evaluated_at:null,operational_loaded:false,
  authority:{
    overview:'VISIBLE_DOM_EXPLICIT_ASOF',
    wow:'NEWS_PULSE_OPERATIONAL.content_as_of',
    themes:'NEWS_PULSE_OPERATIONAL.content_as_of',
    calendar:'CALENDAR_OPERATIONAL_VIEW.generated_at_utc',
    news:'NEWS_PULSE_OPERATIONAL.content_as_of',
    risk:'OLDEST_REQUIRED(D.risk.VIX.last_date,D.risk.WTI.last_date,ESTIMATED_RESIDUAL_GAPS.BRENT.proxy_as_of)'
  },
  legacy_authority:'NONE'
};
window.GMFQ_EDITORIAL_FRESHNESS=state;

function dayFloor(d){return new Date(d.getFullYear(),d.getMonth(),d.getDate());}
function isoDate(d){if(!(d instanceof Date)||Number.isNaN(d.getTime()))return null;return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
function parseIso(s){const m=String(s||'').match(/(20\d{2})-(\d{2})-(\d{2})/);if(!m)return null;return new Date(Number(m[1]),Number(m[2])-1,Number(m[3]));}
function allDates(text){
  const out=[];const seen=new Set();const now=new Date();
  for(const m of String(text||'').matchAll(/\b(20\d{2})-(\d{2})-(\d{2})\b/g)){const d=new Date(Number(m[1]),Number(m[2])-1,Number(m[3]));const k=isoDate(d);if(k&&!seen.has(k)){seen.add(k);out.push(d);}}
  const months=Object.keys(MONTHS).join('|');const re=new RegExp(`\\b(\\d{1,2})\\s+(${months})(?:\\s+(20\\d{2}))?\\b`,'gi');
  for(const m of String(text||'').matchAll(re)){const year=m[3]?Number(m[3]):now.getFullYear();const d=new Date(year,MONTHS[m[2].toLowerCase()],Number(m[1]));const k=isoDate(d);if(k&&!seen.has(k)){seen.add(k);out.push(d);}}
  return out.filter(d=>!Number.isNaN(d.getTime()));
}
function domReferenceDate(el,spec){
  const text=(el?.innerText||'').replace(/\s+/g,' ').trim();
  if(spec.kind==='overview'){const m=text.match(/ULTIMO\s+DATO\s+GLOBALE\s+(20\d{2}-\d{2}-\d{2})/i);if(m)return parseIso(m[1]);}
  const ds=allDates(text);if(!ds.length)return null;return ds.sort((a,b)=>b-a)[0];
}
function riskLaneCoverage(){
  const r=operational.risk;
  const raw={VIX:r?.vix_valid===true?r.vix_date:null,WTI:r?.wti_valid===true?r.wti_date:null,BRENT:r?.brent_date||null};
  const entries=Object.entries(raw).map(([lane,value])=>({lane,date:parseIso(value)}));
  const missing=entries.filter(x=>!x.date).map(x=>x.lane);
  // ALL three visible cards require explicit as-of. A recent secondary Brent
  // quote cannot rescue older or unavailable official VIX/WTI observations.
  if(missing.length)return {date:null,oldest_lane:null,missing_lanes:missing,as_of_by_lane:raw};
  entries.sort((a,b)=>a.date-b.date);
  return {date:entries[0].date,oldest_lane:entries[0].lane,missing_lanes:[],as_of_by_lane:raw};
}
function operationalReference(spec){
  if(spec.kind==='calendar'){
    const x=operational.calendar;if(!x)return {date:null,authority:state.authority.calendar,status:'UNAVAILABLE'};
    return {date:parseIso(x.generated_at_utc),authority:state.authority.calendar,status:x.status||null,schema:x.schema||null};
  }
  if(spec.kind==='news'){
    const x=operational.news;if(!x)return {date:null,authority:'NEWS_PULSE_OPERATIONAL.content_as_of',status:'UNAVAILABLE'};
    return {date:parseIso(x.content_as_of),authority:'NEWS_PULSE_OPERATIONAL.content_as_of',status:x.status||null,schema:x.schema||null};
  }
  if(spec.kind==='risk'){
    const x=operational.risk;if(!x)return {date:null,authority:state.authority.risk,status:'UNAVAILABLE'};
    const coverage=riskLaneCoverage();
    return {date:coverage.date,authority:state.authority.risk,status:coverage.missing_lanes.length?'INCOMPLETE_RISK_LANES':(x.status||null),schema:'GMFQ_RISK_FRESHNESS_AUTHORITY_V2',...coverage};
  }
  return null;
}
function ensureStyle(){
  if(document.getElementById('gmfq-editorial-freshness-style'))return;
  const s=document.createElement('style');s.id='gmfq-editorial-freshness-style';s.textContent=`
    .gmfqEditorialFreshnessBanner{margin:0 0 12px;border:1px solid rgba(242,187,73,.55);background:rgba(242,187,73,.08);border-radius:10px;padding:10px 12px;color:#f5d27c;font:600 11px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
    .gmfqEditorialFreshnessBanner b{display:block;color:#ffd86a;font-size:11px;letter-spacing:.04em;margin-bottom:3px}
    .gmfqEditorialFreshnessBanner[data-status="UNVERIFIED"]{border-color:rgba(255,111,126,.55);background:rgba(255,111,126,.07);color:#ffb3bd}
  `;document.head.appendChild(s);
}
function bannerText(spec,result){
  if(result.status==='STALE'){
    if(spec.kind==='calendar')return `${spec.label} NON CORRENTE · build operativa ${result.reference_date}. La sezione resta visibile come archivio, ma non va usata come calendario operativo di oggi.`;
    if(spec.kind==='news')return `${spec.label} NON CORRENTE · ultimo segnale validato ${result.reference_date}. La sintesi resta visibile, ma non rappresenta più il contesto corrente.`;
    if(spec.kind==='risk')return `${spec.label} NON CORRENTE · il dato più vecchio è ${result.oldest_lane||'una fonte richiesta'} (${result.reference_date}). I valori restano visibili con le rispettive date, ma l'insieme non è uno snapshot corrente.`;
    return `${spec.label} NON CORRENTE · riferimento globale ${result.reference_date}. I layer live/certificati restano validi, ma questa sintesi editoriale non va letta come aggiornata a oggi.`;
  }
  if(result.status==='UNVERIFIED')return spec.kind==='risk'&&result.missing_risk_lanes?.length
    ? `${spec.label} · as-of mancante per ${result.missing_risk_lanes.join(', ')}. Nessun dato secondario può certificare l'intero monitor.`
    : `${spec.label} · freshness operativa non verificabile. La sezione resta fail-closed finché la fonte operativa non è disponibile.`;
  return '';
}
function applyOne(id,spec){
  const el=document.getElementById(id);if(!el)return {status:'MISSING_VIEW',reference_date:null,age_days:null,authority:null};
  let ref=null,authority='VISIBLE_DOM_EXPLICIT_ASOF',sourceStatus=null,sourceSchema=null,sourceDetail=null;
  if(['calendar','news','risk'].includes(spec.kind)){
    if(!operational.loaded){el.dataset.gmfqEditorialFreshness='PENDING_OPERATIONAL';return {status:'PENDING_OPERATIONAL',reference_date:null,age_days:null,max_age_days:spec.maxAgeDays,authority:state.authority[id]};}
    const op=operationalReference(spec);ref=op.date;authority=op.authority;sourceStatus=op.status;sourceSchema=op.schema;sourceDetail=op;
  }else ref=domReferenceDate(el,spec);
  const today=dayFloor(new Date());let status='UNVERIFIED',age=null;
  if(ref){age=Math.floor((today-dayFloor(ref))/86400000);status=age>spec.maxAgeDays?'STALE':'FRESH';}
  const result={status,reference_date:isoDate(ref),age_days:age,max_age_days:spec.maxAgeDays,authority,source_status:sourceStatus,source_schema:sourceSchema};
  if(spec.kind==='risk'&&sourceDetail){
    result.oldest_lane=sourceDetail.oldest_lane;
    result.missing_risk_lanes=sourceDetail.missing_lanes;
    result.risk_as_of_by_lane=sourceDetail.as_of_by_lane;
  }
  el.dataset.gmfqEditorialFreshness=status;el.dataset.gmfqFreshnessAuthority=authority;
  let banner=el.querySelector(':scope > .gmfqEditorialFreshnessBanner');
  if(status==='FRESH'||status==='PENDING_OPERATIONAL'){if(banner)banner.remove();}
  else{if(!banner){banner=document.createElement('div');banner.className='gmfqEditorialFreshnessBanner';el.prepend(banner);}banner.dataset.status=status;const txt=bannerText(spec,result);if(banner.textContent!==txt)banner.innerHTML=`<b>${status==='STALE'?'FRESHNESS FAIL-CLOSED':'FRESHNESS OPERATIVA NON VERIFICABILE'}</b>${txt}`;}
  return result;
}
function apply(){
  ensureStyle();const sections={};for(const [id,spec] of Object.entries(SPECS))sections[id]=applyOne(id,spec);
  state.sections=sections;state.evaluated_at=new Date().toISOString();state.operational_loaded=operational.loaded;state.operational_errors=[...operational.errors];
  const vals=Object.values(sections);state.status=vals.some(x=>x.status==='MISSING_VIEW')?'ERROR':vals.some(x=>x.status==='PENDING_OPERATIONAL')?'LOADING_OPERATIONAL':vals.some(x=>x.status==='UNVERIFIED')?'PASS_WITH_UNVERIFIED':vals.some(x=>x.status==='STALE')?'PASS_FAIL_CLOSED_STALE':'PASS_FRESH';return state;
}
let queued=false;function queue(){if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;apply();});}
async function loadOperationalAuthority(){
  operational.errors=[];
  const specs=[
    ['calendar','live_data/sections/CALENDAR_OPERATIONAL_VIEW.json'],
    ['news','live_data/sections/NEWS_PULSE_OPERATIONAL.json'],
    ['d','live_data/sections/D.json'],
    ['residual','live_data/sections/ESTIMATED_RESIDUAL_GAPS.json']
  ];
  const data={};const settled=await Promise.allSettled(specs.map(async([key,url])=>{const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error(`${key}:${r.status}`);data[key]=await r.json();}));
  settled.forEach((x,i)=>{if(x.status==='rejected')operational.errors.push(`${specs[i][0]}:${String(x.reason?.message||x.reason)}`);});
  operational.calendar=data.calendar||null;operational.news=data.news||null;
  const vix=data.d?.risk?.VIX||{},wti=data.d?.risk?.WTI||{},brent=data.residual?.lanes?.['BRENT.market_proxy']||{};
  const validRisk=(x)=>Array.isArray(x?.dates)&&Array.isArray(x?.values)&&x.dates.length>0&&
    x.dates.length===x.values.length&&x.last_date===x.dates.at(-1)&&
    x.last_value!==null&&x.last_value!==undefined&&x.last_value!==''&&
    x.values.at(-1)!==null&&x.values.at(-1)!==undefined&&x.values.at(-1)!==''&&
    Number.isFinite(Number(x.last_value))&&Number.isFinite(Number(x.values.at(-1)))&&
    Number(x.last_value)===Number(x.values.at(-1));
  operational.risk=(data.d||data.residual)?{status:'ACTIVE_IF_ANY_SOURCE',
    vix_date:vix.last_date||null,vix_valid:validRisk(vix)&&Number(vix.last_value)>0,
    wti_date:wti.last_date||null,wti_valid:validRisk(wti),
    brent_date:brent.proxy_as_of||null}:null;
  operational.loaded=true;apply();
}
const prev=window.showView;if(typeof prev==='function')window.showView=function(){const out=prev.apply(this,arguments);setTimeout(queue,0);return out;};
function boot(){apply();new MutationObserver(queue).observe(document.body,{childList:true,subtree:true});loadOperationalAuthority().catch(e=>{operational.loaded=true;operational.errors.push(String(e?.message||e));apply();});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
window.gmfqEditorialFreshnessAudit=()=>JSON.parse(JSON.stringify(apply()));
})();