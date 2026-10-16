(()=>{
  'use strict';
  const PRICE_RUNTIME='../../payload/part-15.txt';
  const PRICE_HISTORY='../../live_data/sections/ECB_G8_PRICE_HISTORY.json';
  const CCY=['EUR','USD','GBP','JPY','CHF','CAD','AUD','NZD'];
  const WINDOWS={ret1w:7,ret1m:30,ret3m:91,ret6m:182,ret1y:365};
  const MAX_ANCHOR_GAP_DAYS=5;
  const DAY=86400000;
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

  function validateHistory(h){
    if(!h||h.schema!=='GMFQ_ECB_G8_PRICE_HISTORY_V1')throw new Error('ECB Price history schema invalid');
    if(h.status!=='CURRENT_OFFICIAL_HISTORY'||h.base!=='EUR'||h.pair_count!==28)throw new Error('ECB Price history contract invalid');
    if(!Array.isArray(h.currencies)||h.currencies.join(',')!==CCY.join(','))throw new Error('ECB Price history currencies invalid');
    if(!Array.isArray(h.rows)||h.rows.length<500||h.row_count!==h.rows.length)throw new Error('ECB Price history rows invalid');
    let prev='';
    for(const row of h.rows){
      if(!row?.Date||row.Date<=prev)throw new Error('ECB Price history dates not strictly increasing');
      if(row.EUR!==1||CCY.some(c=>!Number.isFinite(Number(row[c]))||Number(row[c])<=0))throw new Error(`ECB Price history row invalid: ${row.Date}`);
      prev=row.Date;
    }
    if(h.first_as_of!==h.rows[0].Date||h.last_as_of!==h.rows[h.rows.length-1].Date)throw new Error('ECB Price history boundary mismatch');
    return h;
  }

  async function officialHistory(){
    const r=await fetch(PRICE_HISTORY,{cache:'no-store'});if(!r.ok)throw new Error(`Price history HTTP ${r.status}`);
    return validateHistory(await r.json());
  }

  function mergedHistory(h,overlayRow){
    const byDate=new Map(h.rows.map(row=>[row.Date,{...row}]));
    if(!byDate.has(overlayRow.Date))byDate.set(overlayRow.Date,{...overlayRow});
    return [...byDate.values()].sort((a,b)=>a.Date.localeCompare(b.Date));
  }

  function referenceRow(history,asOf,days){
    const end=dateMs(asOf);if(end===null)return null;
    const target=end-days*DAY;
    let best=null,bestTime=-Infinity;
    for(const row of history){
      const t=dateMs(row?.Date);if(t===null||t>target)continue;
      if(t>bestTime){best=row;bestTime=t;}
    }
    if(!best)return null;
    const gapDays=(target-bestTime)/DAY;
    return gapDays>=0&&gapDays<=MAX_ANCHOR_GAP_DAYS?best:null;
  }

  function ret(history,currentRow,pair,days){
    const ref=referenceRow(history,currentRow.Date,days);if(!ref)return null;
    const a=cross(currentRow,pair),b=cross(ref,pair);
    return a===null||b===null||b===0?null:(a/b-1)*100;
  }

  async function hydrate(d){
    if(!d||typeof d!=='object')throw new Error('D payload missing');
    const [overlay,h]=await Promise.all([latest(),officialHistory()]);
    const history=mergedHistory(h,overlay.row);
    const currentRow=history[history.length-1];
    if(!currentRow?.Date)throw new Error('ECB Price current row missing');
    const overlayAhead=dateMs(overlay.asOf)>dateMs(h.last_as_of);
    const currentSource=overlayAhead?'canonical overlay':'official history snapshot';

    const old=Array.isArray(d.pairs)?d.pairs:[];
    if(old.length!==28)throw new Error(`Expected 28 G8 pairs, found ${old.length}`);
    let completePairs=0,completeReturns=0;
    d.pairs=old.map(p=>{
      const code=pairCode(p?.pair),last=cross(currentRow,code),next={...p,last,price_asof:currentRow.Date,price_source:'ECB euro foreign exchange reference rates'};
      if(!code||last===null)throw new Error(`Cannot derive canonical FX cross ${p?.pair}`);
      let pairComplete=true;
      for(const [k,days] of Object.entries(WINDOWS)){
        next[k]=ret(history,currentRow,code,days);
        if(Number.isFinite(next[k]))completeReturns+=1;else pairComplete=false;
      }
      if(pairComplete)completePairs+=1;
      return next;
    });
    if(completePairs!==28||completeReturns!==140)throw new Error(`FX returns incomplete: ${completePairs}/28 pairs · ${completeReturns}/140 values`);

    d.prices=history;
    d.price_asof=currentRow.Date;
    d.price_source='ECB euro foreign exchange reference rates';
    d.price_runtime_status='CURRENT_OFFICIAL';
    d.price_history_status='CURRENT_OFFICIAL_HISTORY';
    d.price_runtime_note='Current fixing uses the freshest official ECB row available across the canonical overlay and official history snapshot. Returns use the latest official fixing on or before each target date; anchors more than 5 calendar days before target are withheld.';

    window.GMFQ_WEBSITE_PRICE_AUDIT={
      status:'PASS',
      as_of:currentRow.Date,
      source:'ECB euro foreign exchange reference rates',
      current_row_source:currentSource,
      overlay_asof:overlay.asOf,
      history_status:'CURRENT_OFFICIAL_HISTORY',
      history_asof:h.last_as_of,
      history_rows:h.row_count,
      first_asof:h.first_as_of,
      pair_count:28,
      complete_pair_count:completePairs,
      complete_return_values:completeReturns,
      returns_complete:true,
      horizon_days:{...WINDOWS},
      max_anchor_gap_days:MAX_ANCHOR_GAP_DAYS,
      anchor_rule:'latest official fixing <= target date; max 5 calendar day gap',
      no_lookahead:true
    };
    document.documentElement.setAttribute('data-website-price-asof',currentRow.Date);
    document.documentElement.setAttribute('data-website-price-runtime','CURRENT_OFFICIAL');
    document.documentElement.setAttribute('data-website-price-history','CURRENT_OFFICIAL_HISTORY');
    document.documentElement.setAttribute('data-website-price-history-asof',h.last_as_of);
    document.documentElement.setAttribute('data-website-price-returns','COMPLETE');
    return d;
  }

  window.GMFQWebsitePrice={hydrate,latest,officialHistory,parseOverlay,validateHistory,cross,referenceRow};
})();
