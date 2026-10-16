(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  let state={calendar:null,filter:'ALL'};
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  const esc=s=>String(s??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  function todayRome(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
  function addDays(dateStr,n){const d=new Date(dateStr+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)}
  function fmtDate(s){if(!s)return '—';const d=new Date(s+'T12:00:00Z');return new Intl.DateTimeFormat('it-IT',{day:'2-digit',month:'short'}).format(d)}
  function isCB(e){return e?.event_type==='CENTRAL_BANK_DECISION'}
  function events(){return Array.isArray(state.calendar?.events)?state.calendar.events.filter(e=>e?.status==='UPCOMING'):[]}
  function filteredRows(){const rows=events();if(state.filter==='HIGH')return rows.filter(e=>e.importance==='HIGH');if(state.filter==='CB')return rows.filter(isCB);if(state.filter==='MACRO')return rows.filter(e=>!isCB(e));return rows}
  function renderSummary(){
    const rows=events(),today=todayRome(),end7=addDays(today,7),end14=addDays(today,14);
    const next7=rows.filter(e=>e.date>=today&&e.date<=end7),next14=rows.filter(e=>e.date>=today&&e.date<=end14);
    const high=next14.filter(e=>e.importance==='HIGH').length,cb=next14.filter(isCB).length;
    const active=new Set(next14.map(e=>e.ccy).filter(Boolean)).size;
    const host=document.getElementById('risk-summary');
    host.innerHTML=[
      ['Eventi prossimi 7g',next7.length,'macro + banche centrali'],
      ['High impact 14g',high,'solo calendario canonico'],
      ['Decisioni CB 14g',cb,'schedule certificato'],
      ['Valute coinvolte',active+'/8','copertura G8']
    ].map(([k,v,s])=>`<article class="risk-stat"><small>${k}</small><b>${v}</b><em>${s}</em></article>`).join('');
  }
  function renderEvents(){
    const rows=filteredRows().sort((a,b)=>String(a.date).localeCompare(String(b.date))||String(a.ccy).localeCompare(String(b.ccy)));
    const host=document.getElementById('risk-events');
    host.innerHTML=rows.map(e=>{
      const impact=String(e.importance||'—');
      const impactCls=impact==='HIGH'?'high':impact==='MEDIUM'?'medium':'';
      const type=isCB(e)?'Decisione CB':String(e.event_type||'Macro').replaceAll('_',' ');
      const consensus=e.consensus_status==='AVAILABLE'?`Cons. ${e.consensus||'—'} · Prev. ${e.previous||'—'}`:(e.previous?`Prev. ${e.previous}`:'—');
      const time=e.time_local?`${e.time_local} ${e.timezone||''}`.trim():(e.timezone||'orario non disponibile');
      return `<div class="risk-event-row"><span>${fmtDate(e.date)}<small class="event-meta">${esc(time)}</small></span><span class="ccy">${esc(e.ccy)}</span><span><span class="event-title">${esc(e.title)}</span><small class="event-meta">${esc(e.source_family||e.bank||e.source_layer||'fonte canonica')}</small></span><span class="${isCB(e)?'cb':''}">${esc(type)}</span><span class="${impactCls}">${esc(impact)}</span><span class="consensus">${esc(consensus)}</span></div>`;
    }).join('')||'<div class="method-copy">Nessun evento nel filtro selezionato.</div>';
    const asof=document.getElementById('risk-asof');if(asof)asof.textContent=`${rows.length} eventi mostrati · aggiornamento canonico`;
  }
  function renderCurrencies(){
    const today=todayRome(),end14=addDays(today,14),rows=events().filter(e=>e.date>=today&&e.date<=end14);
    const counts=Object.fromEntries(ORDER.map(c=>[c,{total:0,high:0,cb:0}]));
    rows.forEach(e=>{if(!counts[e.ccy])return;counts[e.ccy].total++;if(e.importance==='HIGH')counts[e.ccy].high++;if(isCB(e))counts[e.ccy].cb++;});
    const rank=ORDER.map(c=>({ccy:c,...counts[c],score:counts[c].high*2+counts[c].cb+counts[c].total*.25})).sort((a,b)=>b.score-a.score||ORDER.indexOf(a.ccy)-ORDER.indexOf(b.ccy));
    const max=Math.max(1,...rank.map(x=>x.score));
    document.getElementById('risk-currencies').innerHTML=rank.map(x=>`<div class="risk-ccy-row"><b>${x.ccy}</b><div class="risk-bar"><i style="width:${Math.round(x.score/max*100)}%"></i></div><span>${x.total}</span></div>`).join('');
    const top=rank[0],second=rank[1];
    document.getElementById('risk-window').innerHTML=`<div class="window-main">${top.total?`${top.ccy} è la valuta con la maggiore concentrazione di eventi nei prossimi 14 giorni.`:'Nessuna concentrazione eventi rilevante nei prossimi 14 giorni.'}</div><div class="window-note">${top.total?`${top.ccy}: ${top.total} eventi (${top.high} high impact). ${second?.total?`${second.ccy} segue con ${second.total}.`:''} La concentrazione segnala <strong>rischio di repricing</strong>, non una direzione di trade.`:'Il calendario non mostra al momento una finestra densa di eventi G8.'}</div>`;
  }
  function render(){renderSummary();renderEvents();renderCurrencies();document.documentElement.setAttribute('data-risk-page','READY')}
  function bind(){document.querySelectorAll('#risk-filters button').forEach(btn=>btn.addEventListener('click',()=>{state.filter=btn.dataset.filter;document.querySelectorAll('#risk-filters button').forEach(b=>b.classList.toggle('active',b===btn));renderEvents()}));document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html')}
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  async function main(){bind();clock();setInterval(clock,30000);try{state.calendar=await load('CALENDAR_OPERATIONAL_VIEW.json');render()}catch(e){console.warn('[GMFQ rischio-eventi]',e);document.documentElement.setAttribute('data-risk-page','FAIL')}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
