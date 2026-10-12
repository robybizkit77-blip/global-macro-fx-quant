(function(){
'use strict';

const MAX_BUSINESS_LAG=1;
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

function productionDate(){
  try{
    if(typeof window.currentProductionBusinessDate==='function'){
      const x=window.currentProductionBusinessDate();
      if(x) return String(x).slice(0,10);
    }
  }catch(e){}
  try{
    if(typeof currentProductionBusinessDate==='function'){
      const x=currentProductionBusinessDate();
      if(x) return String(x).slice(0,10);
    }
  }catch(e){}
  const last=window.LAST_DAILY_CLOSEOUT?.date;
  if(last) return String(last).slice(0,10);
  return new Date().toISOString().slice(0,10);
}

function priceAsOf(){
  return window.GMFQ_ECB_PRICE_AUDIT?.as_of || window.D?.prices?.at?.(-1)?.Date || null;
}

function install(){
  const state={
    status:'WITHHELD_NO_APPLY',
    max_business_lag:MAX_BUSINESS_LAG,
    changes_engine:false,
    changes_bias:false,
    changes_sizing:false,
    changes_pair_structure:false,
    underlying_price_data_mutated:false
  };
  try{
    if(typeof window.deriveCurrencyState!=='function'||typeof window.derivePairDecisionFrame!=='function'){
      state.reason='Price consumers unavailable';
      window.__GMFQ_PRICE_FRESHNESS_GATE_STATE=Object.freeze(state);
      return;
    }

    const originalCurrency=window.deriveCurrencyState;
    const originalPair=window.derivePairDecisionFrame;
    if(originalCurrency.__gmfqPriceFreshnessGuard===true||originalPair.__gmfqPriceFreshnessGuard===true){
      state.status='NO_APPLY_ALREADY_INSTALLED';
      state.reason='price freshness guard already installed';
      window.__GMFQ_PRICE_FRESHNESS_GATE_STATE=Object.freeze(state);
      return;
    }

    const asOf=priceAsOf();
    const reference=productionDate();
    const lag=businessLag(asOf,reference);
    const stale=lag==null || lag>MAX_BUSINESS_LAG;
    const staleNote=`Price WITHHELD: fixing G8 canonico ${asOf||'—'} non abbastanza recente rispetto alla data operativa ${reference||'—'}.`;

    const guardedCurrency=function(c){
      const base=originalCurrency(c);
      if(!stale||!base) return base;
      const out=clone(base)||{...base};
      out.price=0;
      out.confirmation='PREZZO NON RISOLUTIVO';
      out.priceFreshness={status:'WITHHELD_STALE',as_of:asOf,reference_as_of:reference,business_lag:lag,max_business_lag:MAX_BUSINESS_LAG};
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
      out.priceFreshness={status:'WITHHELD_STALE',as_of:asOf,reference_as_of:reference,business_lag:lag,max_business_lag:MAX_BUSINESS_LAG};
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
    state.reason=stale?'Canonical daily G8 Price exceeds certified freshness lag; confirmation/divergence suppressed while underlying history remains visible.':'Canonical daily G8 Price is within certified freshness lag.';
    state.price_asof=asOf;
    state.reference_asof=reference;
    state.business_lag=lag;
    state.currency_confirmation_counts=ccys.reduce((acc,c)=>{const x=currencies[c]?.confirmation||'NULL';acc[x]=(acc[x]||0)+1;return acc;},{});
    state.pair_price_reading_counts=pairs.reduce((acc,p)=>{const x=pairFrames[p]?.priceReading||'NULL';acc[x]=(acc[x]||0)+1;return acc;},{});
    window.__GMFQ_PRICE_FRESHNESS_GATE_STATE=Object.freeze(state);
    window.dispatchEvent(new CustomEvent('gmfq:price-freshness-ready',{detail:window.__GMFQ_PRICE_FRESHNESS_GATE_STATE}));
  }catch(e){
    state.reason=String(e&&e.message||e);
    window.__GMFQ_PRICE_FRESHNESS_GATE_STATE=Object.freeze(state);
    console.error('price-freshness-gate',e);
  }
}

install();
})();
