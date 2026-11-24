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
const SUPPLEMENT_SCHEMA='GMFQ_G8_SEMAPHORE_SUPPLEMENT_V1';
function supplementary(overlay,country,key){
 if(overlay?.schema!==SUPPLEMENT_SCHEMA||!Array.isArray(overlay.series))return null;
 const matches=overlay.series.filter(x=>x?.ccy===country&&x?.area===key&&
   x?.quality==='SOURCE_REVISED_RESEARCH_NOT_PIT'&&
   /^[A-Z0-9_]+$/.test(x.id||'')&&
   ['M','Q'].includes(x.frequency)&&
   ['percent','points'].includes(x.metric_kind)&&
   Array.isArray(x.dates)&&Array.isArray(x.values)&&
   x.dates.length===2&&x.values.length===2&&x.values.every(v=>typeof v==='number'&&Number.isFinite(v))&&
   typeof x.source_page==='string'&&/^https:\/\/(?:fred\.stlouisfed\.org|ec\.europa\.eu|www150\.statcan\.gc\.ca|www\.ons\.gov\.uk)\//.test(x.source_page));
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
 const verdict=invalid||!finite(move)?null:Math.abs(move)<threshold?0:Math.sign(move)*(metric.upGood?1:-1);
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
 const sources=new Map(rows.map(s=>[s.id,s]));
 return AREAS.map(area=>{
   let metrics=MAP[c]?.[area.key]||[];
   if(metrics.length===0){
     const extra=supplementary(overlay,c,area.key);
     if(extra){
       sources.set(extra.id,{...extra,source_file:extra.source_file+' · aggiornamento dal feed supplementare'});
       metrics=[M(extra.id,extra.label,true,{unit:extra.unit,kind:extra.metric_kind,
        minimum:extra.metric_kind==='points'?.2:.15,
        pointUnit:extra.unit==='% QoQ'?'p.p.':'punti',freq:extra.frequency,source_page:extra.source_page})];
     }
   }
   const items=metrics.map(metric=>inspect(metric,sources.get(metric.id),today));
   return {...area,items,expected:metrics.length,signal:classify(items,metrics.length)};
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
  const digits=x.metric.scale?2:x.kind==='points'?2:Math.abs(scaled)>=100?0:1;
  const reading=x.metric.hideValue?'variazione della serie':fmt(scaled,digits)+' '+esc(x.metric.unit||'unità della fonte');
  const diff=x.kind==='points'?d(x.diff,' '+(x.metric.pointUnit||'punti')):d(x.pct,'%');
  return '<div class="sem-measure"><div><strong>'+esc(x.metric.name)+'</strong> <span>'+reading+
   '</span> <b>'+diff+'</b></div><small>Periodo '+esc(x.period)+' (precedente '+esc(x.prior)+') · '+
   esc(x.source)+(x.stale?' · dato datato':'')+(x.invalid?' · confronto sospeso':'')+'</small>'+  (x.metric.source_page?'<a class="sem-src-link" href="'+esc(x.metric.source_page)+'" target="_blank" rel="noopener noreferrer">Fonte e metodologia ↗</a>':'')+'</div>';
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
 const bank={USD:'Fed',EUR:'BCE',GBP:'BoE',JPY:'BoJ',CHF:'SNB',AUD:'RBA',NZD:'RBNZ',CAD:'BoC'}[selected];
 const dots=area=>{
   const q=area.signal;
   return '<span class="sem-mini '+q.tone+'" title="'+esc(q.label)+'" aria-label="'+esc(q.label)+'"><i aria-hidden="true"></i></span>';
 };
 const hasStale=rows.some(x=>x.items.some(z=>z?.stale));
 return '<section class="recession-light" aria-labelledby="recession-light-title">'+
  '<header class="sem-head"><div><span class="sem-kicker">GLOBAL MACRO / G8 / LETTURA CICLICA</span>'+
  '<h2 id="recession-light-title">Il semaforo economico</h2>'+
  '<p>'+esc(NAMES[selected]+': '+intro)+' Segnali direzionali descrittivi, non probabilità di recessione.</p></div>'+
  '<span class="sem-date">Consultazione '+esc(today)+' · periodi originali in tabella</span></header>'+
  '<div class="sem-g8-title"><strong>Otto economie, sette aree</strong><span>Seleziona un Paese. I colori non sono un ranking di forza FX.</span></div>'+
  '<div class="sem-g8-scroll"><table class="sem-g8-table"><thead><tr><th scope="col">Paese</th>'+
  AREAS.map(a=>'<th scope="col">'+esc(a.short)+'</th>').join('')+'</tr></thead><tbody>'+
  FX.map(c=>'<tr'+(c===selected?' class="selected"':'')+'><th scope="row"><button type="button" class="sem-g8-pick" data-ms-country="'+c+'" aria-pressed="'+String(c===selected)+'">'+
   FLAGS[c]+' '+c+'</button></th>'+universe[c].map(a=>'<td>'+dots(a)+'</td>').join('')+'</tr>').join('')+
  '</tbody></table></div>'+
  '<p class="sem-legend"><span class="sem-mini green"><i></i></span> Migliora <span class="sem-mini red"><i></i></span> Peggiora'+
  ' <span class="sem-mini amber"><i></i></span> Misto / stabile <span class="sem-mini neutral"><i></i></span> Non classificabile</p>'+
  '<div class="sem-country-caption">'+FLAGS[selected]+' <strong>'+esc(NAMES[selected])+'</strong> · dettaglio per indicatore</div>'+
  '<div class="sem-table" role="table" aria-label="Semaforo economico '+esc(NAMES[selected])+'">'+
  '<div class="sem-columns" role="row"><span role="columnheader">Area</span><span role="columnheader">Ultima evidenza disponibile</span><span role="columnheader">Segnale</span></div>'+
  rows.map(r=>'<div class="sem-row" role="row"><div role="cell" class="sem-area"><strong>'+esc(r.name)+'</strong><small>'+esc(r.why)+'</small></div>'+
    '<div class="sem-evidence" role="cell">'+(r.items.length?r.items.map(measure).join(''):'<span class="sem-missing">Nessuna serie idonea nel feed attuale</span>')+(r.key==='services'?svcPriceNote:'')+'</div>'+
    '<div class="sem-signal" role="cell"><span class="sem-pill '+r.signal.tone+'"><i aria-hidden="true"></i>'+esc(r.signal.label)+'</span>'+
    (r.items.length===1?'<small>Un solo indicatore</small>':'')+
    (r.items.some(x=>x?.stale)?'<small>Osservazioni datate</small>':'')+'</div></div>').join('')+'</div>'+
  '<div class="sem-policy"><div><span>POLITICA MONETARIA · DA LEGGERE A PARTE</span>'+
  '<p>'+bank+' e aspettative sui tassi possono amplificare o attenuare le pressioni cicliche: non sono però un indicatore diretto di recessione né una prova di movimento del cambio.</p></div>'+
  '<a href="#rates">Apri tassi & OIS ↗</a></div>'+
  '<p class="sem-foot">Metodo: ogni indicatore confronta le sue ultime due osservazioni disponibili; verde indica miglioramento direzionale, rosso peggioramento, giallo quadro misto o quasi invariato, azzurro dati mancanti, troppo vecchi, non consecutivi o non sufficientemente allineati. '+
  'Le soglie descrittive evitano piccoli movimenti: ±0,15% per i livelli e soglie in punti esplicite per tassi, sondaggi e indicatori compositi. '+
  (hasStale?'Sono presenti osservazioni datate: non interpretare i colori come fotografia intraday. ':'')+
  'La matrice confronta direzioni, NON livelli omogenei o cicli sincronizzati. La colonna Servizi misura il momentum dell’attività o dei suoi proxy, NON il livello di un PMI rispetto a 50 e NON l’inflazione dei servizi. Prezzi nominali, saldi di survey, stock di credito e PIL sono strumenti diversi. '+
  'I periodi mostrati NON equivalgono alle date di pubblicazione. Fonte: MACRO_SERIES.json, dati potenzialmente revisionati (non point-in-time); nessuna previsione NBER, sorpresa rispetto al consenso, ranking valutario o segnale di trading.</p>'+
  '</section>';
}
root.FXQuantRecessionLight={render,model,parsePeriod,coverage:FX};
if(typeof module!=='undefined'&&module.exports)module.exports={render,model,parsePeriod,coverage:FX};
})(typeof window!=='undefined'?window:globalThis);
