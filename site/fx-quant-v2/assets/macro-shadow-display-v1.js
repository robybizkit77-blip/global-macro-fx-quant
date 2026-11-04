/* FX Quant V2 domestic Macro shadow: NEVER an FX signal or a rebase of D.
 * A missing standardized feature remains NULL, never zero or "neutral".
 */
(function(root){"use strict";
const CCY=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"];
const SCHEMA="GMFQ_FXV2_MACRO_SHADOW_FORMULA_RESEARCH_V1";
const num=x=>typeof x==="number"&&Number.isFinite(x)&&Math.abs(x)<=3.01;
const iso=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&
 !Number.isNaN(Date.parse(x+"T12:00:00Z"));
const n=x=>Number(x).toLocaleString("it-IT",{maximumFractionDigits:2,minimumFractionDigits:2});
const signed=x=>(x<0?"−":x>0?"+":"")+n(Math.abs(x));
const hasText=x=>typeof x==="string"&&x.trim().length>0;
function validate(doc,today){
 if(!doc||doc.schema!==SCHEMA||
    !["RESEARCH_SHADOW_FORMULA_READY_NOT_FX_MODEL",
      "PARTIAL_SHADOW_SOURCE_GAPS_RESEARCH_ONLY"].includes(doc.status)||
    !iso(today)||!iso(doc.economic_source_cutoff_rome)||
    doc.economic_source_cutoff_rome>today||
    doc.formula_version!=="v2_domestic_activity_2026_10_27_FIXED_50_50"||
    doc.formula!=="Activity = 0.50 * GDP_z + 0.50 * (- unemployment_rate_z); inflation_pressure = CPI_z separately"||
    doc.weights?.growth_z!==.5||doc.weights?.labour_tightness_z!==.5||
    doc.weights?.inflation_in_activity!==0||doc.country_z_scores_not_cross_country_strength!==true||
    doc.source_and_revision_quality_is_not_historical_PIT!==true||
    doc.eligible_for_fx_core!==false||doc.eligible_for_pair_rankings!==false||
    doc.eligible_for_trading!==false||doc.eligible_for_forward!==false||
    doc.eligible_for_backtests!==false||doc.canonical_D_untouched!==true||
    doc.summary?.currencies!==8||doc.summary?.research_axes!==24||
    doc.summary?.fx_directional_signals_generated!==0||
    doc.summary?.fx_pairs_unchanged!==28||
    doc.original_frozen_legacy_D_asof!=="2026-09-25"||
    !doc.countries||Object.keys(doc.countries).length!==8||
    !CCY.every(c=>Object.prototype.hasOwnProperty.call(doc.countries,c)))
    return false;
 const full=doc.status==="RESEARCH_SHADOW_FORMULA_READY_NOT_FX_MODEL";
 let blocked=0;
 for(const c of CCY){
  const x=doc.countries[c];
  if(!x||x.fx_policy_or_return_signal!==null||
     x.official_first_publication_PIT_replay_complete!==false||
     !x.source_axes||!["growth","labour","inflation"].every(p=>{
       const s=x.source_axes[p];
       return s&&hasText(s.period)&&s.period.slice(0,4)<=today.slice(0,4)&&
         hasText(s.quality)&&hasText(s.method)&&typeof s.is_estimate==="boolean"&&
         (s.strict_z_available===undefined||
          (typeof s.strict_z_available==="boolean"&&
           s.strict_z_available===(x[p==="growth"?"growth_z_research":
             p==="labour"?"labour_tightness_z_research":"inflation_pressure_z_research"]!==null)));
     }))return false;
  const g=x.growth_z_research,l=x.labour_tightness_z_research,
        p=x.inflation_pressure_z_research,a=x.activity_z_research;
  const validAxis=v=>v===null||num(v);
  if(![g,l,p,a].every(validAxis))return false;
  if(full&&![g,l,p,a].every(num))return false;
  const calculable=num(g)&&num(l);
  if(calculable!==num(a))return false;
  if(calculable&&Math.abs(a-.5*(g+l))>1e-8)return false;
  if(calculable){
   if(typeof x.stable_for_continuous_growth_weight_25_to_75_pct!=="boolean"||
      !x.hypothetical_independent_axis_z_revision_stability||
      !["10","25","50"].every(k=>
        typeof x.hypothetical_independent_axis_z_revision_stability[k]==="boolean"))return false;
  }else{
   blocked++;
   if(a!==null||x.stable_for_continuous_growth_weight_25_to_75_pct!==null||
      x.hypothetical_independent_axis_z_revision_stability!==null)return false;
  }
 }
 if(full&&blocked!==0)return false;
 if(!full&&(
    blocked===0||
    doc.summary.countries_blocked_activity!==blocked||
    doc.summary.countries_with_calculable_activity!==8-blocked))return false;
 return true;
}
function view(doc,ccy,today){
 if(!validate(doc,today)||!CCY.includes(ccy))return null;
 const x=doc.countries[ccy],axes=x.source_axes;
 const isEstimate=Object.values(axes).some(v=>v.is_estimate);
 const hasActivity=num(x.activity_z_research),stress=x.hypothetical_independent_axis_z_revision_stability||{};
 const missing=["growth","labour"].filter(key=>
   x[key==="growth"?"growth_z_research":"labour_tightness_z_research"]===null)
   .map(key=>key+" ("+(axes[key].missing_reason||axes[key].method)+")").join("; ");
 const activity=hasActivity?
  "Attività A "+signed(x.activity_z_research)+"; crescita "+signed(x.growth_z_research)+
  "; tensione lavoro "+signed(x.labour_tightness_z_research)+
  ". Sensibilità ai pesi 25–75%: "+
  (x.stable_for_continuous_growth_weight_25_to_75_pct?"classe invariata":"CLASSE INSTABILE")+
  "; stress ipotetico ±0,25z: "+(stress["25"]===true?"invariante":"non robusto o da verificare")+". ":
  "Attività A NON CALCOLABILE: z-score necessari mancanti — "+missing+
  ". Nessuno zero imputato, nessun segnale. ";
 const inflation=x.inflation_pressure_z_research!==null?
  "Pressione inflazione separata "+signed(x.inflation_pressure_z_research)+". ":
  "Pressione inflazione non calcolabile: z storico mancante ("+
  (axes.inflation.missing_reason||axes.inflation.method)+"). ";
 return {
  source_cutoff:doc.economic_source_cutoff_rome,
  period_summary:"PIL "+axes.growth.period+" · Lavoro "+axes.labour.period+
    " · Inflazione "+axes.inflation.period,
  text:"FORMULA MACRO SPERIMENTALE · A = 50% Crescita + 50% Tensione lavoro (z storici del singolo paese). "+
    activity+inflation+(isEstimate?"Include almeno una STIMA dichiarata. ":
    "Nessuna stima dichiarata per queste tre coordinate. ")+
    "Periodi: PIL "+axes.growth.period+", lavoro "+axes.labour.period+
    ", inflazione "+axes.inflation.period+". Storici revisionati e first-web non PIT completo; "+
    "la data di calcolo "+doc.economic_source_cutoff_rome+" non è una nuova pubblicazione. "+
    "NON è un punteggio FX né un nuovo bias; baseline operativa 25/09/2026 invariata."
 };
}
const api=Object.freeze({validate,view,SCHEMA});
root.FXV2MacroShadow=api;
if(typeof module==="object"&&module&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
