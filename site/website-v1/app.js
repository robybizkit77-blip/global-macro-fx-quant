(()=>{
  'use strict';

  const referenceLock=document.createElement('style');
  referenceLock.textContent=`
    .brand{position:absolute;top:0;left:0;width:455px;z-index:30;border-bottom:1px solid #163044;overflow:visible;padding-left:27px;gap:15px}
    .brandmark{width:40px!important;height:40px!important;flex:0 0 40px!important;border:2px solid #e4bd61!important;border-radius:50%!important;background:transparent!important;box-shadow:0 0 12px rgba(228,189,97,.10)!important;display:block!important;position:relative!important}
    .brandmark img{display:none!important}
    .brandmark:before{content:""!important;display:block!important;position:absolute!important;left:12px!important;top:3px!important;width:2px!important;height:31px!important;background:#e4bd61!important;transform:rotate(17deg)!important;box-shadow:9px 1px 0 #e4bd61!important}
    .brandmark:after{content:""!important;display:block!important;position:absolute!important;left:5px!important;top:18px!important;width:29px!important;height:2px!important;background:#e4bd61!important;transform:rotate(-36deg)!important}
    .nav-main{margin-top:60px}
    .topbar{z-index:10}
    .content{grid-template-rows:163px 286px 232px 118px}
    .hero{isolation:isolate}
    .hero:after{display:none!important}
    .hero-bg{left:425px!important;right:0!important;top:0!important;bottom:auto!important;width:auto!important;height:88px!important;z-index:0;opacity:1!important;background-image:url('./assets/hero-earth-reference.jpg')!important;background-repeat:no-repeat!important;background-position:left top!important;background-size:1052px 88px!important}
    .hero-bg:before,.hero-bg:after{display:none!important}
    .hero-wordmark{display:block!important}
    .ticker-strip{bottom:0!important}
    .hero-title,.hero-right,.ticker-strip{z-index:4}
    .row3{align-self:start}
  `;
  document.head.appendChild(referenceLock);

  const brandmark=document.querySelector('.brandmark');
  if(brandmark) brandmark.replaceChildren();

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