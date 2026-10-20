(()=>{
'use strict';
const SCHEMA='GMFQ_CONTROL_ROOM_INSIGHTS_TRIGGER_V1';
let fired=false;
function ready(){return !!document.getElementById('gmfq-control-room-home-v1')&&document.querySelectorAll('#gmfq-control-room-home-v1 .crRateRow').length===8&&typeof window.derivePairDecisionFrame==='function';}
function fire(){
  if(fired||!ready()||document.getElementById('gmfq-control-room-insights-v3'))return;
  fired=true;
  const s=document.createElement('script');
  s.id='gmfq-control-room-insights-v3-retry';
  s.src='dashboard/control-room-insights-v3.js?retry=1';
  s.onload=()=>{window.GMFQ_CONTROL_ROOM_INSIGHTS_TRIGGER={schema:SCHEMA,status:document.getElementById('gmfq-control-room-insights-v3')?'ACTIVE':'LOADED_WAITING',core_effect:'NONE'};};
  s.onerror=()=>{window.GMFQ_CONTROL_ROOM_INSIGHTS_TRIGGER={schema:SCHEMA,status:'ERROR',core_effect:'NONE'};};
  document.body.appendChild(s);
}
const obs=new MutationObserver(()=>{fire();if(document.getElementById('gmfq-control-room-insights-v3'))obs.disconnect();});
function boot(){obs.observe(document.documentElement,{childList:true,subtree:true});fire();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();