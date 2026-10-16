(()=>{
  'use strict';

  // Small visual-spec patch kept here while the approved-rendering pass is active.
  const visualPatch=document.createElement('style');
  visualPatch.id='approved-rendering-fidelity';
  visualPatch.textContent=`
    .earth{top:0!important;right:0!important;width:59%!important;height:100%!important;aspect-ratio:auto!important;border-radius:0!important;transform:none!important;box-shadow:none!important;overflow:hidden!important;background:radial-gradient(ellipse at 52% 112%,#16415f 0 16%,#0d314b 30%,#09243a 47%,#061827 61%,rgba(3,12,20,.35) 72%,transparent 76%)!important}
    .earth:before{left:5%!important;bottom:0!important;width:92%!important;height:82%!important;opacity:.68!important}
    .earth-grid{opacity:.12!important;transform:skewY(-2deg)}
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
