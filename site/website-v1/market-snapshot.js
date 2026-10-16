(()=>{
  'use strict';

  const ROOT='../../live_data/sections/';
  const D_PATH=ROOT+'D.json';
  const RATES_PATH=ROOT+'NATIVE_RATES_DATA.json';

  const esc=(v)=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const n=(v)=>Number.isFinite(Number(v))?Number(v):null;
  const pct=(v,d=2)=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}%`;};

  async function load(path){
    const r=await fetch(path,{cache:'no-store'});
    if(!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
    return r.json();
  }

  function sparkPoints(values,w=90,h=44,pad=2){
    const a=(values||[]).map(Number).filter(Number.isFinite);
    if(a.length<2)return `0,${h/2} ${w},${h/2}`;
    const lo=Math.min(...a), hi=Math.max(...a), span=(hi-lo)||1;
    return a.map((v,i)=>{
      const x=pad+(w-2*pad)*(i/(a.length-1));
      const y=pad+(h-2*pad)*(1-(v-lo)/span);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  }

  function findPair(d,label){
    const wanted=label.replace('/','');
    const rows=Array.isArray(d?.pairs)?d.pairs:[];
    return rows.find(x=>String(x?.pair||'').replace('/','')===wanted)||null;
  }

  function pairCard(d,label){
    const row=findPair(d,label);
    if(!row)return null;
    const last=n(row.last);
    const ret=n(row.ret1w);
    const profile=[0,row.ret1w,row.ret1m,row.ret3m,row.ret6m,row.ret1y].map(n).filter(v=>v!==null);
    if(last===null)return null;
    return {
      label,
      value:last>=100?last.toFixed(2):last.toFixed(4),
      change:pct(ret,2),
      dir:(ret??0)>=0?'up':'down',
      values:profile,
      title:`1W · as of ${row.price_asof||d?.asOf||'—'}`
    };
  }

  function latestHistory(series,key){
    const a=Array.isArray(series?.[key])?series[key]:[];
    return a.map(x=>({date:x?.date,value:n(x?.value)})).filter(x=>x.value!==null).sort((a,b)=>String(a.date).localeCompare(String(b.date)));
  }

  function rateCard(rates,tenor){
    const usd=rates?.USD;
    if(!usd)return null;
    const key=tenor===10?'history10':'history2';
    const h=latestHistory(usd,key);
    const current=n(tenor===10?usd?.current?.y10:usd?.current?.y2) ?? h.at(-1)?.value;
    if(current===null||current===undefined)return null;
    const prev=h.at(-2)?.value ?? current;
    const delta=(current-prev)*100;
    return {
      label:`US ${tenor}Y`,
      value:`${current.toFixed(2)}%`,
      change:`${delta>0?'+':''}${delta.toFixed(1)}bp`,
      dir:delta>=0?'up':'down',
      values:h.slice(-30).map(x=>x.value),
      title:`latest official curve history`
    };
  }

  function render(cards){
    const host=document.querySelector('.ticker-strip');
    if(!host||!cards.length)return;
    host.innerHTML=cards.map(c=>`<div class="ticker" title="${esc(c.title||'')}"><div><small>${esc(c.label)}</small><b>${esc(c.value)}</b><em class="${c.dir}">${esc(c.change)}</em></div><svg viewBox="0 0 90 44"><polyline class="${c.dir}" points="${sparkPoints(c.values)}"/></svg></div>`).join('');
    document.documentElement.setAttribute('data-market-snapshot','READY');
  }

  async function run(){
    try{
      const [d,rates]=await Promise.all([load(D_PATH),load(RATES_PATH)]);
      const cards=[
        pairCard(d,'EURUSD'),
        pairCard(d,'GBPUSD'),
        pairCard(d,'USDJPY'),
        pairCard(d,'USDCAD'),
        pairCard(d,'AUDUSD'),
        pairCard(d,'NZDUSD'),
        rateCard(rates,2),
        rateCard(rates,10)
      ].filter(Boolean);
      render(cards.slice(0,8));
    }catch(e){
      console.warn('[GMFQ market snapshot]',e);
      document.documentElement.setAttribute('data-market-snapshot','FAIL');
    }
  }

  function start(){
    if(document.documentElement.getAttribute('data-website-live-adapter')==='READY') return run();
    const obs=new MutationObserver(()=>{
      if(document.documentElement.getAttribute('data-website-live-adapter')==='READY'){
        obs.disconnect();
        run();
      }
    });
    obs.observe(document.documentElement,{attributes:true,attributeFilter:['data-website-live-adapter']});
    setTimeout(()=>{obs.disconnect();run();},2500);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true}); else start();
})();
