(()=>{
  'use strict';

  if(!document.getElementById('control-room-reference-match')){
    const link=document.createElement('link');
    link.id='control-room-reference-match';
    link.rel='stylesheet';
    link.href='./reference-match.css';
    document.head.appendChild(link);
  }

  const clock=document.querySelector('.clock');
  const fmt=new Intl.DateTimeFormat('it-IT',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
  if(clock) clock.textContent=fmt.format(new Date());

  document.querySelectorAll('.nav-item').forEach(item=>item.addEventListener('click',e=>{
    e.preventDefault();
    document.querySelectorAll('.nav-item').forEach(x=>x.classList.remove('active'));
    item.classList.add('active');
  }));
})();
