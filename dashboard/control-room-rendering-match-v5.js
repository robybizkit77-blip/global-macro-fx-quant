(()=>{
'use strict';
const SCHEMA='GMFQ_CONTROL_ROOM_RENDERING_MATCH_V5';
function mountV4(){
  if(document.getElementById('gmfq-control-room-rendering-match-v4'))return;
  const s=document.createElement('script');s.id='gmfq-control-room-rendering-match-v4';s.src='dashboard/control-room-rendering-match-v4.js';s.defer=true;document.body.appendChild(s);
}
function install(){
  const app=document.getElementById('crm-app-v4');
  if(!app)return false;
  if(!document.getElementById('crm-hard-isolation-v5')){
    const style=document.createElement('style');style.id='crm-hard-isolation-v5';style.textContent=`
      html{background:#020812!important;min-height:100%!important}
      body{margin:0!important;background:#020812!important;min-height:0!important;height:auto!important;overflow:auto!important}
      body> :not(#crm-app-v4):not(script):not(style):not(link){display:none!important;visibility:hidden!important;position:absolute!important;pointer-events:none!important}
      #crm-app-v4{display:grid!important;visibility:visible!important;position:relative!important;inset:auto!important;z-index:2147483000!important;width:100%!important;min-height:100vh!important;margin:0!important}
      #crm-app-v4 *{visibility:visible!important}
    `;document.head.appendChild(style);
  }
  const observer=new MutationObserver(()=>{
    [...document.body.children].forEach(el=>{
      if(el===app||['SCRIPT','STYLE','LINK'].includes(el.tagName))return;
      el.setAttribute('aria-hidden','true');
    });
  });
  observer.observe(document.body,{childList:true});
  window.GMFQ_CONTROL_ROOM_RENDERING_MATCH={schema:SCHEMA,status:'ACTIVE',mode:'HARD_ISOLATED_PIXEL_MATCH',core_effect:'NONE'};
  return true;
}
function boot(){mountV4();let n=0;const tick=()=>{n++;if(install())return;if(n<800)setTimeout(tick,30);};tick();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();