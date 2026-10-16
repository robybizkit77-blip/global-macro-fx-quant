(()=>{
  'use strict';

  const referenceLock=document.createElement('style');
  referenceLock.textContent=`
    /* 1672x905 reference lock: geometry measured directly from approved render */
    .brand{position:absolute;top:0;left:0;width:455px;z-index:30;border-bottom:1px solid #163044;overflow:visible;padding-left:27px;gap:15px}
    .brandmark{width:42px!important;height:40px!important;flex:0 0 42px!important;border:0!important;border-radius:0!important;background:none!important;box-shadow:none!important;display:block!important}
    .brandmark:before,.brandmark:after{display:none!important}
    .brandmark img{display:block;width:42px;height:40px;object-fit:contain}

    .nav-main{margin-top:60px}
    .nav{padding-right:2px!important}
    .nav a{gap:17px!important}
    .topbar{z-index:10}

    .content{
      padding-left:14px!important;
      padding-right:14px!important;
      padding-bottom:7px!important;
      grid-template-rows:168px 288px 234px 118px!important;
      gap:10px!important;
    }

    .hero{isolation:isolate}
    .hero-title{left:5px!important}
    .hero:after{display:none!important}
    .hero-bg{
      left:425px!important;right:0!important;top:0!important;bottom:auto!important;
      width:auto!important;height:88px!important;z-index:0;opacity:1!important;
      background-image:url('./assets/hero-earth-reference.jpg')!important;
      background-repeat:no-repeat!important;
      background-position:right top!important;
      background-size:760px 86px!important;
    }
    .hero-bg:before,.hero-bg:after{display:none!important}
    .hero-wordmark{display:block!important}
    .ticker-strip{bottom:2px!important}
    .hero-title,.hero-right,.ticker-strip{z-index:4}

    .row1{grid-template-columns:414fr 338fr 365fr 305fr!important}
    .row2{grid-template-columns:462fr 443fr 526fr!important}
    .row3{grid-template-columns:993fr 446fr!important;align-self:start}
    .theme-card,.watch-card{height:118px!important}

    @media(max-width:900px){
      .nav{padding-right:12px!important}
      .content{padding:5px!important;display:block!important}
      .row1,.row2,.row3{grid-template-columns:1fr!important}
    }
  `;
  document.head.appendChild(referenceLock);

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
