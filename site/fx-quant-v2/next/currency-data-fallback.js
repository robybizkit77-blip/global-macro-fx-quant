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
   label:lead?(lead.label+' '+direction+' · '+lead.asof):'Crescita da verificare',
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
  return {status:'PROXY_INFORMATIVO',quality:'PROXY',label:Math.abs(h.rate).toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2})+'% · proxy',
   value:h.rate,asof,contract:h.contract,instrument:e.instrument||'futures datato',
   source:e.source||'quotazione secondaria',confidence:e.confidence_grade||null,
   description:'Contratto '+h.contract+' ('+(e.instrument||'futures datato')+
    '), quotazione indicativa '+h.rate.toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2})+'% al '+asof+
    '. Non è OIS ufficiale, non misura direttamente il tasso atteso della banca centrale e non fornisce un repricing settimanale verificato.'};
 }

 // Dated CHF/NZD historical observations may explain missing 2Y rows, but
 // are NEVER a certified weekly delta, OIS, or a substitute for live Core.
 const withheld=()=>({status:'NON_DISPONIBILE',label:'Non verificato',asof:null,
   description:'Nessun confronto 2Y di ricerca sufficientemente documentato.',
   eligibleForCore:false});
 function researchRatesAxis(ccy,chf,nzd,rates,now){
  if(!day(now))return withheld();
  const permitted=s=>s?.eligible_for_core===false&&
    s?.eligible_for_backtests===false&&s?.eligible_for_automatic_promotion===false&&
    s?.canonical_government_rates_untouched===true;
  if(ccy==='CHF'){
   const s=chf,observations=s?.observations;
   if(s?.schema!=='GMFQ_FXV2_CHF_SNB_PAIRED_HISTORY_V1'||
      s?.quality!=='SNB_OFFICIAL_OBSERVED_HISTORICAL_RESEARCH'||
      s?.source_url!=='https://data.snb.ch/api/cube/rendeiduebd/data/json/en'||
      s?.source_latest_vintage_not_point_in_time!==true||
      s?.current_session_government_rates_certified!==false||
      s?.eligible_for_fx_engine!==false||!permitted(s)||
      !Array.isArray(observations)||observations.length<2||
      s.observation_count!==observations.length||
      !day(s.anchor_date)||s.anchor_date!==observations[0]?.date||
      !day(s.last_observation_date)||s.last_observation_date!==observations.at(-1)?.date||
      !/^[a-f0-9]{64}$/.test(s.source_response_sha256||''))return withheld();
   const anchor=observations[0],latest=observations.at(-1),canonical=rates?.CHF;
   if(!canonical||canonical.date!==anchor.date||
      !num(canonical['2Y'])||!num(canonical['10Y'])||
      Math.abs(canonical['2Y']-anchor['2Y'])>.001||
      Math.abs(canonical['10Y']-anchor['10Y'])>.001||
      !goodResearchRows(observations,now)||!num(latest['2Y'])||
      !num(latest['10Y'])||!num(latest.curve_bp)||
      Math.abs((latest['10Y']-latest['2Y'])*100-latest.curve_bp)>.11||
      !(days(latest.date,now)>=0&&days(latest.date,now)<=45))return withheld();
   return {status:'STORICO_UFFICIALE_NON_OPERATIVO',
     label:latest['2Y'].toLocaleString('it-IT',{minimumFractionDigits:3,maximumFractionDigits:3})+'% · storico',
     asof:latest.date,quality:'SNB_SERIE_STORICA',
     description:'SNB: 2Y '+signed(latest['2Y'],3,'%')+' e 10Y '+
       signed(latest['10Y'],3,'%')+' osservati entrambi al '+latest.date+
       '. Serie spot ufficiale, ma l’ultima osservazione risale a '+days(latest.date,now)+
       ' giorni fa: NON è un rendimento live né una variazione settimanale recente. Non contribuisce alle conferme Forex.',
     eligibleForCore:false};
  }
  if(ccy==='NZD'){
   const s=nzd,observations=s?.daily_observations;
   if(s?.schema!=='GMFQ_NZD_RBNZ_B2_POSTROLL_WEB_RESEARCH_V1'||
      s?.status!=='PUBLIC_OFFICIAL_WEB_RESEARCH_NOT_XLSX_RECONCILED'||
      s?.source_url!=='https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates'||
      s?.source_capture_method!=='PUBLIC_OFFICIAL_PAGE_MANUAL_RESEARCH_NOT_AUTOMATED_FETCH'||
      s?.official_web_display_observed!==true||
      s?.independent_xlsx_reconciled!==false||
      s?.automated_access_authorized!==false||
      s?.historical_benchmark_roll_continuity!==false||
      s?.no_interpolation!==true||s?.research_only!==true||
      s?.eligible_for_fx_pair_engine!==false||!permitted(s)||
      !Array.isArray(observations)||observations.length<2||
      s?.benchmark_roll_date!=='2026-10-30'||
      s?.benchmark_2Y!=='April 2029'||s?.benchmark_10Y!=='April 2037'||
      s?.before_roll_2Y==='April 2029'||s?.before_roll_10Y==='April 2037'||
      observations[0]?.date!==s.benchmark_roll_date||
      !goodResearchRows(observations,now))return withheld();
   const latest=observations.at(-1),canonical=rates?.NZD;
   if(!canonical||!day(canonical.date)||canonical.date>=s.benchmark_roll_date||
      !day(s.source_release_date)||!day(s.source_capture_date)||
      s.source_release_date<latest.date||s.source_capture_date<latest.date||
      s.source_release_date>now||s.source_capture_date>now||
      !(days(latest.date,now)>=0&&days(latest.date,now)<=10))return withheld();
   return {status:'RICERCA_MANUALE_NON_CERTIFICATA',
     label:latest['2Y'].toLocaleString('it-IT',{minimumFractionDigits:3,maximumFractionDigits:3})+'% · ricerca',
     asof:latest.date,quality:'RBNZ_B2_WEB_NON_RICONCILIATO',
     description:'RBNZ B2: 2Y '+signed(latest['2Y'],3,'%')+' e 10Y '+
       signed(latest['10Y'],3,'%')+' al '+latest.date+
       ', titoli di riferimento April 2029/2037 dopo il cambio del 30 ottobre. Trascrizione manuale dalla pagina ufficiale; manca la riconciliazione XLSX. NON è un dato acquisito oggi, non è OIS e non prova un repricing monetario.',
     eligibleForCore:false};
  }
  return withheld();
 }
 function goodResearchRows(rows,now){
  return rows.every((r,i)=>day(r?.date)&&r.date<=now&&
    (i===0||r.date>rows[i-1].date)&&
    num(r['2Y'])&&num(r['10Y'])&&
    r['2Y']>=-5&&r['2Y']<=25&&r['10Y']>=-5&&r['10Y']<=25);
 }
  function evaluate({macroSeries,estimated,rates,chfResearch,nzdResearch,now}){
  if(!day(now))return {currencies:{},status:'DATA_NON_VALIDA',asof:now};
  const currencies=Object.fromEntries(FX.map(ccy=>[ccy,{
   growth:growthAxis(macroSeries,ccy,now),pricingProxy:pricingProxy(estimated,ccy,now),
   ratesResearch:researchRatesAxis(ccy,chfResearch,nzdResearch,rates,now)
  }]));
  return {currencies,status:'CONTESTO_INFORMATIVO',asof:now,
   policy:'Non modificare le serie ufficiali, le view operative, gli score o i backtest'};
 }
 const api={evaluate,growthAxis,pricingProxy,researchRatesAxis};
 root.FXQuantCurrencyFallback=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
