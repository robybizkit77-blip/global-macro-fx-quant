/* FX Quant V2 research-only explanatory text for identical listed-futures contracts.
 * Source: immutable, dated same-contract sidecar; source-parity verified against
 * the OIS page's CURRENT per-tenor data. Never produces OIS policy deltas,
 * trading signals, implied bank-rate probabilities or automated FX decisions.
 */
(function(root, factory){
  "use strict";
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(root)root.FXV2OisMovementReading=api;
})(typeof window==="object"?window:null,function(){
  "use strict";
  const TENORS=["3m","6m","12m"];
  const NAMES={USD:"dollaro USA",EUR:"euro",CHF:"franco svizzero"};
  const LABEL={ "3m":"3M", "6m":"6M", "12m":"12M"};
  const validDate=s=>typeof s==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&
    Number.isFinite(Date.parse(s+"T12:00:00Z"));
  const displayDate=s=>validDate(s)?s.slice(8,10)+"/"+s.slice(5,7)+"/"+s.slice(0,4):"n.d.";
  function fmtBp(x){
    if(!Number.isFinite(x))return "non disponibile";
    const v=Math.abs(x).toLocaleString("it-IT",{minimumFractionDigits:0,maximumFractionDigits:2});
    return (x>0?"+":x<0?"−":"")+v+" pb";
  }
  function eligibleSidecar(doc){
    return doc?.schema==="GMFQ_FXV2_SAME_CONTRACT_FUTURES_MOVES_V1"&&
      doc?.snapshot_research_only===true&&doc?.eligible_for_fx_engine===false&&
      doc?.eligible_for_policy_repricing_signals===false&&
      doc?.official_ois_created===false&&
      doc?.unknown_is_null_not_zero===true&&
      doc?.strict_reference_dates?.cross_contract_joins===false&&
      doc?.strict_reference_dates?.quarantined_reference_used===false;
  }
  function currentParity(ccy,tenor,doc,shown){
    const r=doc?.currencies?.[ccy]?.[tenor],z=shown?.horizons?.[tenor];
    return Boolean(r&&z&&["VERIFIED_SAME_CONTRACT_PRICE_CHANGE","VERIFIED_CONTRACT_NO_MATCHED_REFERENCE"].includes(r.status)&&
      r.source_type==="SECONDARY_LISTED_FUTURES_NOT_OIS"&&r.official_ois===false&&
      r.policy_repricing_signal===false&&r.fx_signal===null&&
      z.kind==="FUTURES SECONDARI"&&z.quality==="STIMA INDICATIVA"&&
      r.contract&&r.contract===z.contract&&
      validDate(r.as_of)&&r.as_of===z.as_of&&
      Number.isFinite(r.rate_pct)&&Number.isFinite(z.rate)&&
      Math.abs(r.rate_pct-z.rate)<1e-8);
  }
  function validMove(r,v,expectedGap){
    if(!v)return false;
    if(!validDate(v.from_date)||v.to_date!==r.as_of||v.from_date>=v.to_date)
      return false;
    const diff=Math.round((Date.parse(v.to_date+"T12:00:00Z")-
      Date.parse(v.from_date+"T12:00:00Z"))/86400000);
    return v.same_contract===true&&v.same_expiration===true&&
      v.not_policy_rate===true&&Number.isFinite(v.change_bp)&&
      Number.isFinite(v.reference_rate_pct)&&
      Number.isFinite(v.current_rate_pct)&&
      Math.abs(v.current_rate_pct-r.rate_pct)<1e-8&&
      Math.abs((v.current_rate_pct-v.reference_rate_pct)*100-v.change_bp)<0.0002&&
      (expectedGap===7?diff===7:diff===1||diff===3);
  }
  function interpret(ccy,doc,shown){
    const empty={status:"NON_VERIFICABILE",matchedTenors:[],
      latestDate:null,latestTenors:[],olderTenors:[],
      narrative:"Nessuna lettura temporale: fonte o quotazioni non verificabili.",
      verified1D:0,verified1W:0,read_only:true,fx_signals:0,policy_deltas:0};
    if(!Object.hasOwn(NAMES,ccy)||!eligibleSidecar(doc))return empty;
    const matched=TENORS.filter(t=>currentParity(ccy,t,doc,shown));
    if(!matched.length)return {...empty,narrative:
      "Nessuna lettura: i contratti, le date o i tassi pubblicati non coincidono con i livelli visualizzati."};
    const latestDate=matched.map(t=>doc.currencies[ccy][t].as_of).sort().at(-1);
    const latest=matched.filter(t=>doc.currencies[ccy][t].as_of===latestDate);
    const older=matched.filter(t=>doc.currencies[ccy][t].as_of!==latestDate);
    const movements=latest.filter(t=>validMove(doc.currencies[ccy][t],
      doc.currencies[ccy][t].one_day,1));
    const weekly=latest.filter(t=>validMove(doc.currencies[ccy][t],
      doc.currencies[ccy][t].one_week,7));
    const parts=["Ultima data osservata: "+displayDate(latestDate)+"."];
    if(movements.length){
      parts.push("Movimento dello stesso contratto rispetto al precedente giorno feriale: "+
        movements.map(t=>LABEL[t]+" "+fmtBp(doc.currencies[ccy][t].one_day.change_bp))
          .join("; ")+".");
      if(movements.length>1){
        const vals=movements.map(t=>doc.currencies[ccy][t].one_day.change_bp);
        if(vals.every(v=>v<0))parts.push("I tassi impliciti dei contratti confrontabili sono scesi.");
        else if(vals.every(v=>v>0))parts.push("I tassi impliciti dei contratti confrontabili sono saliti.");
        else if(vals.some(v=>v>0)&&vals.some(v=>v<0))parts.push(
          "I tenori hanno direzioni differenti: non c'è una lettura uniforme del front-end.");
        else parts.push("Movimenti piccoli o misti: non emerge una direzione unica.");
      }
      if(movements.length===3){
        const short=Math.abs(doc.currencies[ccy]["3m"].one_day.change_bp);
        const longer=Math.abs(doc.currencies[ccy]["12m"].one_day.change_bp);
        if(longer>short+2)parts.push(
          "La variazione sul 12M è più ampia che sul 3M; è una divergenza tra contratti, non una previsione dei tassi ufficiali.");
      }
    } else parts.push("Manca il confronto verificato del precedente giorno feriale: nessun movimento 1D dedotto.");
    if(weekly.length)parts.push("Su sette giorni, stessa scadenza contrattuale: "+
      weekly.map(t=>LABEL[t]+" "+fmtBp(doc.currencies[ccy][t].one_week.change_bp))
        .join("; ")+".");
    if(older.length)parts.push(
      "Attenzione: "+older.map(t=>LABEL[t]+" fermo al "+
        displayDate(doc.currencies[ccy][t].as_of)).join("; ")+
      "; esclusi dalla lettura dell'ultima data.");
    if(matched.length<3)parts.push(
      "Altri tenori sospesi: lo storico non coincide con la fonte visualizzata.");
    parts.push("Sono movimenti di futures secondari: non dimostrano da soli un repricing Fed/BCE/BNS; servono OIS comparabili, eventi e conferma del mercato FX.");
    // Auditable metadata for the Rates/FX companion. Each 1D comparison has
    // already passed exact contract/date and mathematical source checks.
    const sourceDates=Object.fromEntries(matched.map(t=>[t,doc.currencies[ccy][t].as_of]));
    const oneDayBp=Object.fromEntries(matched.map(t=>[t,
      validMove(doc.currencies[ccy][t],doc.currencies[ccy][t].one_day,1)?
        doc.currencies[ccy][t].one_day.change_bp:null]));
    return {status:"LETTURA_DESCRITTIVA_FUTURES",matchedTenors:matched,
      latestDate,latestTenors:latest,olderTenors:older,sourceDates,oneDayBp,
      narrative:parts.join(" "),verified1D:movements.length,
      verified1W:weekly.length,read_only:true,fx_signals:0,policy_deltas:0};
  }
  return Object.freeze({interpret,fmtBp,validMove,currentParity});
});