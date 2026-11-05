/* FX Quant V2: source-dated, read-only 2Y / FX context for futures research.
 * No 2Y delta from an opaque displayed change field: reconstruct from dated
 * official history. ECB FX fixes are not simultaneous with futures settlements.
 * This is descriptive contextual evidence, NOT a policy/event/trading signal.
 */
(function(root, factory) {
  "use strict";
  const api=factory();
  if (typeof module==="object"&&module.exports) module.exports=api;
  if (root) root.FXV2OisRatesFxContext=api;
})(typeof window==="object"?window:null,function(){
  "use strict";
  const CCY=["USD","EUR","CHF"];
  const TENORS=["3m","6m","12m"];
  const d=s=>typeof s==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&
    Number.isFinite(Date.parse(s+"T12:00:00Z"));
  const days=(a,b)=>d(a)&&d(b)?Math.round((Date.parse(a+"T12:00:00Z")-
    Date.parse(b+"T12:00:00Z"))/86400000):null;
  const fmtDate=s=>d(s)?s.slice(8,10)+"/"+s.slice(5,7)+"/"+s.slice(0,4):"n.d.";
  const bp=v=>Number.isFinite(v)?
    (v>0?"+":v<0?"−":"")+Math.abs(v).toLocaleString("it-IT",{maximumFractionDigits:2})+" pb":"n.d.";
  const pct=v=>Number.isFinite(v)?
    (v>0?"+":v<0?"−":"")+Math.abs(v).toLocaleString("it-IT",
      {minimumFractionDigits:2,maximumFractionDigits:2})+"%":"n.d.";
  function rateTwoYear(ccy,rates,today){
    const v=rates?.[ccy],hist=v?.history2;
    const base={state:"NOT_VERIFIED",day:null,value:null,prevDay:null,changeBp:null,
      source:v?.source||null,declaredChangeBp:null,deltaMismatch:false};
    if(!v||!v.quality?.includes("OFFICIAL")||!d(v.date)||
       !d(today)||v.date>today||!Number.isFinite(v["2Y"])||
       !Array.isArray(hist?.dates)||!Array.isArray(hist?.values)||
       hist.dates.length<2||hist.dates.length!==hist.values.length)return base;
    const dates=hist.dates,values=hist.values,n=dates.length;
    if(dates[n-1]!==v.date||hist.last_date!==v.date||
       !Number.isFinite(values[n-1])||Math.abs(values[n-1]-v["2Y"])>0.000001||
       !d(dates[n-2])||dates[n-2]>=dates[n-1]||
       !Number.isFinite(values[n-2])||days(dates[n-1],dates[n-2])>4 ||
       !v.tenors?.some(t=>t.tenor==="2Y"&&t.date===v.date&&
         Number.isFinite(t.value)&&Math.abs(t.value-v["2Y"])<0.000001))return base;
    const observed=Math.round((values[n-1]-values[n-2])*100000)/1000;
    const declared=Number.isFinite(v.chg2_bp)?v.chg2_bp:null;
    return {state:days(today,v.date)>7?"DATED_HISTORICAL":"HISTORY_VERIFIED",
      day:v.date,value:v["2Y"],prevDay:dates[n-2],changeBp:observed,
      source:v.source,declaredChangeBp:declared,
      deltaMismatch:declared!==null&&Math.abs(observed-declared)>0.2};
  }
  function fxFixing(ccy,history,today){
    const base={state:"NOT_VERIFIED",pair:null,date:null,prevDate:null,level:null,
      changePct:null,subjectDirection:null};
    if(!CCY.includes(ccy)||history?.schema!=="GMFQ_ECB_G8_PRICE_HISTORY_V1"||
       history?.source!=="ECB euro foreign exchange reference rates"||
       !Array.isArray(history.rows)||history.rows.length<2||
       !d(today))return base;
    const rows=history.rows,now=rows.at(-1),prior=rows.at(-2);
    if(!d(now.Date)||!d(prior.Date)||now.Date>today||
      history.last_as_of!==now.Date||days(now.Date,prior.Date)<1||
      days(now.Date,prior.Date)>4||!Number.isFinite(now.USD)||
      !Number.isFinite(prior.USD)||!Number.isFinite(now.CHF)||
      !Number.isFinite(prior.CHF)||now.USD<=0||prior.USD<=0||
      now.CHF<=0||prior.CHF<=0)return base;
    // ECB fixing: USD and CHF per EUR. EUR/USD = USD per EUR.
    // EUR/CHF = CHF per EUR. Negative EUR/CHF means CHF appreciation.
    const pair=ccy==="CHF"?"EUR/CHF":"EUR/USD";
    const a=ccy==="CHF"?now.CHF:now.USD;
    const b=ccy==="CHF"?prior.CHF:prior.USD;
    const movement=Math.round(((a/b)-1)*1000000)/10000;
    let direction="invariato nel fixing";
    if(Math.abs(movement)>0.0001){
      const stronger=ccy==="USD"?(movement<0?"USD":"EUR"):
        ccy==="CHF"?(movement<0?"CHF":"EUR"):
          movement>0?"EUR":"USD";
      direction=stronger+" più forte nel fixing contro "+
        (stronger==="EUR"?(ccy==="CHF"?"CHF":"USD"):"EUR");
    }
    return {state:days(today,now.Date)>7?"DATED_HISTORICAL":"FIXING_VERIFIED",
      pair,date:now.Date,prevDate:prior.Date,level:a,changePct:movement,
      subjectDirection:direction,source:history.source};
  }
  function evaluate(ccy,reading,rates,history,today){
    const empty={status:"NOT_VERIFIED",rate:null,fx:null,aligned:[],
      rateText:"Rendimento 2Y non verificabile: nessuna conferma dei futures.",
      fxText:"Fixing valutario non verificabile.",summary:"Fonti insufficienti.",
      read_only:true,trade_signal:null,policy_probability:null};
    if(!CCY.includes(ccy)||!reading||
      reading.status!=="LETTURA_DESCRITTIVA_FUTURES"||
      !Array.isArray(reading.matchedTenors)||!d(reading.latestDate)||!d(today)||
      reading.latestDate>today)return empty;
    const rate=rateTwoYear(ccy,rates,today),fx=fxFixing(ccy,history,today);
    const aligned=rate.state==="HISTORY_VERIFIED"?
      reading.matchedTenors.filter(t=>TENORS.includes(t)&&
        reading.sourceDates?.[t]===rate.day&&
        Number.isFinite(reading.oneDayBp?.[t])):[];
    let rateText;
    if(rate.state==="HISTORY_VERIFIED"||rate.state==="DATED_HISTORICAL"){
      rateText="Governativo 2Y "+ccy+" "+rate.value.toLocaleString("it-IT",
        {maximumFractionDigits:3})+"% ("+fmtDate(rate.day)+"), variazione "+
        bp(rate.changeBp)+" calcolata dallo storico ("+fmtDate(rate.prevDay)+" → "+
        fmtDate(rate.day)+").";
      if(rate.deltaMismatch)rateText+=" ATTENZIONE: il campo Δ2Y del feed ("+
        bp(rate.declaredChangeBp)+") non coincide con lo storico; non lo utilizziamo.";
      if(rate.state==="DATED_HISTORICAL")rateText+=
        " Osservazione troppo datata per una conferma corrente.";
      else if(aligned.length){
        rateText+=" Futures della stessa data: "+aligned.map(t=>
          t.toUpperCase()+" "+bp(reading.oneDayBp[t])).join("; ")+
          ". Sono strumenti differenti: il confronto riguarda soltanto il segno del movimento.";
        const signs=aligned.map(t=>Math.sign(reading.oneDayBp[t]))
          .filter(x=>x!==0);
        const yr=Math.sign(rate.changeBp);
        if(yr!==0&&signs.length===aligned.length&&signs.length){
          rateText+=signs.every(s=>s===yr)?
            " Direzione concorde nelle scadenze confrontabili.":
            signs.every(s=>s===-yr)?
            " Direzione opposta nelle scadenze confrontabili.":
            " Direzioni non uniformi tra le scadenze confrontabili.";
        }
      }else rateText+=" Nessun movimento futures 1D della stessa data confrontabile con il 2Y.";
      if(rate.day!==reading.latestDate)rateText+=
        " ATTENZIONE: ultimo futures "+fmtDate(reading.latestDate)+
        ", 2Y "+fmtDate(rate.day)+": non sono osservazioni simultanee.";
    }else rateText="Governativo 2Y "+ccy+
      " senza storico o scadenza coerente verificati: nessuna conferma.";
    let fxText="Fixing FX BCE non verificabile per questa valuta.";
    if(fx.state!=="NOT_VERIFIED"){
      fxText="Fixing BCE "+fx.pair+" "+fx.level.toLocaleString("it-IT",
        {maximumFractionDigits:5})+" ("+fmtDate(fx.date)+"), "+
        pct(fx.changePct)+" rispetto al "+fmtDate(fx.prevDate)+
        ": "+fx.subjectDirection+".";
      if(fx.date!==reading.latestDate)fxText+=
        " Il fixing non ha la stessa data dell'ultimo futures.";
      else fxText+=" Stessa data di calendario, ma fixing BCE e futures non sono sincronizzati.";
    }
    return {status:"READ_ONLY_TRIANGULATION",rate,fx,aligned,
      rateText,fxText,
      summary:"Il 2Y non è un OIS. Il fixing BCE non è un prezzo di chiusura intraday sincronizzato: "+
       "co-movimento o divergenza descrittivi non dimostrano causalità, repricing della banca centrale "+
       "né un segnale FX.",read_only:true,trade_signal:null,policy_probability:null};
  }
  return Object.freeze({evaluate,rateTwoYear,fxFixing});
});