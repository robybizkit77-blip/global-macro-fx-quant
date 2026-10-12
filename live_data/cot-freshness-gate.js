(function(){
'use strict';

const MAX_CALENDAR_LAG_DAYS=10;
const FRESHNESS_TIME_ZONE='Europe/Rome';
const MAX_READY_ATTEMPTS=80;
const READY_RETRY_MS=50;
const COT_CANONICAL_PATH='live_data/sections/V250_COT_CHART_DATA.json';
const COT_CCYS=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const clone=x=>{try{return JSON.parse(JSON.stringify(x))}catch{return null}};

let canonicalCotStatus='LOADING';
let canonicalCotAsOf=null;
let canonicalCotError=null;
let canonicalCotDates=null;

(async()=>{
  try{
    const r=await fetch(COT_CANONICAL_PATH,{cache:'no-store'});
    if(!r.ok)throw new Error(`canonical-cot-http-${r.status}`);
    const data=await r.json();
    const per={};
    for(const c of COT_CCYS){
      const dates=data?.[c]?.dates;
      if(!Array.isArray(dates)||!dates.length)throw new Error(`canonical-cot-missing-dates:${c}`);
      const latest=String(dates[dates.length-1]||'');
      if(!/^\d{4}-\d{2}-\d{2}$/.test(latest))throw new Error(`canonical-cot-invalid-date:${c}:${latest}`);
      per[c]=latest;
    }
    const unique=[...new Set(Object.values(per))];
    if(unique.length!==1)throw new Error(`canonical-cot-cross-g8-date-mismatch:${JSON.stringify(per)}`);
    canonicalCotDates=Object.freeze({...per});
    canonicalCotAsOf=unique[0];
    canonicalCotStatus='PASS';
  }catch(e){
    canonicalCotStatus='FAILED';
    canonicalCotError=String(e&&e.message||e);
  }
})();

function currentRomeDate(){
  try{
    const parts=new Intl.DateTimeFormat('en-GB',{timeZone:FRESHNESS_TIME_ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const map=Object.fromEntries(parts.filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
    if(map.year&&map.month&&map.day)return `${map.year}-${map.month}-${map.day}`;
  }catch(e){}
  return new Date().toISOString().slice(0,10);
}

function calendarLag(from,to){
  if(!from||!to)return null;
  const a=new Date(String(from).slice(0,10)+'T12:00:00Z');
  const b=new Date(String(to).slice(0,10)+'T12:00:00Z');
  if(!Number.isFinite(a.getTime())||!Number.isFinite(b.getTime()))return null;
  return Math.max(0,Math.round((b-a)/86400000));
}

function legacyCotAsOf(){
  return window.PRODUCTION_PRICE_COT_LIQ_AUDIT?.cot?.current_as_of || window.FINAL_SOURCE_POLICY_AUDIT?.COT?.current_as_of || null;
}

function cotAsOf(){
  return canonicalCotStatus==='PASS'?canonicalCotAsOf:null;
}

function priceGateTerminal(){
  const s=window.__GMFQ_PRICE_FRESHNESS_GATE_STATE?.status;
  return !!s && s!=='WAITING_FOR_PRICE_PROVENANCE';
}

function stripCotStory(story){
  if(typeof story!=='string')return story;
  const kept=story.split(' · ').filter(x=>{
    const t=x.toLowerCase().replace(/[.]+$/,'').trim();
    if(t.includes('estremo cot'))return false;
    if(t.includes('candidato p70'))return false;
    if(t.includes('early warning sul posizionamento'))return false;
    if(t.includes('concentrazione short net/oi'))return false;
    if(t.includes('concentrazione long net/oi'))return false;
    if(/^p\d+(\s|$)/.test(t))return false;
    return true;
  });
  if(!kept.some(x=>x.toLowerCase().includes('cot withheld per freshness')))kept.push('COT withheld per freshness');
  return kept.join(' · ').replace(/\.+$/,'')+'.';
}

function installBanner(state){
  const host=document.querySelector('#cot');
  if(!host)return;
  let el=document.getElementById('gmfqCotFreshnessBanner');
  if(!el){
    el=document.createElement('div');
    el.id='gmfqCotFreshnessBanner';
    el.style.cssText='margin:12px 0 16px;padding:12px 14px;border:1px solid rgba(245,158,11,.42);border-radius:10px;background:rgba(245,158,11,.08);font:600 12px/1.45 system-ui;color:inherit;';
    host.insertBefore(el,host.firstChild);
  }
  let nextText='',nextHidden=false;
  if(state.status==='PASS_WITHHELD_STALE_COT'){
    nextText=`COT WITHHELD PER FRESHNESS · ultimo snapshot ${state.cot_asof||'—'} · ${state.calendar_lag_days??'—'} giorni di calendario. Percentili e Net/OI restano visibili come storico, ma warning ed estremi non sono trattati come contesto operativo corrente.`;
  }else if(state.status==='PASS_FRESH_COT_UNCHANGED'){
    nextHidden=true;
  }else{
    nextText='COT WITHHELD · freshness/provenienza non certificabile. Dati non usati come warning operativo.';
  }
  if(el.textContent!==nextText)el.textContent=nextText;
  if(el.hidden!==nextHidden)el.hidden=nextHidden;
}

function publishState(state){
  window.__GMFQ_COT_FRESHNESS_GATE_STATE=Object.freeze(state);
  try{installBanner(state)}catch(e){}
  window.dispatchEvent(new CustomEvent('gmfq:cot-freshness-ready',{detail:window.__GMFQ_COT_FRESHNESS_GATE_STATE}));
}

function install(attempt){
  const state={
    status:'WITHHELD_NO_APPLY',
    max_calendar_lag_days:MAX_CALENDAR_LAG_DAYS,
    freshness_time_zone:FRESHNESS_TIME_ZONE,
    provenance_source:'V250_COT_CHART_DATA',
    canonical_dataset_path:COT_CANONICAL_PATH,
    canonical_dataset_status:canonicalCotStatus,
    canonical_dataset_asof:canonicalCotAsOf,
    canonical_dataset_dates:canonicalCotDates,
    legacy_provenance_asof:legacyCotAsOf(),
    provenance_mismatch:!!(canonicalCotAsOf&&legacyCotAsOf()&&canonicalCotAsOf!==legacyCotAsOf()),
    changes_engine:false,
    changes_bias:false,
    changes_sizing:false,
    changes_pair_structure:false,
    underlying_cot_data_mutated:false,
    provenance_wait_attempts:attempt
  };
  try{
    const asOf=cotAsOf();
    const currencyReady=typeof window.deriveCurrencyState==='function';
    const priceReady=priceGateTerminal();
    if((canonicalCotStatus==='LOADING'||!currencyReady||!priceReady)&&attempt<MAX_READY_ATTEMPTS){
      let reason=canonicalCotStatus==='LOADING'?'Canonical COT dataset not ready yet':'COT consumer dependency not ready yet';
      if(canonicalCotStatus==='PASS'&&!priceReady)reason='Price freshness gate not terminal yet';
      else if(canonicalCotStatus==='PASS'&&priceReady&&!currencyReady)reason='currency state consumer not ready yet';
      window.__GMFQ_COT_FRESHNESS_GATE_STATE=Object.freeze({...state,status:'WAITING_FOR_COT_PROVENANCE',reason});
      setTimeout(()=>install(attempt+1),READY_RETRY_MS);
      return;
    }
    const reference=currentRomeDate();
    if(canonicalCotStatus!=='PASS'||!asOf||!currencyReady||!priceReady){
      state.status='WITHHELD_PROVENANCE_UNAVAILABLE';
      state.reason=canonicalCotStatus!=='PASS'?`Canonical COT dataset unavailable: ${canonicalCotError||canonicalCotStatus}`:(!asOf?'Canonical COT as-of unavailable':(!priceReady?'Price freshness dependency unavailable after bounded wait':'currency state consumer unavailable after bounded wait'));
      state.cot_asof=asOf;
      state.reference_asof=reference;
      state.calendar_lag_days=null;
      publishState(state);
      return;
    }
    if(String(asOf)>String(reference)){
      state.status='WITHHELD_PROVENANCE_UNAVAILABLE';
      state.reason=`Canonical COT as-of ${asOf} is later than reference date ${reference}`;
      state.cot_asof=asOf;
      state.reference_asof=reference;
      state.calendar_lag_days=null;
      publishState(state);
      return;
    }

    const originalCurrency=window.deriveCurrencyState;
    if(originalCurrency.__gmfqCotFreshnessGuard===true){
      state.status='NO_APPLY_ALREADY_INSTALLED';
      state.reason='COT freshness guard already installed';
      state.cot_asof=asOf;
      state.reference_asof=reference;
      state.calendar_lag_days=calendarLag(asOf,reference);
      publishState(state);
      return;
    }

    const lag=calendarLag(asOf,reference);
    const stale=lag==null||lag>MAX_CALENDAR_LAG_DAYS;
    const guardedCurrency=function(c){
      const base=originalCurrency(c);
      if(!stale||!base)return base;
      const out=clone(base)||{...base};
      out.cotRisk='';
      out.cotFreshness={status:'WITHHELD_STALE',as_of:asOf,reference_as_of:reference,calendar_lag_days:lag,max_calendar_lag_days:MAX_CALENDAR_LAG_DAYS,time_zone:FRESHNESS_TIME_ZONE};
      out.story=stripCotStory(out.story);
      return out;
    };
    guardedCurrency.__gmfqCotFreshnessGuard=true;
    guardedCurrency.__gmfqOriginal=originalCurrency;
    window.deriveCurrencyState=guardedCurrency;
    try{deriveCurrencyState=guardedCurrency}catch(e){}

    const wrapName=(name,wrapper)=>{
      const fn=window[name];
      if(typeof fn!=='function'||fn.__gmfqCotFreshnessGuard===true)return;
      const wrapped=wrapper(fn);
      wrapped.__gmfqCotFreshnessGuard=true;
      wrapped.__gmfqOriginal=fn;
      window[name]=wrapped;
      try{eval(`${name}=window[${JSON.stringify(name)}]`)}catch(e){}
    };

    if(stale){
      wrapName('cotEarlyWarning',original=>function(){return `COT WITHHELD · snapshot ${asOf} non abbastanza recente`;});
      wrapName('v224CotSummary',original=>function(){return {text:`COT WITHHELD per freshness · ultimo snapshot ${asOf}. Posizionamento visibile solo come storico; nessun warning operativo.`,cls:'neu'};});
      wrapName('v228CotRow',original=>function(){return {side:'WITHHELD',text:`COT ${asOf} stale rispetto a ${reference}: overlay di posizionamento non operativo e non modifica la struttura.`,cls:'neu'};});
      wrapName('v315CotRiskClass',original=>function(){return 'neu';});
      wrapName('cotHeatState',original=>function(c){const x=original(c)||{};return {...x,txt:x.txt?`${x.txt} · STALE`:'STALE',cls:'neu',ext:false};});
    }

    const currencies=Object.fromEntries(COT_CCYS.map(c=>[c,clone(window.deriveCurrencyState(c))]));
    state.status=stale?'PASS_WITHHELD_STALE_COT':'PASS_FRESH_COT_UNCHANGED';
    state.reason=stale?'Canonical weekly COT exceeds allowed calendar lag; warning/context outputs suppressed while raw historical COT remains visible.':'Canonical weekly COT is within freshness window.';
    state.cot_asof=asOf;
    state.reference_asof=reference;
    state.calendar_lag_days=lag;
    state.currency_cot_risk_nonempty=COT_CCYS.filter(c=>String(currencies[c]?.cotRisk||'').trim()).length;
    state.price_dependency_status=window.__GMFQ_PRICE_FRESHNESS_GATE_STATE?.status||null;
    publishState(state);

    const observer=new MutationObserver(()=>{try{installBanner(window.__GMFQ_COT_FRESHNESS_GATE_STATE)}catch(e){}});
    observer.observe(document.documentElement,{childList:true,subtree:true});
  }catch(e){
    state.reason=String(e&&e.message||e);
    publishState(state);
    console.error('cot-freshness-gate',e);
  }
}

install(0);
})();
