(()=>{
  'use strict';

  const VERSION='20261017-dashboard2';
  const SETUP_LOCAL='../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json';
  const SETUP_RAW='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json';
  const SETUP_PRIORITY={'PULITO':5,'CON RISCHI':4,'DA CONFERMARE':3,'DA MONITORARE':2,'NON VALUTABILE':1};

  if(!document.querySelector('link[data-control-room-css]')){
    const link=document.createElement('link');
    link.rel='stylesheet';
    link.href=`control-room.css?v=${VERSION}`;
    link.dataset.controlRoomCss='1';
    document.head.appendChild(link);
  }

  const brandmark=document.querySelector('.brandmark');
  if(brandmark)brandmark.replaceChildren();

  const routes={Dashboard:'index.html',Valute:'valute.html',Tassi:'tassi.html','Banche centrali':'banche-centrali.html',Posizionamento:'posizionamento.html',Coppie:'coppie.html','Rischio/Eventi':'rischio-eventi.html','Top Themes':'top-themes.html',Library:'library.html',Watchlist:'watchlist.html','Macro Data':'macro-data.html',Strumenti:'strumenti.html',Screener:'screener.html',Alert:'alert.html',Impostazioni:'impostazioni.html'};
  document.querySelectorAll('.nav a').forEach(a=>{const label=a.querySelector('b')?.textContent?.trim();if(routes[label])a.href=routes[label];});

  const cardRoutes={changed:'top-themes.html',rates:'tassi.html',cbs:'banche-centrali.html','cot-card':'posizionamento.html',setups:'coppie.html',calendar:'rischio-eventi.html',themes:'top-themes.html',watch:'watchlist.html'};
  Object.entries(cardRoutes).forEach(([cls,href])=>document.querySelectorAll(`.${cls} .card-head a`).forEach(a=>a.href=href));

  const params=new URLSearchParams(location.search);
  const heroAllowed=['1D','1W','1M','3M','YTD'];
  const hierarchyAllowed=['1D','1W','1M'];
  const heroPeriod=heroAllowed.includes(params.get('tf'))?params.get('tf'):'1D';
  const hierarchyPeriod=hierarchyAllowed.includes(params.get('h'))?params.get('h'):'1D';

  const heroTabs=document.querySelector('.hero-tabs');
  if(heroTabs){
    [...heroTabs.children].forEach(node=>{
      const label=node.textContent.trim();
      if(!heroAllowed.includes(label))return;
      const a=document.createElement('a');
      const p=new URLSearchParams(location.search);p.set('tf',label);
      a.href=`?${p.toString()}`;
      a.textContent=label;
      a.className=label===heroPeriod?'active':'';
      a.setAttribute('aria-label',`Timeframe ${label}`);
      node.replaceWith(a);
    });
  }

  const mini=document.querySelector('.hierarchy .mini-tabs');
  if(mini){
    [...mini.children].forEach(node=>{
      const label=node.textContent.trim();
      if(!hierarchyAllowed.includes(label))return;
      const a=document.createElement('a');
      const p=new URLSearchParams(location.search);p.set('h',label);
      a.href=`?${p.toString()}`;
      a.textContent=label;
      a.className=label===hierarchyPeriod?'active':'';
      a.setAttribute('aria-label',`Hierarchy ${label}`);
      node.replaceWith(a);
    });
  }

  const clock=()=>{
    const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');
    if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);
    if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d);
  };
  clock();setInterval(clock,30000);

  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[m]));
  const trim=(v,max)=>{const s=String(v??'');return s.length<=max?s:s.slice(0,max-1).trimEnd()+'…';};
  async function loadSetup(){
    for(const src of [SETUP_LOCAL,SETUP_RAW]){
      try{const r=await fetch(src,{cache:'no-store'});if(r.ok){const j=await r.json();if(j?.status==='CURRENT_CANONICAL_ENGINE'&&Object.keys(j?.pairs||{}).length===28)return j;}}catch(e){console.warn('[GMFQ setup fallback]',src,e);}
    }
    throw new Error('PAIR_SETUP_OPERATIONAL_VIEW unavailable');
  }
  function setupRows(data){return Object.entries(data?.pairs||{}).map(([code,x])=>({code,pair:x?.canonical_pair||`${code.slice(0,3)}/${code.slice(3,6)}`,setup:x?.setup||{},frame:x?.decision_frame||{}})).sort((a,b)=>{const qa=SETUP_PRIORITY[String(a.setup.quality||'').toUpperCase()]||0,qb=SETUP_PRIORITY[String(b.setup.quality||'').toUpperCase()]||0;return qb-qa||a.pair.localeCompare(b.pair);});}
  function renderSetupFallback(data){
    const host=document.querySelector('.setup-table');if(!host)return;
    const current=host.textContent||'';if(!current.includes('Nessun setup disponibile')&&host.querySelectorAll(':scope > div').length>1)return;
    const head='<div class="thead"><span>#</span><span>COPPIA</span><span>FAVORITA</span><span>QUALITÀ</span><span>LETTURA</span></div>';
    const rows=setupRows(data).slice(0,5);
    host.innerHTML=head+rows.map((x,i)=>{const fav=x.setup.structuralFav||x.frame.fav||'—';const q=x.setup.quality||x.frame.quality||'—';const rel=x.setup.structural?.relation||x.frame.relation||x.setup.price?.text||'—';return `<div><span>${i+1}</span><b><a href="coppia.html?pair=${encodeURIComponent(x.code)}">${esc(x.pair)}</a></b><span>${esc(fav)}</span><em>${esc(q)}</em><small>${esc(trim(rel,55))}</small></div>`;}).join('');
    document.documentElement.dataset.dashboardSetup='READY_FALLBACK';
  }
  function renderWatchFallback(data){
    const host=document.querySelector('.watch-table');if(!host)return;
    const head='<div class="thead"><span>COPPIA</span><span>QUALITÀ</span><span>FAVORITA</span><span>PREZZO</span><span>STATO</span></div>';
    let saved=[];try{const x=JSON.parse(localStorage.getItem('gmfq.website.watchlist.v1')||'[]');if(Array.isArray(x))saved=x;}catch{}
    if(!saved.length){host.innerHTML=head+'<div class="watch-empty-row"><span>☆</span><b>Nessuna pair in watchlist</b><small><a href="watchlist.html">Apri Watchlist →</a></small></div>';document.documentElement.dataset.dashboardWatch='EMPTY';return;}
    const pairs=data?.pairs||{};
    host.innerHTML=head+saved.slice(0,6).map(raw=>{const code=String(raw).replace(/[^A-Z]/g,''),x=pairs[code]||{},s=x.setup||{},f=x.decision_frame||{},pair=x.canonical_pair||raw;return `<div><b><a href="coppia.html?pair=${encodeURIComponent(code)}">${esc(pair)}</a></b><span>${esc(s.quality||f.quality||'—')}</span><span>${esc(s.structuralFav||f.fav||'—')}</span><span>${esc(s.price?.text||f.priceReading||'—')}</span><small>${esc(s.timing?.text||'Da monitorare')}</small></div>`;}).join('');
    document.documentElement.dataset.dashboardWatch='READY';
  }
  async function repairDashboardSetup(){try{const data=await loadSetup();renderSetupFallback(data);renderWatchFallback(data);}catch(e){console.warn('[GMFQ dashboard setup repair]',e);}}

  const loadScript=(src)=>new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=src;s.async=false;s.onload=resolve;s.onerror=reject;document.head.appendChild(s);});
  loadScript(`data-adapter.js?v=${VERSION}`).catch(e=>console.warn('[GMFQ data adapter]',e)).finally(()=>{
    repairDashboardSetup();
    loadScript(`market-snapshot.js?v=${VERSION}`).catch(e=>console.warn('[GMFQ market snapshot loader]',e));
  });
})();