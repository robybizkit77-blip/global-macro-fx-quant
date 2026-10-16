(()=>{
  'use strict';

  const fidelity=document.createElement('style');
  fidelity.id='reference-lock-v2';
  fidelity.textContent=`
    /* Approved reference: 1672×905 website viewport. Design geometry locked 1:1. */
    .site{grid-template-columns:196px minmax(0,1fr)!important}
    .brand{position:absolute!important;top:0!important;left:0!important;width:455px!important;height:60px!important;z-index:30!important;padding:0 0 0 27px!important;gap:15px!important;border-bottom:1px solid #163044!important;overflow:visible!important}
    .brandmark{width:42px!important;height:40px!important;flex:0 0 42px!important;border:0!important;border-radius:0!important;background:none!important;box-shadow:none!important;display:block!important}
    .brandmark img{display:block!important;width:42px!important;height:40px!important;object-fit:contain!important}
    .brandname{font-size:21px!important}
    .brandsub{font-size:6.4px!important;letter-spacing:.20em!important}

    .nav-main{margin-top:60px!important}
    .nav{padding-right:2px!important}
    .nav a{gap:17px!important}
    .topbar{height:60px!important;z-index:10!important}
    .search{left:273px!important;top:14px!important;width:380px!important;height:34px!important}

    .content{
      height:calc(100vh - 60px)!important;
      padding:0 14px!important;
      grid-template-rows:195px 286px 261px 72px!important;
      gap:9px!important;
      overflow:hidden!important;
    }

    .hero{isolation:isolate!important;overflow:hidden!important}
    .hero-title{left:5px!important;top:13px!important}
    .hero-title h1{font-size:39px!important}
    .hero-title p{font-size:14px!important}
    .hero:after{display:none!important}
    .hero-bg{
      left:180px!important;right:0!important;top:0!important;bottom:auto!important;
      width:auto!important;height:111px!important;z-index:0!important;opacity:1!important;
      background-image:linear-gradient(90deg,#061726 0%,rgba(6,23,38,.80) 12%,rgba(6,23,38,.18) 36%,rgba(6,23,38,0) 58%),url('./assets/hero-earth-reference.jpg')!important;
      background-repeat:no-repeat!important;
      background-position:left top,right top!important;
      background-size:100% 100%,1300px 111px!important;
      filter:brightness(1.11) saturate(1.08) contrast(1.04)!important;
    }
    .hero-bg:before,.hero-bg:after{display:none!important}
    .hero-right{right:0!important;top:23px!important}
    .hero-wordmark{display:block!important}
    .ticker-strip{left:0!important;right:0!important;bottom:3px!important;gap:8px!important}
    .ticker{height:77px!important;padding:10px!important}
    .hero-title,.hero-right,.ticker-strip{z-index:4!important}

    .row{gap:9px!important}
    .row1{grid-template-columns:414fr 338fr 365fr 305fr!important}
    .row2{grid-template-columns:462fr 443fr 526fr!important}
    .row3{grid-template-columns:993fr 446fr!important;align-self:start!important}
    .card-head{height:39px!important}
    .row3 .card-head{height:28px!important}
    .row3>.card{height:72px!important}
    .theme-strip{height:44px!important}
    .theme-card{height:44px!important}
    .watch-table{height:44px!important;overflow:hidden!important}

    @media(max-width:900px){
      body{overflow:auto!important}
      .site{display:block!important;height:auto!important}
      .sidebar{display:none!important}
      .main{height:auto!important}
      .topbar{height:42px!important}
      .search{display:none!important}
      .content{height:auto!important;padding:5px!important;display:block!important;overflow:visible!important}
      .hero{height:150px!important;margin-bottom:8px!important}
      .row1,.row2,.row3{grid-template-columns:1fr!important}
      .row{display:grid!important;margin-bottom:8px!important}
      .row3>.card{height:auto!important}
      .card-head,.row3 .card-head{height:auto!important;min-height:36px!important}
      .theme-strip,.theme-card,.watch-table{height:auto!important}
    }
  `;
  document.head.appendChild(fidelity);

  const brandmark=document.querySelector('.brandmark');
  if(brandmark){
    const img=document.createElement('img');
    img.src='./assets/logo-reference.png';
    img.alt='';
    brandmark.replaceChildren(img);
  }

  document.querySelectorAll('.nav a').forEach(a=>a.addEventListener('click',e=>{
    e.preventDefault();
    document.querySelectorAll('.nav a').forEach(x=>x.classList.remove('active'));
    a.classList.add('active');
  }));
  document.querySelectorAll('.hero-tabs button,.mini-tabs b,.pill-tabs b,.watch-actions b').forEach(t=>t.addEventListener('click',()=>{
    const group=t.parentElement;
    group.querySelectorAll('.active').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
  }));
})();
