(()=>{
  'use strict';

  const fidelity=document.createElement('style');
  fidelity.id='reference-lock-v5';
  fidelity.textContent=`
    body{overflow-y:auto!important;overflow-x:hidden!important}
    .site{grid-template-columns:196px minmax(0,1fr)!important;height:auto!important;min-height:100vh!important}
    .sidebar{position:sticky!important;top:0!important;align-self:start!important}
    .main{height:auto!important;min-height:100vh!important;overflow:visible!important}
    .brand{position:absolute!important;top:0!important;left:0!important;width:455px!important;height:60px!important;z-index:30!important;padding:0 0 0 27px!important;gap:17px!important;border-bottom:1px solid #163044!important;overflow:visible!important}
    .brandmark{width:39px!important;height:39px!important;flex:0 0 39px!important;border:0!important;border-radius:0!important;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E%3Ccircle cx='20' cy='20' r='16.3' fill='none' stroke='%23e1b94f' stroke-width='2.1'/%3E%3Cpath d='M18 5.7L14.5 34.2M24.8 6.9L20.8 34M7.4 25.8L31.8 10.6M9.6 12.8L30.2 28.8' fill='none' stroke='%23e1b94f' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E")!important;background-size:contain!important;background-repeat:no-repeat!important;background-position:center!important;box-shadow:none!important;display:block!important}
    .brandmark:before,.brandmark:after,.brandmark img{display:none!important}
    .brandname{font-size:21px!important;letter-spacing:.018em!important}
    .brandsub{font-size:6.4px!important;letter-spacing:.20em!important}
    .nav-main{margin-top:60px!important}.nav{padding-right:2px!important}.nav a{gap:17px!important}.topbar{height:60px!important;z-index:10!important;position:sticky!important;top:0!important}.search{left:273px!important;top:14px!important;width:380px!important;height:34px!important}
    .content{height:auto!important;min-height:calc(100vh - 60px)!important;padding:0 14px 12px!important;grid-template-rows:167px 286px 234px 122px!important;gap:9px!important;overflow:visible!important}
    .hero{isolation:isolate!important;overflow:hidden!important}.hero-title{left:5px!important;top:13px!important}.hero-title h1{font-size:39px!important}.hero-title p{font-size:14px!important}.hero:after{display:none!important}
    .hero-bg{left:180px!important;right:0!important;top:0!important;bottom:auto!important;width:auto!important;height:97px!important;z-index:0!important;opacity:1!important;background-image:linear-gradient(90deg,#061726 0%,rgba(6,23,38,.80) 12%,rgba(6,23,38,.18) 36%,rgba(6,23,38,0) 58%),url('./assets/hero-earth-reference.jpg')!important;background-repeat:no-repeat!important;background-position:left top,right top!important;background-size:100% 100%,1210px 97px!important;filter:brightness(1.08) saturate(1.06) contrast(1.03)!important}
    .hero-bg:before,.hero-bg:after{display:none!important}.hero-right{right:0!important;top:25px!important;z-index:10!important;pointer-events:auto!important}.hero-tabs,.hero-tabs button{pointer-events:auto!important;cursor:pointer!important;position:relative!important;z-index:11!important}.hero-wordmark{display:block!important;font-size:9px!important;line-height:1.52!important;letter-spacing:.43em!important;color:#e4edf3!important;text-shadow:0 1px 3px rgba(0,0,0,.72)!important}.hero-wordmark span{font-size:9px!important}.hero-wordmark i{width:39px!important;margin-top:5px!important}.ticker-strip{left:0!important;right:0!important;bottom:3px!important;gap:8px!important}.ticker{height:77px!important;padding:10px!important;border-color:#23485f!important;box-shadow:0 5px 12px rgba(0,0,0,.16)!important}.ticker:has(em.up){background:radial-gradient(ellipse at 85% 64%,rgba(25,217,148,.18),transparent 40%),linear-gradient(180deg,rgba(8,28,43,.98),rgba(5,21,33,.98))!important}.ticker:has(em.down){background:radial-gradient(ellipse at 85% 64%,rgba(255,81,104,.16),transparent 40%),linear-gradient(180deg,rgba(8,28,43,.98),rgba(5,21,33,.98))!important}.hero-title,.hero-right,.ticker-strip{z-index:4!important}
    .card-head a,.mini-tabs b,.pill-tabs b,.watch-actions b{pointer-events:auto!important;cursor:pointer!important;position:relative!important;z-index:5!important}
    .row{gap:9px!important}.row1{grid-template-columns:414fr 338fr 365fr 305fr!important}.row2{grid-template-columns:462fr 443fr 526fr!important}.row3{grid-template-columns:993fr 446fr!important;align-self:start!important}.card-head{height:39px!important}.row3 .card-head{height:31px!important}.row3>.card{height:122px!important}.theme-strip{height:86px!important}.theme-card{height:86px!important}.watch-table{height:86px!important;overflow:hidden!important}
    @media(max-width:900px){body{overflow:auto!important}.site{display:block!important;height:auto!important}.sidebar{display:none!important}.main{height:auto!important}.topbar{height:42px!important}.search{display:none!important}.content{height:auto!important;padding:5px!important;display:block!important;overflow:visible!important}.hero{height:150px!important;margin-bottom:8px!important}.row1,.row2,.row3{grid-template-columns:1fr!important}.row{display:grid!important;margin-bottom:8px!important}.row3>.card{height:auto!important}.card-head,.row3 .card-head{height:auto!important;min-height:36px!important}.theme-strip,.theme-card,.watch-table{height:auto!important}}
  `;
  document.head.appendChild(fidelity);

  const brandmark=document.querySelector('.brandmark');if(brandmark)brandmark.replaceChildren();
  const routes={Dashboard:'index.html',Valute:'valute.html',Tassi:'tassi.html','Banche centrali':'banche-centrali.html',Posizionamento:'posizionamento.html',Coppie:'coppie.html','Rischio/Eventi':'rischio-eventi.html','Top Themes':'top-themes.html',Library:'library.html',Watchlist:'watchlist.html','Macro Data':'macro-data.html',Strumenti:'strumenti.html',Screener:'screener.html',Alert:'alert.html',Impostazioni:'impostazioni.html'};
  document.querySelectorAll('.nav a').forEach(a=>{const label=a.querySelector('b')?.textContent?.trim();if(routes[label])a.href=routes[label];});

  const cardRoutes={changed:'alert.html',rates:'tassi.html',cbs:'banche-centrali.html','cot-card':'posizionamento.html',calendar:'rischio-eventi.html',themes:'top-themes.html',watch:'watchlist.html'};
  Object.entries(cardRoutes).forEach(([cls,href])=>document.querySelectorAll(`.${cls} .card-head a`).forEach(a=>a.href=href));
  document.querySelectorAll('.card-head a').forEach(a=>{if(!a.getAttribute('href')){const title=(a.closest('.card-head')?.querySelector('h2')?.textContent||'').toLowerCase();if(title.includes('setup')||title.includes('pair'))a.href='screener.html';}});

  document.querySelectorAll('.hero-tabs button').forEach(btn=>btn.addEventListener('click',()=>{
    const p=btn.textContent.trim();if(!['1D','1W','1M','3M','YTD'].includes(p))return;
    btn.parentElement.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===btn));
    window.dispatchEvent(new CustomEvent('gmfq:hero-period',{detail:{period:p}}));
  }));
  document.querySelectorAll('.hierarchy .mini-tabs b').forEach(btn=>btn.addEventListener('click',()=>{
    const p=btn.textContent.trim();if(!['1D','1W','1M'].includes(p))return;
    btn.parentElement.querySelectorAll('b').forEach(x=>x.classList.toggle('active',x===btn));
    window.dispatchEvent(new CustomEvent('gmfq:hierarchy-period',{detail:{period:p}}));
  }));

  const clock=()=>{const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('en-US',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'America/New_York'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-US',{hour:'2-digit',minute:'2-digit',timeZone:'America/New_York'}).format(d);};
  clock();setInterval(clock,30000);
  const dataScript=document.createElement('script');dataScript.src='data-adapter.js?v=20261016-2041';document.head.appendChild(dataScript);
  const snapshotScript=document.createElement('script');snapshotScript.src='market-snapshot.js?v=20261016-2041';document.head.appendChild(snapshotScript);
})();