(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const STORE='gmfq.website.watchlist.v1';
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  let state={d:null,setup:null,rates:null,ois:null,cot:null,selected:[]};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const norm=p=>String(p||'').replace(/[^A-Z]/g,'').slice(0,6);
  const split=p=>[norm(p).slice(0,3),norm(p).slice(3,6)];
  const signed=(v,d=1,s='')=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}${s}`};
  const cls=v=>{const x=n(v);return x===null?'':x>0?'pos':x<0?'neg':''};
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: HTTP ${r.status}`);return r.json();}
  function readStore(){try{const x=JSON.parse(localStorage.getItem(STORE)||'[]');return Array.isArray(x)?[...new Set(x.map(norm).filter(x=>x.length===6))]:[]}catch{return []}}
  function writeStore(){localStorage.setItem(STORE,JSON.stringify(state.selected));}
  function rate2(c){return n(state.rates?.[c]?.['2Y'])??n(state.rates?.[c]?.current?.y2)??n(state.d?.macro?.[c]?.rate2y)}
  function ois3(c){return n(state.ois?.currencies?.[c]?.horizons?.['3m']?.rate)}
  function cotPct(c){const a=state.cot?.[c]?.percentile;return Array.isArray(a)&&a.length?n(a.at(-1)):null}
  function qualityClass(q){q=String(q||'').toUpperCase();if(q.includes('PULITO'))return'clean';if(q.includes('RISCHI'))return'risky';if(q.includes('CONFERMARE'))return'confirm';return'monitor'}
  function allPairs(){return (state.d?.pairs||[]).map(x=>norm(x.pair)).filter(x=>x.length===6).sort()}
  function pairRow(pair){return (state.d?.pairs||[]).find(x=>norm(x.pair)===pair)||null}
  function setupRow(pair){return state.setup?.pairs?.[pair]||null}
  function renderSelect(){
    const s=document.getElementById('watch-pair');if(!s)return;
    const available=allPairs().filter(p=>!state.selected.includes(p));
    s.innerHTML=available.length?available.map(p=>`<option value="${p}">${p.slice(0,3)}/${p.slice(3)}</option>`).join(''):'<option value="">Tutte le pair sono già in lista</option>';
    document.getElementById('watch-add').disabled=!available.length;
  }
  function card(pair){
    const row=pairRow(pair),snap=setupRow(pair),setup=snap?.setup||{},[a,b]=split(pair);
    const y2a=rate2(a),y2b=rate2(b),oisa=ois3(a),oisb=ois3(b),ca=cotPct(a),cb=cotPct(b);
    const y2=y2a===null||y2b===null?null:(y2a-y2b)*100;
    const ois=oisa===null||oisb===null?null:(oisa-oisb)*100;
    const cot=ca===null||cb===null?null:ca-cb;
    const q=setup.quality||'NON VALUTABILE', fav=setup.structuralFav||snap?.decision_frame?.fav||'—';
    const relation=setup.structural?.relation||snap?.decision_frame?.relation||'Struttura relativa non disponibile.';
    const missing=setup.structural?.missing||snap?.decision_frame?.missing||setup.timing?.text||'Nessuna nota aggiuntiva.';
    const last=n(row?.last),ret=n(row?.ret1w);
    return `<article class="watch-card" data-pair="${pair}"><div class="watch-top"><div class="watch-pair"><span class="watch-rank">${FLAGS[a]||''}/${FLAGS[b]||''}</span><div><h3>${a}/${b}</h3><span class="watch-quality ${qualityClass(q)}">${esc(q)}</span></div></div><div class="watch-actions"><a href="coppia.html?pair=${pair}">Deep Dive →</a><button type="button" data-remove="${pair}">Rimuovi</button></div></div><div class="watch-thesis"><small>VANTAGGIO STRUTTURALE · ${esc(fav)}</small><b>${esc(setup.price?.text||snap?.decision_frame?.priceReading||'Prezzo non classificato')}</b><p>${esc(relation)}</p></div><div class="watch-metrics"><div class="watch-metric"><small>Prezzo</small><b>${last===null?'—':last.toFixed(last>=100?2:4)}</b></div><div class="watch-metric"><small>1W</small><b class="${cls(ret)}">${signed(ret,2,'%')}</b></div><div class="watch-metric"><small>2Y spread</small><b class="${cls(y2)}">${signed(y2,0,'bp')}</b></div><div class="watch-metric"><small>Pricing 3M</small><b class="${cls(ois)}">${signed(ois,0,'bp')}</b></div><div class="watch-metric"><small>COT diff</small><b class="${cls(cot)}">${signed(cot,0)}</b></div></div><div class="watch-foot"><strong>Da monitorare:</strong> ${esc(missing)} · Timing: ${esc(setup.timing?.text||'—')} · Estensione: ${esc(setup.extension?.text||'—')}</div></article>`;
  }
  function render(){
    renderSelect();
    const grid=document.getElementById('watch-grid'),empty=document.getElementById('watch-empty');
    if(grid)grid.innerHTML=state.selected.map(card).join('');
    if(empty)empty.hidden=state.selected.length>0;
    document.getElementById('watch-count').textContent=String(state.selected.length);
    const asof=document.documentElement.getAttribute('data-website-price-asof')||state.setup?.price_asof||'—';
    document.getElementById('watch-asof').textContent=asof;
    document.getElementById('watch-status').textContent=state.selected.length?`${state.selected.length} pair · aggiornamento canonico ${asof}`:'Nessuna pair aggiunta';
    grid?.querySelectorAll('[data-remove]').forEach(b=>b.addEventListener('click',()=>{state.selected=state.selected.filter(x=>x!==b.dataset.remove);writeStore();render()}));
    document.documentElement.dataset.watchlistPage='READY';
  }
  function bind(){
    document.getElementById('watch-add')?.addEventListener('click',()=>{const p=norm(document.getElementById('watch-pair')?.value);if(p.length!==6||state.selected.includes(p))return;state.selected.push(p);writeStore();render()});
    document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));
    document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html');
  }
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  async function main(){
    bind();clock();setInterval(clock,30000);state.selected=readStore();
    try{
      [state.d,state.setup,state.rates,state.ois,state.cot]=await Promise.all([load('D.json'),load('PAIR_SETUP_OPERATIONAL_VIEW.json'),load('NATIVE_RATES_DATA.json'),load('OIS_OPERATIONAL_VIEW.json'),load('V250_COT_CHART_DATA.json')]);
      if(state.setup?.schema!=='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'||state.setup?.status!=='CURRENT_CANONICAL_ENGINE'||state.setup?.pair_count!==28)throw new Error('Pair setup contract invalid');
      if(!window.GMFQWebsitePrice?.hydrate)throw new Error('Canonical Price runtime adapter missing');
      await window.GMFQWebsitePrice.hydrate(state.d);
      state.selected=state.selected.filter(p=>allPairs().includes(p));writeStore();render();
    }catch(e){console.warn('[GMFQ watchlist]',e);document.documentElement.dataset.watchlistPage='FAIL'}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();