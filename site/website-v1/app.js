(()=>{
  'use strict';

  const referenceLock=document.createElement('style');
  referenceLock.textContent=`
    .brand{position:absolute;top:0;left:0;width:455px;z-index:30;border-bottom:1px solid #163044;overflow:visible}
    .nav-main{margin-top:60px}
    .topbar{z-index:10}
    .content{grid-template-rows:163px 286px 232px 133px}
    .hero-bg{background-size:auto 112px;background-position:right top}
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