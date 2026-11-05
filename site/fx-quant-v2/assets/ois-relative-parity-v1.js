/* FX Quant V2 — research-only, date-aware parity of the 28 displayed pricing comparisons.
 * NEVER used by Core FX, trade signals, P&L, forwards or policy repricing.
 * All numbers come from the same per-tenor source/price currently displayed in
 * ois.html. An old published 28-pair file supplies orientation, NOT live rates.
 */
(function(root,build){
  "use strict";
  const api=build();
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(root)root.FXV2OisRelativeParity=api;
})(typeof window!=="undefined"?window:null,function(){
  "use strict";
  const TENORS=["3m","6m","12m"];
  function value(x){return x&&typeof x.rate==="number"&&Number.isFinite(x.rate)&&x.rate>-5&&x.rate<30&&
    typeof x.as_of==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x.as_of);}
  function rateDiffBp(a,b){return Math.round((a-b)*100000)/1000;}
  function compare(report,currencies){
    const pairs=report?.pairs||{},names=Object.keys(pairs);
    if(names.length!==28||report?.eligible_for_fx_engine!==false||
       report?.not_ois_equivalent!==true||report?.not_policy_repricing!==true)
      return {status:"INVALID_RESEARCH_SOURCE",rows:[],mismatches:[],changedLegs:[]};
    const rows=[],mismatches=[],changedLegs=new Set();
    for(const name of names){
      const saved=pairs[name],base=saved?.base,quote=saved?.quote;
      if(!base||!quote||name!==base+"/"+quote||base===quote)
        return {status:"INVALID_PAIR_ORIENTATION",rows:[],mismatches:[],changedLegs:[]};
      const horizons={};
      for(const tenor of TENORS){
        const x=currencies?.[base]?.horizons?.[tenor],y=currencies?.[quote]?.horizons?.[tenor];
        const old=saved?.horizons?.[tenor];
        if(!value(x)||!value(y)||!old)
          return {status:"WAITING_FOR_24_DATED_LEVELS",rows:[],mismatches:[],changedLegs:[]};
        const changedX=Math.abs(x.rate-old.base_rate_pct)>0.0000001||
          x.as_of!==old.base_as_of||x.contract!==old.base_contract||
          x.kind!==old.base_kind||x.quality!==old.base_quality;
        const changedY=Math.abs(y.rate-old.quote_rate_pct)>0.0000001||
          y.as_of!==old.quote_as_of||y.contract!==old.quote_contract||
          y.kind!==old.quote_kind||y.quality!==old.quote_quality;
        if(changedX)changedLegs.add(base+":"+tenor);
        if(changedY)changedLegs.add(quote+":"+tenor);
        if(changedX||changedY)mismatches.push({pair:name,tenor,base_changed:changedX,quote_changed:changedY});
        const datedA=Date.parse(x.as_of+"T12:00:00Z"),datedB=Date.parse(y.as_of+"T12:00:00Z");
        const dateGap=Number.isFinite(datedA)&&Number.isFinite(datedB)?
          Math.round(Math.abs(datedA-datedB)/86400000):null;
        horizons[tenor]={
          spread_bp:rateDiffBp(x.rate,y.rate),
          base_rate_pct:x.rate,quote_rate_pct:y.rate,
          base_as_of:x.as_of,quote_as_of:y.as_of,
          base_contract:x.contract||null,quote_contract:y.contract||null,
          base_kind:x.kind,quote_kind:y.kind,
          base_quality:x.quality,quote_quality:y.quality,
          base_origin:x.origin,quote_origin:y.origin,
          same_date:dateGap===0,date_gap_days:dateGap,
          estimate_involved:x.quality==="STIMA INDICATIVA"||y.quality==="STIMA INDICATIVA",
          proxy_involved:x.kind==="PROXY FUTURES"||y.kind==="PROXY FUTURES",
          fx_signal:null,policy_repricing_bp:null,
        };
      }
      rows.push({name,base,quote,horizons});
    }
    return {
      status:mismatches.length?"RECALCULATED_FROM_DISPLAYED_TENORS":"MATCHED_PUBLISHED_RESEARCH",
      rows,mismatches,changedLegs:[...changedLegs].sort(),
      compared:rows.length*TENORS.length,
      read_only:true,fx_signal_generated:false,policy_repricing_generated:false,
    };
  }
  return Object.freeze({compare,rateDiffBp});
});
