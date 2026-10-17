(()=>{
  'use strict';
  const DAY=86400000,OIS_MAX_AGE_DAYS=5,COT_MAX_AGE_DAYS=10;
  const originalFetch=window.fetch.bind(window);
  function ageDays(s){if(!/^\d{4}-\d{2}-\d{2}$/.test(String(s||'')))return Infinity;const t=Date.parse(`${s}T00:00:00Z`);const now=new Date(),today=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());return Math.floor((today-t)/DAY);}
  function jsonResponse(data,response){return new Response(JSON.stringify(data),{status:response.status,statusText:response.statusText,headers:{'content-type':'application/json'}});}
  window.fetch=async(input,init)=>{
    const response=await originalFetch(input,init);
    const url=typeof input==='string'?input:input?.url||'';
    if(!response.ok)return response;
    if(url.includes('D.json')){
      const d=await response.clone().json();
      if(d?.macro&&typeof d.macro==='object')for(const x of Object.values(d.macro)){if(!x||typeof x!=='object')continue;delete x.rate2y;delete x.cycle;delete x.cycle_it;}
      document.documentElement.dataset.pairMacroScores='WITHHELD_LEGACY_D';
      return jsonResponse(d,response);
    }
    if(url.includes('OIS_OPERATIONAL_VIEW.json')){
      const d=await response.clone().json();
      for(const x of Object.values(d?.currencies||{})){
        if(ageDays(x?.as_of)<=OIS_MAX_AGE_DAYS)continue;
        for(const h of Object.values(x?.horizons||{})){if(!h||typeof h!=='object')continue;h.rate=null;h.policy_delta_bp=null;}
        x.operational_status='WITHHELD_STALE';x.quality='WITHHELD_STALE';
      }
      return jsonResponse(d,response);
    }
    if(url.includes('V250_COT_CHART_DATA.json')){
      const d=await response.clone().json();
      const dates=d?.USD?.dates,asOf=Array.isArray(dates)&&dates.length?dates.at(-1):null;
      if(ageDays(asOf)>COT_MAX_AGE_DAYS){for(const x of Object.values(d||{})){if(x&&typeof x==='object')x.percentile=[];}document.documentElement.dataset.pairCot='WITHHELD_STALE';}
      else document.documentElement.dataset.pairCot='READY';
      return jsonResponse(d,response);
    }
    return response;
  };
})();