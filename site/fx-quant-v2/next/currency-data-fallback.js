'use strict';
/**
 * FX Quant NEXT G8 source bridge — descriptive history + quarantined proxies.
 * Never promotes secondary quotes to official OIS; never fabricates a GDP
 * nowcast, 6M repricing, an FX score or a new official release.
 * Input series have observation-period dates, not certified release timestamps.
 */
(function(root){
 const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
 const preferred={
  USD:['US_PCEC96_history_value','US_INDPRO_history_value'],
  EUR:['EA_RETAIL_VOL_history_value','EA_IP_history_value'],
  GBP:['UK_RETAIL_VOL_history_value','UK_PRODUCTION_history_value'],
  JPY:['JP_RETAIL_history_value','JP_IIP_history_value'],
  CHF:['CH_RETAIL_REAL_history_value','CH_PRODUCTION_history_value'],
  AUD:['AU_REAL_GDP_QOQ_ABS_history_value','AU_HOUSEHOLD_SPENDING_history_value'],
  NZD:['NZ_REAL_GDP_Q_history_value','NZ_RETAIL_VOLUME_Q_history_value'],
  CAD:['CA_REAL_GDP_M_history_value','CA_RETAIL_VOLUME_history_value']
 };
 const num=v=>typeof v==='number'&&Number.isFinite(v);
 const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&!Number.isNaN(Date.parse(x+'T00:00:00Z'));
 const month=x=>typeof x==='string'&&/^\d{4}-(0[1-9]|1[0-2])(?:-\d{2})?$/.test(x);
 const months=(a,b)=>month(a)&&month(b)?(Number(b.slice(0,4))-Number(a.slice(0,4)))*12+
  Number(b.slice(5,7))-Number(a.slice(5,7)):null;
 const days=(a,b)=>day(a)&&day(b)?(Date.parse(b+'T00:00:00Z')-Date.parse(a+'T00:00:00Z'))/86400000:null;
 const signed=(v,n=1,unit='')=>num(v)?(v>0?'+':v<0?'−':'')+
  Math.abs(v).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n})+unit:'—';
 function growthAxis(series,ccy,now){
  const all=Array.isArray(series?.[ccy])?series[ccy]:[];
  const selections=(preferred[ccy]||[]).map(id=>all.find(s=>s?.id===id)).filter(Boolean);
  const facts=[];
  for(const s of selections){
   if(!Array.isArray(s.dates)||!Array.isArray(s.values)||s.dates.length!==s.values.length)continue;
   const points=s.dates.map((period,i)=>({period,value:s.values[i]}))
    .filter(p=>month(p.period)&&p.period.slice(0,7)<=now.slice(0,7)&&num(p.value))
    .sort((a,b)=>a.period.localeCompare(b.period));
   const last=points.at(-1),prev=points.at(-2);
   if(!last||!prev||last.period===prev.period)continue;
   const m=months(last.period,now),gap=months(prev.period,last.period);
   const quarterly=s.frequency==='Q',maxAge=quarterly?8:5,maxGap=quarterly?6:3;
   if(m===null||m<0||m>maxAge||gap===null||gap<1||gap>maxGap)continue;
   const levelRate=/(?:%|percent)/i.test(String(s.unit||''))||
      /(?:qoq|yoy|y\/y)/i.test(String(s.label||''));
   const change=levelRate?last.value-prev.value:
     (prev.value!==0?(last.value/prev.value-1)*100:null);
   if(!num(change))continue;
   const move=change>0.03?'sale':change<-.03?'scende':'è stabile';
   facts.push({id:s.id,label:s.label,asof:last.period,previous:prev.period,
     latest:last.value,previousValue:prev.value,change,frequency:s.frequency||'',
     unit:levelRate?'punti percentuali':'%',kind:levelRate?'rate':'level',
     source:s.source_file||null,quality:'SERIE_STORICA',
     labelChange:s.label+' '+move+' ('+signed(change,2,levelRate?' pp':'%')+
       ', '+last.period+')'});
  }
  const lead=facts[0]||null,alt=facts[1]||null;
  const direction=lead?
   lead.change>.03?'↑':lead.change<-.03?'↓':'→':'—';
  return {status:lead?'STORICO_DESCRITTIVO':'NON_DISPONIBILE',
   label:lead?(lead.label+' '+direction):'Crescita da verificare',
   description:lead?lead.labelChange+
      (alt?' · '+alt.labelChange:'')+
      '. Queste sono variazioni delle ultime osservazioni disponibili, non PIL stimato, sorprese di mercato o dati pubblicati oggi.':
      'Non ci sono due osservazioni recenti e omogenee delle serie crescita selezionate.',
   observations:facts,quality:lead?'SERIE_STORICA':'NON_DISPONIBILE',
   // Forecast/nowcast requires an explicit validated model and publication vintages.
   forecastValue:null,forecastQuality:'NON_CALCOLATO'};
 }
 function pricingProxy(estimated,ccy,now){
  const e=estimated?.currencies?.[ccy];
  const h=e?.horizons?.['6m'];
  const asof=e?.as_of,age=days(asof,now);
  const valid=e?.status==='ESTIMATED_ACTIVE'&&
    e.input_mode==='LIVE_SECONDARY_OVERLAY'&&
    e.method_id==='TRADINGVIEW_DATED_FUTURES_SSR_V2'&&
    e.source_quality==='SECONDARY_PUBLIC_LIVE_PROXY'&&
    e.governance?.informational_only===true&&
    e.governance?.core_score_effect==='NONE'&&
    e.governance?.pair_engine_effect==='NONE'&&
    e.policy_repricing_inference_allowed===false&&
    h?.quote_timestamp_verified===true&&h?.quote_as_of===asof&&
    h?.raw_level_gap_not_policy_repricing===true&&
    typeof h.contract==='string'&&!h.contract.includes('!')&&
    num(h.rate)&&num(age)&&age>=0&&age<=7;
  if(!valid)return {status:'NON_DISPONIBILE',quality:'NON_DISPONIBILE',
   label:'Proxy non utilizzabile',asof:null,
   description:'Manca una quotazione alternativa a sei mesi con contratto, data e qualità verificabili. Non sostituiamo il dato con una previsione arbitraria.'};
  return {status:'PROXY_INFORMATIVO',quality:'PROXY',label:signed(h.rate,2,'%')+' · proxy',
   value:h.rate,asof,contract:h.contract,instrument:e.instrument||'futures datato',
   source:e.source||'quotazione secondaria',confidence:e.confidence_grade||null,
   description:'Contratto '+h.contract+' ('+(e.instrument||'futures datato')+
    '), quotazione indicativa '+signed(h.rate,2,'%')+' al '+asof+
    '. Non è OIS ufficiale, non misura direttamente il tasso atteso della banca centrale e non fornisce un repricing settimanale verificato.'};
 }
 function evaluate({macroSeries,estimated,now}){
  if(!day(now))return {currencies:{},status:'DATA_NON_VALIDA',asof:now};
  const currencies=Object.fromEntries(FX.map(ccy=>[ccy,{
   growth:growthAxis(macroSeries,ccy,now),pricingProxy:pricingProxy(estimated,ccy,now)
  }]));
  return {currencies,status:'CONTESTO_INFORMATIVO',asof:now,
   policy:'Non modificare le serie ufficiali, le view operative, gli score o i backtest'};
 }
 const api={evaluate,growthAxis,pricingProxy};
 root.FXQuantCurrencyFallback=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
