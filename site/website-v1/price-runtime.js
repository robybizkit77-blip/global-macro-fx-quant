(()=>{
  'use strict';
  const PRICE_RUNTIME='../../payload/part-15.txt';
  const CCY=['EUR','USD','GBP','JPY','CHF','CAD','AUD','NZD'];
  const WINDOWS={ret1w:7,ret1m:30,ret3m:91,ret6m:182,ret1y:365};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const dateMs=s=>{const t=Date.parse(`${s}T00:00:00Z`);return Number.isFinite(t)?t:null};
  const pairCode=p=>String(p||'').replace(/[^A-Z]/g,'').slice(0,6);
  const cross=(row,pair)=>{
    const p=pairCode(pair),a=p.slice(0,3),b=p.slice(3,6),ra=n(row?.[a]),rb=n(row?.[b]);
    return ra===null||rb===null||ra===0?null:rb/ra;
  };
  function parseOverlay(text){
    const scripts=[...String(text||'').matchAll(/<script id="gmfq-price-ecb-(\d{8})">([\s\S]*?)<\/script>/g)];
    if(scripts.length!==1)throw new Error(`Expected one ECB Price overlay, found ${scripts.length}`);
    const body=scripts[0][2];
    const dm=body.match(/Date\s*:\s*'([^']+)'/);if(!dm)throw new Error('ECB Price overlay missing Date');
    const row={Date:dm[1]};
    for(const c of CCY){
      const m=body.match(new RegExp(`\\b${c}\\s*:\\s*(-?\\d+(?:\\.\\d+)?)`));
      if(!m)throw new Error(`ECB Price overlay missing ${c}`);
      row[c]=Number(m[1]);
    }
    if(row.EUR!==1||CCY.some(c=>!Number.isFinite(row[c])||row[c]<=0))throw new Error('ECB Price overlay invalid');
    return {row,asOf:row.Date,source:'ECB euro foreign exchange reference rates'};
  }
  async function latest(){
    const r=await fetch(PRICE_RUNTIME,{cache:'no-store'});if(!r.ok)throw new Error(`Price runtime HTTP ${r.status}`);
    return parseOverlay(await r.text());
  }
  function historyWithLatest(d,row){
    const src=Array.isArray(d?.prices)?d.prices:[];
    const out=src.filter(x=>x&&x.Date&&x.Date!==row.Date).map(x=>({...x}));
    out.push({...row});
    out.sort((a,b)=>String(a.Date).localeCompare(String(b.Date)));
    return out;
  }
  function referenceRow(history,asOf,days){
    const end=dateMs(asOf);if(end===null)return null;
    const target=end-days*86400000;
    let best=null,bestGap=Infinity;
    for(const row of history){
      const t=dateMs(row?.Date);if(t===null||t>end)continue;
      const gap=Math.abs(t-target);
      if(gap<bestGap){best=row;bestGap=gap;}
    }
    // Weekend/holiday tolerance only. If the history has a real gap, fail closed.
    return best&&bestGap<=4*86400000?best:null;
  }
  function ret(history,latestRow,pair,days){
    const ref=referenceRow(history,latestRow.Date,days);if(!ref)return null;
    const a=cross(latestRow,pair),b=cross(ref,pair);return a===null||b===null||b===0?null:(a/b-1)*100;
  }
  async function hydrate(d){
    if(!d||typeof d!=='object')throw new Error('D payload missing');
    const live=await latest();
    const history=historyWithLatest(d,live.row);
    const old=Array.isArray(d.pairs)?d.pairs:[];
    d.pairs=old.map(p=>{
      const code=pairCode(p?.pair),last=cross(live.row,code),next={...p,last,price_asof:live.asOf,price_source:live.source};
      for(const [k,days] of Object.entries(WINDOWS))next[k]=ret(history,live.row,code,days);
      return next;
    });
    d.prices=history;
    d.price_asof=live.asOf;
    d.price_source=live.source;
    d.price_runtime_status='CURRENT_OFFICIAL';
    d.price_runtime_note='Returns are recalculated only when a historical reference exists within a 4-day market-calendar tolerance; otherwise the value is withheld.';
    document.documentElement.setAttribute('data-website-price-asof',live.asOf);
    document.documentElement.setAttribute('data-website-price-runtime','CURRENT_OFFICIAL');
    return d;
  }
  window.GMFQWebsitePrice={hydrate,latest,parseOverlay,cross};
})();
