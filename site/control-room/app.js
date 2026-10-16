(()=>{
  'use strict';
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
