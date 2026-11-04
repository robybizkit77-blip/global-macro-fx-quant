/* FX Quant V2 pair-level Macro V3 OBSERVATIONS — never score/upgrade pair signals. */
(function(root){"use strict";
const SCHEMA="GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1";
const CODES=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"];
const iso=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&
 new Date(x+"T12:00:00Z").toISOString().startsWith(x);
const dateAge=(now,x)=>Math.round((Date.parse(now+"T12:00:00Z")-Date.parse(x+"T12:00:00Z"))/86400000);
const numeric=x=>typeof x==="number"&&Number.isFinite(x);
const money=(x,d=2)=>numeric(x)?x.toLocaleString("it-IT",{maximumFractionDigits:d,minimumFractionDigits:0}):"n.d.";
const signed=x=>numeric(x)?(x>0?"+":x<0?"−":"")+money(Math.abs(x)):"n.d.";
function validate(doc,today){
 if(!doc||doc.schema!==SCHEMA||doc.status!=="OBSERVED_ECONOMIC_CONTEXT_NOT_FX_SIGNAL"||
    !iso(today)||!iso(doc.generated_europe_rome_day)||
    dateAge(today,doc.generated_europe_rome_day)<0||
    dateAge(today,doc.generated_europe_rome_day)>10||
    doc.source_observation_periods_not_release_days!==true||
    doc.historic_PIT_OOS_not_certified!==true||
    doc.safe_to_republish_D!==false||
    doc.safe_to_recompute_structural_pair_theses!==false||
    doc.eligible_for_trading_or_forward_backtest!==false||
    doc.summary?.currencies!==8||doc.summary?.economic_dimensions!==24||
    doc.summary?.pairs!==28||doc.summary?.pair_trade_signals_generated!==0||
    doc.summary?.numeric_old_D_macro_scores_replaced!==0||
    doc.canonical_D_macro_baseline_as_of!=="2026-09-25"||
    typeof doc.countries!=="object"||typeof doc.pair_context!=="object"||
    Object.keys(doc.countries).length!==8||Object.keys(doc.pair_context).length!==28)
  return false;
 for(const c of CODES){
  const x=doc.countries[c];
  if(!x||x.macro_score!==null||x.FX_strength!==null||
     x.not_a_trade_or_policy_signal!==true||
     !x.growth||x.growth.is_growth_strength_score!==false||
     !numeric(x.growth.reported_value)||!x.growth.reported_unit||
     !x.growth.reference_quarter||
     !numeric(x.labour?.observation_value)||!x.labour.observation_period||
     !numeric(x.inflation?.observation_value)||!x.inflation.observation_period)
   return false;
 }
 for(const [pair,x] of Object.entries(doc.pair_context)){
  if(!x||!CODES.includes(x.base)||!CODES.includes(x.quote)||x.base===x.quote||
     pair!==x.base+"/"+x.quote||
     x.pair_trade_bias!==null||x.estimated_FX_expected_return!==null||
     x.recalculated_structural_thesis!==false) return false;
 }
 return true;
}
function view(doc,code,today){
 if(!validate(doc,today)||typeof code!=="string")return null;
 const a=code.slice(0,3),b=code.slice(3,6),p=doc.pair_context[a+"/"+b];
 if(!p||code.length!==6)return null;
 const ca=doc.countries[a],cb=doc.countries[b];
 const fmtUnemp=(ccy,x)=>ccy+" "+money(x.observation_value)+"% ("+x.observation_period+
  ", var. ultimi 3 intervalli "+signed(x.change_over_three_observation_intervals_pp)+" pp)";
 const fmtInfl=(ccy,x)=>ccy+" "+money(x.observation_value)+"% ("+x.observation_period+
  ", var. ultimi 3 intervalli "+signed(x.change_over_three_observation_intervals_pp)+" pp)";
 const fmtGDP=(ccy,x)=>ccy+" "+money(x.reported_value)+"% ("+x.reference_quarter+
  ", "+(x.reported_unit==="PERCENT_SAAR_ANNUALIZED"?"annualizzato SAAR":x.reported_unit.replaceAll("_"," "))+")";
 return {
  generated:doc.generated_europe_rome_day,
  baseline:doc.canonical_D_macro_baseline_as_of,
  text:"MACRO V3 · osservazioni pubblicate, non nuovo bias FX. Lavoro (disoccupazione): "+
   fmtUnemp(a,ca.labour)+"; "+fmtUnemp(b,cb.labour)+
   ". Inflazione: "+fmtInfl(a,ca.inflation)+"; "+fmtInfl(b,cb.inflation)+
   ". Crescita (PIL): "+fmtGDP(a,ca.growth)+"; "+fmtGDP(b,cb.growth)+
   ". Periodi, unità e revisioni possono differire: i livelli di PIL non sono confronti diretti di forza FX. "+
   "Baseline del motore "+doc.canonical_D_macro_baseline_as_of+
   " invariata; questa ricerca osservata non ha punteggi, segnali né backtest point-in-time certificati."
 };
}
const api=Object.freeze({validate,view,SCHEMA});
root.FXV2MacroPairResearch=api;
if(typeof module==="object"&&module&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
