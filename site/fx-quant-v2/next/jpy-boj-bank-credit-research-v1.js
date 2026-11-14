'use strict';
/* BoJ MD11 DLCLAEDBLTTO, official monthly credit stock.
 * 100 million JPY, includes banking/trust/overseas office accounts of
 * domestically licensed banks. Research-only and not a new-loans flow.
 * Reuses audited BoJ candidate exact overlap and no Core modifications.
 */
(function(root){
 const data={
  schema:'GMFQ_NEXT_JPY_BOJ_BANK_CREDIT_RESEARCH_V1',
  status:'WITHHELD_UNTIL_OFFICIAL_MD11_SOURCE_VALIDATED',
  country:'JPY',publisher:'Bank of Japan',
  database:'MD11',series_id:'DLCLAEDBLTTO',
  source_url:'https://www.stat-search.boj.or.jp/ssi/mtshtml/md11_m_1_en.html',
  source_contract:'Outstanding Loans and Bills Discounted / End of Period / Banking, Trust and Overseas Office Accounts / Domestically Licensed Banks',
  category:'bank_credit_end_period_stock',
  unit:'100 milioni JPY',frequency:'M',end_of_period:true,
  first_release_pit_verified:false,eligible_for_fx_core:false,
  eligible_for_backtest:false,observation_is_not_publication_date:true,
  last_observation:null,dates:[],values:[],
  original_canonical_last:'2026-07',
  original_canonical_value:6764306,
  inference:'Total credit stock including trust and overseas office accounts, not newly originated loans, credit impulse or BoJ current-account reserves.'
 };
 root.FXQuantJPYBankCreditResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
