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
     (/^https:\/\/www\.rba\.gov\.au\/statistics\/frequency\/fin-agg\/20\d{2}\/fin-agg-\d{4}\.html$/.test(x.source_page)||
      x.source_page==='https://www.rba.gov.au/statistics/tables/csv/d1-data.csv'&&x.frequency==='M'&&x.metric_kind==='points'&&x.unit==='% m/m SA');
 }
 if(c==='NZD'&&key==='credit'&&x?.quality==='SOURCE_REVISED_RESEARCH_NOT_PIT'&&x.source_series_id==='RBNZ_PRIVATE_CREDIT_STOCK_TE'){
   return x.source_page==='https://tradingeconomics.com/new-zealand/private-sector-credit'&&x.metric_kind==='percent'&&x.unit==='mln NZD nominali';
 }
 if(c==='NZD'&&key==='credit'&&x?.quality==='SOURCE_VERIFIED_MANUAL_NONPIT'){
   return x.source_series_id==='RBNZ_C5_BUSINESS_YOY'&&x.source_page==='https://www.rbnz.govt.nz/statistics/series/lending-and-monetary/registered-banks-and-non-bank-lending-institutions-sector-lending';
 }
 if(c==='NZD'&&key==='leading'){
   return x?.source_series_id==='ANZ_NZD_OWN_ACTIVITY_OUTLOOK_ROUNDED'&&
     x.source_page==='https://www.anz.co.nz/about-us/economic-markets-research/business-outlook/'&&
     x.quality==='SOURCE_REVISED_RESEARCH_NOT_PIT'&&x.frequency==='M'&&x.metric_kind==='points'&&
     x.unit==='saldo netto %'&&x.history?.quality==='ROUNDED_RELEASE_SUMMARIES_NOT_SINGLE_VINTAGE'&&
     x.values?.every(v=>finite(v)&&Math.abs(v)<=100);
 }
 if(c==='NZD'&&key==='house'){
   if(x?.source_series_id==='QNZR368BIS')return x.source_page==='https://fred.stlouisfed.org/series/QNZR368BIS'&&
     x.quality==='SOURCE_REVISED_RESEARCH_NOT_PIT'&&x.frequency==='Q'&&x.metric_kind==='points'&&x.unit==='% a/a reale';
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
   typeof x.source_page==='string'&&/^https:\/\/(?:fred\.stlouisfed\.org|ec\.europa\.eu|www150\.statcan\.gc\.ca|www\.ons\.gov\.uk|businessnz\.org\.nz|www\.abs\.gov\.au|www\.bankofengland\.co\.uk|www\.stats\.govt\.nz|www\.rba\.gov\.au|www\.stat-search\.boj\.or\.jp|www\.rbnz\.govt\.nz|data\.snb\.ch|www\.bnz\.co\.nz|www\.anz\.co\.nz|tradingeconomics\.com)\//.test(x.source_page)&&
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
// Phase 1: descriptive economic-cycle research, isolated from the legacy
// direction semaphore and all currency scoring. Regime meanings are source-specific.
const REAL_ACTIVITY_LEVELS=new Set([
 'US_INDPRO_history_value','INDPRO','US_PCEC96_history_value','PCEC96','US_RRSFS_history_value',
 'EA_IP_history_value','STS_INPR_M_EA21_PRD_B-D_SCA_I21','EA_RETAIL_VOL_history_value','STS_TRTU_M_EA21_VOL_SLS_G47_SCA_I21',
 'UK_PRODUCTION_history_value','ONS_K222_DIOP','ONS_S2KU_IOS1','UK_RETAIL_VOL_history_value',
 'JP_IIP_history_value','CH_PRODUCTION_history_value','CH_RETAIL_REAL_history_value',
 'NZ_RETAIL_VOLUME_Q_history_value','CA_RETAIL_VOLUME_history_value','CAN_RETAIL_REAL_LASPEYRES',
 '36100434_SERVICES_T003','JPNRGDPPRI'
]);
const REAL_ACTIVITY_GROWTH=new Set([
 'JPNPRMNTO01GPSAM','SLRTTO01JPQ657S','PRMNTO01CHQ657S','SLRTTO01CHQ657S',
 'SLRTTO01NZQ657S','PRMNTO01AUQ657S','PRMNTO01NZQ657S'
]);
// Keep the two-observation legacy signal intact. Admit longer history only
// with matching identity, vintage type, frequency and exact current endpoints.
function cycleHistory(source,today,frequency){
 const h=source?.history;
 if(!h||h.schema!=='GMFQ_SEMAPHORE_CONTIGUOUS_HISTORY_V1'||
    typeof source.source_series_id!=='string'||h.source_series_id!==source.source_series_id||
    h.frequency!==frequency||!['M','Q'].includes(frequency)||
    h.quality!=='SINGLE_SOURCE_REVISED_VINTAGE_NOT_PIT'||
    source.quality!=='SOURCE_REVISED_RESEARCH_NOT_PIT'||
    !Array.isArray(h.dates)||!Array.isArray(h.values)||h.dates.length!==h.values.length||
    h.observations!==h.dates.length||h.max_observations!==(frequency==='M'?36:12)||
    h.observations<2||h.observations>h.max_observations||
    !Array.isArray(source.dates)||!Array.isArray(source.values)||source.dates.length!==2||source.values.length!==2||
    h.dates.at(-2)!==source.dates[0]||h.dates.at(-1)!==source.dates[1]||
    h.values.at(-2)!==source.values[0]||h.values.at(-1)!==source.values[1]||
    !h.values.every(finite))return source;
 let last=null;
 for(const p of h.dates){
   if(typeof p!=='string'||!(frequency==='M'?/^\d{4}-\d{2}$/:/^\d{4}-Q[1-4]$/).test(p))return source;
   const date=parsePeriod(p);
   if(!date||date>today)return source;
   const idx=Number(p.slice(0,4))*(frequency==='M'?12:4)+Number(p.slice(5).replace('Q',''));
   if(last!==null&&idx!==last+1)return source;
   last=idx;
 }
 return {...source,dates:h.dates,values:h.values};
}
function cycleMetric(metric,source,today,frequency,stale=false){
 const empty={phase:null,level:null,direction:null,acceleration:null,persistence:null,
   basis:null,observations:0,historySufficient:false,quality:'INSUFFICIENT',scope:'INDICATOR_NOT_ECONOMY'};
 if(stale||!source||!Array.isArray(source.dates)||!Array.isArray(source.values)||
    source.dates.length!==source.values.length)return empty;
 const freq=String(frequency||'').toUpperCase();
 const months=freq==='M'?1:freq==='Q'?3:0;
 source=cycleHistory(source,today,freq);
 const records=new Map();
 source.dates.forEach((period,i)=>{
   const date=parsePeriod(period),value=source.values[i];
   if(!date||date>today||!finite(value))return;
   const y=Number(date.slice(0,4)),m=Number(date.slice(5,7));
   const key=months?y*12+Math.floor((m-1)/months)*months:Date.parse(date)/864e5;
   const prev=records.get(key);
   if(!prev||date>=prev.date)records.set(key,{key,date,value});
 });
 const all=[...records.values()].sort((a,b)=>a.key-b.key);
 const contiguous=(a,b)=>months?b.key-a.key===months:freq==='W'&&b.key-a.key>=5&&b.key-a.key<=9;
 const tail=[];
 for(let i=all.length-1;i>=0;i--){
   if(tail.length&&!contiguous(all[i],tail[0]))break;
   tail.unshift(all[i]);
 }
 const n=tail.length,id=source.source_series_id||metric.id;
 const result={...empty,observations:n};
 if(n<2)return result;
 const direction=(x,epsilon)=>Math.abs(x)<epsilon||x===0?0:Math.sign(x);
 const phaseOf=(level,dir)=>level===0||dir===0?null:level>0?(dir>0?'expansion':'slowdown'):(dir>0?'recovery':'contraction');
 let values=[],basis=null,threshold=metric.minimum??.15,levelThreshold=null;
 if(metric.diffusionThreshold===50){
   values=tail.map(x=>x.value);basis='DIFFUSION_50';levelThreshold=50;
 }else if(REAL_ACTIVITY_GROWTH.has(id)){
   values=tail.map(x=>x.value);basis='REAL_ACTIVITY_REPORTED_GROWTH';levelThreshold=0;
 }else if(REAL_ACTIVITY_LEVELS.has(id)&&months){
   const lag=12/months;
   // Require exact same-frequency consecutive history; no interpolation,
   // no comparing a monthly series with quarterly or a different source.
   values=tail.slice(lag).map((x,i)=>tail[i].value>0&&x.value>0?100*(x.value/tail[i].value-1):null);
   basis='REAL_ACTIVITY_YOY_GROWTH';levelThreshold=0;threshold=.2;
 }else{
   // Nominal spending, credit stocks, prices, employment levels and generic
   // surveys do not establish an activity expansion/contraction threshold.
   values=tail.map(x=>x.value);
   basis=metric.kind==='points'?'DESCRIPTIVE_POINTS':'DESCRIPTIVE_PERCENT';
 }
 const structural=levelThreshold!==null;
 const signedMove=(a,b)=>{
   if(!finite(a)||!finite(b))return null;
   if(structural||metric.kind==='points')return (b-a)*(metric.upGood===false?-1:1);
   return a>0?100*(b/a-1)*(metric.upGood===false?-1:1):null;
 };
 const moves=values.slice(1).map((x,i)=>signedMove(values[i],x));
 const last=moves.at(-1),prior=moves.at(-2);
 const dir=finite(last)?direction(last,threshold):null;
 let persistence=null;
 if(dir!==null&&dir!==0){
   persistence=0;
   for(let i=moves.length-1;i>=0&&finite(moves[i])&&direction(moves[i],threshold)===dir;i--)persistence++;
 }
 // A reversal requires a preceding opposite material move, not merely persistence.
 const priorRun=finite(persistence)&&persistence>0?moves.at(-persistence-1):null;
 const reversal=finite(priorRun)&&direction(priorRun,threshold)===-dir?
    (persistence===1?'INITIAL_REVERSAL':persistence===2?'PERSISTENT_REVERSAL':null):null;
 const levelValue=values.at(-1);
 const level=structural&&finite(levelValue)?Math.sign(levelValue-levelThreshold):null;
 return {...result,phase:level!==null&&dir!==null?phaseOf(level,dir):null,level,levelValue:finite(levelValue)?levelValue:null,
   direction:dir,move:finite(last)?last:null,acceleration:finite(last)&&finite(prior)?direction(last-prior,threshold):null,
   persistence,reversal,basis,historySufficient:values.filter(finite).length>=3,quality:dir===null?'INSUFFICIENT':'DESCRIPTIVE_UNCALIBRATED',
   threshold,scope:'INDICATOR_NOT_ECONOMY'};
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
  current:c,previous:p,diff,pct,kind,verdict,stale,invalid,age:Math.round(age),freq,
  cycle:cycleMetric(metric,source,today,freq,stale||invalid)};
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
   const strictProxy=c==='NZD'&&['house','leading'].includes(area.key)||c==='AUD'&&['house','credit'].includes(area.key);
   const preferNewer=(c==='EUR'&&area.key==='services'||c==='NZD'&&area.key==='leading'||
      c==='AUD'&&['house','credit'].includes(area.key))&&latestExtra>originalLatest;
   const newerValid=(!strictProxy&&missingOriginal||officialAlternative&&(missingOriginal||baseline.tone==='neutral'||preferNewer));
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

/* Phase 3A: inflation is policy context, not a growth traffic light.
 * Explicit IDs only; US CPI index levels converted to annual rates using
 * exact calendar lags. All other series already report annual inflation.
 */
const INFLATION_MAP={
 USD:[['US_CPIAUCSL_history_value','CPI headline','M',true],['US_CPILFESL_history_value','CPI core','M',true]],
 EUR:[['EA_HICP_HEADLINE_YOY_history_value','HICP headline','M'],['EA_HICP_CORE_YOY_history_value','HICP core','M'],['EA_HICP_SERVICES_YOY_history_value','HICP servizi','M']],
 GBP:[['UK_CPI_HEADLINE_YOY_history_value','CPI headline','M'],['UK_CPI_CORE_YOY_history_value','CPI core','M']],
 JPY:[['JP_CPI_HEADLINE_YOY_history_value','CPI headline','M'],['JP_CPI_CORE_YOY_history_value','CPI core (definizione nazionale)','M']],
 CHF:[['CH_CPI_HEADLINE_YOY_history_value','CPI headline','M'],['CH_CPI_CORE1_YOY_history_value','CPI core 1','M']],
 AUD:[['AU_CPI_HEADLINE_Q_YOY_history_value','CPI headline trimestrale','Q'],['AU_CPI_TRIMMED_MEAN_Q_YOY_history_value','CPI trimmed mean trimestrale','Q']],
 NZD:[['NZ_CPI_HEADLINE_YOY_history_value','CPI headline','Q'],['NZ_CORE_INFLATION_SFM_Q_history_value','Core inflation SFM','Q']],
 CAD:[['CA_CPI_HEADLINE_YOY_history_value','CPI headline','M'],['CA_CPI_MEDIAN_YOY_history_value','CPI median','M'],['CA_CPI_TRIM_YOY_history_value','CPI trim','M']]
};
const WAGE_MAP={
 USD:[['US_AHE_TOTAL_PRIVATE_history_value','Salari orari medi nominali (AHE)','M',true]],
 EUR:[['EA_NEGOTIATED_WAGES_YOY_history_value','Salari negoziati nominali','Q']],
 AUD:[['AU_WPI_YOY_history_value','Wage Price Index nominale','Q']],
 GBP:[['UK_AWE_TOTAL_YOY','Retribuzioni medie settimanali','M']],
 JPY:[['JP_CASH_EARNINGS_YOY','Retribuzioni monetarie','M']],
 CHF:[['CH_SWISS_WAGE_INDEX_YOY','Indice salari svizzero','A']],
 NZD:[['NZ_LCI_WAGE_YOY','Labour Cost Index','Q']],
 CAD:[['CA_AVERAGE_HOURLY_WAGES_YOY','Salari orari medi','M']]
};
function inflationContext(catalog,today,country){
 return annualRateContext(catalog,today,country,INFLATION_MAP);
}
const WAGE_SUPPLEMENT={
 GBP:['KAC3','https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kac3/lms','M','Retribuzioni medie settimanali nominali (totale, media 3 mesi a/a)'],
 CAD:['STATCAN_14100063_HOURLY_WAGE_YOY','https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301','M','Salari orari medi nominali (LFS, NSA)'],
 NZD:['STATSNZ_LCI_ALL_RATES_YOY','https://www.stats.govt.nz/information-releases/labour-market-statistics-september-2026-quarter/','Q','Labour Cost Index nominale (tutti i settori)'],
 JPY:['LCEAMN01JPQ659S','https://fred.stlouisfed.org/series/LCEAMN01JPQ659S','Q','Salari orari manifatturieri (proxy settoriale OECD, SA)']
};
function wageContext(catalog,today,country,overlay=null){
 const canonical=annualRateContext(catalog,today,country,WAGE_MAP);
 if(country==='CHF'&&overlay?.schema===SUPPLEMENT_SCHEMA&&overlay.wage_context?.schema==='GMFQ_G8_WAGE_CONTEXT_V1'){
   const rows=overlay.wage_context.series;
   const matches=Array.isArray(rows)?rows.filter(x=>x.ccy==='CHF'&&x.area==='wages'&&
    x.source_series_id==='FSO_SWI_NOMINAL_ANNUAL'&&x.source_page==='https://statistik.admin.ch/en/asset/36503589'&&
    x.frequency==='A'&&x.unit==='% a/a'&&x.quality==='SOURCE_VERIFIED_MANUAL_NONPIT'&&
    x.scope==='ANNUAL_ACTUAL_NOT_QUARTERLY'&&x.manual_verified_on==='2026-11-25'&&x.official_release_date==='2026-04-21'&&
    x.manual_expires_on==='2027-04-30'&&today>=x.manual_verified_on&&today<x.manual_expires_on&&
    JSON.stringify(x.dates)===JSON.stringify(['2023','2024','2025'])&&JSON.stringify(x.values)===JSON.stringify([1.7,1.8,1.8])):[];
   if(matches.length===1)return [{id:matches[0].source_series_id,label:'Swiss Wage Index nominale (annuale definitivo)',freq:'A',
    available:true,period:'2025',prior:'2024',value:1.8,previous:1.8,change:0,direction:null,stale:true,
    basis:'ANNUAL_ACTUAL_NOT_QUARTERLY',source:'FSO · verifica manuale; dato annuale, non utilizzato per il momentum corrente'}];
 }
 if(canonical.some(x=>x.available&&!x.stale)||!WAGE_SUPPLEMENT[country]||
    overlay?.schema!==SUPPLEMENT_SCHEMA||overlay.wage_context?.schema!=='GMFQ_G8_WAGE_CONTEXT_V1'||
    !Array.isArray(overlay.wage_context.series))return canonical;
 const [id,page,freq,label]=WAGE_SUPPLEMENT[country];
 const matches=overlay.wage_context.series.filter(x=>x.ccy===country&&x.area==='wages'&&
   x.source_series_id===id&&(country==='NZD'?/^https:\/\/www\.stats\.govt\.nz\/(?:information-releases\/labour-market-statistics-|news\/unemployment-rate-)[a-z0-9-]+-quarter\/$/.test(x.source_page):x.source_page===page)&&x.frequency===freq&&x.unit==='% a/a'&&
   x.metric_kind==='points'&&(x.quality==='SOURCE_REVISED_RESEARCH_NOT_PIT'||country==='NZD'&&x.quality==='SOURCE_VERIFIED_MANUAL_NONPIT'&&x.source_page===page&&x.manual_verified_on==='2026-11-25'&&x.official_release_date==='2026-11-04'&&x.manual_expires_on==='2027-02-04'&&today>=x.manual_verified_on&&today<x.manual_expires_on)&&
   Array.isArray(x.dates)&&Array.isArray(x.values)&&x.dates.length===2&&x.values.length===2&&x.values.every(finite));
 if(matches.length!==1)return canonical;
 const x=matches[0],manual=x.quality==='SOURCE_VERIFIED_MANUAL_NONPIT';
 const validated=manual?x:cycleHistory(x,today,freq);
 if(!manual&&validated===x)return canonical;
 if(manual&&(x.dates[0]!=='2026-Q2'||x.dates[1]!=='2026-Q3'||x.values[0]!==2||x.values[1]!==2.1))return canonical;
 const result=annualRateContext({[country]:[{...validated,id}]},today,country,{[country]:[[id,label,freq]]});
 return result[0]?.available?result:canonical;
}
const EXTERNAL_KEYS={USD:'NAEXKP06USQ659S',GBP:'NAEXKP06GBQ659S',JPY:'NAEXKP06JPQ659S',
 CHF:'NAEXKP06CHQ659S',CAD:'NAEXKP06CAQ659S',AUD:'NAEXKP06AUQ659S',
 NZD:'NAEXKP06NZQ659S',EUR:'EUROSTAT_EA21_P6_REAL_EXPORTS_YOY'};
function externalContext(today,country,overlay=null){
 const id=EXTERNAL_KEYS[country],label='Esportazioni reali di beni e servizi (SA)';
 const missing={id,label,freq:'Q',available:false};
 if(!id||overlay?.schema!==SUPPLEMENT_SCHEMA||overlay.external_context?.schema!=='GMFQ_G8_EXTERNAL_CONTEXT_V1'||
    !Array.isArray(overlay.external_context.series))return missing;
 const page=country==='EUR'?'https://ec.europa.eu/eurostat/databrowser/view/namq_10_gdp/default/table?lang=en':'https://fred.stlouisfed.org/series/'+id;
 const matches=overlay.external_context.series.filter(x=>x.ccy===country&&x.area==='external'&&
    x.source_series_id===id&&x.source_page===page&&x.frequency==='Q'&&x.unit==='% a/a reale'&&
    x.metric_kind==='points'&&x.quality==='SOURCE_REVISED_RESEARCH_NOT_PIT');
 if(matches.length!==1)return missing;
 const x=matches[0],validated=cycleHistory(x,today,'Q');
 if(validated===x)return missing;
 const result=annualRateContext({[country]:[{...validated,id}]},today,country,{[country]:[[id,label,'Q']]})[0];
 if(!result?.available)return missing;
 const values=validated.values;
 const deltas=values.slice(1).map((v,i)=>v-values[i]);
 const sign=v=>Math.abs(v)<.1?0:Math.sign(v);
 const last=sign(deltas.at(-1));
 let persistence=0;
 for(let i=deltas.length-1;i>=0&&sign(deltas[i])===last;i--)persistence++;
 return {...result,observations:values.length,
   regime:result.stale?null:result.value>0?'volumi in crescita annua':result.value<0?'volumi in calo annuo':'volumi invariati su base annua',
   persistence:result.stale?null:persistence};
}
function annualRateContext(catalog,today,country,mapping){
 const rows=Array.isArray(catalog?.[country])?catalog[country]:[];
 const now=Date.parse(today+'T12:00:00Z');
 return (mapping[country]||[]).map(([id,label,freq,index])=>{
   const src=rows.find(r=>r.id===id),missing={id,label,freq,available:false};
   if(!['M','Q'].includes(freq)||!src||src.frequency!==freq||!Array.isArray(src.dates)||!Array.isArray(src.values)||src.dates.length!==src.values.length||!Number.isFinite(now))return missing;
   const months=freq==='Q'?3:1,records=new Map();
   for(let i=0;i<src.dates.length;i++){
     const d=parsePeriod(src.dates[i]),v=src.values[i];
     if(!d||!finite(v)||index&&v<=0)continue;
     const y=Number(d.slice(0,4)),m=Number(d.slice(5,7)),endMonth=Math.ceil(m/months)*months;
     const end=new Date(Date.UTC(y,endMonth,0)).toISOString().slice(0,10);
     if(end>today)continue;
     const k=y*12+endMonth-1;
     if(records.has(k)&&records.get(k).v!==v)return missing;
     records.set(k,{v,end,period:freq==='Q'?y+'-Q'+endMonth/3:y+'-'+String(endMonth).padStart(2,'0')});
   }
   const keys=[...records.keys()].sort((a,b)=>a-b);
   const k=keys.at(-1);if(k===undefined)return missing;
   const current=records.get(k),prior=records.get(k-months);
   const rate=j=>{
     const v=records.get(j)?.v;
     if(!finite(v))return null;
     if(!index)return v;
     const base=records.get(j-12)?.v;
     return finite(base)&&base>0?100*(v/base-1):null;
   };
   const value=rate(k),previous=rate(k-months);
   if(!finite(value))return missing;
   const age=Math.floor((now-Date.parse(current.end+'T12:00:00Z'))/864e5);
   const stale=age>(freq==='Q'?175:85);
   const change=prior&&finite(previous)?value-previous:null;
   const direction=stale||!finite(change)?null:Math.abs(change)<.1?'stabile':change>0?'accelera':'rallenta';
   return {id,label,freq,available:true,period:current.period,prior:prior?.period||null,value,
     previous:finite(previous)?previous:null,change,direction,stale,age,
     basis:index?'YOY_EXACT_INDEX_LAG':'REPORTED_YOY',source:src.source_file||'MACRO_SERIES'};
 });
}

function turningPointMonitor(rows){
 const areas=[];
 for(const row of rows){
   if(row.signal?.tone==='neutral')continue;
   const active=(row.signalSource==='original'?row.items:row.items.slice(0,1));
   if(!active.length||active.some(x=>!x||x.stale||x.invalid||x.verdict===null||
      !x.cycle?.historySufficient||!finite(x.cycle.direction)))continue;
   const signs=active.map(x=>x.cycle.direction);
   const dir=signs.every(x=>x===1)?1:signs.every(x=>x===-1)?-1:0;
   const evidence=active.filter(x=>x.cycle.reversal);
   const reversal=dir!==0&&evidence.length===active.length?
      evidence.every(x=>x.cycle.reversal==='PERSISTENT_REVERSAL')?'PERSISTENT_REVERSAL':'INITIAL_REVERSAL':null;
   areas.push({key:row.key,name:row.name,dir,reversal,
    structural:active.every(x=>x.cycle.level!==null),
    dates:active.map(x=>x.date),periods:active.map(x=>x.period),
    indicators:active.map(x=>({name:x.metric.name,phase:x.cycle.phase,period:x.period,
      persistence:x.cycle.persistence,reversal:x.cycle.reversal}))});
 }
 const improving=areas.filter(x=>x.dir===1),weakening=areas.filter(x=>x.dir===-1);
 const up=areas.filter(x=>x.dir===1&&x.reversal),down=areas.filter(x=>x.dir===-1&&x.reversal);
 const dates=areas.flatMap(x=>x.dates).map(x=>Date.parse(x)).filter(Number.isFinite);
 const aligned=dates.length>0&&Math.max(...dates)-Math.min(...dates)<=120*864e5;
 const eligible=areas.length>=4&&aligned;
 const judgment=!eligible?'Copertura storica o allineamento insufficienti per una lettura trasversale.':
   up.length>=2&&down.length===0&&improving.length>weakening.length?'Segnali di possibile svolta favorevole in più aree.':
   down.length>=2&&up.length===0&&weakening.length>improving.length?'Segnali di possibile svolta sfavorevole in più aree.':
   up.length||down.length?'Svolte locali: il quadro complessivo non è ancora concorde.':
   'Non emergono nuove inversioni concordi; la direzione osservata può essere già in corso.';
 return {areas,improving,weakening,up,down,aligned,eligible,judgment,coverage:areas.length,
   total:rows.length,quality:'DESCRIPTIVE_UNCALIBRATED'};
}
function macroNarrative(rows,inflation,wages,external,turning){
 const active=r=>(r.signalSource==='original'?r.items:r.items.slice(0,1)).filter(x=>x&&!x.stale&&!x.invalid&&x.verdict!==null);
 const valid=rows.filter(r=>r.signal.tone!=='neutral'&&active(r).length);
 const up=valid.filter(r=>r.signal.tone==='green'),down=valid.filter(r=>r.signal.tone==='red');
 const names=a=>a.map(r=>r.name.toLowerCase()).join(', ');
 const dates=valid.flatMap(r=>active(r).map(x=>Date.parse(x.date))).filter(Number.isFinite);
 const enough=valid.length>=4&&dates.length>0&&Math.max(...dates)-Math.min(...dates)<=120*864e5;
 let growth=enough?(up.length>down.length&&up.length>=3?'Il miglioramento è più diffuso del deterioramento.':
    down.length>up.length&&down.length>=3?'Il deterioramento è più diffuso del miglioramento.':'La direzione dell’attività resta mista.'):
    'Copertura o allineamento dei dati insufficienti per un giudizio complessivo.';
 if(up.length)growth+=' Migliorano '+names(up)+'.';
 if(down.length)growth+=' Peggiorano '+names(down)+'.';
 if(valid.length<rows.length)growth+=' '+(rows.length-valid.length)+' aree non sono classificabili.';
 const structural=valid.flatMap(r=>active(r)).filter(x=>x.cycle?.level!==null&&x.cycle?.level!==undefined);
 if(structural.length)growth+=' Tra gli indicatori con soglia definita, '+structural.filter(x=>x.cycle.level>0).length+' sopra e '+structural.filter(x=>x.cycle.level<0).length+' sotto soglia. Non equivale al livello del PIL.';
 const current=a=>a.filter(x=>x.available&&!x.stale&&x.freq!=='A'&&x.direction&&finite(x.value));
 const core=current(inflation.filter(x=>/core|trimmed|median|trim/i.test(x.label)));
 const head=current(inflation.filter(x=>/headline/i.test(x.label)));
 const w=current(wages);
 const describe=x=>x.label+' '+fmt(x.value,2)+'% a/a ('+x.period+', '+x.direction+')';
 const pressures=[...head,...core].map(describe);
 let prices=pressures.length?pressures.join('; ')+'.':'Direzione delle pressioni inflazionistiche non determinabile con dati correnti comparabili.';
 if(w.length)prices+=' Salari: '+w.map(describe).join('; ')+'.';
 else prices+=' Momentum salariale corrente non valutabile.';
 const coreUp=core.length>0&&core.every(x=>x.direction==='accelera');
 const coreDown=core.length>0&&core.every(x=>x.direction==='rallenta');
 const wageUp=w.some(x=>x.direction==='accelera'),wageDown=w.some(x=>x.direction==='rallenta');
 let policy='La risposta della banca centrale dipende anche da obiettivi, aspettative e dati futuri; il pricing dei tassi va verificato separatamente.';
 if((coreUp&&wageDown)||(coreDown&&wageUp))policy='Core e salari divergono: manca una conferma univoca delle pressioni interne. '+policy;
 else if(coreUp&&wageUp)policy='Core e salari accelerano: possibile ostacolo a un allentamento monetario. '+policy;
 else if(coreDown&&wageDown)policy='Core e salari rallentano: possibile attenuazione delle pressioni interne, non una garanzia di tagli. '+policy;
 let trade='Domanda estera: evidenza corrente insufficiente.';
 if(external.available&&!external.stale&&finite(external.value))trade='Esportazioni reali '+fmt(external.value,2)+'% a/a ('+external.period+'). '+(external.value<0?'Volumi inferiori a un anno prima.':external.value>0?'Volumi superiori a un anno prima.':'Volumi invariati su base annua.')+(external.direction?' La crescita '+external.direction+'.':'');
 let watch='Monitorare le prossime osservazioni di lavoro, consumi e attività produttiva; verificare la persistenza dei segnali e la coerenza dei periodi.';
 if(enough&&up.length>=3&&up.length>down.length)watch='Il miglioramento perderebbe credibilità se si estendessero i segnali di deterioramento, soprattutto in lavoro e consumi.';
 else if(enough&&down.length>=3&&down.length>up.length)watch='Il deterioramento perderebbe credibilità se lavoro, consumi e attività tornassero a migliorare in modo persistente.';
 return {growth,prices,trade,policy,watch,turning:turning.judgment,coverage:valid.length,aligned:enough,quality:'DESCRIPTIVE_UNCALIBRATED'};
}
// Presentation only: retain the approved activity signals and narrative engine.
function overviewCountry(rows,inflation,wages,external,turning,narrative){
 const up=rows.filter(r=>r.signal.tone==='green'),down=rows.filter(r=>r.signal.tone==='red');
 const mixed=rows.filter(r=>r.signal.tone==='amber'),missing=rows.filter(r=>r.signal.tone==='neutral');
 const tone=!narrative.aligned?'neutral':up.length>=3&&up.length>down.length?'green':down.length>=3&&down.length>up.length?'red':'amber';
 const label={green:'Miglioramento diffuso',red:'Deterioramento diffuso',amber:'Quadro misto',neutral:'Giudizio sospeso'}[tone];
 const active=r=>(r.signalSource==='original'?r.items:r.items.slice(0,1));
 const phase=r=>{
   if(r.signal.tone==='neutral')return null;
   const items=active(r);
   if(!items.length||items.some(x=>!x||x.stale||x.invalid||x.verdict===null||!x.cycle?.phase))return null;
   const phases=items.map(x=>x.cycle.phase);
   return phases.every(p=>p===phases[0])?phases[0]:null;
 };
 const phaseLabels={expansion:'Espansione',slowdown:'Rallentamento',contraction:'Contrazione',recovery:'Recupero'};
 const cells=rows.map(r=>({key:r.key,name:r.name,tone:r.signal.tone,phase:phase(r),periods:active(r).filter(x=>x&&!x.stale&&!x.invalid&&x.verdict!==null).map(x=>x.period)}));
 const current=x=>x?.available&&!x.stale&&finite(x.value);
 const head=inflation.find(x=>/headline/i.test(x.label));
 const core=inflation.find(x=>/core|trimmed|median|trim/i.test(x.label));
 const wage=wages.find(current)||wages.find(x=>x.available);
 return {tone,label,up,down,mixed,missing,cells,phaseLabels,head,core,wage,external,
  turning,summary:(up.length?'Migliora: '+up.map(r=>r.name.toLowerCase()).join(', ')+'. ':'')+
   (down.length?'Peggiora: '+down.map(r=>r.name.toLowerCase()).join(', ')+'.':'')||
   'Nessuna direzione settoriale univoca.',
  coverage:rows.length-missing.length};
}
function exportSparkline(today,country,overlay,external,esc){
 if(!external?.available||external.stale||!overlay?.external_context?.series)return '';
 const matches=overlay.external_context.series.filter(x=>x.ccy===country&&x.source_series_id===EXTERNAL_KEYS[country]);
 if(matches.length!==1)return '';
 const x=matches[0],h=cycleHistory(x,today,'Q');
 if(h===x||h.values.length<3||h.values.at(-1)!==external.value)return '';
 const w=240,height=45,pad=4,lo=Math.min(0,...h.values),hi=Math.max(0,...h.values),span=hi-lo||1;
 const py=v=>height-pad-(v-lo)/span*(height-2*pad);
 const points=h.values.map((v,i)=>((pad+i*(w-2*pad)/(h.values.length-1)).toFixed(2))+','+py(v).toFixed(2)).join(' ');
 const desc='Esportazioni reali a/a, '+h.dates[0]+' – '+h.dates.at(-1)+': '+h.values.map(v=>fmt(v,2)+'%').join(', ');
 return '<div class="sem-export-trend"><svg role="img" aria-label="'+esc(desc)+'" viewBox="0 0 240 45" preserveAspectRatio="none"><line x1="4" x2="236" y1="'+py(0).toFixed(2)+'" y2="'+py(0).toFixed(2)+'" stroke="#6a8296" stroke-dasharray="3 3"/><polyline points="'+points+'" fill="none" stroke="#81c9e8" stroke-width="1.8" vector-effect="non-scaling-stroke"/><circle cx="236" cy="'+py(h.values.at(-1)).toFixed(2)+'" r="2.6" fill="#81c9e8"/></svg><small>'+esc(h.dates[0])+' <span>Export reale · '+h.values.length+' trim.</span> '+esc(h.dates.at(-1))+'</small></div>';
}
function render({catalog={},dayNow,country='USD',overlay=null,esc=(x)=>String(x??'')}={}){
 const today=dayNow?.()||'';
 if(!/^\d{4}-\d{2}-\d{2}$/.test(today))return '';
 const selected=FX.includes(country)?country:'USD';
 const universe=Object.fromEntries(FX.map(ccy=>[ccy,model(catalog,today,ccy,overlay)]));
 const rows=universe[selected];
 const overview=Object.fromEntries(FX.map(ccy=>{
   const r=universe[ccy],i=inflationContext(catalog,today,ccy),w=wageContext(catalog,today,ccy,overlay),e=externalContext(today,ccy,overlay),t=turningPointMonitor(r),n=macroNarrative(r,i,w,e,t);
   return [ccy,overviewCountry(r,i,w,e,t,n)];
 }));
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
  const cycle=x.cycle;
  const cycleLabel=cycle?.phase?{expansion:'Espansione',slowdown:'Rallentamento',contraction:'Contrazione',recovery:'Recupero'}[cycle.phase]:null;
  const cycleText=cycle?.direction!==null&&cycle?.direction!==undefined?
    '<small class="sem-source-note"><strong>Lettura ciclica · </strong>'+esc(cycleLabel||(cycle.level===null?'Solo direzione, livello non determinato':cycle.level===0?'Livello sulla soglia':cycle.direction===0?'Livello '+(cycle.level>0?'sopra':'sotto')+' soglia, momentum stabile':'Livello determinato'))+
    (cycle.basis==='REAL_ACTIVITY_YOY_GROWTH'?' · crescita a/a '+d(cycle.levelValue,'%'):cycle.basis==='REAL_ACTIVITY_REPORTED_GROWTH'?' · crescita reale della serie':cycle.basis==='DIFFUSION_50'?' · soglia 50':' · variazione descrittiva')+
    (cycle.observations>2?' · '+cycle.observations+' osservazioni consecutive':'')+
    (cycle.persistence>1?' · '+cycle.persistence+' confronti consecutivi nella stessa direzione':cycle.persistence===1?' · un solo confronto nella direzione attuale':'')+
    (cycle.acceleration!==null?' · '+({1:'momentum in aumento',0:'momentum stabile','-1':'momentum in diminuzione'}[cycle.acceleration]):'')+
    '</small>':'';
  const value=(v,p,label)=>'<div class="sem-value"><small>'+label+' · '+esc(p)+'</small><strong>'+fmt(v,digits)+'</strong><span>'+unit+'</span></div>';
  return '<div class="sem-measure '+tone+'"><div class="sem-measure-title"><strong>'+esc(x.metric.name)+'</strong></div>'+
   '<div class="sem-value-grid'+(x.metric.hideValue?' sem-value-hidden':'')+'">'+
   (x.metric.hideValue?'<div class="sem-value"><small>Confronto</small><strong class="sem-period-pair">'+esc(x.prior)+' → '+esc(x.period)+'</strong></div>':value(scaled,x.period,'Attuale')+value(prior,x.prior,'Precedente'))+
   '<div class="sem-value sem-change"><small>Variazione</small><strong class="'+tone+'">'+esc(diff)+'</strong><span>'+({green:'Favorevole',red:'Sfavorevole',amber:'Quasi stabile',neutral:'Non classificabile'}[tone])+'</span></div></div>'+
   '<small class="sem-source-note">'+esc(x.source)+(x.stale?' · dato datato':'')+(x.invalid?' · confronto sospeso':'')+'</small>'+diffusion+cycleText+
   (x.metric.source_page?'<a class="sem-src-link" href="'+esc(x.metric.source_page)+'" target="_blank" rel="noopener noreferrer">Fonte e metodologia ↗</a>':'')+'</div>';
 };

 const inflation=inflationContext(catalog,today,selected);
 const inflationNote='<p><strong>Inflazione · pressioni sui prezzi (separate dal ciclo)</strong></p>'+
   inflation.map(x=>'<p><strong>'+esc(x.label)+'</strong> · '+(x.available?
    esc(fmt(x.value,2))+'% a/a · '+esc(x.period)+
    (finite(x.change)?' · variazione '+esc(d(x.change,' p.p.'))+' rispetto a '+esc(x.prior):' · confronto non disponibile')+
    (x.stale?' · dato datato, giudizio sospeso':x.direction?' · '+esc(x.direction):' · direzione non determinabile')+
    ' <small>'+esc(x.source)+'</small>':'dato non disponibile')+'</p>').join('')+
   '<small>Pressioni sui prezzi in aumento o diminuzione: non sono un giudizio positivo/negativo sulla crescita. Headline e core possono riferirsi a periodi diversi; le misure core nazionali non sono omogenee.</small>';
 const wages=wageContext(catalog,today,selected,overlay);
 const wageNote='<p><strong>Salari · crescita nominale effettiva</strong></p>'+
   wages.map(x=>'<p><strong>'+esc(x.label)+'</strong> · '+(x.available?
    esc(fmt(x.value,2))+'% a/a · '+esc(x.period)+
    (finite(x.change)?' · variazione '+esc(d(x.change,' p.p.'))+' rispetto a '+esc(x.prior):' · confronto non disponibile')+
    (x.freq==='A'?' · dato annuale: momentum corrente non valutabile':x.stale?' · dato datato, giudizio sospeso':x.direction?' · '+esc(x.direction):' · direzione non determinabile')+
    ' <small>'+esc(x.source)+'</small>':'serie effettiva non ancora disponibile nel database')+'</p>').join('')+
   '<small>Le retribuzioni nominali non sono salari reali o costo unitario del lavoro. Gli indicatori nazionali hanno definizioni differenti. Le aspettative salariali non sostituiscono i dati effettivi; nessun contributo ai semafori della crescita.</small>';
 const external=externalContext(today,selected,overlay);
 const externalNote='<p><strong>Domanda estera · esportazioni reali</strong></p><p><strong>'+esc(external.label)+'</strong> · '+
   (external.available?esc(fmt(external.value,2))+'% a/a · '+esc(external.period)+
    (finite(external.change)?' · variazione '+esc(d(external.change,' p.p.'))+' rispetto a '+esc(external.prior):' · confronto non disponibile')+
    (external.stale?' · dato datato, giudizio sospeso':' · '+esc(external.regime||'')+(external.direction?' · crescita '+esc(external.direction):''))+
    (external.persistence>1?' · direzione persistente per '+external.persistence+' variazioni trimestrali':'')+
    ' <small>'+esc(external.source)+' · '+external.observations+' trimestri consecutivi</small>':'serie reale non disponibile')+
   '</p><small>I volumi esportati misurano vendite effettive all’estero, non soltanto domanda: contano anche offerta e competitività. Non sono bilancia commerciale o contributo netto al PIL. Nessun contributo ai sette semafori della crescita.</small>';
 const turning=turningPointMonitor(rows);
 const turningNote='<p><strong>Turning Point Monitor · segnali di svolta</strong></p><p>'+esc(turning.judgment)+'</p>'+
   '<p>Copertura storica utile: '+turning.coverage+'/'+turning.total+' aree · '+turning.improving.length+' in miglioramento · '+turning.weakening.length+' in deterioramento.</p>'+
   [...turning.up,...turning.down].map(x=>'<p><strong>'+esc(x.name)+'</strong> · '+(x.dir>0?'svolta favorevole':'svolta sfavorevole')+
   ' · '+(x.reversal==='PERSISTENT_REVERSAL'?'due variazioni consecutive dopo inversione':'prima variazione dopo inversione')+
   ' · '+esc(x.periods.join(' / '))+(x.structural?'':' · segnale direzionale, livello ciclico non determinato')+'</p>').join('')+
   '<small>Soglie descrittive non calibrate: una prima inversione non conferma una svolta economica; due variazioni indicano persistenza locale, non una previsione. Nessun punteggio o segnale Forex.</small>';
 const narrative=macroNarrative(rows,inflation,wages,external,turning);
 const narrativeTone=!narrative.aligned?'neutral':rows.filter(x=>x.signal.tone==='green').length>=3&&rows.filter(x=>x.signal.tone==='green').length>rows.filter(x=>x.signal.tone==='red').length?'green':rows.filter(x=>x.signal.tone==='red').length>=3&&rows.filter(x=>x.signal.tone==='red').length>rows.filter(x=>x.signal.tone==='green').length?'red':'amber';
 const narrativeNote='<section class="sem-desk-reading" aria-label="Giudizio macro">'+
   '<header><span class="sem-desk-eyebrow">LETTURA IN 30 SECONDI</span><h3>Cosa vedo davvero · giudizio macro</h3></header>'+
   '<div class="sem-desk-lead '+narrativeTone+'"><span>ECONOMIA</span><p>'+esc(narrative.growth)+'</p></div>'+
   '<div class="sem-desk-grid">'+[['Svolta','neutral',narrative.turning],['Prezzi e salari','neutral',narrative.prices],['Domanda estera','neutral',narrative.trade],['Implicazioni per i tassi','neutral',narrative.policy]].map(([label,tone,value])=>'<div class="sem-desk-card '+tone+'"><h4>'+esc(label)+'</h4><p>'+esc(value)+'</p></div>').join('')+'</div>'+
   '<div class="sem-desk-watch"><h4>Cosa controllare</h4><p>'+esc(narrative.watch)+'</p></div>'+
   '<small>Lettura descrittiva automatica delle osservazioni disponibili, non previsione o segnale operativo.</small></section>';
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
 const marketCount=t=>FX.filter(ccy=>overview[ccy].tone===t).length;
 const turningCountries=FX.filter(ccy=>overview[ccy].turning.up.length||overview[ccy].turning.down.length);
 const turnList=turningCountries.map(ccy=>{
   const t=overview[ccy].turning;
   const tone=t.up.length&&t.down.length?'amber':t.up.length?'green':'red';
   const sides=[t.up.length?'↗ '+t.up.map(x=>x.name.toLowerCase()).join(', '):'',t.down.length?'↘ '+t.down.map(x=>x.name.toLowerCase()).join(', '):''].filter(Boolean).join(' · ');
   return '<button type="button" class="sem-turn-chip '+tone+'" data-ms-country="'+ccy+'"><strong>'+FLAGS[ccy]+' '+ccy+'</strong><span>'+esc(sides)+'</span></button>';
 }).join('');
 const rateTile=(label,x)=>{
   const ok=x?.available&&finite(x.value);
   const direction=ok&&!x.stale&&x.freq!=='A'?x.direction:null;
   const mark={accelera:'↗',rallenta:'↘',stabile:'→'}[direction]||'—';
   return '<div class="sem-context-metric"><span>'+esc(label)+'</span><strong>'+ (ok?esc(fmt(x.value,1))+'%':'—')+'</strong><small>'+esc(ok?x.period+(x.stale||x.freq==='A'?' · datato':' · '+mark+(direction?' '+direction:'')):'Non disponibile')+'</small></div>';
 };
 const cards=FX.map(ccy=>{
   const o=overview[ccy],t=o.turning,active=ccy===selected;
   const changeText=t.up.length||t.down.length?'Svolte locali: '+t.up.length+' favorevoli / '+t.down.length+' sfavorevoli':'Nessuna nuova svolta rilevata';
   return '<article class="sem-country-card '+o.tone+(active?' selected':'')+'">'+
    '<button type="button" class="sem-country-card-head" data-ms-country="'+ccy+'" aria-pressed="'+active+'"><span>'+FLAGS[ccy]+' <b>'+esc(NAMES[ccy])+'</b></span><strong>'+ccy+' ↗</strong></button>'+
    '<div class="sem-country-card-body"><div class="sem-country-status '+o.tone+'">'+esc(o.label)+'</div>'+
    '<div class="sem-country-breadth" aria-label="'+o.up.length+' aree migliorano, '+o.down.length+' peggiorano, '+o.mixed.length+' miste, '+o.missing.length+' non classificabili">'+['green','amber','red','neutral'].map(k=>'<i class="'+k+'" style="flex:'+({green:o.up.length,amber:o.mixed.length,red:o.down.length,neutral:o.missing.length}[k])+'"></i>').join('')+'</div>'+
    '<div class="sem-country-breadth-label"><span class="green">↗ '+o.up.length+'</span><span class="amber">→ '+o.mixed.length+'</span><span class="red">↘ '+o.down.length+'</span><small>'+o.coverage+'/7 aree valide</small></div>'+
    '<p class="sem-country-quick">'+esc(o.summary)+'</p><p class="sem-country-turn">'+esc(changeText)+'</p>'+
    '<div class="sem-context-metrics">'+rateTile('Inflazione',o.head)+rateTile('Core',o.core)+rateTile('Salari',o.wage)+rateTile('Export reale',o.external)+'</div>'+
    exportSparkline(today,ccy,overlay,o.external,esc)+'</div></article>';
 }).join('');
 const phaseDot=(ccy,a)=>{
   const cell=overview[ccy].cells.find(x=>x.key===a.key),phase=cell?.phase;
   const label=phase?overview[ccy].phaseLabels[phase]:tones[a.signal.tone];
   return '<span class="sem-matrix-cell '+a.signal.tone+'" title="'+esc(a.name+' · '+label+(cell?.periods?.length?' · '+cell.periods.join(' / '):''))+'"><b>'+symbols[a.signal.tone]+'</b><span>'+esc(label)+'</span></span>';
 };
 const hasStale=rows.some(x=>x.items.some(z=>z?.stale));
 const hasManual=rows.some(x=>x.items.some(z=>z?.source?.includes('verificato manualmente')));
 return '<section class="recession-light" aria-labelledby="recession-light-title">'+
  '<header class="sem-head"><div><span class="sem-kicker">GLOBAL MACRO / G8 / LETTURA CICLICA</span>'+
  '<h2 id="recession-light-title">Economic Cycle Monitor <small>G8</small></h2>'+
  '<p>Il semaforo economico: direzione, fase degli indicatori e segnali di svolta. Non è un ranking FX né una probabilità di recessione.</p></div>'+
  '<span class="sem-date">Consultazione '+esc(today)+' · periodi originali in tabella</span></header>'+
  '<div class="sem-overview"><div class="sem-overview-coverage"><span>Copertura dati G8</span><strong>'+covered+'<small>/56</small></strong><div class="sem-coverage-track" role="progressbar" aria-label="Copertura G8" aria-valuenow="'+covered+'" aria-valuemin="0" aria-valuemax="56"><i style="width:'+(covered/56*100)+'%"></i></div></div>'+['green','amber','red','neutral'].map(t=>'<div class="sem-overview-kpi '+t+'"><span>'+tones[t]+'</span><strong>'+tally(allRows,t)+'</strong></div>').join('')+'</div>'+
  '<div class="sem-global-verdict"><div><span>QUADRO G8 · DIFFUSIONE DELLE DIREZIONI</span><h3>'+marketCount('green')+' migliorano · '+marketCount('red')+' peggiorano</h3><p>'+marketCount('amber')+' quadri misti · '+marketCount('neutral')+' giudizi sospesi. Regole descrittive, non un confronto del livello di crescita.</p></div><div class="sem-global-turn"><span>PUNTI DI SVOLTA · LOCALI</span><strong>'+turningCountries.length+' economie</strong><small>Non equivalgono a inversioni confermate del ciclo.</small></div></div>'+
  '<section class="sem-turn-radar" aria-label="Radar delle svolte"><h3>Radar delle svolte</h3><div class="sem-turn-chips">'+(turnList||'<p>Nessuna nuova inversione rilevata con evidenza sufficiente.</p>')+'</div></section>'+
  '<div class="sem-dashboard-title"><div><span>COUNTRY BOARD</span><h3>Le otto economie in 30 secondi</h3></div><small>Seleziona una scheda per il dettaglio. Prezzi, salari ed export sono contesto separato.</small></div>'+
  '<div class="sem-country-board">'+cards+'</div>'+
  '<div class="sem-g8-title"><strong>Matrice del ciclo · sette aree</strong><span>Fase soltanto se gli indicatori attivi concordano su una soglia definita.</span></div>'+
  '<div class="sem-g8-scroll"><table class="sem-g8-table"><thead><tr><th scope="col">Paese</th>'+
  AREAS.map(a=>'<th scope="col">'+esc(a.short)+'</th>').join('')+'</tr></thead><tbody>'+
  FX.map(c=>'<tr'+(c===selected?' class="selected"':'')+'><th scope="row"><button type="button" class="sem-g8-pick" data-ms-country="'+c+'" aria-pressed="'+String(c===selected)+'">'+
   FLAGS[c]+' '+c+'</button></th>'+universe[c].map(a=>'<td>'+phaseDot(c,a)+'</td>').join('')+'</tr>').join('')+
  '</tbody></table></div>'+
  '<div class="sem-legend">'+['green','amber','red','neutral'].map(t=>'<span class="sem-legend-item"><span class="sem-mini sem-cell '+t+'" aria-hidden="true">'+symbols[t]+'</span>'+tones[t]+'</span>').join('')+'</div>'+
  '<div class="sem-sector-compare" aria-label="Industria e servizi a confronto"><p>Industria e servizi · direzione del ciclo</p><div class="sem-sector-compare-grid">'+
    sectorSummary('industry','Manifattura')+sectorSummary('services','Servizi')+'</div>'+
    '<small>La direzione non è il livello: un PSI sopra 50 può rallentare pur restando in espansione. Non confrontare i livelli di serie differenti.</small></div>'+
  '<div class="sem-country-caption"><div>'+FLAGS[selected]+' <strong>'+esc(NAMES[selected])+'</strong><small>Dettaglio per indicatore</small></div><div class="sem-country-counts">'+['green','amber','red','neutral'].map(t=>'<span class="sem-country-count '+t+'" title="'+tones[t]+'">'+symbols[t]+' '+tally(rows,t)+'</span>').join('')+'</div></div>'+
  narrativeNote+
  '<section class="sem-desk-turn" aria-label="Punti di svolta">'+turningNote+'</section>'+
  '<div class="sem-desk-context"><details class="sem-desk-detail"><summary>Inflazione · dettaglio dei dati</summary><div>'+inflationNote+'</div></details>'+
  '<details class="sem-desk-detail"><summary>Salari · dettaglio dei dati</summary><div>'+wageNote+'</div></details>'+
  '<details class="sem-desk-detail"><summary>Domanda estera · dettaglio dei dati</summary><div>'+externalNote+'</div></details></div>'+
  '<details class="sem-desk-evidence" open><summary>Sette aree del ciclo · dettaglio per indicatore</summary>'+
  '<div class="sem-table" role="table" aria-label="Semaforo economico '+esc(NAMES[selected])+'">'+
  '<div class="sem-columns" role="row"><span role="columnheader">Area</span><span role="columnheader">Ultima evidenza disponibile</span><span role="columnheader">Segnale</span></div>'+
  rows.map(r=>'<div class="sem-row '+r.signal.tone+'" role="row"><div role="cell" class="sem-area"><strong>'+esc(r.name)+'</strong><span class="sem-area-reading">'+esc(tones[r.signal.tone])+'</span><small>'+esc(r.why)+'</small></div>'+
    '<div class="sem-evidence" role="cell"><div class="sem-area-judgment"><span>Cosa sta cambiando</span><p>'+esc(readingFor(r))+'</p></div>'+(r.items.length?(r.signalSource==='fallback'?measure(r.items[0])+'<details class="sem-history"><summary>Altre serie di contesto ('+(r.items.length-1)+')</summary>'+r.items.slice(1).map(measure).join('')+'</details>':r.items.map(measure).join('')):'<span class="sem-missing">Nessuna serie idonea nel feed attuale</span>')+(r.key==='services'?svcPriceNote:'')+'</div>'+
    '<div class="sem-signal" role="cell"><span class="sem-pill '+r.signal.tone+'"><i aria-hidden="true"></i>'+esc(tones[r.signal.tone])+'</span>'+
    (r.items.length===1?'<small>Un solo indicatore</small>':'')+
    (r.signalSource==='fallback'?'<small>Segnale da fonte supplementare aggiornata; serie precedenti nel dettaglio</small>':'')+
    (r.proxy?'<small>Proxy/sondaggio, non misura esaustiva del ciclo</small>':'')+
    (r.items.some(x=>x?.stale)?'<small>Osservazioni datate</small>':'')+'</div></div>').join('')+'</div>'+
  '</details>'+ 
  '<div class="sem-policy"><div><span>POLITICA MONETARIA · DA LEGGERE A PARTE</span>'+
  '<p>'+bank+' e aspettative sui tassi possono amplificare o attenuare le pressioni cicliche: non sono però un indicatore diretto di recessione né una prova di movimento del cambio.</p></div>'+
  '<a href="#rates">Apri tassi & OIS ↗</a></div>'+
  '<details class="sem-method"><summary>Metodo, soglie e fonti</summary><p class="sem-foot">Metodo: ogni indicatore confronta le sue ultime due osservazioni disponibili; verde indica miglioramento direzionale, rosso peggioramento, giallo quadro misto o quasi invariato, azzurro dati mancanti, troppo vecchi, non consecutivi o non sufficientemente allineati. '+
  'Lettura ciclica sperimentale per singolo indicatore: soglia 50 per indici di diffusione, zero per crescita reale e crescita a/a per livelli reali con storia consecutiva; gli altri indicatori descrivono solo direzione. Nessun segnale ciclico aggregato o calibrazione storica. '+
  'Le soglie descrittive evitano piccoli movimenti: ±0,15% per i livelli e soglie in punti esplicite per tassi, sondaggi e indicatori compositi. Le osservazioni oltre la soglia di anzianità sono visibili ma non producono semafori direzionali. '+
  (hasStale?'Sono presenti osservazioni datate: non interpretare i colori come fotografia intraday. ':'')+
  (hasManual?'Sono presenti rilevazioni ufficiali verificate manualmente: la data del dato è esplicita e i segnali scadono se non vengono aggiornati. ':'')+
  'La matrice confronta direzioni, NON livelli omogenei o cicli sincronizzati. La colonna Servizi misura il momentum dell’attività o dei suoi proxy e distingue il livello di espansione/contrazione SOLO per un indice di diffusione con soglia documentata a 50 (es. PSI BusinessNZ). Non misura l’inflazione dei servizi. Prezzi nominali, saldi di survey, stock di credito e PIL sono strumenti diversi. '+
  'I periodi mostrati NON equivalgono alle date di pubblicazione. Fonti: MACRO_SERIES.json e semaforo supplementare, dati potenzialmente revisionati (non point-in-time); nessuna previsione NBER, sorpresa rispetto al consenso, ranking valutario o segnale di trading.</p></details>'+
  '</section>';
}
root.FXQuantRecessionLight={render,model,parsePeriod,cycleMetric,cycleHistory,inflationContext,wageContext,externalContext,turningPointMonitor,macroNarrative,overviewCountry,exportSparkline,coverage:FX};
if(typeof module!=='undefined'&&module.exports)module.exports={render,model,parsePeriod,cycleMetric,cycleHistory,inflationContext,wageContext,externalContext,turningPointMonitor,macroNarrative,overviewCountry,exportSparkline,coverage:FX};
})(typeof window!=='undefined'?window:globalThis);
