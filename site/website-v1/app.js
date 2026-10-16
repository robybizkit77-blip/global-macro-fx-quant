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
    .hero-bg{inset:0!important;background:none!important;overflow:hidden;opacity:1!important;z-index:0}
    .hero-bg:before{content:"";position:absolute;right:-25px;top:-103px;width:1040px;height:250px;border-radius:50%;background:
      radial-gradient(circle at 31% 72%,rgba(246,185,83,.95) 0 1px,transparent 1.8px),
      radial-gradient(circle at 37% 64%,rgba(242,176,71,.85) 0 1px,transparent 1.7px),
      radial-gradient(circle at 43% 78%,rgba(255,207,103,.95) 0 1.2px,transparent 2px),
      radial-gradient(circle at 48% 58%,rgba(237,171,68,.9) 0 1px,transparent 1.8px),
      radial-gradient(circle at 53% 69%,rgba(255,213,117,.95) 0 1.1px,transparent 1.9px),
      radial-gradient(circle at 58% 76%,rgba(244,183,78,.9) 0 1px,transparent 1.8px),
      radial-gradient(circle at 63% 60%,rgba(255,221,128,.95) 0 1.3px,transparent 2px),
      radial-gradient(circle at 69% 73%,rgba(241,178,71,.9) 0 1px,transparent 1.8px),
      radial-gradient(circle at 76% 64%,rgba(255,218,120,.95) 0 1.2px,transparent 2px),
      radial-gradient(circle at 83% 75%,rgba(241,175,71,.9) 0 1px,transparent 1.8px),
      radial-gradient(ellipse at 55% 100%,#114e73 0 26%,#0c3b5b 38%,#082940 53%,#061928 66%,#04111c 73%,transparent 74%);
      box-shadow:0 -2px 28px rgba(83,176,230,.42),inset 0 15px 45px rgba(78,172,226,.10);transform:rotate(-2deg)}
    .hero-bg:after{content:"";position:absolute;right:0;top:-5px;width:1050px;height:120px;opacity:.55;background:
      repeating-radial-gradient(ellipse at 58% 150%,transparent 0 18px,rgba(87,162,205,.14) 19px 20px),
      repeating-linear-gradient(13deg,transparent 0 36px,rgba(73,143,183,.12) 37px 38px),
      linear-gradient(90deg,#061726 0%,rgba(6,23,38,.58) 22%,rgba(6,23,38,0) 55%)}
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