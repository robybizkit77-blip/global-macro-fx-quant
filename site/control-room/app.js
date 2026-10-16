(()=>{
  'use strict';

  const ensureCss=(id,href)=>{
    if(document.getElementById(id)) return;
    const link=document.createElement('link');
    link.id=id;
    link.rel='stylesheet';
    link.href=href;
    document.head.appendChild(link);
  };

  ensureCss('control-room-pixel-match','./pixel-match.css');

  const clock=document.querySelector('.clock');
  const fmt=new Intl.DateTimeFormat('it-IT',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
  if(clock) clock.textContent=fmt.format(new Date());

  document.querySelectorAll('.nav-item').forEach(item=>item.addEventListener('click',e=>{
    e.preventDefault();
    document.querySelectorAll('.nav-item').forEach(x=>x.classList.remove('active'));
    item.classList.add('active');
  }));
})();
