(()=>{
'use strict';
const SCHEMA='GMFQ_CONTROL_ROOM_RENDERING_MATCH_V4';
function mountV3(){
  if(document.getElementById('gmfq-control-room-rendering-match-v3'))return;
  const s=document.createElement('script');s.id='gmfq-control-room-rendering-match-v3';s.src='dashboard/control-room-rendering-match-v3.js';s.defer=true;document.body.appendChild(s);
}
function install(){
  const root=document.getElementById('crm-rendering-match');
  const side=document.querySelector('.crm-sidebar');
  const top=document.getElementById('crm-topbar');
  if(!root||!side||!top||window.GMFQ_CONTROL_ROOM_RENDERING_MATCH?.status!=='ACTIVE')return false;
  if(document.getElementById('crm-app-v4'))return true;

  const legacyShell=document.querySelector('.shell');
  const app=document.createElement('div');app.id='crm-app-v4';app.className='crm-app-v4';
  const main=document.createElement('main');main.className='crm-app-main-v4';
  const content=document.createElement('div');content.className='crm-app-content-v4';

  side.remove();top.remove();root.remove();
  content.appendChild(root);main.appendChild(top);main.appendChild(content);app.appendChild(side);app.appendChild(main);document.body.appendChild(app);
  if(legacyShell)legacyShell.style.display='none';
  [...document.body.children].forEach(el=>{
    if(el===app||['SCRIPT','STYLE','LINK'].includes(el.tagName))return;
    if(el.id==='crm-app-v4')return;
    el.dataset.crmLegacyHidden='true';
    el.style.display='none';
  });

  side.querySelectorAll('[data-go]').forEach(btn=>{
    btn.onclick=(ev)=>{ev.preventDefault();side.querySelectorAll('.crm-nav').forEach(x=>x.classList.remove('active'));btn.classList.add('active');if(btn.dataset.go==='overview')return;};
  });

  const style=document.createElement('style');style.id='crm-app-v4-style';style.textContent=`
    html,body{margin:0!important;min-height:100%!important;background:#020812!important}
    body{overflow:auto!important}
    #crm-app-v4{display:grid!important;grid-template-columns:174px minmax(0,1fr)!important;min-height:100vh!important;width:100%!important;background:#020812!important;color:#eef4f8!important;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important}
    #crm-app-v4 .crm-sidebar{display:flex!important;position:sticky!important;top:0!important;align-self:start!important;height:100vh!important;width:174px!important;min-width:174px!important;max-width:174px!important;overflow:auto!important;z-index:5!important}
    #crm-app-v4 .crm-app-main-v4{min-width:0!important;background:#020812!important;display:block!important}
    #crm-app-v4 #crm-topbar{position:sticky!important;top:0!important;z-index:6!important;width:100%!important;box-sizing:border-box!important}
    #crm-app-v4 .crm-app-content-v4{padding:6px 8px 10px!important;box-sizing:border-box!important}
    #crm-app-v4 #crm-rendering-match{width:100%!important;max-width:none!important;margin:0!important}
    #crm-app-v4 .crm-hero{margin-top:0!important}
    @media(max-width:900px){
      #crm-app-v4{grid-template-columns:1fr!important}
      #crm-app-v4 .crm-sidebar{display:none!important}
      #crm-app-v4 .crm-app-content-v4{padding:5px!important}
    }
  `;document.head.appendChild(style);
  document.documentElement.dataset.gmfqControlRoomApp='v4';
  window.GMFQ_CONTROL_ROOM_RENDERING_MATCH={schema:SCHEMA,status:'ACTIVE',mode:'DETACHED_PIXEL_MATCH',core_effect:'NONE'};
  return true;
}
function boot(){mountV3();let n=0;const tick=()=>{n++;if(install())return;if(n<600)setTimeout(tick,40);};tick();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();