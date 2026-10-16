(()=>{
'use strict';
const SCHEMA='GMFQ_CONTROL_ROOM_RENDERING_MATCH_V3';
function mountV2(){
  if(document.getElementById('gmfq-control-room-rendering-match-v2'))return;
  const s=document.createElement('script');
  s.id='gmfq-control-room-rendering-match-v2';
  s.src='dashboard/control-room-rendering-match-v2.js';
  s.defer=true;
  document.body.appendChild(s);
}
function install(){
  const root=document.getElementById('crm-rendering-match');
  if(!root||!document.body.classList.contains('crm-pixel-v2'))return false;
  document.querySelectorAll('.crm-globe path').forEach(p=>p.setAttribute('fill','none'));
  if(document.getElementById('crm-pixel-v3-style'))return true;
  const s=document.createElement('style');
  s.id='crm-pixel-v3-style';
  s.textContent=`
  body.crm-pixel-v2 .crm-hero{height:96px!important;min-height:96px!important;grid-template-columns:1fr 42%!important}
  body.crm-pixel-v2 .crm-globe svg{max-height:94px!important;transform:scale(1.08) translateX(2%)!important}
  body.crm-pixel-v2 .crm-globe path{fill:none!important}
  body.crm-pixel-v2 .crm-hero h1{font-size:25px!important}
  body.crm-pixel-v2 .crm-kicker{font-size:5.6px!important}
  body.crm-pixel-v2 .crm-hero p{font-size:7.4px!important}
  body.crm-pixel-v2 .crm-grid-main .crm-card{height:176px!important;min-height:176px!important}
  body.crm-pixel-v2 .crm-grid-second .crm-card{height:164px!important;min-height:164px!important}
  body.crm-pixel-v2 .crm-grid-bottom .crm-card{height:141px!important;min-height:141px!important}
  body.crm-pixel-v2 .crm-theme{display:grid!important;grid-template-columns:54px minmax(0,1fr)!important;align-items:stretch!important;background:#081522!important;border:1px solid #142b42!important}
  body.crm-pixel-v2 .crm-theme-img{width:54px!important;min-width:54px!important;height:100%!important;position:relative!important;overflow:hidden!important}
  body.crm-pixel-v2 .crm-theme-img:after{content:'';position:absolute;inset:0;background:linear-gradient(135deg,rgba(70,155,220,.55),rgba(6,16,28,.15) 55%,rgba(208,164,80,.38));mix-blend-mode:screen;opacity:.8}
  body.crm-pixel-v2 .crm-theme.t1 .crm-theme-img:after,body.crm-pixel-v2 .crm-theme-img.t1:after{background:linear-gradient(135deg,rgba(218,151,60,.55),rgba(8,18,30,.12) 55%,rgba(76,152,214,.34))}
  body.crm-pixel-v2 .crm-theme>div:last-child{padding:5px 6px!important;min-width:0!important;display:flex!important;flex-direction:column!important;justify-content:center!important}
  body.crm-pixel-v2 .crm-theme span{font-size:5.2px!important;color:#66a8d6!important}
  body.crm-pixel-v2 .crm-theme b{display:block!important;font-size:6.6px!important;line-height:1.08!important;color:#eef4f8!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
  body.crm-pixel-v2 .crm-theme p{font-size:5.4px!important;color:#718399!important;-webkit-line-clamp:2!important}
  body.crm-pixel-v2 .crm-themes-wrap{gap:5px!important}
  body.crm-pixel-v2 .crm-watch{display:grid!important;grid-template-columns:60px 1fr 34px!important;align-items:center!important;gap:5px!important}
  body.crm-pixel-v2 .crm-watch b{font-size:6.7px!important;text-align:right!important;color:#e8eef4!important}
  body.crm-pixel-v2 .crm-watch em{font-size:5.3px!important;text-align:right!important;color:#67839b!important}
  body.crm-pixel-v2 .crm-card{box-shadow:inset 0 1px 0 rgba(255,255,255,.015)!important}
  body.crm-pixel-v2 .crm-snap{position:relative!important;overflow:hidden!important}
  body.crm-pixel-v2 .crm-snap:after{content:'';position:absolute;left:0;right:0;bottom:0;height:1px;background:linear-gradient(90deg,transparent,#1a7db8,transparent);opacity:.5}
  body.crm-pixel-v2 .crm-snap strong{letter-spacing:.01em!important}
  @media(min-width:1300px){body.crm-pixel-v2 .crm-sidebar{width:174px!important;min-width:174px!important;max-width:174px!important}}
  `;
  document.head.appendChild(s);
  window.GMFQ_CONTROL_ROOM_RENDERING_MATCH={schema:SCHEMA,status:'ACTIVE',mode:'PIXEL_MATCH_REFINED',core_effect:'NONE'};
  return true;
}
function boot(){mountV2();let n=0;const tick=()=>{n++;if(install())return;if(n<500)setTimeout(tick,40);};tick();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();