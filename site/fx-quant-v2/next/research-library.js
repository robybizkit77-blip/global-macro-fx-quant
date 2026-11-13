(function(root){
'use strict';
/* Research Library: one approved, published edition per report type.
   The public GitHub index discovers newer HTML; source creation is separate.
   Historical files are retained, never presented as current editions. */
const BASE='../../website-v1/reports/';
const ROOT='./reports/';
const PUBLIC_API='https://api.github.com/repos/robybizkit77-blip/global-macro-fx-quant/contents/site/fx-quant-v2/next/reports?ref=main';
const REPORTS=Object.freeze([
 {type:'daily',date:'2026-11-13',title:'Briefing Forex & Commodities',file:'Briefing_Forex_Commodities_2026-11-13_V3_MORNING_RESEARCH_DESK.html',desc:'Morning Research Desk V3: repricing Fed, catalizzatore PPI USA, USD/JPY e driver delle commodities.',publicUrl:'./reports/Briefing_Forex_Commodities_2026-11-13_V3_MORNING_RESEARCH_DESK.html'},
 {type:'macro',date:'2026-11-06',title:'Weekly Global Macro Report',file:'Weekly_Global_Macro_Report_2026-11-06_COUNTRY_BOOK_NARRATIVO_V4_CORRETTA.html',desc:'Country Book: crescita, inflazione, lavoro, tassi, rischio e forza relativa delle valute.'},
 {type:'bank',date:'2026-11-06',title:'Weekly Bank FX Report',file:'Weekly_Bank_FX_Report_2026-11-06_DARK_DESK_NARRATIVO_V5.html',desc:'View bancarie G8 e giudizio indipendente, con fonti e consenso datati.'},
 {type:'cb',date:'2026-11-06',title:'Weekly Central Bank Sentiment',file:'Weekly_CB_Sentiment_Report_2026-11-06_DARK_RESEARCH_DESK_WANT_CAN_V4_PALETTE.html',desc:'WANT/CAN: intenzioni e vincoli delle banche centrali, separati dal bias Forex.'},
 {type:'ois',date:'2026-11-06',title:'Weekly Central Bank Pricing G8 · Curve OIS',file:'Weekly_CB_Pricing_G8_2026-11-06_V7_CONFRONTO_31OTT_06NOV.html',desc:'Curve monetarie, repricing G8 e confronto delle attese al 31 ottobre e 6 novembre, con lettura FX.'},
 {type:'cot',date:'2026-11-03',title:'COT FX G8',file:'COT_FX_G8_03_NOV_2026_DARK_QUANT_DESK_v10_DEFINITIVO_LETTURA_INTEGRATA.html',desc:'Posizioni CFTC riferite al 3 novembre, pubblicate il 6: variazioni, concentrazione e prezzo.'},
 {type:'cross',date:'2026-10-17',title:'Weekly Macro & Cross-Asset',file:'Weekly_Global_Macro_Strength_Cross_Asset_2026-10-17_DARK_EDITORIAL_PRO_CLEAN.html',desc:'Relazioni tra azioni, credito, bond, commodities e valute.',publicUrl:'./reports/Weekly_Global_Macro_Strength_Cross_Asset_2026-10-17_DARK_EDITORIAL_PRO_CLEAN.html'},
 {type:'pairs',date:'2026-10-17',title:'Weekly FX Pair Selection',file:'Weekly_FX_Pair_Selection_Conviction_2026-10-17.html',desc:'Selezione delle coppie Forex e confronto relativo delle valute G8.',publicUrl:'./reports/Weekly_FX_Pair_Selection_Conviction_2026-10-17.html'}
]);
const CATEGORIES=Object.freeze([['all','Tutti'],['daily','Daily Forex'],['macro','Global Macro'],['bank','Banche FX'],['cb','Banche centrali'],['ois','Curve OIS'],['cot','COT'],['cross','Cross-Asset'],['pairs','Coppie FX']]);
const MONTHS=Object.freeze({GEN:1,FEB:2,MAR:3,APR:4,MAG:5,GIU:6,LUG:7,AGO:8,SET:9,OTT:10,NOV:11,DIC:12});
const BLOCKED=/(_PROVA|_TEST|_BOZZA|_DRAFT|_BACKUP|_ANTEPRIMA|_PREVIEW|_LEGACY|_OLD|_DATI_PARZIALI)(_|\.|$)/i;
let category='all',query='',remoteReports=[],lastLookupAt=0,refreshInFlight=false;
const esc=x=>String(x==null?'':x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
const norm=x=>String(x||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('it-IT').trim();
const label=x=>(CATEGORIES.find(c=>c[0]===x)||['','Report'])[1];
const datestr=s=>s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4);
function reportType(file){
 if(file.startsWith('Briefing_Forex_Commodities_'))return 'daily';
 if(file.startsWith('Weekly_Global_Macro_Report_'))return 'macro';
 if(file.startsWith('Weekly_Bank_FX_Report_'))return 'bank';
 if(file.startsWith('Weekly_CB_Sentiment_Report_'))return 'cb';
 if(file.startsWith('Weekly_CB_Pricing_G8_')||file.startsWith('Weekly_Central_Bank_Pricing_G8_'))return 'ois';
 if(file.startsWith('COT_FX_G8_'))return 'cot';
 if(file.startsWith('Weekly_Global_Macro_Strength_Cross_Asset_'))return 'cross';
 if(file.startsWith('Weekly_FX_Pair_Selection_'))return 'pairs';
 return null;
}
function reportDate(file){
 const iso=file.match(/(?:^|_)(20\d{2}-\d{2}-\d{2})(?:_|\.|$)/);
 if(iso)return iso[1];
 const cot=file.match(/^COT_FX_G8_(\d{2})_([A-Z]{3})_(20\d{2})_/i);
 if(cot&&MONTHS[cot[2].toUpperCase()])return cot[3]+'-'+String(MONTHS[cot[2].toUpperCase()]).padStart(2,'0')+'-'+cot[1];
 return null;
}
function revisionScore(file){
 const versions=[...file.matchAll(/(?:^|_)V(\d+)(?:_|\.|$)/gi)].map(m=>+m[1]);
 return Math.max(0,...versions)*100+(/(DEFINITIV|CORRETT|FINAL|APPROVAT)/i.test(file)?1:0);
}
function remoteReport(file){
 if(typeof file!=='string'||!file.endsWith('.html')||BLOCKED.test(file))return null;
 const type=reportType(file),date=reportDate(file),canonical=REPORTS.find(r=>r.type===type);
 if(!type||!date||!canonical)return null;
 const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 if(date>today)return null;
 return {...canonical,date,file,publicUrl:ROOT+encodeURIComponent(file)};
}
function latestPerType(items){
 const selected=new Map();
 for(const item of items){
  const prior=selected.get(item.type);
  if(!prior||item.date>prior.date||(item.date===prior.date&&revisionScore(item.file)>revisionScore(prior.file)))selected.set(item.type,item);
 }
 return [...selected.values()].sort((a,b)=>b.date.localeCompare(a.date)||a.title.localeCompare(b.title));
}
function filterReports(type=category,search=query){
 const q=norm(search);
 return latestPerType([...REPORTS,...remoteReports]).filter(r=>(type==='all'||type===r.type)
  &&(!q||norm([r.title,label(r.type),r.desc,r.date,r.file].join(' ')).includes(q)));
}
// "Latest published" is a publication fact, not a freshness guarantee.
// For COT, the filename date is the Tuesday POSITION snapshot, not release.
function romeDay(){
 return new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',
  month:'2-digit',day:'2-digit'}).format(new Date());
}
function dayAge(then,today){
 const pat=/^20\d{2}-(0[1-9]|1[0-2])-([0-2]\d|3[01])$/;
 if(!pat.test(then||'')||!pat.test(today||'')||then>today)return null;
 const a=Date.parse(then+'T12:00:00Z'),b=Date.parse(today+'T12:00:00Z');
 return Number.isFinite(a)&&Number.isFinite(b)?Math.round((b-a)/86400000):null;
}
function expectedLastWeekday(today){
 if(dayAge(today,today)===null)return null;
 const d=new Date(today+'T12:00:00Z');
 while(d.getUTCDay()===0||d.getUTCDay()===6)d.setUTCDate(d.getUTCDate()-1);
 return d.toISOString().slice(0,10);
}
function editionStatus(r,today=romeDay()){
 const days=dayAge(r?.date,today);
 if(days===null)return {state:'unverified',text:'Data del report non confrontabile con oggi'};
 if(r.type==='daily'){
  if(r.date===today)return {state:'today',text:'Briefing pubblicato per la seduta odierna'};
  if(r.date===expectedLastWeekday(today))return {state:'latest-business',text:'Ultimo briefing feriale disponibile'};
  return {state:'previous',text:'Ultimo briefing pubblicato · non copre l’ultima seduta feriale'};
 }
 if(r.type==='cot')return {state:days<=10?'weekly':'previous',
  text:(days<=10?'Ultimo COT pubblicato':'Edizione COT precedente')+
   ' · posizioni al '+datestr(r.date)+' (martedì)'};
 return {state:days<=8?'weekly':'previous',
  text:days<=8?'Ultimo report settimanale pubblicato':'Edizione storica · non aggiornata questa settimana'};
}
function url(r){return r.publicUrl||(r.date>='2026-11-01'?ROOT:BASE)+encodeURIComponent(r.file);}
function rows(today=romeDay()){
 const list=filterReports();
 return list.length?list.map(r=>'<article class="rl-card"><div class="rl-card-meta"><span class="rl-tag">'+esc(label(r.type))+'</span><time datetime="'+esc(r.date)+'">'+datestr(r.date)+'</time></div>'+
  '<h3>'+esc(r.title)+'</h3><p>'+esc(r.desc)+'</p>'+
  '<div class="rl-card-bottom"><span class="rl-status">'+esc(editionStatus(r,today).text)+'</span>'+
  '<a href="'+esc(url(r))+'" target="_blank" rel="noopener noreferrer" aria-label="Apri '+esc(r.title)+' del '+datestr(r.date)+'">Apri report ↗</a></div></article>').join('')
  :'<div class="rl-empty">Nessun report corrisponde alla ricerca. Cambia categoria o parola chiave.</div>';
}
function filters(){return CATEGORIES.map(([id,name])=>'<button type="button" data-library-type="'+id+'" aria-pressed="'+String(id===category)+'">'+esc(name)+'</button>').join('');}
function render(){
 if(root.document&&!refreshInFlight&&Date.now()-lastLookupAt>30*60*1000){lastLookupAt=Date.now();Promise.resolve().then(refresh);}
 const latest=latestPerType([...REPORTS,...remoteReports]);
 return '<section class="rl-head"><div><span class="rl-eyebrow">FX QUANT / RESEARCH LIBRARY</span>'+
  '<h1>Solo l’ultima edizione.</h1>'+
  '<p>Una lettura per ciascun report: Briefing Forex, Macro, banche centrali, curve OIS, posizionamento e selezione delle coppie.</p>'+
  '<div class="rl-head-note"><strong>Ogni report conserva la propria frequenza.</strong> La pagina segnala se l’ultima edizione pubblicata è ancora recente. Le date sono riferimenti editoriali, non quotazioni intraday: produzione e trasferimento dei report sono processi separati.</div>'+
  '</div><div class="rl-stats"><div><small>ULTIME EDIZIONI PUBBLICATE</small><strong>'+latest.length+'</strong></div>'+
  '<div><small>ULTIMA EDIZIONE DISPONIBILE</small><strong id="library-latest-date">'+(latest[0]?datestr(latest[0].date):'—')+'</strong></div>'+
  '<div><small>TIPOLOGIE</small><strong>'+(CATEGORIES.length-1)+'</strong></div></div></section>'+
  '<section class="rl-controls" aria-label="Filtri e ricerca"><div id="library-filterbar" class="rl-filters">'+filters()+'</div>'+
  '<label class="rl-search" for="library-search"><span>Cerca fra gli ultimi report</span><input id="library-search" type="search" autocomplete="off" placeholder="Es. OIS, COT, Fed, macro..." value="'+esc(query)+'"></label></section>'+
  '<section aria-label="Ultimi report pubblicati"><div class="rl-result-head"><h2>Ultime edizioni</h2><span id="library-match-count">'+filterReports().length+' di '+latest.length+' report · uno per categoria</span></div>'+
  '<div id="library-grid" class="rl-grid">'+rows()+'</div></section>'+
  '<section class="rl-disclaimer"><h2>Come avviene l’aggiornamento</h2>'+
  '<p>La Library seleziona automaticamente l’ultima edizione approvata presente sul sito. Quando è accessibile il repository pubblico, controlla anche nuove pubblicazioni HTML e mostra solo quelle già raggiungibili su GitHub Pages. La creazione e il trasferimento automatico dei report da ChatGPT restano processi distinti: una nuova edizione compare solo se è stata realmente pubblicata.</p>'+
  '<div class="rl-next"><span>APPROFONDIMENTI</span><a href="#overview">Panoramica FX ↗</a><a href="#news">Calendario macro ↗</a><a href="#pairs">Monitor tesi FX ↗</a></div></section>';
}
function setCategory(value){category=CATEGORIES.some(x=>x[0]===value)?value:'all';}
function setQuery(value){query=String(value||'').slice(0,120);}
function sync(){
 if(!root.document)return;
 const grid=root.document.getElementById('library-grid'),count=root.document.getElementById('library-match-count'),bar=root.document.getElementById('library-filterbar');
 if(grid)grid.innerHTML=rows();
 if(count)count.textContent=filterReports().length+' di '+latestPerType([...REPORTS,...remoteReports]).length+' report · uno per categoria';
 if(bar)bar.innerHTML=filters();
 const dateEl=root.document.getElementById('library-latest-date');
 if(dateEl){const top=latestPerType([...REPORTS,...remoteReports])[0];dateEl.textContent=top?datestr(top.date):'—';}
}
async function refresh(){
 if(typeof root.fetch!=='function'||refreshInFlight)return;
 refreshInFlight=true;lastLookupAt=Date.now();
 try{
  const response=await root.fetch(PUBLIC_API,{headers:{Accept:'application/vnd.github+json'},cache:'no-store'});
  if(!response.ok)throw Error('Repo API '+response.status);
  const entries=await response.json();
  if(!Array.isArray(entries))throw Error('Invalid catalog');
  const found=latestPerType(entries.filter(e=>e&&e.type==='file'&&typeof e.name==='string').map(e=>remoteReport(e.name)).filter(Boolean));
  const published=await Promise.all(found.map(async r=>{
   try{const h=await root.fetch(r.publicUrl,{method:'HEAD',cache:'no-store'});return h.ok?r:null;}
   catch(_){return null;}
  }));
  remoteReports=published.filter(Boolean);
 }catch(_){/* Keep last verified edition or pinned catalog. */}
 finally{refreshInFlight=false;}
 if(root.document?.getElementById('library-grid'))sync();
}
const api={REPORTS,CATEGORIES,filterReports,reportType,reportDate,remoteReport,latestPerType,editionStatus,render,rows,setCategory,setQuery,sync,url,refresh};
root.FXQuantResearchLibrary=api;
if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
