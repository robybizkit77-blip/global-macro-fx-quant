'use strict';
/* FX Quant Next — read-only source contract, as of 2026-11-27.
 * Exact snapshot derived from validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json.
 * PROVENANCE READY ≠ source refreshed ≠ current release. Always fail closed.
 * Updated via audited policy only; no market scoring or Core writes.
 */
(function(root){
 const AS_OF="2026-11-27";
 const MAP={
 "USD": {
  "liquidity": {
   "ready": true,
   "status": "AUTOMATION_CONTRACT_VERIFIED_NATIVE_PARITY"
  },
  "credit": {
   "ready": false,
   "status": "OFFICIAL_SERIES_IDENTIFIED_TRANSPORT_NOT_STABLE"
  },
  "conditions": {
   "ready": false,
   "status": "OFFICIAL_PROVIDER_CONFIRMED_SERIES_MAPPING_PENDING"
  }
 },
 "EUR": {
  "liquidity": {
   "ready": true,
   "status": "OFFICIAL_SERIES_CONFIRMED"
  },
  "credit": {
   "ready": true,
   "status": "AUTOMATION_CONTRACT_VERIFIED_NATIVE_PARITY"
  },
  "conditions": {
   "ready": false,
   "status": "OFFICIAL_PROVIDER_CONFIRMED_SERIES_MAPPING_PENDING"
  }
 },
 "GBP": {
  "liquidity": {
   "ready": true,
   "status": "AUTOMATION_CONTRACT_PROVEN_CONTROLLED_APPLY"
  },
  "credit": {
   "ready": true,
   "status": "AUTOMATION_CONTRACT_PROVEN_CONTROLLED_APPLY"
  },
  "conditions": {
   "ready": false,
   "status": "OFFICIAL_SOURCE_CONFIRMED_VALUE_MAPPING_PENDING"
  }
 },
 "JPY": {
  "liquidity": {
   "ready": false,
   "status": "OFFICIAL_PROVIDER_CONFIRMED_SERIES_MAPPING_PENDING"
  },
  "credit": {
   "ready": true,
   "status": "AUTOMATION_CONTRACT_PROVEN_CONTROLLED_APPLY"
  },
  "conditions": {
   "ready": false,
   "status": "OFFICIAL_SOURCE_CONFIRMED_VALUE_MAPPING_PENDING"
  }
 },
 "CHF": {
  "liquidity": {
   "ready": false,
   "status": "OFFICIAL_PROVIDER_CONFIRMED_VARIANT_MATCH_PENDING"
  },
  "credit": {
   "ready": false,
   "status": "OFFICIAL_PROVIDER_CONFIRMED_DIMENSION_MATCH_PENDING"
  },
  "conditions": null
 },
 "CAD": {
  "liquidity": {
   "ready": true,
   "status": "AUTOMATION_CONTRACT_VERIFIED_NATIVE_PARITY"
  },
  "credit": null,
  "conditions": {
   "ready": false,
   "status": "OFFICIAL_PROVIDER_CONFIRMED_SERIES_MAPPING_PENDING"
  }
 },
 "AUD": {
  "liquidity": {
   "ready": true,
   "status": "AUTOMATION_CONTRACT_VERIFIED_NATIVE_PARITY"
  },
  "credit": {
   "ready": true,
   "status": "AUTOMATION_CONTRACT_VERIFIED_NATIVE_PARITY"
  },
  "conditions": null
 },
 "NZD": {
  "liquidity": {
   "ready": true,
   "status": "AUTOMATION_CONTRACT_RECOVERED"
  },
  "credit": {
   "ready": true,
   "status": "AUTOMATION_CONTRACT_RECOVERED"
  },
  "conditions": null
 }
};
 function check(ccy,role){
  const record=MAP[ccy]?.[role]||null;
  const withheld=ccy==='USD'&&role==='conditions';
  if(withheld)return {available:false,withheld:true,ready:false,code:'VARIANT_NOT_ALIGNED',label:'SLOOS IN VERIFICA',
   narrative:'Le due serie interne con etichetta SLOOS hanno valori diversi nello stesso periodo. Identificare variante e perimetro ufficiali prima di interpretare il saldo; il numero è temporaneamente escluso dalla lettura.'};
  if(!record)return {available:false,withheld:false,ready:false,code:'NO_APPROVED_MAPPING',label:'MAPPATURA ASSENTE',
   narrative:ccy==='CAD'&&role==='credit'?
   'Il feed operativo non dispone del credito canadese. Esiste una serie separata in ricerca, non certificata per questa pagina: nessuna promozione automatica.':
   'Non è disponibile un contratto di serie certificato per questo canale.'};
  if(record.ready)return {available:true,withheld:false,ready:true,code:record.status,label:'CONTRATTO MAPPATO',
   narrative:'Serie identificata nel registro fonti ('+AS_OF+'). Questo NON prova che un nuovo rilascio sia stato acquisito o che il dato osservato sia corrente.'};
  return {available:true,withheld:false,ready:false,code:record.status,label:'AUTOMAZIONE NON CERTIFICATA',
   narrative:'Il registro ('+AS_OF+') non certifica ancora acquisizione e applicazione continuativa di questa serie. La lettura storica resta distinta dall’aggiornamento ufficiale.'};
 }
 function review(ccy){
  const fields=['liquidity','credit','conditions'];
  const entries=fields.map(role=>({role,...check(ccy,role)}));
  return {as_of:AS_OF,entries,verifiedContracts:entries.filter(x=>x.ready).length,
   withheld:entries.filter(x=>x.withheld).length,unmapped:entries.filter(x=>!x.available&&!x.withheld).length};
 }
 const api={AS_OF,MAP,check,review};
 root.FXQuantLiquiditySourcePolicy=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
