(()=>{
  'use strict';

  const referenceLock=document.createElement('style');
  referenceLock.textContent=`
    .brand{position:absolute;top:0;left:0;width:455px;z-index:30;border-bottom:1px solid #163044;overflow:visible;padding-left:27px;gap:15px}
    .brandmark{width:42px!important;height:40px!important;flex:0 0 42px!important;border:0!important;border-radius:0!important;background:url('./assets/logo-reference.png') center/contain no-repeat!important;box-shadow:none!important}
    .brandmark:before,.brandmark:after{display:none!important}
    .nav-main{margin-top:60px}
    .topbar{z-index:10}
    .content{grid-template-rows:163px 286px 232px 118px}
    .hero{isolation:isolate}
    .hero:after{display:none!important}
    .hero-bg{left:425px!important;right:0!important;top:0!important;bottom:auto!important;width:auto!important;height:88px!important;z-index:0;opacity:1!important;background-image:url('./assets/hero-earth-reference.jpg')!important;background-repeat:no-repeat!important;background-position:left top!important;background-size:1052px 88px!important}
    .hero-bg:before,.hero-bg:after{display:none!important}
    .hero-wordmark{display:none!important}
    .ticker-strip{bottom:0!important}
    .hero-title,.hero-right,.ticker-strip{z-index:4}
    .row3{align-self:start}
    .theme-card,.watch-card{height:118px!important}
  `;
  document.head.appendChild(referenceLock);

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