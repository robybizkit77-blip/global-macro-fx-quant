'use strict';
/*
 * FX Quant NEXT — G8 Economic Traffic Light.
 * Per-economy descriptive changes only, NEVER an NBER/recession forecast,
 * cross-country economic score, FX signal, or point-in-time release surprise.
 * Source: read-only live_data/sections/MACRO_SERIES.json.
 */
(function(root){
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const NAMES={USD:'Stati Uniti',EUR:'Area euro',GBP:'Regno Unito',JPY:'Giappone',
 CHF:'Svizzera',AUD:'Australia',NZD:'Nuova Zelanda',CAD:'Canada'};
const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',AUD:'🇦🇺',NZD:'🇳🇿',CAD:'🇨🇦'};
const AREAS=[
 {key:'house',name:'Immobiliare',short:'Case',why:'Domanda di abitazioni, costruzioni e credito casa. Gli stock di mutui non misurano da soli le nuove compravendite.'},
 {key:'jobs',name:'Lavoro',short:'Lavoro',why:'Occupazione e disoccupazione descrivono parti diverse del ciclo; livelli e assunzioni non sono sinonimi.'},
 {key:'industry',name:'Manifattura',short:'Industria',why:'Produzione industriale e ordini possono anticipare cambiamenti nella domanda, ma non sono il PIL.'},
 {key:'services',name:'Servizi',short:'Servizi',why:'Attività reale e indagini del settore terziario. La direzione dei sondaggi non coincide necessariamente con il livello di espansione o contrazione; inflazione dei servizi separata.'},
 {key:'leading',name:'Indicatore anticipatore',short:'Anticipatori',why:'Indici compositi e sondaggi misurano aspettative o condizioni, non il PIL realizzato.'},
 {key:'demand',name:'Consumi e domanda',short:'Consumi',why:'La domanda effettiva sostiene il ciclo. Se la serie è nominale, l’inflazione non è stata sottratta.'},
 {key:'credit',name:'Credito',short:'Credito',why:'Stock, condizioni e domanda di prestiti sono fenomeni differenti. Più stock non prova maggiore disponibilità di nuovo credito.'}
];
const M=(id,name,upGood,extra={})=>({id,name,upGood,...extra});
/* Whitelist explicit: no inferred signs or invented substitutes across G8.
 * kind=points for rates, surveys or GDP growth rates; default is level
 * with an absolute percentage change (not percent points).
 */
const MAP={
 USD:{
  house:[M('US_PERMIT_history_PERMIT','Permessi edilizi',true,{unit:'mila annualizzati'}),
         M('US_HOUST_history_HOUST','Nuovi cantieri',true,{unit:'mila annualizzati'})],
  jobs:[M('US_PAYEMS_history_value','Payrolls',true,{unit:'mila occupati'}),
        M('US_CCSA_history_CCSA','Sussidi continuativi',false,{scale:1000000,unit:'mln persone'})],
  industry:[M('US_INDPRO_history_value','Produzione industriale',true,{unit:'indice'}),
            M('US_NEWORDER_history_NEWORDER','Nuovi ordini core',true,{hideValue:true})],
  leading:[M('US_CFNAI_LEAD_INDICATOR_history_CFNAI','CFNAI',true,{kind:'points',minimum:.05,unit:'indice',pointUnit:'punti'})],
  demand:[M('US_PCEC96_history_value','Consumi reali',true,{unit:'mld USD reali SAAR'}),
          M('US_RRSFS_history_value','Vendite reali al dettaglio',true,{unit:'mln USD reali'})],
  credit:[M('US_SLOOS_CI_LARGE_MIDDLE_history_value','SLOOS: standard restrittivi',false,{kind:'points',minimum:1,unit:'saldo percentuale',pointUnit:'p.p.'}),
          M('US_TOTBKCR_history_value','Credito bancario totale',true,{unit:'mld USD'})]
 },
 EUR:{
  services:[M('EA_ECFIN_BCS_LEAD_INDICATORS_history_Services','Fiducia imprese dei servizi (DG ECFIN)',true,{kind:'points',minimum:.2,unit:'saldo fiducia',pointUnit:'punti',source_page:'https://economy-finance.ec.europa.eu/economic-forecast-and-surveys/business-and-consumer-surveys_en'})],
  jobs:[M('EA_UNEMP_history_value','Disoccupazione',false,{kind:'points',minimum:.05,unit:'%',pointUnit:'p.p.'}),
        M('EA_EMPLOYMENT_history_value','Occupati',true,{unit:'mila persone'})],
  industry:[M('EA_IP_history_value','Produzione industriale',true,{unit:'indice 2021=100'}),
            M('EA_ECFIN_BCS_LEAD_INDICATORS_history_Industry','Fiducia industria',true,{kind:'points',minimum:.2,hideValue:true,pointUnit:'punti'})],
  leading:[M('EA_ECFIN_BCS_LEAD_INDICATORS_history_ESI','Economic Sentiment Indicator',true,{kind:'points',minimum:.2,unit:'indice',pointUnit:'punti'})],
  demand:[M('EA_RETAIL_VOL_history_value','Vendite reali al dettaglio',true,{unit:'indice'})],
  credit:[M('EA_BLS_CREDIT_STANDARDS_ENTERPRISES_history_value','BLS: restrizione standard imprese',false,{kind:'points',minimum:1,unit:'saldo netto',pointUnit:'p.p.'})]
 },
 GBP:{
  house:[M('UK_MORTGAGE_APPROVALS_HOUSE_PURCHASE_SA_history_value','Mutui approvati per acquisto',true,{unit:'numero'})],
  jobs:[M('UK_UNEMP_RATE_history_value','Disoccupazione',false,{kind:'points',minimum:.05,unit:'%',pointUnit:'p.p.'}),
        M('UK_PAYE_PAYROLLED_EMPLOYEES_SA_history_value','Occupati in payroll PAYE',true,{unit:'persone'})],
  industry:[M('UK_PRODUCTION_history_value','Produzione industriale',true,{unit:'indice'})],
  leading:[M('UK_BOE_DMP_LEAD_INDICATORS_history_SalesExpected','DMP: vendite attese',true,{kind:'points',minimum:.2,hideValue:true,pointUnit:'punti'})],
  demand:[M('UK_RETAIL_VOL_history_value','Volumi vendite al dettaglio',true,{unit:'indice'})],
  credit:[M('UK_CCS_CORPORATE_CREDIT_AVAILABILITY_history_value','Disponibilità credito corporate',true,{kind:'points',minimum:1,unit:'saldo netto',pointUnit:'p.p.'})]
 },
 JPY:{
  services:[M('JP_BOJ_TANKAN_LEAD_INDICATORS_history_Large_Nonmanufacturing_Forecast','Tankan grandi imprese non manifatturiere — prospettive',true,{kind:'points',minimum:1,unit:'saldo sondaggio',pointUnit:'punti',freq:'Q',source_page:'https://www.boj.or.jp/en/statistics/tk/'})],
  jobs:[M('JP_UNEMP_RATE_history_value','Disoccupazione',false,{kind:'points',minimum:.05,unit:'%',pointUnit:'p.p.'}),
        M('JP_EMPLOYED_history_value','Occupati',true,{unit:'decine di migliaia persone'})],
  industry:[M('JP_IIP_history_value','Produzione industriale',true,{unit:'indice 2020=100'})],
  leading:[M('JP_BOJ_TANKAN_LEAD_INDICATORS_history_Large_Manufacturing_Forecast','Tankan manifattura: prospettive',true,{kind:'points',minimum:1,unit:'saldo sondaggio',pointUnit:'punti',freq:'Q'})],
  demand:[M('JP_RETAIL_history_value','Vendite al dettaglio',true,{unit:'indice 2020=100'})],
  credit:[M('JP_BANK_CREDIT_DOMESTIC_BANKS_history_value','Credito banche domestiche',true,{unit:'100 mln JPY'})]
 },
 CHF:{
  house:[M('CH_MORTGAGE_CREDIT_DOMESTIC_history_value','Credito ipotecario domestico',true,{unit:'mln CHF'})],
  jobs:[M('CH_UNEMP_RATE_history_value','Disoccupazione',false,{kind:'points',minimum:.05,unit:'%',pointUnit:'p.p.'}),
        M('CH_EMPLOYMENT_history_value','Occupati',true,{unit:'persone'})],
  industry:[M('CH_PRODUCTION_history_value','Produzione industriale',true,{unit:'indice'})],
  leading:[M('CH_SECO_CONSUMER_SENTIMENT_LEAD_history_SECO_Consumer_Sentiment','SECO: fiducia consumatori',true,{kind:'points',minimum:.2,unit:'saldo sondaggio',pointUnit:'punti',freq:'Q'})],
  demand:[M('CH_RETAIL_REAL_history_value','Vendite reali al dettaglio',true,{unit:'indice'})],
  credit:[M('CH_BANK_CREDIT_CUSTOMERS_history_value','Credito bancario ai clienti',true,{unit:'mln CHF'})]
 },
 AUD:{
  house:[M('AU_CREDIT_OWNER_OCC_HOUSING_SA_history_value','Credito mutui proprietari',true,{unit:'mld AUD'})],
  jobs:[M('AU_UNEMP_RATE_history_value','Disoccupazione',false,{kind:'points',minimum:.05,unit:'%',pointUnit:'p.p.'}),
        M('AU_EMPLOYMENT_history_value','Occupati',true,{unit:'mila persone'})],
  leading:[M('AU_OECD_CLI_LEAD_INDICATOR_history_OECD_CLI_AUS','OECD Composite Leading Indicator',true,{kind:'points',minimum:.05,unit:'indice',pointUnit:'punti'})],
  demand:[M('AU_HOUSEHOLD_SPENDING_history_value','Spesa famiglie nominale',true,{unit:'mln AUD nominali'})],
  credit:[M('AU_CREDIT_BUSINESS_CURRENT_SA_history_value','Credito alle imprese',true,{unit:'mld AUD'})]
 },
 NZD:{
  leading:[M('NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_Unemp_1Y','RBNZ: disoccupazione attesa a 1 anno',false,{kind:'points',minimum:.1,unit:'%',pointUnit:'p.p.',freq:'Q'})],
  jobs:[M('NZ_UNEMP_RATE_history_value','Disoccupazione',false,{kind:'points',minimum:.05,unit:'%',pointUnit:'p.p.'}),
        M('NZ_EMPLOYED_history_value','Occupati',true,{unit:'mila persone'})],
  demand:[M('NZ_RETAIL_VOLUME_Q_history_value','Volumi vendita al dettaglio',true,{unit:'mln NZD reali'})]
 },
 CAD:{
  house:[M('CA_MORTGAGE_OUTSTANDING_UNINSURED_history_value','Mutui non assicurati (stock)',true,{unit:'mln CAD'})],
  jobs:[M('CA_UNEMP_RATE_history_value','Disoccupazione',false,{kind:'points',minimum:.05,unit:'%',pointUnit:'p.p.'}),
        M('CA_EMPLOYMENT_history_value','Occupati',true,{unit:'mila persone'})],
  leading:[M('CA_BOC_BOS_LEAD_INDICATORS_history_BOS_Activity_Indicator','BoC BOS: attività attesa',true,{kind:'points',minimum:.1,unit:'saldo sondaggio',pointUnit:'punti',freq:'Q'})],
  demand:[M('CA_RETAIL_VOLUME_history_value','Volumi vendita al dettaglio',true,{unit:'mln CAD reali'})],
  credit:[M('CA_BUSINESS_LOANS_OUTSTANDING_history_value','Prestiti alle imprese',true,{unit:'mln CAD'})]
 }
};
const WAVE3_FRED_FALLBACK={
  "GBP": {
    "leading": [
      "GBRLOLITOAASTSAM",
      "https://fred.stlouisfed.org/series/GBRLOLITOAASTSAM"
    ]
  },
  "JPY": {
    "jobs": [
      "LRUNTTTTJPM156S",
      "https://fred.stlouisfed.org/series/LRUNTTTTJPM156S"
    ],
    "industry": [
      "JPNPRMNTO01GPSAM",
      "https://fred.stlouisfed.org/series/JPNPRMNTO01GPSAM"
    ],
    "demand": [
      "SLRTTO01JPQ657S",
      "https://fred.stlouisfed.org/series/SLRTTO01JPQ657S"
    ],
    "house": [
      "JPNRGDPPRI",
      "https://fred.stlouisfed.org/series/JPNRGDPPRI"
    ]
  },
  "CHF": {
    "house": [
      "QCHR368BIS",
      "https://fred.stlouisfed.org/series/QCHR368BIS"
    ],
    "industry": [
      "PRMNTO01CHQ657S",
      "https://fred.stlouisfed.org/series/PRMNTO01CHQ657S"
    ],
    "demand": [
      "SLRTTO01CHQ657S",
      "https://fred.stlouisfed.org/series/SLRTTO01CHQ657S"
    ]
  },
  "AUD": {
    "jobs": [
      "LRUNTTTTAUM156S",
      "https://fred.stlouisfed.org/series/LRUNTTTTAUM156S"
    ],
    "leading": [
      "AUSLOLITOAASTSAM",
      "https://fred.stlouisfed.org/series/AUSLOLITOAASTSAM"
    ]
  },
  "NZD": {
    "demand": [
      "SLRTTO01NZQ657S",
      "https://fred.stlouisfed.org/series/SLRTTO01NZQ657S"
    ]
  }
};
const VERIFIED_FRESH_FALLBACK={
 CHF:{credit:['SNB_BAKREDINAUSBM_AV1_I_T1_F','https://data.snb.ch/en/topics/banken/cube/bakredinausbm']},
 JPY:{credit:['BOJ_MD13_FAAPOBAL1_YOY','https://www.stat-search.boj.or.jp/ssi/mtshtml/md13_m_1_en.html']},
 NZD:{credit:['RBNZ_C5_BUSINESS_YOY','https://www.rbnz.govt.nz/statistics/series/lending-and-monetary/Registered-banks-and-non-bank-lending-institutions-sector-lending']},
 CAD:{
  house:['CAN_HOUSEHOLD_MORTGAGES_SA','https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610063901'],
  demand:['CAN_RETAIL_REAL_LASPEYRES','https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010006701'],
  credit:['CAN_NFC_NONMORTGAGE_LOANS_SA','https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610064001']
 },
 AUD:{
  demand:['ABS_MHSI_TOTAL_MONTHLY_SA','https://www.abs.gov.au/statistics/economy/finance/monthly-household-spending-indicator/latest-release']
 },
 USD:{
  house:['PERMIT','https://fred.stlouisfed.org/series/PERMIT'],
  industry:['INDPRO','https://fred.stlouisfed.org/series/INDPRO'],
  leading:['UMCSENT','https://fred.stlouisfed.org/series/UMCSENT'],
  demand:['PCEC96','https://fred.stlouisfed.org/series/PCEC96'],
  credit:['DRTSCILM','https://fred.stlouisfed.org/series/DRTSCILM']
 },
 GBP:{
  house:['BOE_LPMVTVX','https://www.bankofengland.co.uk/boeapps/database/BankStats.asp'],
  industry:['ONS_K222_DIOP','https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries/k222/diop']
 },
 EUR:{
  house:['EA21_PRC_HPI_Q_TOTAL_RCH_A','https://ec.europa.eu/eurostat/databrowser/view/prc_hpi_q/default/table?lang=en'],
  services:['TEIBS020_BS-SCI-BAL_SA_EA21','https://ec.europa.eu/eurostat/databrowser/view/teibs020/default/table?lang=en'],
  industry:['STS_INPR_M_EA21_PRD_B-D_SCA_I21','https://ec.europa.eu/eurostat/databrowser/view/sts_inpr_m/default/table?lang=en'],
  leading:['TEIBS010_EA21_BS-ESI-I_SA','https://ec.europa.eu/eurostat/databrowser/view/teibs010/default/table?lang=en'],
  demand:['STS_TRTU_M_EA21_VOL_SLS_G47_SCA_I21','https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table?lang=en']
 }
};
function verifiedFreshAlternative(x,c,key){
 if(c==='AUD'&&['house','credit'].includes(key)){
   return !!x&&x.quality==='SOURCE_REVISED_RESEARCH_NOT_PIT'&&
     x.source_series_id===(key==='house'?'RBA_HOUSING_CREDIT_GROWTH_MM':'RBA_BUSINESS_CREDIT_GROWTH_MM')&&
     /^https:\/\/www\.rba\.gov\.au\/statistics\/frequency\/fin-agg\/20\d{2}\/fin-agg-\d{4}\.html$/.test(x.source_page);
 }
 if(c==='NZD'&&key==='credit'&&x?.quality==='SOURCE_REVISED_RESEARCH_NOT_PIT'&&x.source_series_id==='RBNZ_PRIVATE_CREDIT_STOCK_TE'){
   return x.source_page==='https://tradingeconomics.com/new-zealand/private-sector-credit'&&x.metric_kind==='percent'&&x.unit==='mln NZD nominali';
 }
 if(c==='NZD'&&key==='credit'&&x?.quality==='SOURCE_VERIFIED_MANUAL_NONPIT'){
   return x.source_series_id==='RBNZ_C5_BUSINESS_YOY'&&x.source_page==='https://www.rbnz.govt.nz/statistics/series/lending-and-monetary/registered-banks-and-non-bank-lending-institutions-sector-lending';
 }
 if(c==='NZD'&&key==='house'){
   return !!x&&x.source_series_id==='STATSNZ_NEWDWELLINGS_SA'&&
     ['SOURCE_REVISED_RESEARCH_NOT_PIT','SOURCE_VERIFIED_MANUAL_NONPIT'].includes(x.quality)&&
     /^https:\/\/www\.stats\.govt\.nz\/information-releases\/building-consents-issued-(?:january|february|march|april|may|june|july|august|september|october|november|december)-20\d{2}\/$/.test(x.source_page);
 }
 const expected=VERIFIED_FRESH_FALLBACK[c]?.[key]||WAVE3_FRED_FALLBACK[c]?.[key];
 return !!expected&&x?.source_series_id===expected[0]&&x?.source_page===expected[1]&&
   x.quality==='SOURCE_REVISED_RESEARCH_NOT_PIT'&&x.up_good!==null;
}
const SUPPLEMENT_SCHEMA='GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1';
function supplementary(overlay,country,key,today){
 if(overlay?.schema!==SUPPLEMENT_SCHEMA||!Array.isArray(overlay.series))return null;
 const matches=overlay.series.filter(x=>x?.ccy===country&&x?.area===key&&
   (x?.quality==='SOURCE_REVISED_RESEARCH_NOT_PIT'||
    (country==='NZD'&&['services','house','credit'].includes(key)&&
     x?.quality==='SOURCE_VERIFIED_MANUAL_NONPIT'&&
     /^20\d{2}-\d{2}-\d{2}$/.test(x.manual_verified_on||'')&&x.manual_verified_on<=today&&
     parsePeriod(x.dates?.[1])&&
     (Date.parse(today+'T12:00:00Z')-Date.parse(parsePeriod(x.dates[1])+'T12:00:00Z'))/864e5<=110&&
     (key==='services'?x.diffusion_threshold===50:
       key==='credit'?x.diffusion_threshold==null&&x.source_series_id==='RBNZ_C5_BUSINESS_YOY'&&
         x.source_page==='https://www.rbnz.govt.nz/statistics/series/lending-and-monetary/registered-banks-and-non-bank-lending-institutions-sector-lending'&&
         /^20\d{2}-\d{2}-\d{2}$/.test(x.official_release_date||'')&&x.official_release_date<=x.manual_verified_on&&
         (Date.parse(today+'T12:00:00Z')-Date.parse(x.official_release_date+'T12:00:00Z'))/864e5<=38:
       x.diffusion_threshold==null&&x.source_page===
       'https://www.stats.govt.nz/information-releases/building-consents-issued-september-2026/')))&&
   /^[A-Z0-9_]+$/.test(x.id||'')&&
   ['M','Q'].includes(x.frequency)&&
   ['percent','points'].includes(x.metric_kind)&&
   Array.isArray(x.dates)&&Array.isArray(x.values)&&
   x.dates.length===2&&x.values.length===2&&x.values.every(v=>typeof v==='number'&&Number.isFinite(v))&&
   typeof x.source_page==='string'&&/^https:\/\/(?:fred\.stlouisfed\.org|ec\.europa\.eu|www150\.statcan\.gc\.ca|www\.ons\.gov\.uk|businessnz\.org\.nz|www\.abs\.gov\.au|www\.bankofengland\.co\.uk|www\.stats\.govt\.nz|www\.rba\.gov\.au|www\.stat-search\.boj\.or\.jp|www\.rbnz\.govt\.nz|data\.snb\.ch|www\.bnz\.co\.nz|tradingeconomics\.com)\//.test(x.source_page)&&
   (x.diffusion_threshold==null||(country==='NZD'&&key==='services'&&x.diffusion_threshold===50&&
    x.metric_kind==='points'&&(/^https:\/\/businessnz\.org\.nz\/psi(?:\/[a-z0-9-]+)?$/.test(x.source_page)||x.source_series_id==='BNZ_BUSINESSNZ_PSI'&&x.source_page==='https://www.bnz.co.nz/institutional-banking/research/publications'))));
 return matches.length===1?matches[0]:null;
}
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const fmt=(x,n=1)=>finite(x)?x.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
function parsePeriod(s){
 if(typeof s!=='string')return null;
 let m,y,month,day;
 const trim=s.trim();
 if((m=trim.match(/^(\d{4})-?Q([1-4])$/i))){
   y=Number(m[1]);month=Number(m[2])*3;day=new Date(Date.UTC(y,month,0)).getUTCDate();
 }else if((m=trim.match(/^(\d{4})[-/](\d{2})(?:-(\d{2}))?(?:T.*|\s.*)?$/))){
   y=Number(m[1]);month=Number(m[2]);day=m[3]?Number(m[3]):new Date(Date.UTC(y,month,0)).getUTCDate();
 }else if((m=trim.match(/^(\d{2})\/(\d{2})\/(\d{4})$/))){
   day=Number(m[1]);month=Number(m[2]);y=Number(m[3]);
 }else if((m=trim.match(/^(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})$/))){
   const mon=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].indexOf(m[2].toLowerCase());
   if(mon<0)return null;day=Number(m[1]);month=mon+1;y=Number(m[3]);
 }else if((m=trim.match(/^([A-Za-z]{3})[- ](\d{2})$/))){
   const mon=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].indexOf(m[1].toLowerCase());
   if(mon<0)return null;month=mon+1;y=2000+Number(m[2]);day=new Date(Date.UTC(y,month,0)).getUTCDate();
 }else return null;
 if(y<2000||month<1||month>12||day<1)return null;
 const dt=new Date(Date.UTC(y,month-1,day));
 if(dt.getUTCFullYear()!==y||dt.getUTCMonth()!==month-1||dt.getUTCDate()!==day)return null;
 return dt.toISOString().slice(0,10);
}
function recentTwo(series,today){
 if(!series||!Array.isArray(series.dates)||!Array.isArray(series.values)||
     series.dates.length!==series.values.length)return null;
 const distinct=new Map();
 series.dates.forEach((period,i)=>{
  const date=parsePeriod(period),value=series.values[i];
  if(date&&date<=today&&finite(value))distinct.set(date,{period,date,value});
 });
 const a=[...distinct.values()].sort((x,y)=>x.date.localeCompare(y.date));
 if(a.length<2)return null;
 return {cur:a.at(-1),pre:a.at(-2)};
}
function inspect(metric,source,today){
 const pair=recentTwo(source,today);
 if(!pair)return null;
 const c=pair.cur.value,p=pair.pre.value;
 const kind=metric.kind||'percent';
 const diff=c-p,pct=p===0?null:100*diff/Math.abs(p);
 const move=kind==='points'?diff:pct;
 const threshold=metric.minimum===undefined?.15:metric.minimum;
 const age=(Date.parse(today+'T12:00:00Z')-Date.parse(pair.cur.date+'T12:00:00Z'))/864e5;
 const gap=(Date.parse(pair.cur.date+'T12:00:00Z')-Date.parse(pair.pre.date+'T12:00:00Z'))/864e5;
 const freq=metric.freq||source.frequency||(/^(\d{4})-?Q[1-4]$/.test(pair.cur.period)?'Q':'M');
 const stale=age>(freq==='Q'?175:freq==='W'?42:85);
 const invalid=age>(freq==='Q'?300:freq==='W'?100:210)||
   gap>(freq==='Q'?200:freq==='W'?25:78);
 const verdict=invalid||stale||!finite(move)?null:Math.abs(move)<threshold?0:Math.sign(move)*(metric.upGood?1:-1);
 return {metric,period:pair.cur.period,prior:pair.pre.period,date:pair.cur.date,source:source.source_file||'MACRO_SERIES',
  current:c,previous:p,diff,pct,kind,verdict,stale,invalid,age:Math.round(age),freq};
}
function classify(items,needed){
 if(!needed)return {tone:'neutral',label:'Non classificabile',coverage:0};
 const valid=items.filter(x=>x&&x.verdict!==null);
 if(valid.length<needed)return {tone:'neutral',label:'Non classificabile',coverage:valid.length};
 const span=Math.max(...valid.map(x=>Date.parse(x.date)))-Math.min(...valid.map(x=>Date.parse(x.date)));
 if(span>120*86400000)return {tone:'neutral',label:'Non allineato',coverage:valid.length};
 const signs=valid.map(x=>x.verdict);
 const tone=signs.every(v=>v===1)?'green':signs.every(v=>v===-1)?'red':'amber';
 return {tone,label:{green:'Verde',red:'Rosso',amber:'Giallo'}[tone],coverage:valid.length};
}
function model(catalog,today,country='USD',overlay=null){
 const c=FX.includes(country)?country:'USD';
 const rows=Array.isArray(catalog?.[c])?catalog[c]:[];
 const sources=new Map(rows.map(x=>[x.id,x]));
 return AREAS.map(area=>{
   const metrics=MAP[c]?.[area.key]||[];
   const original=metrics.map(metric=>inspect(metric,sources.get(metric.id),today));
   const baseline=classify(original,metrics.length);
   const extra=supplementary(overlay,c,area.key,today);
   const originalLatest=original.reduce((latest,item)=>item?.date&&item.date>latest?item.date:latest,'');
   const latestExtra=extra?.dates?.[1] ? parsePeriod(extra.dates[1]):null;
   const officialAlternative=verifiedFreshAlternative(extra,c,area.key);
   const missingOriginal=metrics.length===0;
   const newerValid=(missingOriginal||officialAlternative&&(
       baseline.tone==='neutral'||(c==='EUR'&&area.key==='services'&&latestExtra>originalLatest)));
   let supplement=null;
   if(extra&&newerValid){
     const src={...extra,source_file:extra.source_file+
       (extra.quality==='SOURCE_VERIFIED_MANUAL_NONPIT'?' · dato verificato manualmente, non aggiornato automaticamente':
         ' · aggiornamento dal feed supplementare')};
     const metric=M(extra.id,extra.label,extra.up_good!==false,{unit:extra.unit,
       kind:extra.metric_kind,minimum:extra.metric_kind==='points'?(area.key==='jobs'||area.key==='leading'?.05:.2):.15,
       pointUnit:extra.unit.startsWith('%')?'p.p.':'punti',
       freq:extra.frequency,source_page:extra.source_page,
       diffusionThreshold:extra.diffusion_threshold===50?50:null});
     supplement=inspect(metric,src,today);
   }
   const promoted=!!supplement&&supplement.verdict!==null;
   const items=promoted?[supplement,...original]:original;
   return {...area,items,expected:promoted?1:metrics.length,
     signal:promoted?classify([supplement],1):baseline,
     signalSource:promoted?(metrics.length?'fallback':'new'):'original',
     proxy:promoted&&
        (extra.label.toLowerCase().includes('proxy')||extra.label.toLowerCase().includes('survey')||
          extra.label.toLowerCase().includes('fiducia'))};
 });
}
function render({catalog={},dayNow,country='USD',overlay=null,esc=(x)=>String(x??'')}={}){
 const today=dayNow?.()||'';
 if(!/^\d{4}-\d{2}-\d{2}$/.test(today))return '';
 const selected=FX.includes(country)?country:'USD';
 const universe=Object.fromEntries(FX.map(ccy=>[ccy,model(catalog,today,ccy,overlay)]));
 const rows=universe[selected];
 const d=(v,suffix='')=>finite(v)?(v>0?'+':v<0?'−':'')+fmt(Math.abs(v),2)+suffix:'—';
 const measure=x=>{
  if(!x)return '<span class="sem-missing">Serie assente oppure periodi non confrontabili</span>';
  const scaled=x.metric.scale?x.current/x.metric.scale:x.current;
  const prior=x.metric.scale?x.previous/x.metric.scale:x.previous;
  const digits=x.metric.scale?2:x.kind==='points'?2:Math.abs(scaled)>=100?0:1;
  const unit=esc(x.metric.unit||'unità della fonte');
  const diff=x.kind==='points'?d(x.diff,' '+(x.metric.pointUnit||'punti')):d(x.pct,'%');
  const tone=x.verdict===null?'neutral':x.verdict>0?'green':x.verdict<0?'red':'amber';
  const diffusion=x.metric.diffusionThreshold===50?
   '<span class="sem-psi-regime">'+(x.current>50?'Livello: espansione (PSI sopra 50)':x.current<50?'Livello: contrazione (PSI sotto 50)':'Livello: soglia neutrale 50')+
   ' · Direzione: '+(x.verdict===null?'non classificabile':x.diff>.2?'indice in accelerazione':x.diff<-.2?'indice in rallentamento':'indice stabile')+
   '</span>':'';
  const value=(v,p,label)=>'<div class="sem-value"><small>'+label+' · '+esc(p)+'</small><strong>'+fmt(v,digits)+'</strong><span>'+unit+'</span></div>';
  return '<div class="sem-measure '+tone+'"><div class="sem-measure-title"><strong>'+esc(x.metric.name)+'</strong></div>'+
   '<div class="sem-value-grid'+(x.metric.hideValue?' sem-value-hidden':'')+'">'+
   (x.metric.hideValue?'<div class="sem-value"><small>Confronto</small><strong class="sem-period-pair">'+esc(x.prior)+' → '+esc(x.period)+'</strong></div>':value(scaled,x.period,'Attuale')+value(prior,x.prior,'Precedente'))+
   '<div class="sem-value sem-change"><small>Variazione</small><strong class="'+tone+'">'+esc(diff)+'</strong><span>'+({green:'Favorevole',red:'Sfavorevole',amber:'Quasi stabile',neutral:'Non classificabile'}[tone])+'</span></div></div>'+
   '<small class="sem-source-note">'+esc(x.source)+(x.stale?' · dato datato':'')+(x.invalid?' · confronto sospeso':'')+'</small>'+diffusion+
   (x.metric.source_page?'<a class="sem-src-link" href="'+esc(x.metric.source_page)+'" target="_blank" rel="noopener noreferrer">Fonte e metodologia ↗</a>':'')+'</div>';
 };
 const servicePriceContext=selected==='EUR'?(catalog?.EUR||[]).find(x=>x.id==='EA_HICP_SERVICES_YOY_history_value'):null;
 const svcPrices=servicePriceContext?recentTwo(servicePriceContext,today):null;
 const svcPriceNote=svcPrices?'<p class="sem-services-price"><strong>Inflazione servizi (contesto, fuori dal semaforo):</strong> '+esc(fmt(svcPrices.cur.value,1))+'% YoY · '+esc(svcPrices.cur.period)+' (prima '+esc(fmt(svcPrices.pre.value,1))+'%). Prezzi e attività sono fenomeni diversi.</p>':'';
 const noData=rows.every(x=>x.signal.tone==='neutral');
 const red=rows.filter(x=>x.signal.tone==='red').map(x=>x.name.toLowerCase());
 const green=rows.filter(x=>x.signal.tone==='green').map(x=>x.name.toLowerCase());
 const unavailable=rows.filter(x=>x.signal.tone==='neutral').length;
 const intro=noData?'Nelle osservazioni disponibili non emerge un quadro ciclico sufficientemente classificabile.':
   (red.length?'Le ultime variazioni mostrano deterioramento in '+red.join(' e ')+'. ':'')+
   (green.length?'Si osserva un miglioramento in '+green.join(' e ')+'. ':'')+
   (unavailable?'Alcune aree restano senza segnale affidabile.':'Nelle altre aree il quadro è misto o stabile.');
 const sectorSummary=(key,label)=>{
  const a=rows.find(x=>x.key===key);
  const tone=a?.signal.tone||'neutral';
  const wording={green:'migliora',red:'peggiora',amber:'misto o stabile',neutral:'dato insufficiente'}[tone];
  const item=a?.items?.find(x=>x&&x.verdict!==null);
  const level=item?.metric?.diffusionThreshold===50?
    (item.current>50?' · PSI sopra 50: espansione':item.current<50?' · PSI sotto 50: contrazione':' · PSI a 50: soglia neutrale'):'';
  return '<div class="sem-sector-compare-item"><strong>'+esc(label)+'</strong><span class="'+tone+'">'+esc(wording)+
   '</span><small>'+esc(item?.period||'senza periodo valido')+esc(level)+'</small></div>';
 };
 const readingFor=r=>{
   if(r.signal.tone==='neutral')return 'Le osservazioni disponibili non consentono un giudizio direzionale affidabile.';
   const active=(r.signalSource==='original'?r.items:r.items.slice(0,1)).filter(x=>x&&x.verdict!==null);
   if(!active.length)return 'Nessun confronto valido.';
   const clauses=active.map(x=>{
     const m=x.kind==='points'?x.diff:x.pct;
     return x.metric.name+': '+(m>0?'aumenta':m<0?'diminuisce':'resta invariato')+(m!==0?' ('+d(m,x.kind==='points'?' '+(x.metric.pointUnit||'punti'):'%')+')':'');
   });
   const judgment={green:'Segnale di miglioramento rispetto alle osservazioni precedenti.',red:'Segnale di deterioramento rispetto alle osservazioni precedenti.',amber:'Il quadro è misto o le variazioni sono contenute.'}[r.signal.tone];
   return clauses.join('; ')+'. '+judgment;
 };
 const bank={USD:'Fed',EUR:'BCE',GBP:'BoE',JPY:'BoJ',CHF:'SNB',AUD:'RBA',NZD:'RBNZ',CAD:'BoC'}[selected];
 const tones={green:'Migliora',red:'Peggiora',amber:'Stabile / misto',neutral:'Non classificabile'};
 const symbols={green:'↗',red:'↘',amber:'→',neutral:'—'};
 const allRows=Object.values(universe).flat();
 const covered=allRows.filter(a=>a.signal.tone!=='neutral').length;
 const tally=(items,tone)=>items.filter(a=>a.signal.tone===tone).length;
 const dots=area=>{
   const q=area.signal;
   return '<span class="sem-mini sem-cell '+q.tone+'" title="'+esc(area.name+' · '+tones[q.tone])+'" aria-label="'+esc(tones[q.tone])+'"><span aria-hidden="true">'+symbols[q.tone]+'</span></span>';
 };
 const hasStale=rows.some(x=>x.items.some(z=>z?.stale));
 const hasManual=rows.some(x=>x.items.some(z=>z?.source?.includes('verificato manualmente')));
 return '<section class="recession-light" aria-labelledby="recession-light-title">'+
  '<header class="sem-head"><div><span class="sem-kicker">GLOBAL MACRO / G8 / LETTURA CICLICA</span>'+
  '<h2 id="recession-light-title">Il semaforo economico</h2>'+
  '<p>'+esc(NAMES[selected]+': '+intro)+' Segnali direzionali descrittivi, non probabilità di recessione.</p></div>'+
  '<span class="sem-date">Consultazione '+esc(today)+' · periodi originali in tabella</span></header>'+
  '<div class="sem-overview"><div class="sem-overview-coverage"><span>Copertura dati G8</span><strong>'+covered+'<small>/56</small></strong><div class="sem-coverage-track" role="progressbar" aria-label="Copertura G8" aria-valuenow="'+covered+'" aria-valuemin="0" aria-valuemax="56"><i style="width:'+(covered/56*100)+'%"></i></div></div>'+['green','amber','red','neutral'].map(t=>'<div class="sem-overview-kpi '+t+'"><span>'+tones[t]+'</span><strong>'+tally(allRows,t)+'</strong></div>').join('')+'</div>'+
  '<div class="sem-g8-title"><strong>Otto economie, sette aree</strong><span>Seleziona un Paese. I colori non sono un ranking di forza FX.</span></div>'+
  '<div class="sem-g8-scroll"><table class="sem-g8-table"><thead><tr><th scope="col">Paese</th>'+
  AREAS.map(a=>'<th scope="col">'+esc(a.short)+'</th>').join('')+'</tr></thead><tbody>'+
  FX.map(c=>'<tr'+(c===selected?' class="selected"':'')+'><th scope="row"><button type="button" class="sem-g8-pick" data-ms-country="'+c+'" aria-pressed="'+String(c===selected)+'">'+
   FLAGS[c]+' '+c+'</button></th>'+universe[c].map(a=>'<td>'+dots(a)+'</td>').join('')+'</tr>').join('')+
  '</tbody></table></div>'+
  '<div class="sem-legend">'+['green','amber','red','neutral'].map(t=>'<span class="sem-legend-item"><span class="sem-mini sem-cell '+t+'" aria-hidden="true">'+symbols[t]+'</span>'+tones[t]+'</span>').join('')+'</div>'+
  '<div class="sem-sector-compare" aria-label="Industria e servizi a confronto"><p>Industria e servizi · direzione del ciclo</p><div class="sem-sector-compare-grid">'+
    sectorSummary('industry','Manifattura')+sectorSummary('services','Servizi')+'</div>'+
    '<small>La direzione non è il livello: un PSI sopra 50 può rallentare pur restando in espansione. Non confrontare i livelli di serie differenti.</small></div>'+
  '<div class="sem-country-caption"><div>'+FLAGS[selected]+' <strong>'+esc(NAMES[selected])+'</strong><small>Dettaglio per indicatore</small></div><div class="sem-country-counts">'+['green','amber','red','neutral'].map(t=>'<span class="sem-country-count '+t+'" title="'+tones[t]+'">'+symbols[t]+' '+tally(rows,t)+'</span>').join('')+'</div></div>'+
  '<div class="sem-table" role="table" aria-label="Semaforo economico '+esc(NAMES[selected])+'">'+
  '<div class="sem-columns" role="row"><span role="columnheader">Area</span><span role="columnheader">Ultima evidenza disponibile</span><span role="columnheader">Segnale</span></div>'+
  rows.map(r=>'<div class="sem-row '+r.signal.tone+'" role="row"><div role="cell" class="sem-area"><strong>'+esc(r.name)+'</strong><span class="sem-area-reading">'+esc(tones[r.signal.tone])+'</span><small>'+esc(r.why)+'</small></div>'+
    '<div class="sem-evidence" role="cell"><div class="sem-area-judgment"><span>Cosa sta cambiando</span><p>'+esc(readingFor(r))+'</p></div>'+(r.items.length?(r.signalSource==='fallback'?measure(r.items[0])+'<details class="sem-history"><summary>Altre serie di contesto ('+(r.items.length-1)+')</summary>'+r.items.slice(1).map(measure).join('')+'</details>':r.items.map(measure).join('')):'<span class="sem-missing">Nessuna serie idonea nel feed attuale</span>')+(r.key==='services'?svcPriceNote:'')+'</div>'+
    '<div class="sem-signal" role="cell"><span class="sem-pill '+r.signal.tone+'"><i aria-hidden="true"></i>'+esc(tones[r.signal.tone])+'</span>'+
    (r.items.length===1?'<small>Un solo indicatore</small>':'')+
    (r.signalSource==='fallback'?'<small>Segnale da fonte supplementare aggiornata; serie precedenti nel dettaglio</small>':'')+
    (r.proxy?'<small>Proxy/sondaggio, non misura esaustiva del ciclo</small>':'')+
    (r.items.some(x=>x?.stale)?'<small>Osservazioni datate</small>':'')+'</div></div>').join('')+'</div>'+
  '<div class="sem-policy"><div><span>POLITICA MONETARIA · DA LEGGERE A PARTE</span>'+
  '<p>'+bank+' e aspettative sui tassi possono amplificare o attenuare le pressioni cicliche: non sono però un indicatore diretto di recessione né una prova di movimento del cambio.</p></div>'+
  '<a href="#rates">Apri tassi & OIS ↗</a></div>'+
  '<details class="sem-method"><summary>Metodo, soglie e fonti</summary><p class="sem-foot">Metodo: ogni indicatore confronta le sue ultime due osservazioni disponibili; verde indica miglioramento direzionale, rosso peggioramento, giallo quadro misto o quasi invariato, azzurro dati mancanti, troppo vecchi, non consecutivi o non sufficientemente allineati. '+
  'Le soglie descrittive evitano piccoli movimenti: ±0,15% per i livelli e soglie in punti esplicite per tassi, sondaggi e indicatori compositi. Le osservazioni oltre la soglia di anzianità sono visibili ma non producono semafori direzionali. '+
  (hasStale?'Sono presenti osservazioni datate: non interpretare i colori come fotografia intraday. ':'')+
  (hasManual?'Sono presenti rilevazioni ufficiali verificate manualmente: la data del dato è esplicita e i segnali scadono se non vengono aggiornati. ':'')+
  'La matrice confronta direzioni, NON livelli omogenei o cicli sincronizzati. La colonna Servizi misura il momentum dell’attività o dei suoi proxy e distingue il livello di espansione/contrazione SOLO per un indice di diffusione con soglia documentata a 50 (es. PSI BusinessNZ). Non misura l’inflazione dei servizi. Prezzi nominali, saldi di survey, stock di credito e PIL sono strumenti diversi. '+
  'I periodi mostrati NON equivalgono alle date di pubblicazione. Fonti: MACRO_SERIES.json e semaforo supplementare, dati potenzialmente revisionati (non point-in-time); nessuna previsione NBER, sorpresa rispetto al consenso, ranking valutario o segnale di trading.</p></details>'+
  '</section>';
}
root.FXQuantRecessionLight={render,model,parsePeriod,coverage:FX};
if(typeof module!=='undefined'&&module.exports)module.exports={render,model,parsePeriod,coverage:FX};
})(typeof window!=='undefined'?window:globalThis);
