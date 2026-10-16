(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const esc=s=>String(s??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  function card(t){const ccy=t.ccy2?`${t.ccy}/${t.ccy2}`:t.ccy;return `<article class="theme-card"><div class="theme-card-top"><span class="theme-ccy">${esc(ccy)}</span><span class="theme-state">${esc(t.state)}</span></div><h3>${esc(t.title)}</h3><p>${esc(t.body)}</p><div class="theme-driver"><small>Driver principale</small><b>${esc(t.lead)}</b></div><div class="theme-checks"><div class="theme-check confirm"><span>Conferma</span><b>${esc(t.confirm)}</b></div><div class="theme-check diverge"><span>Divergenza</span><b>${esc(t.diverge)}</b></div><div class="theme-check invalidate"><span>Invalida</span><b>${esc(t.invalidate)}</b></div></div></article>`}
  function render(rows){
    if(!Array.isArray(rows)||!rows.length)throw new Error('TOP_THEMES_EMPTY');
    const lead=rows[0],ccy=lead.ccy2?`${lead.ccy}/${lead.ccy2}`:lead.ccy;
    document.getElementById('themes-hero').innerHTML=`<article class="theme-lead"><div><small>Tema principale · ${esc(ccy)} · ${esc(lead.state)}</small><h2>${esc(lead.title)}</h2><p>${esc(lead.body)}</p></div><div class="theme-lead-side"><div class="theme-kpi"><span>Driver</span><b>${esc(lead.lead)}</b></div><div class="theme-kpi"><span>Conferma</span><b>${esc(lead.confirm)}</b></div><div class="theme-kpi"><span>Divergenza</span><b>${esc(lead.diverge)}</b></div><div class="theme-kpi"><span>Invalidazione</span><b>${esc(lead.invalidate)}</b></div></div></article>`;
    document.getElementById('themes-grid').innerHTML=rows.slice(1).map(card).join('');
    document.getElementById('themes-count').textContent=`${rows.length} temi · TOP_THEMES.json`;
    document.documentElement.setAttribute('data-top-themes-page','READY');
  }
  function bind(){document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html')}
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  async function main(){bind();clock();setInterval(clock,30000);try{render(await load('TOP_THEMES.json'))}catch(e){console.warn('[GMFQ top-themes]',e);document.documentElement.setAttribute('data-top-themes-page','FAIL')}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
