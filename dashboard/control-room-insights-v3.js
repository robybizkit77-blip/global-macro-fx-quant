(()=>{
'use strict';
const SCHEMA='GMFQ_CONTROL_ROOM_RENDERING_LOADER_V3';
function boot(){
  if(document.getElementById('gmfq-control-room-rendering-match-v3'))return;
  const s=document.createElement('script');
  s.id='gmfq-control-room-rendering-match-v3';
  s.src='dashboard/control-room-rendering-match-v3.js';
  s.defer=true;
  document.body.appendChild(s);
  window.GMFQ_CONTROL_ROOM_INSIGHTS={schema:SCHEMA,status:'LOADING_PIXEL_MATCH_REFINED',scope:'PRESENTATION_ONLY',core_effect:'NONE'};
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();