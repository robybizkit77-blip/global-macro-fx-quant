(()=>{
'use strict';
const SCHEMA='GMFQ_CONTROL_ROOM_RENDERING_LOADER_V1';
function fixGlobe(){
  let tries=0;
  const tick=()=>{
    tries++;
    const paths=document.querySelectorAll('.crm-globe svg g:last-of-type path');
    if(paths.length){paths.forEach(p=>p.setAttribute('fill','none'));return;}
    if(tries<120)setTimeout(tick,50);
  };
  tick();
}
function boot(){
  if(document.getElementById('gmfq-control-room-rendering-match-v1')){fixGlobe();return;}
  const s=document.createElement('script');
  s.id='gmfq-control-room-rendering-match-v1';
  s.src='dashboard/control-room-rendering-match-v1.js';
  s.defer=true;
  s.addEventListener('load',fixGlobe,{once:true});
  document.body.appendChild(s);
  window.GMFQ_CONTROL_ROOM_INSIGHTS={schema:SCHEMA,status:'LOADING_RENDERING_MATCH',scope:'PRESENTATION_ONLY',core_effect:'NONE'};
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();