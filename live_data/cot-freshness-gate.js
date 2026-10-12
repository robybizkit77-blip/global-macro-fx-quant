(function(){
'use strict';

const MAX_CALENDAR_LAG_DAYS=10;
const FRESHNESS_TIME_ZONE='Europe/Rome';
const MAX_READY_ATTEMPTS=80;
const READY_RETRY_MS=50;
const clone=x=>{try{return JSON.parse(JSON.stringify(x))}catch{return null}};

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

function cotAsOf(){
  return window.PRODUCTION_PRICE_COT_LIQ_AUDIT?.cot?.current_as_of || window.FINAL_SOURCE_POLICY_AUDIT?.COT?.current_as_of || null;
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
  if(state.status==='PASS_WITHHELD_STALE_COT'){
    el.textContent=`COT WITHHELD PER FRESHNESS · ultimo snapshot ${state.cot_asof||'—'} · ${state.calendar_lag_days??'—'} giorni di calendario. Percentili e Net/OI restano visibili come storico, ma warning ed estremi non sono trattati come contesto operativo corrente.`;
    el.hidden=false;
  }else if(state.status==='PASS_FRESH_COT_UNCHANGED'){
    el.hidden=true;
  }else{
    el.textContent='COT WITHHELD · freshness/provenienza non certificabile. Dati non usati come warning operativo.';
    el.hidden=false;
  }
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
    if((!asOf||!currencyReady)&&attempt<MAX_READY_ATTEMPTS){
      window.__GMFQ_COT_FRESHNESS_GATE_STATE=Object.freeze({...state,status:'WAITING_FOR_COT_PROVENANCE',reason:!asOf?'COT provenance not ready yet':'currency state consumer not ready yet'});
      setTimeout(()=>install(attempt+1),READY_RETRY_MS);
      return;
    }
    const reference=currentRomeDate();
    if(!asOf||!currencyReady){
      state.status='WITHHELD_PROVENANCE_UNAVAILABLE';
      state.reason=!asOf?'COT provenance unavailable after bounded wait':'currency state consumer unavailable after bounded wait';
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

    const ccys=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
    const currencies=Object.fromEntries(ccys.map(c=>[c,clone(window.deriveCurrencyState(c))]));
    state.status=stale?'PASS_WITHHELD_STALE_COT':'PASS_FRESH_COT_UNCHANGED';
    state.reason=stale?'Canonical weekly COT exceeds allowed calendar lag; warning/context outputs suppressed while raw historical COT remains visible.':'Canonical weekly COT is within freshness window.';
    state.cot_asof=asOf;
    state.reference_asof=reference;
    state.calendar_lag_days=lag;
    state.currency_cot_risk_nonempty=ccys.filter(c=>String(currencies[c]?.cotRisk||'').trim()).length;
    state.raw_cot_currency_count=Object.keys(window.D?.cot||{}).length;
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
