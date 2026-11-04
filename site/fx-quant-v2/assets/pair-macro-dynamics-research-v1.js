/* FX Quant V2 — transparent dynamic Macro V3 research, NEVER a trading-score rebase.
 * Uses observed published rates of change, no fitted coefficients, no FX vote.
 */
(function(root){"use strict";
const CCYS=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"];
const BAND_PP=0.05; // descriptive dead band, NOT an estimated noise distribution
const good=x=>typeof x==="number"&&Number.isFinite(x);
const iso=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&
 new Date(x+"T12:00:00Z").toISOString().startsWith(x);
const quarter=x=>typeof x==="string"&&/^\d{4}Q[1-4]$/.test(x);
const addQuarter=x=>{
 if(!quarter(x))return null;
 const y=+x.slice(0,4),q=+x.slice(-1);
 return q===4?(y+1)+"Q1":y+"Q"+(q+1);
};
const signed=(n,p=2)=>good(n)?(n>0?"+":n<0?"−":"")+Math.abs(n).toLocaleString("it-IT",{maximumFractionDigits:p})+" pp":"n.d.";
function classify(x){
 if(!good(x))return "NON_CALCOLABILE";
 return x>BAND_PP?"AUMENTO":x<(-BAND_PP)?"CALO":"QUASI_STABILE";
}
function buildCountry(country,ccy,today){
 if(!country||country.not_a_trade_or_policy_signal!==true||
    country.macro_score!==null||country.FX_strength!==null)throw Error(ccy+" unsafe macro input");
 const growth=country.growth||{},prior=growth.prior_documented_quarter;
 if(!quarter(growth.reference_quarter)||!good(growth.reported_value)||
    !good(growth.nonannualized_qoq_descriptive_pct)||
    !iso(growth.publisher_release_day)||growth.publisher_release_day>today)
  throw Error(ccy+" invalid growth source");
 // Q/Q is comparable only within the SAME economy after normalization; SAAR
 // is already converted by the Macro V3 source layer. No cross-country score.
 let accel=null,comparison="NON_CALCOLABILE_UNICO_TRIMESTRE";
 if(prior){
  if(quarter(prior.reference_quarter)&&
    addQuarter(prior.reference_quarter)===growth.reference_quarter&&
    good(prior.nonannualized_qoq_descriptive_pct)&&
    prior.reported_unit===growth.reported_unit&&
    iso(prior.publisher_release_day)&&prior.publisher_release_day<=today){
   accel=+((growth.nonannualized_qoq_descriptive_pct-prior.nonannualized_qoq_descriptive_pct).toFixed(6));
   comparison="DUE_TRIMESTRI_CONTIGUI_STESSA_DEFINIZIONE";
  }else throw Error(ccy+" GDP previous quarter incompatible");
 }
 const validateChange=(x,label)=>{
  if(!x||!good(x.observation_value)||!good(x.change_over_three_observation_intervals_pp)||
     typeof x.observation_period!=="string"||
     !/^\d{4}-(?:0[1-9]|1[0-2])$|^\d{4}Q[1-4]$/.test(x.observation_period)||
     x.observation_period.slice(0,4)>today.slice(0,4)||
     x.observation_period_is_not_release_instant!==true||
     x.observed_history_revised_not_historic_PIT!==true)
    throw Error(ccy+" invalid "+label+" source");
  const periodType=x.observation_period.includes("Q")?"QUARTERLY":"MONTHLY";
  return {period:x.observation_period,period_type:periodType,
    level:x.observation_value,change_pp:x.change_over_three_observation_intervals_pp,
    movement:classify(x.change_over_three_observation_intervals_pp),
    source_id:x.series_id,observation_intervals_not_fixed_calendar_months:true};
 };
 return {
  ccy,growth:{period:growth.reference_quarter,
    qoq_pct:growth.nonannualized_qoq_descriptive_pct,
    prior_quarter:prior?.reference_quarter||null,
    qoq_change_pp:accel,
    movement:classify(accel),
    evidence:comparison,release_day:growth.publisher_release_day,
    not_directly_comparable_as_fx_strength:true},
  labour:{...validateChange(country.labour,"labour"),
    interpretation:"Aumento disoccupazione = più slack, non automaticamente tagli o FX debole"},
  inflation:{...validateChange(country.inflation,"inflation"),
    interpretation:"Aumento inflazione YoY = pressione sui prezzi, non automaticamente repricing hawkish"},
  feature_quality:"REVISED_OBSERVATIONAL_NOT_PIT",
  macro_score:null,fx_strength:null,policy_rate_signal:null
 };
}
function evaluate(doc,pair,today,baseValidate){
 if(!iso(today)||!baseValidate?.(doc,today))return null;
 const cleaned=pair?.replace("/","").toUpperCase();
 if(!/^[A-Z]{6}$/.test(cleaned))return null;
 const a=cleaned.slice(0,3),b=cleaned.slice(3,6);
 if(a===b||!CCYS.includes(a)||!CCYS.includes(b)||
    !doc.pair_context?.[a+"/"+b])return null;
 const A=buildCountry(doc.countries[a],a,today),B=buildCountry(doc.countries[b],b,today);
 const sync=(x,y)=>x.period===y.period&&x.period_type===y.period_type;
 const inflationSame=sync(A.inflation,B.inflation),labourSame=sync(A.labour,B.labour);
 const bothGDP=good(A.growth.qoq_change_pp)&&good(B.growth.qoq_change_pp)&&
   A.growth.period===B.growth.period&&A.growth.prior_quarter===B.growth.prior_quarter;
 const labourSummary=labourSame?
   "Disoccupazione nello stesso periodo ("+A.labour.period+"): "+a+" "+signed(A.labour.change_pp)+
   ", "+b+" "+signed(B.labour.change_pp)+". ":
   "Disoccupazione con periodi/frequenze diversi ("+a+" "+A.labour.period+", "+b+" "+B.labour.period+"): "+
   a+" "+signed(A.labour.change_pp)+", "+b+" "+signed(B.labour.change_pp)+
   "; niente confronto diretto. ";
 const inflationSummary=inflationSame?
   "Inflazione nello stesso periodo ("+A.inflation.period+"): "+a+" "+signed(A.inflation.change_pp)+
   ", "+b+" "+signed(B.inflation.change_pp)+". ":
   "Inflazione non sincronizzata ("+a+" "+A.inflation.period+", "+b+" "+B.inflation.period+"): "+
   a+" "+signed(A.inflation.change_pp)+", "+b+" "+signed(B.inflation.change_pp)+
   "; niente confronto diretto. ";
 const growthSummary=bothGDP?
   "PIL: variazione del ritmo trimestrale Q/Q rispetto al trimestre prima — "+a+" "+
   signed(A.growth.qoq_change_pp)+", "+b+" "+signed(B.growth.qoq_change_pp)+
   " (stesso Q"+A.growth.period.slice(-1)+", pubblicazioni e revisioni distinte). ":
   "PIL: accelerazione relativa NON calcolabile su due trimestri allineati ("+
   a+" "+A.growth.period+", "+b+" "+B.growth.period+"). ";
 return {
  schema:"GMFQ_FXV2_MACRO_DYNAMIC_RESEARCH_V1",pair:a+"/"+b,
  as_of_research:doc.generated_europe_rome_day,
  canonical_core_as_of:doc.canonical_D_macro_baseline_as_of,
  formula:"GDP delta Q/Q = latest nonannualized qoq - immediately preceding qoq; labour/inflation delta = observed change over 3 observation intervals; no fitted scores or cross-country z-normalization.",
  base:A,quote:B,
  comparable:{growth_acceleration:bothGDP,labour_trend_same_period:labourSame,
    inflation_trend_same_period:inflationSame},
  macro_score:null,fx_bias:null,expected_fx_return:null,
  safe_to_modify_core:false,safe_for_backtest:false,
  summary:"DINAMICA MACRO (RICERCA, NON NUOVO BIAS): "+
    growthSummary+labourSummary+inflationSummary+
    "Variazioni su tre intervalli osservati, non necessariamente tre mesi; dati rivisti, non vintage point-in-time. "+
    "Senza consenso, sorpresa, OIS e reazione del prezzo non possiamo dedurre un repricing né modificare le 28 tesi."
 };
}
const api=Object.freeze({evaluate,buildCountry,classify,BAND_PP});
root.FXV2MacroDynamics=api;
if(typeof module==="object"&&module&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
