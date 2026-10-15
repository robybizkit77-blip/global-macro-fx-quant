(()=>{
'use strict';
const MONTHS={gennaio:0,febbraio:1,marzo:2,aprile:3,maggio:4,giugno:5,luglio:6,agosto:7,settembre:8,ottobre:9,novembre:10,dicembre:11};
const SPECS={
  overview:{maxAgeDays:7,label:'OVERVIEW',kind:'overview'},
  calendar:{maxAgeDays:1,label:'CALENDARIO',kind:'calendar'},
  news:{maxAgeDays:2,label:'NEWS PULSE',kind:'news'}
};
const state={schema:'GMFQ_EDITORIAL_FRESHNESS_GUARD_V1',status:'INIT',sections:{},evaluated_at:null};
window.GMFQ_EDITORIAL_FRESHNESS=state;

function dayFloor(d){return new Date(d.getFullYear(),d.getMonth(),d.getDate());}
function isoDate(d){if(!(d instanceof Date)||Number.isNaN(d.getTime()))return null;return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
function parseIso(s){const m=String(s||'').match(/\b(20\d{2})-(\d{2})-(\d{2})\b/);if(!m)return null;return new Date(Number(m[1]),Number(m[2])-1,Number(m[3]));}
function allDates(text){
  const out=[];const seen=new Set();const now=new Date();
  for(const m of String(text||'').matchAll(/\b(20\d{2})-(\d{2})-(\d{2})\b/g)){
    const d=new Date(Number(m[1]),Number(m[2])-1,Number(m[3]));const k=isoDate(d);if(k&&!seen.has(k)){seen.add(k);out.push(d);}
  }
  const months=Object.keys(MONTHS).join('|');
  const re=new RegExp(`\\b(\\d{1,2})\\s+(${months})(?:\\s+(20\\d{2}))?\\b`,'gi');
  for(const m of String(text||'').matchAll(re)){
    const year=m[3]?Number(m[3]):now.getFullYear();
    const d=new Date(year,MONTHS[m[2].toLowerCase()],Number(m[1]));const k=isoDate(d);if(k&&!seen.has(k)){seen.add(k);out.push(d);}
  }
  return out.filter(d=>!Number.isNaN(d.getTime()));
}
function referenceDate(el,spec){
  const text=(el?.innerText||'').replace(/\s+/g,' ').trim();
  if(spec.kind==='overview'){
    const m=text.match(/ULTIMO\s+DATO\s+GLOBALE\s+(20\d{2}-\d{2}-\d{2})/i);
    if(m)return parseIso(m[1]);
  }
  const ds=allDates(text);
  if(!ds.length)return null;
  return ds.sort((a,b)=>b-a)[0];
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
    if(spec.kind==='calendar') return `${spec.label} NON CORRENTE · ultimo giorno riconosciuto ${result.reference_date}. La sezione resta visibile come archivio, ma non va usata come calendario operativo di oggi.`;
    if(spec.kind==='news') return `${spec.label} NON CORRENTE · ultimo riferimento riconosciuto ${result.reference_date}. Le voci sotto sono uno snapshot storico, non “ultime 24 ore”.`;
    return `${spec.label} NON CORRENTE · riferimento globale ${result.reference_date}. I layer live/certificati restano validi, ma questa sintesi editoriale non va letta come aggiornata a oggi.`;
  }
  return `${spec.label} · freshness non verificabile automaticamente. Trattare la sezione come contesto finché non viene fornito un as-of esplicito.`;
}
function applyOne(id,spec){
  const el=document.getElementById(id);
  if(!el)return {status:'MISSING_VIEW',reference_date:null,age_days:null};
  const ref=referenceDate(el,spec);const today=dayFloor(new Date());
  let status='UNVERIFIED',age=null;
  if(ref){age=Math.floor((today-dayFloor(ref))/86400000);status=age>spec.maxAgeDays?'STALE':'FRESH';}
  const result={status,reference_date:isoDate(ref),age_days:age,max_age_days:spec.maxAgeDays};
  el.dataset.gmfqEditorialFreshness=status;
  let banner=el.querySelector(':scope > .gmfqEditorialFreshnessBanner');
  if(status==='FRESH'){
    if(banner)banner.remove();
  }else{
    if(!banner){banner=document.createElement('div');banner.className='gmfqEditorialFreshnessBanner';el.prepend(banner);}
    banner.dataset.status=status;
    const txt=bannerText(spec,result);
    if(banner.textContent!==txt){banner.innerHTML=`<b>${status==='STALE'?'FRESHNESS FAIL-CLOSED':'FRESHNESS NON VERIFICABILE'}</b>${txt}`;}
  }
  return result;
}
function apply(){
  ensureStyle();
  const sections={};for(const [id,spec] of Object.entries(SPECS))sections[id]=applyOne(id,spec);
  state.sections=sections;state.evaluated_at=new Date().toISOString();
  const vals=Object.values(sections);
  state.status=vals.some(x=>x.status==='MISSING_VIEW')?'ERROR':vals.some(x=>x.status==='UNVERIFIED')?'PASS_WITH_UNVERIFIED':vals.some(x=>x.status==='STALE')?'PASS_FAIL_CLOSED_STALE':'PASS_FRESH';
  return state;
}
let queued=false;
function queue(){if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;apply();});}
const prev=window.showView;if(typeof prev==='function')window.showView=function(){const out=prev.apply(this,arguments);setTimeout(queue,0);return out;};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{apply();new MutationObserver(queue).observe(document.body,{childList:true,subtree:true});},{once:true});
else{apply();new MutationObserver(queue).observe(document.body,{childList:true,subtree:true});}
window.gmfqEditorialFreshnessAudit=()=>JSON.parse(JSON.stringify(apply()));
})();