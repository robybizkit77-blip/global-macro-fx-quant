(()=>{
  'use strict';

  // Approved rendering: use extracted visual assets from the approved mockup.
  const visualPatch=document.createElement('style');
  visualPatch.id='approved-rendering-fidelity';
  visualPatch.textContent=`
    .earth{top:0!important;right:0!important;width:60%!important;height:100%!important;aspect-ratio:auto!important;border-radius:0!important;transform:none!important;box-shadow:none!important;overflow:hidden!important;background:linear-gradient(90deg,rgba(6,21,34,.94) 0%,rgba(6,21,34,.45) 22%,rgba(2,8,17,.06) 54%),url('./assets/hero-earth-reference.jpg') center right/cover no-repeat!important;filter:saturate(.92) contrast(1.06)!important}
    .earth:before,.earth-grid,.earth .city{display:none!important}
    .theme-card .thumb{background-image:url('./assets/theme-sprite.jpg')!important;background-repeat:no-repeat!important;background-size:500% 100%!important}
    .theme-card .thumb:before{display:none!important}
    .theme-card.t1 .thumb{background-position:0% 50%!important}
    .theme-card.t2 .thumb{background-position:25% 50%!important}
    .theme-card.t3 .thumb{background-position:50% 50%!important}
    .theme-card.t4 .thumb{background-position:75% 50%!important}
    .theme-card.t5 .thumb{background-position:100% 50%!important}
  `;
  document.head.appendChild(visualPatch);

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
