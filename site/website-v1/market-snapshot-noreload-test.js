(()=>{
  'use strict';

  const ROOT='../../live_data/sections/';
  const D_PATH=ROOT+'D.json';
  const RATES_PATH=ROOT+'NATIVE_RATES_DATA.json';
  const FX_PATH='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/ECB_G8_PRICE_HISTORY.json';
  const PAIRS=['EURUSD','GBPUSD','USDJPY','USDCAD','AUDUSD','NZDUSD'];
  const ALLOWED=['1D','1W','1M','3M','YTD'];
  const params=new URLSearchParams(location.search);
  let d=null,rates=null,fx=null,heroPeriod=ALLOWED.includes(params.get('tf'))?params.get('tf'):'1D';

  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const pct=(v,digits=2)=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(digits)}%`;};
  async function load(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}
  async function tryLoad(path){try{return await load(path);}catch{return null;}}
  function sparkPoints(values,w=90,h=44,pad=2){const a=(values||[]).map(Number).filter(Number.isFinite);if(a.length<2)return `0,${h/2} ${w},${h/2}`;const lo=Math.min(...a),hi=Math.max(...a),span=(hi-lo)||1;return a.map((v,i)=>`${(pad+(w-2*pad)*(i/(a.length-1))).toFixed(1)},${(pad+(h-2*pad)*(1-(v-lo)/span)).toFixed(1)}`).join(' ');}
  function sampled(values,max=34){if(values.length<=max)return values;return Array.from({length:max},(_,i)=>values[Math.round(i*(values.length-1)/(max-1))]);}
  function datedRows(){return (Array.isArray(fx?.rows)?fx.rows:[]).filter(r=>r?.Date).slice().sort((a,b)=>String(a.Date).localeCompare(String(b.Date)));}
  function startIndex(rows,period){if(rows.length<2)return 0;if(period==='1D')return Math.max(0,rows.length-2);const last=new Date(`${rows.at(-1).Date}T00:00:00Z`);let target;if(period==='YTD')target=new Date(Date.UTC(last.getUTCFullYear(),0,1));else{target=new Date(last);if(period==='1W')target.setUTCDate(target.getUTCDate()-7);if(period==='1M')target.setUTCMonth(target.getUTCMonth()-1);if(period==='3M')target.setUTCMonth(target.getUTCMonth()-3);}const ts=target.toISOString().slice(0,10);let idx=rows.findIndex(r=>r.Date>=ts);if(idx<0)idx=0;return Math.min(idx,rows.length-2);}
  function pairValue(row,label){const a=label.slice(0,3),b=label.slice(3,6);const av=a==='EUR'?1:n(row?.[a]),bv=b==='EUR'?1:n(row?.[b]);return av&&bv?bv/av:null;}
  function findPair(label){const wanted=label.replace('/','');return (Array.isArray(d?.pairs)?d.pairs:[]).find(x=>String(x?.pair||'').replace('/','')===wanted)||null;}
  function fallbackPairCard(label,period){const row=findPair(label);if(!row)return null;const last=n(row.last);if(last===null)return null;const key={1W:'ret1w',1M:'ret1m',3M:'ret3m'}[period];const ret=n(key?row[key]:null);const profile=[0,row.ret1w,row.ret1m,row.ret3m,row.ret6m,row.ret1y].map(n).filter(v=>v!==null);return{label,value:last>=100?last.toFixed(2):last.toFixed(4),change:ret===null?'—':pct(ret,2),dir:(ret??0)>=0?'up':'down',values:profile,title:`${period} · fallback snapshot`};}
  function pairCard(label,period){const rows=datedRows();if(rows.length<2)return fallbackPairCard(label,period);const si=startIndex(rows,period),window=rows.slice(si),vals=window.map(r=>pairValue(r,label)).filter(v=>v!==null);if(vals.length<2)return fallbackPairCard(label,period);const first=vals[0],last=vals.at(-1),ret=(last/first-1)*100;return{label,value:last>=100?last.toFixed(2):last.toFixed(4),change:pct(ret,2),dir:ret>=0?'up':'down',values:sampled(vals),title:`${period} · ECB fixing · as of ${rows.at(-1).Date}`};}
  function rateHistory(series,key){const h=series?.[key];if(Array.isArray(h))return h.map(x=>({date:x?.date,value:n(x?.value)})).filter(x=>x.date&&x.value!==null);const dates=Array.isArray(h?.dates)?h.dates:[],values=Array.isArray(h?.values)?h.values:[];return dates.map((date,i)=>({date,value:n(values[i])})).filter(x=>x.date&&x.value!==null);}
  function startRateIndex(h,period){if(h.length<2)return 0;if(period==='1D')return Math.max(0,h.length-2);const last=new Date(`${h.at(-1).date}T00:00:00Z`);let target;if(period==='YTD')target=new Date(Date.UTC(last.getUTCFullYear(),0,1));else{target=new Date(last);if(period==='1W')target.setUTCDate(target.getUTCDate()-7);if(period==='1M')target.setUTCMonth(target.getUTCMonth()-1);if(period==='3M')target.setUTCMonth(target.getUTCMonth()-3);}const ts=target.toISOString().slice(0,10);let idx=h.findIndex(x=>x.date>=ts);if(idx<0)idx=0;return Math.min(idx,h.length-2);}
  function rateCard(tenor,period){const usd=rates?.USD;if(!usd)return null;const key=tenor===10?'history10':'history2',h=rateHistory(usd,key);if(h.length<2)return null;const si=startRateIndex(h,period),window=h.slice(si),current=n(usd?.[`${tenor}Y`])??window.at(-1)?.value;if(current==null)return null;const first=window[0].value,delta=(current-first)*100;return{label:`US ${tenor}Y`,value:`${current.toFixed(2)}%`,change:`${delta>0?'+':''}${delta.toFixed(1)}bp`,dir:delta>=0?'up':'down',values:sampled(window.map(x=>x.value)),title:`${period} · rates`};}
  function renderHero(){const host=document.querySelector('.ticker-strip');if(!host||!d||!rates)return;const cards=[...PAIRS.map(p=>pairCard(p,heroPeriod)),rateCard(2,heroPeriod),rateCard(10,heroPeriod)].filter(Boolean);host.innerHTML=cards.map(c=>`<div class="ticker"><div><small>${esc(c.label)}</small><b>${esc(c.value)}</b><em class="${c.dir}">${esc(c.change)}</em></div><svg viewBox="0 0 90 44"><polyline class="${c.dir}" points="${sparkPoints(c.values)}"/></svg></div>`).join('');document.getElementById('status').textContent=`READY · timeframe=${heroPeriod} · cards=${cards.length}`;}
  function bind(){document.querySelectorAll('.hero-tabs a[data-timeframe]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();const p=a.dataset.timeframe;if(!ALLOWED.includes(p))return;heroPeriod=p;document.querySelectorAll('.hero-tabs a[data-timeframe]').forEach(x=>x.classList.toggle('active',x===a));const u=new URL(location.href);u.searchParams.set('tf',p);history.replaceState(null,'',u);renderHero();}));}
  async function run(){bind();[d,rates]=await Promise.all([load(D_PATH),load(RATES_PATH)]);fx=await tryLoad(FX_PATH);renderHero();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();