(()=>{
  'use strict';
  const SCHEMA='GMFQ_OVERVIEW_HIERARCHY_V1';
  const STYLE_ID='gmfq-overview-hierarchy-v1-style';
  if(document.getElementById(STYLE_ID)) return;

  const css=`
  #overview{
    --ov-gap:18px;
  }

  #overview .ov387Hero{
    border:1px solid rgba(87,184,255,.14);
    background:linear-gradient(135deg,rgba(20,42,70,.72),rgba(8,18,31,.95));
    box-shadow:0 18px 46px rgba(0,0,0,.14);
  }

  #overview .gmfqOverviewExecutive{
    gap:12px !important;
  }

  #overview .gmfqExecCard,
  #overview .ov387Card,
  #overview .gmfqCcyCard{
    border-color:rgba(148,163,184,.14) !important;
    box-shadow:0 1px 0 rgba(255,255,255,.015),0 12px 32px rgba(0,0,0,.08);
  }

  #overview #ov387Risk{
    border-color:rgba(245,158,11,.20) !important;
  }

  #overview .ov387MapPanel{
    border-color:rgba(87,184,255,.16) !important;
  }

  @media (max-width:720px){
    #overview{
      display:flex !important;
      flex-direction:column !important;
      gap:14px !important;
      overflow:visible !important;
    }

    #overview > .ov387Hero{order:1;}
    #overview > .gmfqOverviewExecutive{order:2;}
    #overview > #ov387Risk{order:3;}
    #overview > .ov387MapPanel{order:4;}
    #overview > .ov387BottomGrid{order:5;}
    #overview > #gmfqCurrencyOverview{order:6;}
    #overview > .ov387RatesGrid{order:7;}
    #overview > #v472RefreshCoverage{order:8;}
    #overview > .v302OverviewGrid{order:9;}

    #overview .ov387Hero{
      padding:18px 16px !important;
      margin:0 !important;
      border-radius:16px !important;
    }

    #overview .gmfqOverviewExecutive{
      display:grid !important;
      grid-auto-flow:column !important;
      grid-auto-columns:minmax(260px,82vw) !important;
      grid-template-columns:none !important;
      overflow-x:auto !important;
      overscroll-behavior-inline:contain;
      scroll-snap-type:x proximity;
      gap:10px !important;
      padding:2px 2px 8px !important;
      margin:0 !important;
    }
    #overview .gmfqOverviewExecutive > .gmfqExecCard{
      scroll-snap-align:start;
      min-height:118px;
      height:auto !important;
      padding:13px 14px !important;
    }

    #overview #gmfqCurrencyOverview{
      padding:14px !important;
      border-radius:16px !important;
      background:rgba(8,17,29,.58);
      border:1px solid rgba(148,163,184,.12);
    }
    #overview #gmfqCcyGrid{
      display:grid !important;
      grid-auto-flow:column !important;
      grid-auto-columns:minmax(270px,84vw) !important;
      grid-template-columns:none !important;
      overflow-x:auto !important;
      overscroll-behavior-inline:contain;
      scroll-snap-type:x proximity;
      gap:10px !important;
      padding:2px 2px 9px !important;
      margin-top:10px !important;
    }
    #overview #gmfqCcyGrid > .gmfqCcyCard{
      scroll-snap-align:start;
      min-height:145px;
      height:auto !important;
      padding:13px 14px !important;
    }

    #overview .ov387RatesGrid{
      display:grid !important;
      grid-auto-flow:column !important;
      grid-auto-columns:minmax(286px,88vw) !important;
      grid-template-columns:none !important;
      overflow-x:auto !important;
      overscroll-behavior-inline:contain;
      scroll-snap-type:x proximity;
      gap:10px !important;
      padding:2px 2px 9px !important;
      margin:0 !important;
      align-items:start;
    }
    #overview .ov387RatesGrid > *{
      scroll-snap-align:start;
      min-width:0 !important;
    }

    #overview .ov387BottomGrid{
      display:grid !important;
      grid-auto-flow:column !important;
      grid-auto-columns:minmax(286px,88vw) !important;
      grid-template-columns:none !important;
      overflow-x:auto !important;
      overscroll-behavior-inline:contain;
      scroll-snap-type:x proximity;
      gap:10px !important;
      padding:2px 2px 9px !important;
      margin:0 !important;
      align-items:start;
    }
    #overview .ov387BottomGrid > *{
      scroll-snap-align:start;
      min-width:0 !important;
    }

    #overview .ov387MapPanel,
    #overview #ov387Risk,
    #overview #v472RefreshCoverage{
      margin:0 !important;
      border-radius:14px !important;
    }

    #overview .gmfqOverviewExecutive,
    #overview #gmfqCcyGrid,
    #overview .ov387RatesGrid,
    #overview .ov387BottomGrid{
      scrollbar-width:thin;
      scrollbar-color:rgba(87,184,255,.28) transparent;
    }

    #overview .gmfqOverviewExecutive::after,
    #overview #gmfqCcyGrid::after,
    #overview .ov387RatesGrid::after,
    #overview .ov387BottomGrid::after{
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
  document.getElementById('overview')?.setAttribute('data-gmfq-hierarchy','overview-v1');
  window.GMFQ_OVERVIEW_HIERARCHY={
    schema:SCHEMA,
    status:'ACTIVE',
    scope:'PRESENTATION_ONLY',
    core_effect:'NONE',
    mobile_strategy:'PRIORITY_ORDER_PLUS_HORIZONTAL_DETAIL_RAILS'
  };
})();
