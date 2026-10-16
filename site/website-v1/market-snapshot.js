(()=>{
  'use strict';

  const ROOT='../../live_data/sections/';
  const D_PATH=ROOT+'D.json';
  const RATES_PATH=ROOT+'NATIVE_RATES_DATA.json';
  const FX_PATH='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/ECB_G8_PRICE_HISTORY.json';
  const PAIRS=['EURUSD','GBPUSD','USDJPY','USDCAD','AUDUSD','NZDUSD'];
  const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const ALLOWED=['1D','1W','1M','3M','YTD'];
  const params=new URLSearchParams(location.search);
  let d=null,rates=null,fx=null,heroPeriod=ALLOWED.includes(params.get('tf'))?params.get('tf'):'1D',hierarchyPeriod='1D',rendering=false;

  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const pct=(v,digits=2)=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(digits)}%`;};
  async function load(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}
  async function tryLoad(path){try{return await load(path);}catch(e){console.warn('[GMFQ optional feed]',e);return null;}}

  function sparkPoints(values,w=90,h=44,pad=2){const a=(values||[]).map(Number).filter(Number.isFinite);if(a.length<2)return `0,${h/2} ${w},${h/2}`;const lo=Math.min(...a),hi=Math.max(...a),span=(hi-lo)||1;return a.map((v,i)=>`${(pad+(w-2*pad)*(i/(a.length-1))).toFixed(1)},${(pad+(h-2*pad)*(1-(v-lo)/span)).toFixed(1)}`).join(' ');}
  function sampled(values,max=34){if(values.length<=max)return values;return Array.from({length:max},(_,i)=>values[Math.round(i*(values.length-1)/(max-1))]);}

  function datedRows(){return (Array.isArray(fx?.rows)?fx.rows:[]).filter(r=>r?.Date).slice().sort((a,b)=>String(a.Date).localeCompare(String(b.Date)));}
  function startIndex(rows,period){if(rows.length<2)return 0;if(period==='1D')return Math.max(0,rows.length-2);const last=new Date(`${rows.at(-1).Date}T00:00:00Z`);let target;if(period==='YTD')target=new Date(Date.UTC(last.getUTCFullYear(),0,1));else{target=new Date(last);if(period==='1W')target.setUTCDate(target.getUTCDate()-7);if(period==='1M')target.setUTCMonth(target.getUTCMonth()-1);if(period==='3M')target.setUTCMonth(target.getUTCMonth()-3);}const ts=target.toISOString().slice(0,10);let idx=rows.findIndex(r=>r.Date>=ts);if(idx<0)idx=0;return Math.min(idx,rows.length-2);}
  function pairValue(row,label){const a=label.slice(0,3),b=label.slice(3,6);const av=a==='EUR'?1:n(row?.[a]),bv=b==='EUR'?1:n(row?.[b]);return av&&bv?bv/av:null;}
  function findPair(label){const wanted=label.replace('/','');return (Array.isArray(d?.pairs)?d.pairs:[]).find(x=>String(x?.pair||'').replace('/','')===wanted)||null;}
  function fallbackPairCard(label,period){const row=findPair(label);if(!row)return null;const last=n(row.last);if(last===null)return null;const key={1W:'ret1w',1M:'ret1m',3M:'ret3m'}[period];const ret=n(key?row[key]:null);const profile=[0,row.ret1w,row.ret1m,row.ret3m,row.ret6m,row.ret1y].map(n).filter(v=>v!==null);return{label,value:last>=100?last.toFixed(2):last.toFixed(4),change:ret===null?'—':pct(ret,2),dir:(ret??0)>=0?'up':'down',values:profile,title:`${period} · fallback snapshot · as of ${row.price_asof||d?.asOf||'—'}`};}
  function pairCard(label,period){const rows=datedRows();if(rows.length<2)return fallbackPairCard(label,period);const si=startIndex(rows,period),window=rows.slice(si),vals=window.map(r=>pairValue(r,label)).filter(v=>v!==null);if(vals.length<2)return fallbackPairCard(label,period);const first=vals[0],last=vals.at(-1),ret=(last/first-1)*100;return{label,value:last>=100?last.toFixed(2):last.toFixed(4),change:pct(ret,2),dir:ret>=0?'up':'down',values:sampled(vals),title:`${period} · ECB fixing · as of ${rows.at(-1).Date}`};}

  function rateHistory(series,key){const h=series?.[key];if(Array.isArray(h))return h.map(x=>({date:x?.date,value:n(x?.value)})).filter(x=>x.date&&x.value!==null).sort((a,b)=>String(a.date).localeCompare(String(b.date)));const dates=Array.isArray(h?.dates)?h.dates:[],values=Array.isArray(h?.values)?h.values:[];return dates.map((date,i)=>({date,value:n(values[i])})).filter(x=>x.date&&x.value!==null).sort((a,b)=>String(a.date).localeCompare(String(b.date)));}
  function startRateIndex(h,period){if(h.length<2)return 0;if(period==='1D')return Math.max(0,h.length-2);const last=new Date(`${h.at(-1).date}T00:00:00Z`);let target;if(period==='YTD')target=new Date(Date.UTC(last.getUTCFullYear(),0,1));else{target=new Date(last);if(period==='1W')target.setUTCDate(target.getUTCDate()-7);if(period==='1M')target.setUTCMonth(target.getUTCMonth()-1);if(period==='3M')target.setUTCMonth(target.getUTCMonth()-3);}const ts=target.toISOString().slice(0,10);let idx=h.findIndex(x=>x.date>=ts);if(idx<0)idx=0;return Math.min(idx,h.length-2);}
  function rateCard(tenor,period){const usd=rates?.USD;if(!usd)return null;const key=tenor===10?'history10':'history2',h=rateHistory(usd,key);if(h.length<2)return null;const si=startRateIndex(h,period),window=h.slice(si),current=n(usd?.[`${tenor}Y`])??n(usd?.current?.[tenor===10?'y10':'y2'])??window.at(-1)?.value;if(current===null||current===undefined)return null;const first=window[0].value,delta=(current-first)*100;return{label:`US ${tenor}Y`,value:`${current.toFixed(2)}%`,change:`${delta>0?'+':''}${delta.toFixed(1)}bp`,dir:delta>=0?'up':'down',values:sampled(window.map(x=>x.value)),title:`${period} · official Treasury curve · as of ${usd.date||h.at(-1).date}`};}

  function renderHero(){const host=document.querySelector('.ticker-strip');if(!host||!d||!rates)return;const cards=[...PAIRS.map(p=>pairCard(p,heroPeriod)),rateCard(2,heroPeriod),rateCard(10,heroPeriod)].filter(Boolean);if(!cards.length)return;rendering=true;host.innerHTML=cards.map(c=>`<div class="ticker" title="${esc(c.title)}"><div><small>${esc(c.label)}</small><b>${esc(c.value)}</b><em class="${c.dir}">${esc(c.change)}</em></div><svg viewBox="0 0 90 44"><polyline class="${c.dir}" points="${sparkPoints(c.values)}"/></svg></div>`).join('');rendering=false;document.documentElement.setAttribute('data-market-snapshot',cards.length===8?'READY':'PARTIAL');document.documentElement.setAttribute('data-hero-period',heroPeriod);}
  function currencyStrength(period){const rows=datedRows();if(rows.length<2)return[];const si=startIndex(rows,period),a=rows[si],b=rows.at(-1),raw=CCYS.map(ccy=>{const pa=ccy==='EUR'?1:1/n(a[ccy]),pb=ccy==='EUR'?1:1/n(b[ccy]);return{ccy,r:(pb/pa-1)*100};});const mean=raw.reduce((s,x)=>s+x.r,0)/raw.length;return raw.map(x=>({...x,score:x.r-mean})).sort((x,y)=>y.score-x.score);}
  function renderHierarchy(){const rows=[...document.querySelectorAll('.hierarchy .rankrow')],data=currencyStrength(hierarchyPeriod);if(!rows.length||!data.length)return;const mx=Math.max(...data.map(x=>Math.abs(x.score)),.01);rows.forEach((el,i)=>{const x=data[i];if(!x)return;const label=el.querySelector(':scope > span'),bar=el.querySelector(':scope > i > b'),val=el.querySelector(':scope > em'),cls=x.score>=0?'pos':'neg';if(label)label.textContent=`${FLAGS[x.ccy]} ${x.ccy}`;if(bar){bar.className=cls;bar.style.width=`${Math.max(8,Math.abs(x.score)/mx*90).toFixed(1)}%`;}if(val){val.className=cls;val.textContent=`${x.score>0?'+':''}${x.score.toFixed(2)}`;}});}
  function protectStrip(){const host=document.querySelector('.ticker-strip');if(!host)return;new MutationObserver(()=>{if(!rendering&&host.children.length===0&&d&&rates)queueMicrotask(renderHero);}).observe(host,{childList:true});}

  async function run(){try{protectStrip();[d,rates]=await Promise.all([load(D_PATH),load(RATES_PATH)]);renderHero();fx=await tryLoad(FX_PATH);if(fx){renderHero();renderHierarchy();}document.documentElement.setAttribute('data-market-snapshot','READY');}catch(e){console.warn('[GMFQ market snapshot]',e);document.documentElement.setAttribute('data-market-snapshot','FAIL');}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();