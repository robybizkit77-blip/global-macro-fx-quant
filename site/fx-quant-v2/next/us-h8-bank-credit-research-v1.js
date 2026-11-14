'use strict';
/* Research-only US bank credit; official Fed H.8 via FRED TOTBKCR.
 * Withheld until the collector verifies source, overlap, chronology and dates.
 * No FX Core effect and no automatic substitution of native NATIVE_LIQ_DATA.
 */
(function(root){
 const data={
  schema:'GMFQ_NEXT_US_H8_CREDIT_RESEARCH_V1',
  status:'WITHHELD_UNTIL_SOURCE_VERIFIED',
  country:'USD',publisher:'Board of Governors of the Federal Reserve System (US)',
  mirror:'FRED (Federal Reserve Bank of St. Louis)',series_id:'TOTBKCR',
  source_url:'https://fred.stlouisfed.org/series/TOTBKCR',
  api_url:'https://fred.stlouisfed.org/graph/fredgraph.csv?id=TOTBKCR&cosd=2026-06-01',
  label:'Bank Credit, All Commercial Banks',
  category:'bank_credit_stock',
  unit:'miliardi USD',frequency:'W',seasonally_adjusted:true,
  first_release_pit_verified:false,eligible_for_fx_core:false,
  eligible_for_backtest:false,observation_is_not_publication_date:true,
  latest_observation:null,dates:[],values:[],
  inference:'Totale credito bancario Fed H.8: stock di attività, non nuovi prestiti o survey sugli standard. Seconda fonte di ricerca, non nuovo segnale USD.'
 };
 root.FXQuantUSBanksCreditResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
