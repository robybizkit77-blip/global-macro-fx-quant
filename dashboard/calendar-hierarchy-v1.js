(()=>{
  'use strict';
  const SCHEMA='GMFQ_CALENDAR_HIERARCHY_V1';
  const STYLE_ID='gmfq-calendar-hierarchy-v1-style';
  if(document.getElementById(STYLE_ID)) return;

  function mark(){
    const root=document.querySelector('#calendar [data-gmfq-operational="calendar"]');
    if(!root) return false;
    const grids=[...root.querySelectorAll(':scope > .opGrid')];
    if(grids.length>=1) grids[0].setAttribute('data-gmfq-calendar-rail','cb');
    if(grids.length>=2) grids[1].setAttribute('data-gmfq-calendar-rail','macro');
    root.setAttribute('data-gmfq-hierarchy','calendar-v1');
    return grids.length>=2;
  }

  const css=`
  #calendar [data-gmfq-operational="calendar"] .opHero{
    border-color:rgba(87,184,255,.14) !important;
    box-shadow:0 14px 36px rgba(0,0,0,.10);
  }
  @media (max-width:720px){
    #calendar [data-gmfq-operational="calendar"]{
      padding:14px 12px 24px !important;
      overflow:visible !important;
    }
    #calendar [data-gmfq-operational="calendar"] .opHero{
      padding:16px !important;
      margin-bottom:12px !important;
      border-radius:16px !important;
    }
    #calendar [data-gmfq-operational="calendar"] .opSection{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      margin:15px 2px 8px !important;
    }
    #calendar [data-gmfq-operational="calendar"] .opSection::after{
      content:'Scorri →';
      font-size:10px;
      letter-spacing:.02em;
      text-transform:none;
      color:#6f8198;
      font-weight:700;
    }
    #calendar [data-gmfq-calendar-rail]{
      display:grid !important;
      grid-auto-flow:column !important;
      grid-auto-columns:minmax(290px,86vw) !important;
      grid-template-columns:none !important;
      gap:10px !important;
      overflow-x:auto !important;
      overflow-y:hidden !important;
      overscroll-behavior-inline:contain;
      scroll-snap-type:x mandatory;
      padding:2px 2px 10px !important;
      margin:0 !important;
      align-items:start;
      scrollbar-width:thin;
      scrollbar-color:rgba(87,184,255,.28) transparent;
      -webkit-overflow-scrolling:touch;
    }
    #calendar [data-gmfq-calendar-rail] > .opCard{
      scroll-snap-align:start;
      min-width:0 !important;
      width:auto !important;
      height:auto !important;
      margin:0 !important;
      padding:14px !important;
      border-radius:15px !important;
      border-color:rgba(148,163,184,.14) !important;
      box-shadow:0 1px 0 rgba(255,255,255,.015),0 14px 32px rgba(0,0,0,.08);
    }
    #calendar [data-gmfq-calendar-rail]::after{
      content:'';
      width:2px;
    }
    #calendar [data-gmfq-operational="calendar"] .opFoot{
      margin-top:12px !important;
      padding:10px 12px !important;
      border-radius:12px !important;
      line-height:1.4 !important;
    }
  }
  `;

  const style=document.createElement('style');
  style.id=STYLE_ID;
  style.dataset.gmfqDesign=SCHEMA;
  style.textContent=css;
  document.head.appendChild(style);

  let tries=0;
  function boot(){
    tries++;
    if(mark()){
      window.GMFQ_CALENDAR_HIERARCHY={
        schema:SCHEMA,status:'ACTIVE',scope:'PRESENTATION_ONLY',core_effect:'NONE',
        mobile_strategy:'SEPARATE_CB_AND_MACRO_HORIZONTAL_EVENT_RAILS'
      };
      return;
    }
    if(tries<160) setTimeout(boot,100);
    else window.GMFQ_CALENDAR_HIERARCHY={schema:SCHEMA,status:'FAIL',scope:'PRESENTATION_ONLY',core_effect:'NONE',error:'CALENDAR_HIERARCHY_BOOT_TIMEOUT'};
  }

  const obs=new MutationObserver(()=>{
    if(mark()) window.GMFQ_CALENDAR_HIERARCHY={schema:SCHEMA,status:'ACTIVE',scope:'PRESENTATION_ONLY',core_effect:'NONE',mobile_strategy:'SEPARATE_CB_AND_MACRO_HORIZONTAL_EVENT_RAILS'};
  });
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>{boot();obs.observe(document.body,{childList:true,subtree:true});},{once:true});
  else {boot();obs.observe(document.body,{childList:true,subtree:true});}
})();
