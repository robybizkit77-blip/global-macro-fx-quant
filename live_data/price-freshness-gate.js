(function(){
'use strict';

const MAX_BUSINESS_LAG=1;
const FRESHNESS_TIME_ZONE='Europe/Rome';
const MAX_READY_ATTEMPTS=80;
const READY_RETRY_MS=50;
const clone=x=>{try{return JSON.parse(JSON.stringify(x))}catch{return null}};

function businessLag(from,to){
  if(!from||!to) return null;
  const a=new Date(String(from).slice(0,10)+'T12:00:00Z');
  const b=new Date(String(to).slice(0,10)+'T12:00:00Z');
  if(!Number.isFinite(a.getTime())||!Number.isFinite(b.getTime())) return null;
  if(!(a<b)) return 0;
  let d=new Date(a),n=0;
  while(d<b){
    d.setUTCDate(d.getUTCDate()+1);
    const wd=d.getUTCDay();
    if(wd!==0&&wd!==6)n++;
  }
  return n;
}

function currentRomeDate(){
  try{
    const parts=new Intl.DateTimeFormat('en-GB',{
      timeZone:FRESHNESS_TIME_ZONE,
      year:'numeric',month:'2-digit',day:'2-digit'
    }).formatToParts(new Date());
    const map=Object.fromEntries(parts.filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
    if(map.year&&map.month&&map.day) return `${map.year}-${map.month}-${map.day}`;
  }catch(e){}
  return new Date().toISOString().slice(0,10);
}

function priceAsOf(){
  return window.GMFQ_ECB_PRICE_AUDIT?.as_of || window.D?.prices?.at?.(-1)?.Date || null;
}

function publishState(state){
  window.__GMFQ_PRICE_FRESHNESS_GATE_STATE=Object.freeze(state);
  window.dispatchEvent(new CustomEvent('gmfq:price-freshness-ready',{detail:window.__GMFQ_PRICE_FRESHNESS_GATE_STATE}));
}

function install(attempt){
  const state={
    status:'WITHHELD_NO_APPLY',
    max_business_lag:MAX_BUSINESS_LAG,
    freshness_time_zone:FRESHNESS_TIME_ZONE,
    changes_engine:false,
    changes_bias:false,
    changes_sizing:false,
    changes_pair_structure:false,
    underlying_price_data_mutated:false,
    provenance_wait_attempts:attempt
  };
  try{
    const asOf=priceAsOf();
    const consumersReady=typeof window.deriveCurrencyState==='function'&&typeof window.derivePairDecisionFrame==='function';
    if((!asOf||!consumersReady)&&attempt<MAX_READY_ATTEMPTS){
      window.__GMFQ_PRICE_FRESHNESS_GATE_STATE=Object.freeze({...state,status:'WAITING_FOR_PRICE_PROVENANCE',reason:!asOf?'Price provenance not ready yet':'Price consumers not ready yet'});
      setTimeout(()=>install(attempt+1),READY_RETRY_MS);
      return;
    }
    if(!asOf||!consumersReady){
      state.status='WITHHELD_PROVENANCE_UNAVAILABLE';
      state.reason=!asOf?'Price provenance unavailable after bounded wait':'Price consumers unavailable after bounded wait';
      state.price_asof=asOf;
      state.reference_asof=currentRomeDate();
      state.business_lag=null;
      publishState(state);
      return;
    }

    const originalCurrency=window.deriveCurrencyState;
    const originalPair=window.derivePairDecisionFrame;
    if(originalCurrency.__gmfqPriceFreshnessGuard===true||originalPair.__gmfqPriceFreshnessGuard===true){
      state.status='NO_APPLY_ALREADY_INSTALLED';
      state.reason='price freshness guard already installed';
      state.price_asof=asOf;
      state.reference_asof=currentRomeDate();
      state.business_lag=businessLag(asOf,state.reference_asof);
      publishState(state);
      return;
    }

    const reference=currentRomeDate();
    const lag=businessLag(asOf,reference);
    const stale=lag==null || lag>MAX_BUSINESS_LAG;
    const staleNote=`Price WITHHELD: fixing G8 canonico ${asOf} non abbastanza recente rispetto alla data corrente ${reference} (${FRESHNESS_TIME_ZONE}).`;

    const guardedCurrency=function(c){
      const base=originalCurrency(c);
      if(!stale||!base) return base;
      const out=clone(base)||{...base};
      out.price=0;
      out.confirmation='PREZZO NON RISOLUTIVO';
      out.priceFreshness={status:'WITHHELD_STALE',as_of:asOf,reference_as_of:reference,business_lag:lag,max_business_lag:MAX_BUSINESS_LAG,time_zone:FRESHNESS_TIME_ZONE};
      if(typeof out.story==='string'){
        out.story=out.story
          .replace(/ · il prezzo diverge dalla struttura/g,' · prezzo withheld per freshness')
          .replace(/ · il prezzo conferma la struttura/g,' · prezzo withheld per freshness')
          .replace(/ · il prezzo non dà ancora una conferma risolutiva/g,' · prezzo withheld per freshness')
          .replace(/ · Prezzo è in ritardo/g,' · prezzo withheld per freshness');
      }
      return out;
    };

    const guardedPair=function(pair){
      const base=originalPair(pair);
      if(!stale||!base) return base;
      const out=clone(base)||{...base};
      out.priceReading='PREZZO NON RISOLUTIVO';
      out.priceNote=staleNote;
      out.watch=staleNote+' Il Price resta solo una verifica e non modifica la struttura Macro + Tassi/CB.';
      out.priceFreshness={status:'WITHHELD_STALE',as_of:asOf,reference_as_of:reference,business_lag:lag,max_business_lag:MAX_BUSINESS_LAG,time_zone:FRESHNESS_TIME_ZONE};
      return out;
    };

    guardedCurrency.__gmfqPriceFreshnessGuard=true;
    guardedCurrency.__gmfqOriginal=originalCurrency;
    guardedPair.__gmfqPriceFreshnessGuard=true;
    guardedPair.__gmfqOriginal=originalPair;

    window.deriveCurrencyState=guardedCurrency;
    window.derivePairDecisionFrame=guardedPair;
    try{deriveCurrencyState=guardedCurrency}catch(e){}
    try{derivePairDecisionFrame=guardedPair}catch(e){}

    const ccys=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
    const pairs=[];
    for(let i=0;i<ccys.length;i++) for(let j=i+1;j<ccys.length;j++) pairs.push(`${ccys[i]}/${ccys[j]}`);
    const currencies=Object.fromEntries(ccys.map(c=>[c,clone(window.deriveCurrencyState(c))]));
    const pairFrames=Object.fromEntries(pairs.map(p=>[p,clone(window.derivePairDecisionFrame(p))]));

    state.status=stale?'PASS_WITHHELD_STALE_PRICE':'PASS_FRESH_PRICE_UNCHANGED';
    state.reason=stale?'Canonical daily G8 Price exceeds certified freshness lag versus current Europe/Rome date; confirmation/divergence suppressed while underlying history remains visible.':'Canonical daily G8 Price is within certified freshness lag.';
    state.price_asof=asOf;
    state.reference_asof=reference;
    state.business_lag=lag;
    state.currency_confirmation_counts=ccys.reduce((acc,c)=>{const x=currencies[c]?.confirmation||'NULL';acc[x]=(acc[x]||0)+1;return acc;},{});
    state.pair_price_reading_counts=pairs.reduce((acc,p)=>{const x=pairFrames[p]?.priceReading||'NULL';acc[x]=(acc[x]||0)+1;return acc;},{});
    publishState(state);
  }catch(e){
    state.reason=String(e&&e.message||e);
    publishState(state);
    console.error('price-freshness-gate',e);
  }
}

install(0);
})();
