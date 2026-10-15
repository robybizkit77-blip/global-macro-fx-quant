(()=>{
  'use strict';
  const SCHEMA='GMFQ_CURRENCIES_HIERARCHY_V1';
  const STYLE_ID='gmfq-currencies-hierarchy-v1-style';
  if(document.getElementById(STYLE_ID)) return;
  const css=`
  #currencies .v461Hero{
    border:1px solid rgba(87,184,255,.14);
    background:linear-gradient(135deg,rgba(20,42,70,.62),rgba(8,18,31,.94));
    box-shadow:0 14px 36px rgba(0,0,0,.10);
  }
  @media (max-width:720px){
    #currencies{overflow:visible!important;}
    #currencies .v461Selector{
      padding:14px!important;
      border-radius:16px!important;
      margin-bottom:10px!important;
    }
    #currencies #currencyGrid{
      display:grid!important;
      grid-auto-flow:column!important;
      grid-auto-columns:minmax(118px,34vw)!important;
      grid-template-columns:none!important;
      gap:8px!important;
      overflow-x:auto!important;
      overflow-y:hidden!important;
      scroll-snap-type:x mandatory;
      overscroll-behavior-inline:contain;
      padding:2px 2px 8px!important;
      margin:8px 0 0!important;
      scrollbar-width:thin;
      scrollbar-color:rgba(87,184,255,.28) transparent;
    }
    #currencies #currencyGrid>.ccy{
      scroll-snap-align:start;
      min-width:0!important;
      width:auto!important;
      margin:0!important;
    }
    #currencies .v461Hero{
      padding:15px!important;
      border-radius:16px!important;
      margin-bottom:10px!important;
    }
    #currencies .v461CoreGrid,
    #currencies .v461DecisionGrid,
    #currencies .v461ChartsGrid,
    #currencies .v461EndGrid{
      display:grid!important;
      grid-auto-flow:column!important;
      grid-auto-columns:minmax(300px,88vw)!important;
      grid-template-columns:none!important;
      gap:10px!important;
      overflow-x:auto!important;
      overflow-y:hidden!important;
      scroll-snap-type:x mandatory;
      overscroll-behavior-inline:contain;
      align-items:start!important;
      padding:2px 2px 10px!important;
      margin:0 0 10px!important;
      scrollbar-width:thin;
      scrollbar-color:rgba(87,184,255,.28) transparent;
    }
    #currencies .v461CoreGrid>* ,
    #currencies .v461DecisionGrid>* ,
    #currencies .v461ChartsGrid>* ,
    #currencies .v461EndGrid>*{
      scroll-snap-align:start;
      min-width:0!important;
      width:auto!important;
      max-width:none!important;
      margin:0!important;
    }
    #currencies .v461CoreGrid .v224LayerDetail,
    #currencies .v461ChartsGrid .v224LayerDetail{
      max-width:100%!important;
    }
    #currencies .v220MacroLink{
      margin-top:2px!important;
      padding:12px 14px!important;
      border-radius:14px!important;
    }
  }
  `;
  const style=document.createElement('style');
  style.id=STYLE_ID;
  style.dataset.gmfqDesign=SCHEMA;
  style.textContent=css;
  document.head.appendChild(style);
  const root=document.getElementById('currencies');
  root?.setAttribute('data-gmfq-hierarchy','currencies-v1');
  root?.querySelector('.v461CoreGrid')?.setAttribute('data-gmfq-currency-rail','core');
  root?.querySelector('.v461DecisionGrid')?.setAttribute('data-gmfq-currency-rail','decision');
  root?.querySelector('.v461ChartsGrid')?.setAttribute('data-gmfq-currency-rail','charts');
  root?.querySelector('.v461EndGrid')?.setAttribute('data-gmfq-currency-rail','end');
  window.GMFQ_CURRENCIES_HIERARCHY={
    schema:SCHEMA,status:'ACTIVE',scope:'PRESENTATION_ONLY',core_effect:'NONE',
    mobile_strategy:'DECISION_FIRST_MULTI_RAIL',baseline_mobile_screens:3.66
  };
})();
