(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  let state={d:null,ctx:null,releases:null,changed:null,selected:'USD'};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const score=(v)=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(2)}`};
  const cls=v=>{const x=n(v);return x===null?'':x>.15?'pos':x<-.15?'neg':''};
  const cycle=c=>state.d?.macro?.[c]?.cycle_it||state.d?.macro?.[c]?.cycle||'—';
  const macro=c=>state.d?.macro?.[c]||{};
  const ctx=c=>state.ctx?.[c]||{};
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  function trim(s,max=150){s=String(s||'');return s.length<=max?s:s.slice(0,max-1).trimEnd()+'…';}
  function renderSelect(){
    const h=document.getElementById('macro-select');if(!h)return;
    h.innerHTML=ORDER.map(c=>`<button data-ccy="${c}" class="${c===state.selected?'active':''}"><span class="flag">${FLAGS[c]}</span>${c}</button>`).join('');
    h.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{state.selected=b.dataset.ccy;renderSelect();renderGrid();renderDetail();}));
  }
  function card(c){
    const m=macro(c),x=ctx(c);
    return `<article class="macro-card ${c===state.selected?'selected':''}" data-ccy="${c}"><div class="macro-card-top"><div class="macro-id"><span class="flag">${FLAGS[c]}</span><div><b>${c}</b><small>${esc(x.status||m.quality_label||'CURRENT')}</small></div></div><span class="cycle-pill">${esc(cycle(c))}</span></div><div class="macro-scores"><div><small>Crescita</small><b class="${cls(m.growth)}">${score(m.growth)}</b></div><div><small>Lavoro</small><b class="${cls(m.labour)}">${score(m.labour)}</b></div><div><small>Inflazione</small><b class="${cls(m.inflation)}">${score(m.inflation)}</b></div></div><p class="macro-summary">${esc(trim(x.summary_it||m.simple_summary||'',150))}</p></article>`;
  }
  function renderGrid(){
    const h=document.getElementById('macro-grid');if(!h)return;
    h.innerHTML=ORDER.map(card).join('');
    h.querySelectorAll('.macro-card').forEach(el=>el.addEventListener('click',()=>{state.selected=el.dataset.ccy;renderSelect();renderGrid();renderDetail();}));
    const asof=document.getElementById('macro-asof');if(asof)asof.textContent=`8 valute G8 · dataset ${state.d?.asOf||'—'}`;
  }
  function renderDetail(){
    const c=state.selected,x=ctx(c),m=macro(c);
    const title=document.getElementById('macro-detail-title'),status=document.getElementById('macro-detail-status'),lead=document.getElementById('macro-detail-lead'),table=document.getElementById('macro-sector-table');
    if(title)title.textContent=`${FLAGS[c]} ${c} · ${cycle(c)}`;
    if(status)status.textContent=String(x.macro_quality||x.confidence||x.status||m.quality_label||'CURRENT').replaceAll('_',' ');
    if(lead)lead.textContent=x.summary_it||m.simple_summary||'Quadro non disponibile.';
    const sectors=Object.entries(x.sector_states_it||{});
    if(table)table.innerHTML=sectors.length?sectors.map(([k,v])=>`<div class="macro-sector-row"><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join(''):'<div class="macro-sector-row"><span>Dettaglio settoriale non disponibile.</span></div>';
    renderReleases();renderChange();
  }
  function renderReleases(){
    const h=document.getElementById('macro-releases');if(!h)return;
    const events=(state.releases?.events||[]).filter(e=>e.ccy===state.selected).sort((a,b)=>String(a.date).localeCompare(String(b.date))).slice(0,5);
    h.innerHTML=events.length?events.map(e=>`<div class="macro-release"><div class="macro-release-top"><b>${esc(e.title)}</b><em class="${e.importance==='HIGH'?'high':''}">${esc(e.date||'—')}</em></div><small>${esc(e.event_type||'MACRO')} · ${esc(e.reference_period||'—')} · ${esc(e.source_family||'fonte ufficiale')}</small></div>`).join(''):'<div class="macro-release"><small>Nessun prossimo release ufficiale pubblicato per questa valuta nel seed corrente.</small></div>';
  }
  function renderChange(){
    const h=document.getElementById('macro-change');if(!h)return;
    const x=Array.isArray(state.changed)?state.changed.find(r=>r.ccy===state.selected):null;
    if(!x){h.textContent='Nessun aggiornamento sintetico disponibile.';return;}
    const rm=n(x.rate_move),pct=n(x.pct),netoi=n(x.netoi);
    h.innerHTML=`${esc(x.summary||'')}<br><br><strong>2Y:</strong> ${rm===null?'—':`${rm>0?'+':''}${rm.toFixed(1)}bp`} · <strong>COT pct:</strong> ${pct===null?'—':pct.toFixed(1)} · <strong>Net/OI:</strong> ${netoi===null?'—':`${netoi.toFixed(1)}%`}<br><br><span class="status">Questi layer sono contesto: non modificano da soli il quadro macro.</span>`;
  }
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d);}
  function bind(){document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html');}
  async function main(){bind();clock();setInterval(clock,30000);try{[state.d,state.ctx,state.releases,state.changed]=await Promise.all([load('D.json'),load('COUNTRY_CTX.json'),load('MACRO_RELEASE_OFFICIAL_SEED_V1.json'),load('WHAT_CHANGED.json')]);if(!state.d?.macro||Object.keys(state.d.macro).length<8)throw new Error('Macro payload incomplete');if(state.releases?.schema!=='GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1')throw new Error('Macro release contract invalid');renderSelect();renderGrid();renderDetail();document.documentElement.dataset.macroDataPage='READY';}catch(e){console.warn('[GMFQ Macro Data]',e);document.documentElement.dataset.macroDataPage='FAIL';}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
