(()=>{
  'use strict';
  const SCHEMA='GMFQ_INFLATIONLABOUR_HIERARCHY_V1';
  const STYLE_ID='gmfq-inflationlabour-hierarchy-v1-style';
  if(document.getElementById(STYLE_ID)) return;
  const css=`
  #inflationlabour .il407Hero{
    border:1px solid rgba(87,184,255,.14);
    background:linear-gradient(135deg,rgba(20,42,70,.62),rgba(8,18,31,.94));
    box-shadow:0 14px 36px rgba(0,0,0,.10);
  }
  @media (max-width:720px){
    #inflationlabour{
      overflow:visible !important;
    }
    #inflationlabour .il407Hero{
      padding:16px !important;
      border-radius:16px !important;
      margin-bottom:10px !important;
    }
    #inflationlabour .il407Legend{
      margin:0 0 10px !important;
      padding:0 2px !important;
      overflow-x:auto !important;
      white-space:nowrap;
      scrollbar-width:none;
    }
    #inflationlabour .il407Legend::-webkit-scrollbar{display:none;}
    #inflationlabour #il407Grid{
      display:grid !important;
      grid-auto-flow:column !important;
      grid-auto-columns:minmax(302px,88vw) !important;
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
    }
    #inflationlabour #il407Grid > .il407Card{
      scroll-snap-align:start;
      scroll-snap-stop:normal;
      width:auto !important;
      min-width:0 !important;
      height:auto !important;
      margin:0 !important;
      padding:14px !important;
      border-radius:15px !important;
      border-color:rgba(148,163,184,.14) !important;
      box-shadow:0 1px 0 rgba(255,255,255,.015),0 14px 32px rgba(0,0,0,.09);
    }
    #inflationlabour #il407Grid::after{
      content:'';
      width:2px;
    }
  }
  `;
  const style=document.createElement('style');
  style.id=STYLE_ID;
  style.dataset.gmfqDesign=SCHEMA;
  style.textContent=css;
  document.head.appendChild(style);
  document.getElementById('inflationlabour')?.setAttribute('data-gmfq-hierarchy','inflationlabour-v1');
  window.GMFQ_INFLATIONLABOUR_HIERARCHY={
    schema:SCHEMA,status:'ACTIVE',scope:'PRESENTATION_ONLY',core_effect:'NONE',
    mobile_strategy:'G8_HORIZONTAL_SCROLL_SNAP_RAIL'
  };
})();
