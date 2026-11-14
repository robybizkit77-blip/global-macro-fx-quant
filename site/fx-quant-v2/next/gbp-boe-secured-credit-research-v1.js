'use strict';
/* BoE IADB LPMVTYI: monthly annual growth of sterling net secured lending
 * to individuals, seasonally adjusted. Research only, never inferred from
 * reserve balance stocks, and never a direct GBP FX trade signal.
 */
(function(root){
 const data={
  schema:'GMFQ_NEXT_GBP_BOE_SECURED_CREDIT_GROWTH_V1',
  status:'WITHHELD_UNTIL_OFFICIAL_IADB_VALIDATION',
  country:'GBP',publisher:'Bank of England',
  series_id:'LPMVTYI',
  source_url:'https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?SeriesCodes=LPMVTYI&UsingCodes=Y',
  api_url:'https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2021&Dateto=now&SeriesCodes=LPMVTYI&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N',
  source_contract:'Monthly 12 month growth rate of total sterling net secured lending to individuals, seasonally adjusted',
  category:'secured_household_credit_yoy_growth',
  frequency:'M',unit:'percent_yoy',seasonally_adjusted:true,
  first_release_pit_verified:false,observation_is_not_publication_date:true,
  eligible_for_fx_core:false,eligible_for_backtest:false,
  last_observation:null,dates:[],values:[],
  inference:'Crescita annuale del credito ipotecario garantito alle persone, non nuove erogazioni, credito imprese o liquidità di riserva BoE. Le variazioni dei tassi sono punti percentuali.'
 };
 root.FXQuantGBPBoESecuredCreditResearch=Object.freeze(data);
 if(typeof module!=='undefined'&&module.exports)module.exports=data;
})(typeof window!=='undefined'?window:globalThis);
