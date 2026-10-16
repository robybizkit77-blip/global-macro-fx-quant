(()=>{
'use strict';
const SCHEMA='GMFQ_CONTROL_ROOM_RENDERING_LOADER_V5';
function boot(){
  if(document.getElementById('gmfq-control-room-rendering-match-v5'))return;
  const s=document.createElement('script');
  s.id='gmfq-control-room-rendering-match-v5';
  s.src='dashboard/control-room-rendering-match-v5.js';
  s.defer=true;
  document.body.appendChild(s);
  window.GMFQ_CONTROL_ROOM_INSIGHTS={schema:SCHEMA,status:'LOADING_HARD_ISOLATED_PIXEL_MATCH',scope:'PRESENTATION_ONLY',core_effect:'NONE'};
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();