(function(root){
'use strict';
/* Historical public report index. Never infer that a private Library report is public. */
const BASE='../../website-v1/reports/';
const REPORTS=Object.freeze([
 {date:'2026-11-11',type:'daily',title:'Briefing Forex & Commodities',file:'Briefing_Forex_Commodities_2026-11-11_V3_HEADER_CORRETTO.html',desc:'Lettura mattutina Forex G8 e commodities: quadro dopo il CPI USA, rischi e cosa monitorare. Edizione con intestazione corretta.'},
 {date:'2026-11-09',type:'daily',title:'Briefing Forex & Commodities',file:'Briefing_Forex_Commodities_2026-11-09_V2_FONT_COMPATTO.html',desc:'Briefing del 9 novembre con analisi G8, driver macro e valutazione relativa delle valute.'},
 {date:'2026-11-06',type:'macro',title:'Weekly Global Macro Report',file:'Weekly_Global_Macro_Report_2026-11-06_COUNTRY_BOOK_NARRATIVO_V4_CORRETTA.html',desc:'Edizione canonica settimanale Country Book: lettura narrativa di crescita, tassi, rischio e valute.'},
 {date:'2026-11-06',type:'bank',title:'Weekly Bank FX Report',file:'Weekly_Bank_FX_Report_2026-11-06_DARK_DESK_NARRATIVO_V5.html',desc:'Le view bancarie G8 e il giudizio indipendente del desk, con fonti e consenso datati.'},
 {date:'2026-11-06',type:'cb',title:'Weekly Central Bank Sentiment',file:'Weekly_CB_Sentiment_Report_2026-11-06_DARK_RESEARCH_DESK_WANT_CAN_V4_PALETTE.html',desc:'Approccio WANT/CAN alle banche centrali G8: tono, vincoli e implicazioni FX distinte.'},
 {date:'2026-11-03',type:'cot',title:'COT FX G8',file:'COT_FX_G8_03_NOV_2026_DARK_QUANT_DESK_v10_DEFINITIVO_LETTURA_INTEGRATA.html',desc:'Posizionamento CFTC riferito al 3 novembre, pubblicato il 6: flussi, concentrazione e confronto con il prezzo.'},
 {date:'2026-10-15',type:'monitor',title:'Trade Thesis Monitor',file:'Trade_Thesis_Monitor_2026-10-15_DARK_DESK_CLEAN.html',desc:'Verifica delle tesi FX: contesto macro, pricing, posizionamento e reazione del prezzo.'},
 {date:'2026-10-14',type:'monitor',title:'Trade Thesis Monitor',file:'Trade_Thesis_Monitor_2026-10-14_DARK_DESK_CLEAN.html',desc:'Come si sono evolute le tesi FX e quali conferme sono arrivate dal mercato.'},
 {date:'2026-10-13',type:'monitor',title:'Trade Thesis Monitor',file:'Trade_Thesis_Monitor_2026-10-13_DARK_DESK.html',desc:'Forza della tesi distinta dall’attrattiva del trade, con rischi e condizioni di conferma.'},
 {date:'2026-10-11',type:'cb',title:'Weekly Central Bank Sentiment',file:'Weekly_CB_Sentiment_Report_2026-10-11_DARK_RESEARCH_DESK_v23_TERMINOLOGY_HAWKISH.html',desc:'Tono e priorità delle banche centrali G8: contesto storico, non il pricing di oggi.'},
 {date:'2026-10-10',type:'bank',title:'Weekly Bank FX Report',file:'Weekly_Bank_FX_Report_2026-10-10_DARK_RESEARCH_DESK_v9_COMPLETE_LIGHT.html',desc:'Le view bancarie sul Forex, separate dall’interpretazione autonoma del desk.'},
 {date:'2026-10-10',type:'cross',title:'Weekly Macro & Cross-Asset',file:'Weekly_Global_Macro_Strength_Cross_Asset_2026-10-10_DARK_EDITORIAL_PRO_BTC.html',desc:'Collegamenti storici tra rischio, azioni, bond, commodities e valute.'},
 {date:'2026-10-10',type:'macro',title:'Weekly Global Macro Report',file:'Weekly_Global_Macro_Report_2026-10-10_DARK_DESK_DEFINITIVO.html',desc:'Macro Strength: confronto tra economie, crescita, inflazione e condizioni finanziarie.'},
 {date:'2026-10-10',type:'pairs',title:'Weekly FX Pair Selection',file:'Weekly_FX_Pair_Selection_Conviction_2026-10-10.html',desc:'Selezione storica delle coppie e confronto relativo tra valute G8.'},
 {date:'2026-10-06',type:'cot',title:'COT FX G8',file:'COT_FX_G8_06_OTT_2026_DARK_QUANT_DESK_v6_ORDINATO_FINAL.html',desc:'Posizionamento CFTC della settimana di riferimento: variazioni e concentrazione dei fondi.'}
]);
const CATEGORIES=Object.freeze([['all','Tutti'],['daily','Daily Forex'],['macro','Global Macro'],['cross','Cross-Asset'],['bank','Banche FX'],['cb','Banche centrali'],['cot','COT'],['pairs','Coppie FX'],['monitor','Trade Monitor']]);
let category='all',query='';
function esc(x){return String(x===null||x===undefined?'':x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));}
function norm(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('it-IT').trim();}
function label(type){return (CATEGORIES.find(x=>x[0]===type)||['','Archivio'])[1];}
function datestr(s){return s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4);}
function filterReports(type=category,search=query){
 const term=norm(search);
 return REPORTS.filter(r=>(type==='all'||r.type===type)&&(!term||norm([r.title,r.type,label(r.type),r.desc,r.date,r.file].join(' ')).includes(term)))
   .sort((a,b)=>b.date.localeCompare(a.date)||a.title.localeCompare(b.title));
}
function url(r){return BASE+encodeURIComponent(r.file);}
function rows(){
 const list=filterReports();
 return list.length?list.map(r=>
  '<article class="rl-card"><div class="rl-card-meta"><span class="rl-tag">'+esc(label(r.type))+'</span><time datetime="'+esc(r.date)+'">'+datestr(r.date)+'</time></div>'+
  '<h3>'+esc(r.title)+'</h3><p>'+esc(r.desc)+'</p>'+
  '<div class="rl-card-bottom"><span class="rl-status">'+(r.type==='monitor'?'Trade Monitor storico · non aggiornato':r.type==='daily'?'Briefing quotidiano · HTML originale':'Report datato · HTML originale')+'</span>'+
  '<a href="'+esc(url(r))+'" target="_blank" rel="noopener noreferrer" aria-label="Apri '+esc(r.title)+' del '+datestr(r.date)+'">Apri report ↗</a></div></article>'
 ).join(''):'<div class="rl-empty">Nessun report corrisponde alla ricerca. Cambia categoria o parola chiave.</div>';
}
function filters(){return CATEGORIES.map(([id,text])=>'<button type="button" data-library-type="'+id+'" aria-pressed="'+String(id===category)+'">'+esc(text)+'</button>').join('');}
function render(){
 return '<section class="rl-head"><div><span class="rl-eyebrow">FX QUANT / RESEARCH LIBRARY</span>'+
  '<h1>La ricerca che resta.</h1>'+
  '<p>Un unico posto per ritrovare le tesi dei report pubblicati e confrontare come leggevamo il mercato nelle settimane precedenti.</p>'+
  '<div class="rl-head-note"><strong>Edizioni datate, non feed intraday.</strong> I report conservano contenuti e giudizi originali. Il Briefing HTML più recente pubblicato è dell’11 novembre 2026. Per la lettura Forex aggiornata usa Panoramica e Coppie FX.</div>'+
  '</div><div class="rl-stats"><div><small>REPORT PUBBLICATI</small><strong>'+REPORTS.length+'</strong></div>'+
  '<div><small>ULTIMA EDIZIONE ONLINE</small><strong>'+datestr(filterReports('all','')[0].date)+'</strong></div>'+
  '<div><small>TIPOLOGIE</small><strong>'+(CATEGORIES.length-1)+'</strong></div></div></section>'+
  '<section class="rl-controls" aria-label="Ricerca e categorie report"><div id="library-filterbar" class="rl-filters">'+filters()+'</div>'+
  '<label class="rl-search" for="library-search"><span>Ricerca nei titoli e nelle descrizioni</span><input id="library-search" type="search" autocomplete="off" placeholder="Es. COT, banche, EUR, macro..." value="'+esc(query)+'"></label></section>'+
  '<section aria-label="Report pubblicati"><div class="rl-result-head"><h2>Archivio dei report</h2><span id="library-match-count">'+filterReports().length+' di '+REPORTS.length+' report · più recenti prima</span></div>'+
  '<div id="library-grid" class="rl-grid">'+rows()+'</div></section>'+
  '<section class="rl-disclaimer"><h2>Cosa è incluso, e cosa no</h2>'+
  '<p>I Daily e i Weekly qui elencati sono copie di report reali, pubblicate con data e contenuti originali. La sincronizzazione automatica da ChatGPT Library a GitHub non è ancora attiva: nuovi report prodotti non compariranno qui finché non vengono pubblicati. I tre Trade Thesis Monitor disponibili si fermano al 15 ottobre; restano consultabili soltanto come storico.</p>'+
  '<div class="rl-next"><span>LETTURA AGGIORNATA NEL SITO</span><a href="#overview">Panoramica FX ↗</a><a href="#news">Calendario macro ↗</a><a href="#pairs">Monitor tesi FX ↗</a></div></section>';
}
function setCategory(value){category=CATEGORIES.some(x=>x[0]===value)?value:'all';}
function setQuery(value){query=String(value||'').slice(0,120);}
function sync(){
 if(!root.document)return;
 const grid=root.document.getElementById('library-grid'),count=root.document.getElementById('library-match-count'),bar=root.document.getElementById('library-filterbar');
 if(grid)grid.innerHTML=rows();
 if(count)count.textContent=filterReports().length+' di '+REPORTS.length+' report · più recenti prima';
 if(bar)bar.innerHTML=filters();
}
const api={REPORTS,CATEGORIES,filterReports,render,rows,setCategory,setQuery,sync,url};
root.FXQuantResearchLibrary=api;
if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
