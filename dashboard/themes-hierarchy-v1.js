(()=>{
  'use strict';
  const SCHEMA='GMFQ_THEMES_HIERARCHY_V1';
  const STYLE_ID='gmfq-themes-hierarchy-v1-style';
  if(document.getElementById(STYLE_ID)) return;

  function mark(){
    const root=document.querySelector('#themes [data-gmfq-operational="themes"]');
    if(!root) return false;
    const grids=[...root.querySelectorAll(':scope > .ttGrid')];
    if(grids.length>=1) grids[0].setAttribute('data-gmfq-themes-rail','top');
    if(grids.length>=2) grids[1].setAttribute('data-gmfq-themes-rail','context');
    const divider=root.querySelector(':scope > .ttDivider');
    if(divider) divider.setAttribute('data-gmfq-themes-divider','context');
    root.setAttribute('data-gmfq-hierarchy','themes-v1');
    return grids.length>=2;
  }

  const css=`
  #themes [data-gmfq-operational="themes"] .ttHero{
    border-color:rgba(87,184,255,.16) !important;
    box-shadow:0 14px 36px rgba(0,0,0,.10);
  }
  #themes [data-gmfq-operational="themes"] [data-tier="top"]{
    box-shadow:0 1px 0 rgba(255,255,255,.018),0 14px 34px rgba(0,0,0,.10);
  }
  @media (max-width:720px){
    #themes [data-gmfq-operational="themes"]{
      padding:14px 12px 24px !important;
      overflow:visible !important;
    }
    #themes [data-gmfq-operational="themes"] .ttHero{
      padding:16px !important;
      margin-bottom:10px !important;
      border-radius:16px !important;
    }
    #themes [data-gmfq-operational="themes"] .ttTitle{
      font-size:20px !important;
      margin:6px 0 5px !important;
    }
    #themes [data-gmfq-operational="themes"] .ttSub{
      font-size:12px !important;
      line-height:1.42 !important;
    }
    #themes [data-gmfq-themes-rail]{
      display:grid !important;
      grid-auto-flow:column !important;
      grid-auto-columns:minmax(310px,89vw) !important;
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
    #themes [data-gmfq-themes-rail] > .ttCard{
      scroll-snap-align:start;
      min-width:0 !important;
      width:auto !important;
      height:auto !important;
      margin:0 !important;
      padding:14px !important;
      border-radius:15px !important;
    }
    #themes [data-gmfq-themes-rail]::after{
      content:'';
      width:2px;
    }
    #themes [data-gmfq-themes-rail="top"]{
      margin-bottom:8px !important;
    }
    #themes [data-gmfq-themes-divider="context"]{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:10px;
      margin:12px 2px 8px !important;
    }
    #themes [data-gmfq-themes-divider="context"]::after{
      content:'Scorri →';
      font-size:10px;
      letter-spacing:.02em;
      text-transform:none;
      color:#6f8198;
      font-weight:700;
    }
    #themes [data-gmfq-themes-rail="top"]::before{
      content:'Priorità · scorri →';
      position:sticky;
      left:0;
      align-self:start;
      height:0;
      overflow:visible;
      transform:translateY(-18px);
      font-size:10px;
      line-height:1;
      color:#6f8198;
      font-weight:700;
      pointer-events:none;
    }
    #themes [data-gmfq-operational="themes"] .ttRow{
      grid-template-columns:1fr 1fr !important;
      gap:6px !important;
    }
    #themes [data-gmfq-operational="themes"] .ttMini{
      padding:7px 8px !important;
    }
    #themes [data-gmfq-operational="themes"] .ttPath{
      gap:5px !important;
    }
    #themes [data-gmfq-operational="themes"] .ttBucket{
      padding:7px !important;
    }
    #themes [data-gmfq-operational="themes"] .ttFoot{
      margin-top:12px !important;
      padding:10px 12px !important;
      border-radius:12px !important;
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
      window.GMFQ_THEMES_HIERARCHY={schema:SCHEMA,status:'ACTIVE',scope:'PRESENTATION_ONLY',core_effect:'NONE',mobile_strategy:'TOP4_AND_CONTEXT4_SEPARATE_SCROLL_RAILS'};
      return;
    }
    if(tries<160) setTimeout(boot,100);
    else window.GMFQ_THEMES_HIERARCHY={schema:SCHEMA,status:'FAIL',scope:'PRESENTATION_ONLY',core_effect:'NONE',error:'THEMES_HIERARCHY_BOOT_TIMEOUT'};
  }

  const obs=new MutationObserver(()=>{
    if(mark()) window.GMFQ_THEMES_HIERARCHY={schema:SCHEMA,status:'ACTIVE',scope:'PRESENTATION_ONLY',core_effect:'NONE',mobile_strategy:'TOP4_AND_CONTEXT4_SEPARATE_SCROLL_RAILS'};
  });
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>{boot();obs.observe(document.body,{childList:true,subtree:true});},{once:true});
  else {boot();obs.observe(document.body,{childList:true,subtree:true});}
})();
