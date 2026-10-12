(function(){
'use strict';

const CCYS=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const clone=x=>{try{return JSON.parse(JSON.stringify(x))}catch{return null}};

function canonicalCotAsOf(){
  const data=window.__GMFQ_DATA?.V250_COT_CHART_DATA || window.V250_COT_CHART_DATA || null;
  if(!data||typeof data!=='object')return null;
  const per={};
  for(const c of CCYS){
    const dates=data?.[c]?.dates;
    const last=Array.isArray(dates)&&dates.length?String(dates[dates.length-1]||'').slice(0,10):null;
    if(!last)return null;
    per[c]=last;
  }
  const unique=[...new Set(Object.values(per))];
  if(unique.length!==1)return null;
  return {as_of:unique[0],per_currency:per};
}

function apply(){
  const canonical=canonicalCotAsOf();
  const prior={
    production:window.PRODUCTION_PRICE_COT_LIQ_AUDIT?.cot?.current_as_of||null,
    source_policy:window.FINAL_SOURCE_POLICY_AUDIT?.COT?.current_as_of||window.FINAL_SOURCE_POLICY_AUDIT?.cot?.current_as_of||null,
    d_cot_asof:window.D?.cotAsOf||null
  };
  if(!canonical){
    window.__GMFQ_COT_PROVENANCE_REALIGN_STATE=Object.freeze({
      status:'WITHHELD_CANONICAL_COT_ASOF_UNRESOLVED',
      changed:false,
      prior
    });
    window.dispatchEvent(new CustomEvent('gmfq:cot-provenance-realign-ready',{detail:window.__GMFQ_COT_PROVENANCE_REALIGN_STATE}));
    return;
  }

  const asOf=canonical.as_of;
  if(window.PRODUCTION_PRICE_COT_LIQ_AUDIT?.cot){
    Object.assign(window.PRODUCTION_PRICE_COT_LIQ_AUDIT.cot,{
      status:'CURRENT_WEEKLY',
      current_as_of:asOf,
      action:'CURRENT_CANONICAL_SNAPSHOT',
      rule:'Weekly CFTC Legacy Futures Only snapshot only; no interpolation.'
    });
  }
  if(window.FINAL_SOURCE_POLICY_AUDIT?.COT){
    Object.assign(window.FINAL_SOURCE_POLICY_AUDIT.COT,{current_as_of:asOf});
  }
  if(window.FINAL_SOURCE_POLICY_AUDIT?.cot){
    Object.assign(window.FINAL_SOURCE_POLICY_AUDIT.cot,{current_as_of:asOf});
  }
  if(window.D&&typeof window.D==='object')window.D.cotAsOf=asOf;

  try{if(typeof window.syncCoreFreshnessRegistryFromLive==='function')window.syncCoreFreshnessRegistryFromLive();}catch(e){}

  const next={
    production:window.PRODUCTION_PRICE_COT_LIQ_AUDIT?.cot?.current_as_of||null,
    source_policy:window.FINAL_SOURCE_POLICY_AUDIT?.COT?.current_as_of||window.FINAL_SOURCE_POLICY_AUDIT?.cot?.current_as_of||null,
    d_cot_asof:window.D?.cotAsOf||null
  };
  window.__GMFQ_COT_PROVENANCE_REALIGN_STATE=Object.freeze({
    status:'PASS_CANONICAL_COT_PROVENANCE_REALIGNED',
    changed:prior.production!==asOf||prior.source_policy!==asOf||prior.d_cot_asof!==asOf,
    canonical_as_of:asOf,
    per_currency:Object.freeze(clone(canonical.per_currency)),
    prior:Object.freeze(prior),
    next:Object.freeze(next),
    changes_engine:false,
    changes_bias:false,
    changes_sizing:false,
    changes_pair_structure:false,
    underlying_cot_data_mutated:false
  });
  window.dispatchEvent(new CustomEvent('gmfq:cot-provenance-realign-ready',{detail:window.__GMFQ_COT_PROVENANCE_REALIGN_STATE}));
}

apply();
})();
