(()=>{
  'use strict';

  if(!document.getElementById('control-room-css')){
    const css=document.createElement('link');
    css.id='control-room-css';
    css.rel='stylesheet';
    css.href='control-room.css?v=20261016-bonifica1';
    document.head.appendChild(css);
  }

  const brandmark=document.querySelector('.brandmark');
  if(brandmark)brandmark.replaceChildren();

  const routes={Dashboard:'index.html',Valute:'valute.html',Tassi:'tassi.html','Banche centrali':'banche-centrali.html',Posizionamento:'posizionamento.html',Coppie:'coppie.html','Rischio/Eventi':'rischio-eventi.html','Top Themes':'top-themes.html',Library:'library.html',Watchlist:'watchlist.html','Macro Data':'macro-data.html',Strumenti:'strumenti.html',Screener:'screener.html',Alert:'alert.html',Impostazioni:'impostazioni.html'};
  document.querySelectorAll('.nav a').forEach(a=>{const label=a.querySelector('b')?.textContent?.trim();if(routes[label])a.href=routes[label];});

  const cardRoutes={changed:'alert.html',rates:'tassi.html',cbs:'banche-centrali.html','cot-card':'posizionamento.html',calendar:'rischio-eventi.html',themes:'top-themes.html',watch:'watchlist.html'};
  Object.entries(cardRoutes).forEach(([cls,href])=>document.querySelectorAll(`.${cls} .card-head a`).forEach(a=>a.href=href));
  document.querySelectorAll('.card-head a').forEach(a=>{
    if(a.getAttribute('href'))return;
    const title=(a.closest('.card-head')?.querySelector('h2')?.textContent||'').toLowerCase();
    if(title.includes('setup')||title.includes('pair'))a.href='screener.html';
  });

  const allowed=['1D','1W','1M','3M','YTD'];
  const params=new URLSearchParams(location.search);
  const selected=allowed.includes(params.get('tf'))?params.get('tf'):'1D';
  document.querySelectorAll('.hero-tabs button').forEach(btn=>{
    const label=btn.textContent.trim();
    if(!allowed.includes(label))return;
    const a=document.createElement('a');
    const p=new URLSearchParams(location.search);
    p.set('tf',label);
    a.href=`?${p.toString()}`;
    a.textContent=label;
    a.className=label===selected?'active':'';
    a.setAttribute('data-timeframe',label);
    btn.replaceWith(a);
  });

  const clock=()=>{
    const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');
    if(date)date.textContent=new Intl.DateTimeFormat('en-US',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'America/New_York'}).format(d);
    if(time)time.textContent=new Intl.DateTimeFormat('en-US',{hour:'2-digit',minute:'2-digit',timeZone:'America/New_York'}).format(d);
  };
  clock();
  setInterval(clock,30000);

  const dataScript=document.createElement('script');
  dataScript.src='data-adapter.js?v=20261017-datahygiene1';
  document.head.appendChild(dataScript);

  const snapshotScript=document.createElement('script');
  snapshotScript.src='market-snapshot.js?v=20261017-datahygiene1';
  document.head.appendChild(snapshotScript);
})();