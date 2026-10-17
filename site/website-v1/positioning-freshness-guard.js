(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const MAX_AGE_DAYS=10;
  const DAY=86400000;
  const ageDays=s=>{const t=Date.parse(`${String(s||'').slice(0,10)}T00:00:00Z`);if(!Number.isFinite(t))return Infinity;const now=new Date(),today=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());return Math.floor((today-t)/DAY);};
  const latestDate=data=>{const dates=Object.values(data||{}).flatMap(x=>Array.isArray(x?.dates)?[x.dates.at(-1)]:[]).filter(Boolean).sort();return dates.at(-1)||null;};
  const withheld=(asof)=>{
    const grid=document.getElementById('cot-grid');if(grid)grid.innerHTML='<article class="cot-card"><div class="cot-top"><div class="cot-name"><div><b>COT WITHHELD</b><small>Dati CFTC oltre soglia di freschezza</small></div></div></div><div class="cot-main"><div class="cot-metric"><small>As of</small><b>'+String(asof||'—')+'</b></div><div class="cot-metric"><small>Soglia</small><b>10 giorni</b></div></div></article>';
    const ext=document.getElementById('extremes-list');if(ext)ext.innerHTML='<div class="extreme-row"><b>WITHHELD</b><em class="short">STALE</em></div>';
    const flow=document.getElementById('flow-table');if(flow)flow.innerHTML='<div class="flow-row"><span>WITHHELD</span><small>COT stale</small><b>—</b><em>—</em></div>';
    const svg=document.getElementById('cot-chart');if(svg)svg.innerHTML='';
    const meta=document.getElementById('cot-asof');if(meta)meta.textContent=`CFTC · WITHHELD · as of ${asof||'—'}`;
    const legend=document.getElementById('cot-price-legend');if(legend)legend.innerHTML='<span class="withheld">COT WITHHELD · freshness gate</span>';
    const pm=document.getElementById('cot-price-meta');if(pm)pm.textContent='Posizionamento non mostrato finché il feed CFTC non rientra nella soglia di freschezza.';
    document.documentElement.setAttribute('data-positioning-page','WITHHELD');
    document.documentElement.setAttribute('data-cot-freshness','WITHHELD');
  };
  async function run(){
    try{
      const r=await fetch(ROOT+'V250_COT_CHART_DATA.json',{cache:'no-store'});if(!r.ok)throw new Error(`COT HTTP ${r.status}`);
      const data=await r.json(),asof=latestDate(data),age=ageDays(asof);
      if(!(age>=0&&age<=MAX_AGE_DAYS))withheld(asof);else document.documentElement.setAttribute('data-cot-freshness','FRESH');
    }catch(e){console.warn('[GMFQ COT freshness]',e);withheld(null);}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(run,0),{once:true});else setTimeout(run,0);
})();
