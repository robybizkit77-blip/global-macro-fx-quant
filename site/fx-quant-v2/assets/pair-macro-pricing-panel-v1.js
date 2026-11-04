/* FX Quant V2 — pair research view: reads source quotes without changing Core. */
(function(root){"use strict";
const ROOT="https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/";
let data=null,latest={pair:"EURUSD",p:null,macro:null};
const $=id=>document.getElementById(id);
const fmt=(n,d)=>Number.isFinite(n)?n.toLocaleString("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d}):"—";
const bp=v=>Number.isFinite(v)?(v>0?"+":"")+fmt(v,1)+" pb":"non verificata";
const date=v=>/^\d{4}-\d{2}-\d{2}$/.test(v||"")?v.slice(8,10)+"/"+v.slice(5,7)+"/"+v.slice(0,4):"n.d.";
const today=()=>new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Rome",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
function show(pair,p,macro){
 if(!$( "macroOisBridge" ))return;
 latest={pair,p,macro};
 const model=root.FXV2PairMacroPricing;
 const v=model?.view(data,pair);
 const a=pair.slice(0,3),b=pair.slice(3),observed=root.FXV2MacroPairResearch?.view(macro,pair,today());
 const ccy=(name,rows)=>name+" · "+["3m","6m","12m"].map(k=>{
  const h=rows?.[k];
  return k.toUpperCase()+" "+(h?fmt(h.rate,3)+"% · "+date(h.date)+" · "+h.kind+
   " · "+(h.origin==="feed"?"feed":"snapshot")+
   " · 1D "+bp(h.change_1d_bp)+" · 1W "+bp(h.change_1w_bp):
   "nessuna quotazione");
 }).join(" | ");
 $("macroOisPairTitle").textContent=a+"/"+b+" · dati osservati e pricing";
 $("macroOisMacroText").textContent="Motore FX, baseline 25/09/2026: "+
  (p?.macroSide?"Macro favorisce "+p.macroSide:"Macro senza lato netto")+"; "+
  (p?.policySide?"Rates/CB favoriscono "+p.policySide:"Rates/CB senza lato netto")+
  ". "+(observed?"Macro V3 verificata: vedi sopra la dinamica, che NON ricalcola il bias delle 28 coppie.":
  "Macro V3 non verificata: nessun nuovo bias dedotto.");
 $("macroOisMonitor").textContent=p?.macroSide&&p?.policySide&&p.macroSide!==p.policySide?
  "DIVERGENZA: Macro e Rates/CB canonici favoriscono valute diverse. Verifica front-end 6M, governativi 2Y e risposta del cambio, senza forzare un trade.":
  "Monitora variazioni 1D/1W realmente disponibili sulle due gambe, poi il 2Y e il prezzo. Un differenziale di livello non dimostra un repricing.";
 $("macroOisPricingTitle").textContent=a+" / "+b+" · 3M, 6M, 12M";
 $("macroOisBase").textContent=v?ccy(a,v.baseTenors):a+" · caricamento pricing / feed indisponibile";
 $("macroOisQuote").textContent=v?ccy(b,v.quoteTenors):b+" · caricamento pricing / feed indisponibile";
 $("macroOisGap").textContent=Number.isFinite(v?.sixMonthGapBp)?
  "6M "+a+" − "+b+": "+bp(v.sixMonthGapBp)+" (livello indicativo, non spread OIS omogeneo).":
  "6M · differenziale non calcolabile: manca una gamba";
 $("macroOisFreshness").textContent=v?.baseTenors?.["6m"]&&v?.quoteTenors?.["6m"]?
  "Data 6M: "+a+" "+date(v.baseTenors["6m"].date)+" / "+b+" "+date(v.quoteTenors["6m"].date)+
  " · "+(v.matchingDate?"stessa data":"DATE DIFFERENTI")+
  " · "+(v.matchingType?"categoria strumento simile; basis da verificare":"STRUMENTI DIVERSI")+
  ". Nessuna differenza delle variazioni 1D/1W calcolata.":"Data 6M non confrontabile; nessun repricing dedotto.";
 $("macroOisCaveat").textContent="Solo ricerca V2: futures, OIS e proxy con fonte e data specifiche. Nessuna probabilità di meeting, carry, nuovo punteggio o segnale FX, nessun backtest.";
}
async function get(path){
 const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),10000);
 try{const r=await fetch(path,{cache:"no-store",signal:ctrl.signal});if(!r.ok)throw Error("HTTP "+r.status);return await r.json();}
 finally{clearTimeout(timer);}
}
async function refresh(){
 const adapter=root.FXV2PairMacroPricing;
 if(!adapter)return;
 let snapshot=null;
 try{snapshot=await get("./ois-pricing-snapshot.json");}
 catch(e){console.warn("[FXV2 Pair] OIS dated snapshot unavailable",e);}
 const publish=(op,est,nzd)=>{
  data=adapter.build(snapshot,op,est,nzd,today());
  show(latest.pair,latest.p,latest.macro);
 };
 try{publish(null,null,null);}catch(e){console.warn("[FXV2 Pair] OIS fallback rejected",e);}
 const names=["OIS_OPERATIONAL_VIEW.json","CB_PRICING_ESTIMATED.json","NZD_CB_PRICING_DIRECTIONAL_PROXY.json"];
 const results=await Promise.allSettled(names.map(n=>get(ROOT+n)));
 try{publish(...results.map(x=>x.status==="fulfilled"?x.value:null));}
 catch(e){console.warn("[FXV2 Pair] live pricing rejected; existing fallback shown",e);}
}
root.FXV2PairMacroPricingBridge={show,refresh};
})(typeof window!=="undefined"?window:globalThis);
