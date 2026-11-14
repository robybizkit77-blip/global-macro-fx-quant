'use strict';
/* Euro area ECB NFC-loan stocks, research only: fail-closed placeholder.
 * Exact series BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E; non-seasonally
 * adjusted end-of-period stocks, millions EUR, NOT new originations.
 */
(function(root){
 const data={
  schema:'GMFQ_NEXT_EUR_ECB_NFC_CREDIT_RESEARCH_V1',
  status:'WITHHELD_UNTIL_OFFICIAL_SOURCE_VERIFIED',
  country:'EUR',publisher:'European Central Bank / ESCB',
  series_id:'BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E',
  source_url:'https://data.ecb.europa.eu/data/datasets/BSI/BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E',
  api_url:'https://data-api.ecb.europa.eu/service/data/BSI/M.U2.N.A.A20.A.1.U2.2240.Z01.E?format=csvdata&startPeriod=2024-01',
  label:'Loans to Euro Area Non-Financial Corporations — Stocks',
  category:'nfc_loans_stock',frequency:'M',
  unit:'milioni EUR',seasonally_adjusted:false,
  first_release_pit_verified:false,
  eligible_for_fx_core:false,eligible_for_backtest:false,
  observation_is_not_publication_date:true,
  latest_observation:null,dates:[],values:[],
  inference:'Stock di prestiti BCE a imprese non finanziarie, non nuove erogazioni. Fonte ricerca indipendente dal feed nativo.'
 };
 root.FXQuantEURNFCCreditResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
