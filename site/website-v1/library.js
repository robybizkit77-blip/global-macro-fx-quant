(()=>{
  'use strict';
  const reports=[
    {date:'2026-10-15',type:'Trade Monitor',title:'Trade Thesis Monitor',file:'Trade_Thesis_Monitor_2026-10-15_DARK_DESK_CLEAN.html',href:'reports/Trade_Thesis_Monitor_2026-10-15_DARK_DESK_CLEAN.html',desc:'Monitor serale delle tesi FX con controllo Macro → Rates → Pricing → Positioning → Price.'},
    {date:'2026-10-14',type:'Trade Monitor',title:'Trade Thesis Monitor',file:'Trade_Thesis_Monitor_2026-10-14_DARK_DESK_CLEAN.html',href:'reports/Trade_Thesis_Monitor_2026-10-14_DARK_DESK_CLEAN.html',desc:'Monitor serale delle tesi FX e verifica della reazione effettiva del mercato.'},
    {date:'2026-10-13',type:'Trade Monitor',title:'Trade Thesis Monitor',file:'Trade_Thesis_Monitor_2026-10-13_DARK_DESK.html',href:'reports/Trade_Thesis_Monitor_2026-10-13_DARK_DESK.html',desc:'Monitor serale delle tesi FX con separazione tra thesis strength e trade attractiveness.'},
    {date:'2026-10-11',type:'CB Sentiment',title:'Weekly CB Sentiment',file:'Weekly_CB_Sentiment_Report_2026-10-11_DARK_RESEARCH_DESK_v23_TERMINOLOGY_HAWKISH.html',href:'reports/Weekly_CB_Sentiment_Report_2026-10-11_DARK_RESEARCH_DESK_v23_TERMINOLOGY_HAWKISH.html',desc:'Stance, focus, pricing e cambi di tono delle principali banche centrali G8.'},
    {date:'2026-10-10',type:'Bank FX',title:'Weekly Bank FX Report',file:'Weekly_Bank_FX_Report_2026-10-10_DARK_RESEARCH_DESK_v9_COMPLETE_LIGHT.html',href:'reports/Weekly_Bank_FX_Report_2026-10-10_DARK_RESEARCH_DESK_v9_COMPLETE_LIGHT.html',desc:'Sintesi settimanale delle view FX delle principali banche con dati, pricing e spot.'},
    {date:'2026-10-10',type:'Cross Asset',title:'Weekly Global Macro Strength & Cross-Asset',file:'Weekly_Global_Macro_Strength_Cross_Asset_2026-10-10_DARK_EDITORIAL_PRO_BTC.html',href:'reports/Weekly_Global_Macro_Strength_Cross_Asset_2026-10-10_DARK_EDITORIAL_PRO_BTC.html',desc:'Macro globale, rates, FX, commodities e cross-asset in formato editoriale operativo.'},
    {date:'2026-10-10',type:'Global Macro',title:'Weekly Global Macro Report',file:'Weekly_Global_Macro_Report_2026-10-10_DARK_DESK_DEFINITIVO.html',href:'reports/Weekly_Global_Macro_Report_2026-10-10_DARK_DESK_DEFINITIVO.html',desc:'Quadro macro settimanale con livello, direzione, velocità e turning point.'},
    {date:'2026-10-10',type:'COT',title:'COT FX G8',file:'COT_FX_G8_06_OTT_2026_DARK_QUANT_DESK_v6_ORDINATO_FINAL.html',href:'reports/COT_FX_G8_06_OTT_2026_DARK_QUANT_DESK_v6_ORDINATO_FINAL.html',desc:'Posizionamento CFTC G8 con percentile 104W, Net/OI, flussi ed estremi.'},
    {date:'2026-10-10',type:'Pair Selection',title:'Weekly FX Pair Selection',file:'Weekly_FX_Pair_Selection_Conviction_2026-10-10.html',href:'reports/Weekly_FX_Pair_Selection_Conviction_2026-10-10.html',desc:'Selezione settimanale delle coppie FX con confronto relativo tra valute e conviction.'}
  ];
  let active='Tutti';
  const TYPES=['Tutti',...new Set(reports.map(r=>r.type))];
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  function fmtDate(s){const d=new Date(s+'T12:00:00Z');return new Intl.DateTimeFormat('it-IT',{day:'2-digit',month:'short',year:'numeric'}).format(d)}
  function renderStats(){
    const cats=new Set(reports.map(r=>r.type)).size;
    const latest=[...reports].sort((a,b)=>b.date.localeCompare(a.date))[0]?.date||'—';
    const mirrored=reports.filter(r=>r.href).length;
    document.getElementById('library-stats').innerHTML=`<div class="library-stat"><small>Report indicizzati</small><b>${reports.length}</b></div><div class="library-stat"><small>Categorie</small><b>${cats}</b></div><div class="library-stat"><small>Ultimo report</small><b>${fmtDate(latest)}</b></div><div class="library-stat"><small>Web mirror</small><b>${mirrored}/${reports.length}</b></div>`;
  }
  function renderFilters(){document.getElementById('library-filters').innerHTML=TYPES.map(t=>`<button data-type="${esc(t)}" class="${t===active?'active':''}">${esc(t)}</button>`).join('')}
  function renderGrid(){
    const q=document.getElementById('library-search').value.trim().toLowerCase();
    const rows=reports.filter(r=>(active==='Tutti'||r.type===active)&&(!q||`${r.title} ${r.file} ${r.type} ${r.desc}`.toLowerCase().includes(q))).sort((a,b)=>b.date.localeCompare(a.date));
    document.getElementById('library-count').textContent=`${rows.length} report · archivio canonico`;
    document.getElementById('library-grid').innerHTML=rows.length?rows.map(r=>`<article class="report-card"><div class="report-top"><span class="report-type">${esc(r.type)}</span><span class="report-date">${esc(fmtDate(r.date))}</span></div><h3>${esc(r.title)}</h3><p>${esc(r.desc)}</p><div class="report-file">${esc(r.file)}</div><div class="report-footer">${r.href?`<span class="report-status">● Disponibile nel sito</span><a class="report-action ready" href="${esc(r.href)}" target="_blank" rel="noopener">Apri report →</a>`:`<span class="report-status pending">● Presente in Library</span><span class="report-action disabled" aria-disabled="true">Mirror web da completare</span>`}</div></article>`).join(''):'<div class="library-empty">Nessun report corrisponde al filtro selezionato.</div>';
  }
  function bind(){
    document.getElementById('library-filters').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;active=b.dataset.type;renderFilters();renderGrid()});
    document.getElementById('library-search').addEventListener('input',renderGrid);
    document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));
    document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html');
  }
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  function main(){renderStats();renderFilters();renderGrid();bind();clock();setInterval(clock,30000);document.documentElement.setAttribute('data-library-page','READY')}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();