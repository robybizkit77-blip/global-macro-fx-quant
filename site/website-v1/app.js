(()=>{
  'use strict';

  const referenceLock=document.createElement('style');
  referenceLock.textContent=`
    /* Pixel geometry measured directly from the approved 1672×905 website reference */
    .site{grid-template-columns:196px minmax(0,1fr)!important}
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
      padding-bottom:8px!important;
      grid-template-rows:169px 289px 235px 117px!important;
      gap:9px!important;
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
    .ticker-strip{bottom:3px!important}
    .hero-title,.hero-right,.ticker-strip{z-index:4}

    .row{gap:9px!important}
    .row1{grid-template-columns:414fr 338fr 365fr 305fr!important}
    .row2{grid-template-columns:462fr 443fr 526fr!important}
    .row3{grid-template-columns:993fr 446fr!important;align-self:start}
    .card-head{height:37px!important}
    .row3 .card-head{height:28px!important}
    .theme-card,.watch-card{height:117px!important}

    @media(max-width:900px){
      .site{display:block!important}
      .nav{padding-right:12px!important}
      .content{padding:5px!important;display:block!important}
      .row1,.row2,.row3{grid-template-columns:1fr!important}
      .card-head,.row3 .card-head{height:auto!important;min-height:36px}
    }
  `;
  document.head.appendChild(referenceLock);

  const brandmark=document.querySelector('.brandmark');
  if(brandmark){
    const img=document.createElement('img');
    img.src='data:image/png;base64,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';
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
