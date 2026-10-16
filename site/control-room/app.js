(()=>{
  'use strict';

  const fidelity=document.createElement('style');
  fidelity.id='approved-rendering-final-tuning';
  fidelity.textContent=`
    @media (min-width:901px){
      .page{grid-template-rows:120px 270px 210px 145px!important}
      .row-one{margin-top:31px!important}
      .theme-card{height:103px!important;grid-template-columns:44% 1fr!important}
      .theme-card>div:last-child{padding:6px!important}
      .watch{height:24px!important}
      .watch-head{height:20px!important}
    }
    .earth{
      width:57%!important;
      background-color:#061522!important;
      background-size:92% auto!important;
      background-position:right 46%!important;
      filter:saturate(.98) contrast(1.08)!important;
    }
    .ticker-row{left:7px!important;right:7px!important;gap:3px!important}
    .ticker{box-shadow:0 4px 10px rgba(0,0,0,.26)!important}
    .positioning .cot i{position:relative!important;background:#0b2234!important;overflow:visible!important}
    .positioning .cot i:after{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:#315168;opacity:.7}
    .positioning .cot i b{position:absolute!important;left:50%!important;top:0!important;height:100%!important;transform:scaleX(.5)!important;transform-origin:left center!important;border-radius:1px}
    .positioning .cot i.neg b{left:auto!important;right:50%!important;transform-origin:right center!important}
    .rates-chart text{font:5px Inter,system-ui,sans-serif;fill:#60798e}
    .rates-chart .endpoint{stroke-width:1.3;fill:#071624}
  `;
  document.head.appendChild(fidelity);

  const chart=document.querySelector('.rates-chart');
  if(chart && !chart.dataset.enhanced){
    chart.dataset.enhanced='1';
    const NS='http://www.w3.org/2000/svg';
    const labels=[
      {x:10,y:187,t:'Q1'},{x:120,y:187,t:'Q2'},{x:230,y:187,t:'Q3'},{x:340,y:187,t:'Q4'},{x:430,y:187,t:'Now'}
    ];
    labels.forEach(o=>{const t=document.createElementNS(NS,'text');t.setAttribute('x',o.x);t.setAttribute('y',o.y);t.textContent=o.t;chart.appendChild(t)});
    const ends=[
      {x:455,y:35,c:'#e1b34f',t:'USD'},{x:455,y:40,c:'#38a6e6',t:'EUR'},{x:455,y:29,c:'#a184f7',t:'GBP'},{x:455,y:96,c:'#f05c78',t:'JPY'}
    ];
    ends.forEach(o=>{
      const c=document.createElementNS(NS,'circle');c.setAttribute('cx',o.x);c.setAttribute('cy',o.y);c.setAttribute('r','2.4');c.setAttribute('class','endpoint');c.setAttribute('stroke',o.c);chart.appendChild(c);
      const t=document.createElementNS(NS,'text');t.setAttribute('x',o.x-18);t.setAttribute('y',o.y-4);t.setAttribute('fill',o.c);t.textContent=o.t;chart.appendChild(t);
    });
  }

  const clock=document.querySelector('.clock');
  const fmt=new Intl.DateTimeFormat('it-IT',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
  const refreshClock=()=>{ if(clock) clock.textContent=fmt.format(new Date()); };
  refreshClock();
  setInterval(refreshClock,60000);

  document.querySelectorAll('.nav a').forEach(item=>item.addEventListener('click',e=>{
    e.preventDefault();
    document.querySelectorAll('.nav a').forEach(x=>x.classList.remove('active'));
    item.classList.add('active');
  }));
})();
