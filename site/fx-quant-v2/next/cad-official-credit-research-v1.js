'use strict';
/* Official Bank of Canada monthly business-loans stock, research-only sidecar.
 * This DOES NOT populate NATIVE_LIQ_DATA.CAD.credit, the Core FX ranking,
 * or a point-in-time / first-release vintage.
 * The monthly series is V122667770, business loans total outstanding.
 * Initial values transcribed from issuer's published official table
 * on 2026-11-14; ongoing workflow refreshes only after strict validation.
 */
(function(root){
 const data={
  schema:'GMFQ_NEXT_CAD_BUSINESS_CREDIT_OFFICIAL_RESEARCH_V1',
  status:'ISSUER_PAGE_VERIFIED_HISTORICAL_RESEARCH',
  country:'CAD',
  publisher:'Bank of Canada',
  series_id:'V122667770',
  source_url:'https://www.bankofcanada.ca/rates/banking-and-financial-statistics/funds-advanced-and-outstanding-balances-for-new-and-existing-lending-by-chartered-banks/',
  api_url:'https://www.bankofcanada.ca/valet/observations/V122667770/json?recent=24',
  label:'Prestiti alle imprese · totale in essere',
  category:'outstanding_business_loans',
  units:'milioni CAD',
  frequency:'M',
  seasonally_adjusted:'not_verified',
  first_release_pit_verified:false,
  eligible_for_fx_core:false,
  eligible_for_backtest:false,
  observation_is_not_publication_date:true,
  last_checked_rome:'2026-11-14',
  latest_observation:'2026-08',
  dates:['2026-04','2026-05','2026-06','2026-07','2026-08'],
  values:[922171,927358,937138,941686,944614],
  inference:'Livelli di stock, non nuove erogazioni, domanda di prestiti o standard bancari. Serie parallela: non certifica il canale CAD.credit del feed principale.'
 };
 root.FXQuantCADCreditResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
