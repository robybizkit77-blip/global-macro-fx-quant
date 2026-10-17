(()=>{
  'use strict';

  const VERSION='20261017-finalui1';

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

  const cardRoutes={changed:'alert.html',rates:'tassi.html',cbs:'banche-centrali.html','cot-card':'posizionamento.html',calendar:'rischio-eventi.html',themes:'top-themes.html',watch:'watchlist.html'};
  Object.entries(cardRoutes).forEach(([cls,href])=>document.querySelectorAll(`.${cls} .card-head a`).forEach(a=>a.href=href));
  document.querySelectorAll('.card-head a').forEach(a=>{if(!a.getAttribute('href')){const title=(a.closest('.card-head')?.querySelector('h2')?.textContent||'').toLowerCase();if(title.includes('setup')||title.includes('pair'))a.href='screener.html';}});

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
      node.replaceWith(a);
    });
  }

  const clock=()=>{
    const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');
    if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);
    if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d);
  };
  clock();setInterval(clock,30000);

  const loadScript=(src)=>new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=src;s.async=false;s.onload=resolve;s.onerror=reject;document.head.appendChild(s);});
  loadScript(`data-adapter.js?v=${VERSION}`).catch(e=>console.warn('[GMFQ data adapter]',e)).finally(()=>{
    loadScript(`market-snapshot.js?v=${VERSION}`).catch(e=>console.warn('[GMFQ market snapshot loader]',e));
  });
})();
