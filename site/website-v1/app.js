(()=>{
  'use strict';

  const referenceLock=document.createElement('style');
  referenceLock.textContent=`
    .brand{position:absolute;top:0;left:0;width:455px;z-index:30;border-bottom:1px solid #163044;overflow:visible;padding-left:27px;gap:18px}
    .brandmark{position:relative;background:none;border:2px solid #d6ae4f;box-shadow:0 0 14px rgba(214,174,79,.15)}
    .brandmark:before{content:"";position:absolute;left:8px;top:3px;width:2px;height:29px;background:#d6ae4f;transform:rotate(17deg);box-shadow:8px 1px 0 #d6ae4f}
    .brandmark:after{content:"";position:absolute;left:5px;top:16px;width:27px;height:2px;background:#d6ae4f;transform:rotate(-36deg)}
    .nav-main{margin-top:60px}
    .topbar{z-index:10}
    .content{grid-template-rows:163px 286px 232px 133px}
    .hero{isolation:isolate}
    .hero-bg{inset:0!important;z-index:0;opacity:1!important;background-image:linear-gradient(90deg,#061726 0%,rgba(6,23,38,.82) 20%,rgba(6,23,38,.20) 46%,rgba(6,23,38,0) 66%),url('./assets/hero-earth-reference.jpg')!important;background-repeat:no-repeat!important;background-position:left top,right top!important;background-size:100% 100%,auto 112px!important}
    .hero-bg:before,.hero-bg:after{display:none!important}
    .hero-title,.hero-right,.ticker-strip{z-index:4}
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