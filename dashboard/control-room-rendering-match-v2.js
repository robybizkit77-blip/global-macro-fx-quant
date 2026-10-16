(()=>{
'use strict';
const SCHEMA='GMFQ_CONTROL_ROOM_RENDERING_MATCH_V2';
function mountV1(){
  if(document.getElementById('gmfq-control-room-rendering-match-v1')) return;
  const s=document.createElement('script');
  s.id='gmfq-control-room-rendering-match-v1';
  s.src='dashboard/control-room-rendering-match-v1.js';
  s.defer=true;
  document.body.appendChild(s);
}
function install(){
  const root=document.getElementById('crm-rendering-match');
  if(!root) return false;
  document.body.classList.add('crm-pixel-v2');
  if(document.getElementById('crm-pixel-v2-style')) return true;
  const css=`
  body.crm-pixel-v2{background:#020812!important;overflow-x:hidden!important}
  body.crm-pixel-v2 .shell{background:#020812!important;min-height:100vh!important}
  body.crm-pixel-v2 .crm-sidebar{width:168px!important;min-width:168px!important;max-width:168px!important;background:linear-gradient(180deg,#07111d 0%,#05101a 100%)!important;border-right:1px solid #102337!important;box-shadow:none!important;padding:0!important}
  body.crm-pixel-v2 .crm-brand{height:55px!important;padding:9px 10px!important;border-bottom:1px solid #102337!important;gap:7px!important}
  body.crm-pixel-v2 .crm-brand span{font-size:18px!important}
  body.crm-pixel-v2 .crm-brand b{font-size:8.5px!important;letter-spacing:.04em!important;white-space:nowrap!important}
  body.crm-pixel-v2 .crm-brand small{font-size:5.8px!important;letter-spacing:.12em!important;color:#64758b!important}
  body.crm-pixel-v2 .crm-sidebar nav{padding:7px 7px 4px!important;display:grid!important;gap:1px!important}
  body.crm-pixel-v2 .crm-nav{height:31px!important;padding:0 8px!important;border-radius:5px!important;font-size:8.5px!important;gap:7px!important;border:1px solid transparent!important}
  body.crm-pixel-v2 .crm-nav span{width:13px!important;font-size:11px!important}
  body.crm-pixel-v2 .crm-nav b{font-size:8.5px!important;font-weight:650!important}
  body.crm-pixel-v2 .crm-nav.active{background:linear-gradient(90deg,#0e3d68,#0b2947)!important;border-color:#15518a!important;box-shadow:inset 2px 0 0 #2b8dd0!important}
  body.crm-pixel-v2 .crm-side-bottom{margin:6px 7px 8px!important;padding:8px!important;border-radius:6px!important;font-size:7px!important;background:#0b1724!important;border:1px solid #142b42!important}
  body.crm-pixel-v2 [data-gmfq-control-room-workspace="true"]{min-width:0!important;background:#020812!important}
  body.crm-pixel-v2 #crm-topbar{height:42px!important;min-height:42px!important;margin:0!important;padding:0 10px!important;border-bottom:1px solid #102337!important;background:#06101a!important;display:flex!important;align-items:center!important;justify-content:space-between!important;box-shadow:none!important}
  body.crm-pixel-v2 .crm-search{height:27px!important;min-width:330px!important;max-width:510px!important;border-radius:5px!important;background:#091725!important;border:1px solid #17304a!important;padding:0 8px!important;font-size:8px!important}
  body.crm-pixel-v2 .crm-search input{font-size:8px!important}
  body.crm-pixel-v2 .crm-top-right{gap:9px!important;font-size:7px!important;color:#8696aa!important}
  body.crm-pixel-v2 .crm-top-right strong{width:24px!important;height:24px!important;border-radius:50%!important;font-size:7px!important}
  body.crm-pixel-v2 #overview.crm-overview{max-width:none!important;width:100%!important;margin:0!important;padding:6px 8px 10px!important;background:#020812!important}
  body.crm-pixel-v2 #crm-rendering-match{display:grid!important;gap:6px!important;width:100%!important;max-width:none!important}
  body.crm-pixel-v2 .crm-hero{height:106px!important;min-height:106px!important;margin:0!important;border-radius:5px!important;border:1px solid #12304a!important;background:
    radial-gradient(circle at 78% 42%,rgba(20,112,177,.32),transparent 26%),
    radial-gradient(circle at 88% 18%,rgba(80,180,220,.16) 0 1px,transparent 1.4px),
    radial-gradient(circle at 70% 26%,rgba(80,180,220,.12) 0 1px,transparent 1.4px),
    linear-gradient(90deg,#071725 0%,#071623 47%,#06111d 100%)!important;
    position:relative!important;overflow:hidden!important;display:grid!important;grid-template-columns:1fr 44%!important;align-items:center!important;padding:0 12px!important}
  body.crm-pixel-v2 .crm-hero:after{content:'';position:absolute;inset:0;background-image:radial-gradient(rgba(129,191,230,.42) .65px,transparent .8px);background-size:22px 22px;opacity:.16;pointer-events:none}
  body.crm-pixel-v2 .crm-hero-copy{z-index:2!important;align-self:center!important;padding-left:2px!important}
  body.crm-pixel-v2 .crm-kicker{font-size:6px!important;letter-spacing:.18em!important;margin-bottom:3px!important;color:#88a7bd!important}
  body.crm-pixel-v2 .crm-hero h1{font-size:27px!important;line-height:1!important;margin:0!important;font-family:Georgia,'Times New Roman',serif!important;font-weight:600!important;letter-spacing:-.03em!important}
  body.crm-pixel-v2 .crm-hero p{font-size:8px!important;margin:4px 0 0!important;color:#8c9db0!important}
  body.crm-pixel-v2 .crm-globe{height:100%!important;display:flex!important;align-items:center!important;justify-content:flex-end!important;z-index:1!important;opacity:.9!important}
  body.crm-pixel-v2 .crm-globe svg{width:100%!important;height:100%!important;max-height:104px!important;transform:scale(1.18) translateX(4%)!important}
  body.crm-pixel-v2 .crm-snapshot-strip{display:grid!important;grid-template-columns:repeat(8,minmax(0,1fr))!important;gap:4px!important;margin:0!important}
  body.crm-pixel-v2 .crm-snap{height:43px!important;min-height:43px!important;padding:5px 6px!important;border-radius:4px!important;background:#081522!important;border:1px solid #142b42!important;box-shadow:none!important}
  body.crm-pixel-v2 .crm-snap span{font-size:6.5px!important;letter-spacing:.04em!important;color:#8595a8!important}
  body.crm-pixel-v2 .crm-snap strong{font-size:11px!important;margin-top:2px!important;line-height:1!important}
  body.crm-pixel-v2 .crm-snap i{font-size:5.5px!important;margin-top:2px!important}
  body.crm-pixel-v2 .crm-grid-main{display:grid!important;grid-template-columns:1.08fr 1.02fr 1.42fr .95fr!important;gap:5px!important;align-items:stretch!important}
  body.crm-pixel-v2 .crm-grid-second{display:grid!important;grid-template-columns:.86fr 1.16fr 1.05fr!important;gap:5px!important;align-items:stretch!important}
  body.crm-pixel-v2 .crm-grid-bottom{display:grid!important;grid-template-columns:1.52fr .88fr!important;gap:5px!important;align-items:stretch!important}
  body.crm-pixel-v2 .crm-card{border-radius:5px!important;border:1px solid #142b42!important;background:linear-gradient(180deg,#081522 0%,#07131f 100%)!important;box-shadow:none!important;padding:7px 8px!important;min-width:0!important;overflow:hidden!important}
  body.crm-pixel-v2 .crm-grid-main .crm-card{height:184px!important;min-height:184px!important}
  body.crm-pixel-v2 .crm-grid-second .crm-card{height:173px!important;min-height:173px!important}
  body.crm-pixel-v2 .crm-grid-bottom .crm-card{height:148px!important;min-height:148px!important}
  body.crm-pixel-v2 .crm-card header{height:20px!important;min-height:20px!important;margin:0 0 5px!important;padding:0 0 4px!important;border-bottom:1px solid #10283c!important;display:flex!important;align-items:center!important;justify-content:space-between!important}
  body.crm-pixel-v2 .crm-card header div{gap:5px!important}
  body.crm-pixel-v2 .crm-card header b{font-size:8.5px!important;font-weight:750!important;letter-spacing:0!important}
  body.crm-pixel-v2 .crm-card header span{font-size:8px!important;color:#d0aa5d!important}
  body.crm-pixel-v2 .crm-card header em{font-size:5.8px!important;color:#5fa9d9!important}
  body.crm-pixel-v2 .crm-change{padding:3px 0!important;gap:5px!important;min-height:0!important;border-bottom:1px solid rgba(27,52,76,.55)!important}
  body.crm-pixel-v2 .crm-change>b{width:14px!important;height:14px!important;min-width:14px!important;font-size:6px!important}
  body.crm-pixel-v2 .crm-change span{font-size:6px!important}
  body.crm-pixel-v2 .crm-change p{font-size:6.5px!important;line-height:1.18!important;margin-top:1px!important;display:-webkit-box!important;-webkit-line-clamp:2!important;-webkit-box-orient:vertical!important;overflow:hidden!important}
  body.crm-pixel-v2 .crm-rank{grid-template-columns:42px 1fr 14px!important;gap:4px!important;padding:2px 0!important}
  body.crm-pixel-v2 .crm-rank span{font-size:7px!important}
  body.crm-pixel-v2 .crm-rank div{height:6px!important}
  body.crm-pixel-v2 .crm-rank em{font-size:6px!important}
  body.crm-pixel-v2 .crm-chartlegend{gap:7px!important;margin-bottom:3px!important;white-space:nowrap!important;overflow:hidden!important}
  body.crm-pixel-v2 .crm-chartlegend span{font-size:5.4px!important}
  body.crm-pixel-v2 .crm-rates-svg{height:137px!important;display:block!important}
  body.crm-pixel-v2 .crm-cb-row,body.crm-pixel-v2 .crm-cot-row,body.crm-pixel-v2 .crm-setup-row,body.crm-pixel-v2 .crm-event,body.crm-pixel-v2 .crm-watch{min-height:0!important;height:auto!important;padding:3px 0!important;border-bottom:1px solid rgba(27,52,76,.45)!important}
  body.crm-pixel-v2 .crm-cb-row span,body.crm-pixel-v2 .crm-cot-row span,body.crm-pixel-v2 .crm-setup-row span,body.crm-pixel-v2 .crm-event span,body.crm-pixel-v2 .crm-watch span{font-size:6.7px!important}
  body.crm-pixel-v2 .crm-cb-row b,body.crm-pixel-v2 .crm-cb-row em,body.crm-pixel-v2 .crm-cot-row em,body.crm-pixel-v2 .crm-setup-row b,body.crm-pixel-v2 .crm-setup-row em,body.crm-pixel-v2 .crm-event b,body.crm-pixel-v2 .crm-event em,body.crm-pixel-v2 .crm-watch b,body.crm-pixel-v2 .crm-watch em{font-size:6px!important}
  body.crm-pixel-v2 .crm-cot-row div{height:7px!important}
  body.crm-pixel-v2 .crm-dots i{width:5px!important;height:5px!important}
  body.crm-pixel-v2 .crm-theme{min-height:0!important;height:54px!important;border-radius:4px!important;padding:0!important;overflow:hidden!important}
  body.crm-pixel-v2 .crm-theme-img{width:64px!important;min-width:64px!important}
  body.crm-pixel-v2 .crm-theme span{font-size:5.5px!important}
  body.crm-pixel-v2 .crm-theme b{font-size:6.8px!important;line-height:1.1!important}
  body.crm-pixel-v2 .crm-theme p{font-size:5.7px!important;line-height:1.15!important;margin-top:2px!important;display:-webkit-box!important;-webkit-line-clamp:2!important;-webkit-box-orient:vertical!important;overflow:hidden!important}
  body.crm-pixel-v2 .crm-themes-wrap{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:4px!important}
  body.crm-pixel-v2 .crm-watchlist{display:grid!important;gap:0!important}
  body.crm-pixel-v2 #gmfq-control-room-home-v1,body.crm-pixel-v2 #gmfq-control-room-insights-v3,body.crm-pixel-v2 #gmfq-control-room-inline-insights{display:none!important}
  @media(max-width:900px){
    body.crm-pixel-v2 .crm-sidebar{display:none!important}
    body.crm-pixel-v2 #crm-topbar{height:40px!important;padding:0 8px!important}
    body.crm-pixel-v2 .crm-search{display:none!important}
    body.crm-pixel-v2 #overview.crm-overview{padding:5px!important}
    body.crm-pixel-v2 .crm-hero{height:94px!important;min-height:94px!important;grid-template-columns:1fr 42%!important;padding:0 9px!important}
    body.crm-pixel-v2 .crm-hero h1{font-size:23px!important}
    body.crm-pixel-v2 .crm-snapshot-strip{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:4px!important}
    body.crm-pixel-v2 .crm-grid-main,body.crm-pixel-v2 .crm-grid-second,body.crm-pixel-v2 .crm-grid-bottom{grid-template-columns:1fr!important;gap:5px!important}
    body.crm-pixel-v2 .crm-grid-main .crm-card,body.crm-pixel-v2 .crm-grid-second .crm-card,body.crm-pixel-v2 .crm-grid-bottom .crm-card{height:auto!important;min-height:150px!important}
    body.crm-pixel-v2 .crm-themes-wrap{grid-template-columns:1fr 1fr!important}
  }
  `;
  const s=document.createElement('style');s.id='crm-pixel-v2-style';s.textContent=css;document.head.appendChild(s);
  window.GMFQ_CONTROL_ROOM_RENDERING_MATCH={schema:SCHEMA,status:'ACTIVE',mode:'PIXEL_MATCH',core_effect:'NONE'};
  return true;
}
function boot(){mountV1();let n=0;const tick=()=>{n++;if(install())return;if(n<400)setTimeout(tick,50);else window.GMFQ_CONTROL_ROOM_RENDERING_MATCH={schema:SCHEMA,status:'WITHHELD',reason:'ROOT_TIMEOUT',core_effect:'NONE'};};tick();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();