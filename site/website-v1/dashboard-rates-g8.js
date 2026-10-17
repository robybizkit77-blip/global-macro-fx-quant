(()=>{
'use strict';
const ROOT='../../live_data/sections/';
const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const COLORS={USD:'#e6b448',EUR:'#2f8ce9',GBP:'#a05af0',JPY:'#f34b66',CHF:'#24d99a',CAD:'#e98b38',AUD:'#49c2d0',NZD:'#c3d067'};
const MONTHS=['Gen','Feb','Mar','Apr','Mag','Giu','Lug','Ago','Set','Ott','Nov','Dic'];
const n=v=>Number.isFinite(Number(v))?Number(v):null;
const dateIT=s=>{if(!s)return'—';const d=new Date(`${String(s).slice(0,10)}T00:00:00Z`);return Number.isNaN(d.getTime())?String(s):`${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`};
async function load(){const r=await fetch(ROOT+'NATIVE_RATES_DATA.json',{cache:'no-store'});if(!r.ok)throw new Error(`Rates HTTP ${r.status}`);return r.json();}
function hist(x){const h=x?.history2;if(Array.isArray(h))return h.map(p=>({date:p?.date,value:n(p?.value)})).filter(p=>p.date&&p.value!==null);const ds=Array.isArray(h?.dates)?h.dates:[],vs=Array.isArray(h?.values)?h.values:[];return ds.map((date,i)=>({date,value:n(vs[i])})).filter(p=>p.date&&p.value!==null);}
const MAX_AGE_DAYS=5;
const age=s=>{const d=Date.parse(String(s||'').slice(0,10)+'T00:00:00Z');if(!Number.isFinite(d))return Infinity;const now=new Date();return Math.floor((Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate())-d)/86400000);};
const valid=x=>{const end=hist(x).at(-1)?.date;return !!end && String(x?.date||'').slice(0,10)===String(end).slice(0,10) && age(end)>=0 && age(end)<=MAX_AGE_DAYS;};
function y2(x){return n(x?.['2Y'])??n(x?.current?.y2)??n(x?.history2?.last_value);}
function render(data){
 const legend=document.querySelector('.rates .rate-legend'),svg=document.querySelector('.rates .ratechart'),tip=document.querySelector('.rates .rate-tip');
 if(!legend||!svg)return;
 legend.innerHTML=ORDER.map(c=>`<span style="color:${COLORS[c]}">● ${c} ${valid(data?.[c])?(y2(data?.[c])?.toFixed(2)??'—')+'%':'WITHHELD'}</span>`).join('');
 const series=ORDER.filter(c=>valid(data?.[c])).map(c=>({c,data:hist(data[c]).slice(-120)})).filter(s=>s.data.length>1);
 const all=series.flatMap(s=>s.data.map(p=>p.value));
 if(!all.length){if(tip)tip.innerHTML='<small>Storico 2Y G8 non disponibile</small>';return;}
 const maxY=Math.max(...all)+.15,minY=Math.min(...all)-.15,span=(maxY-minY)||1,top=20,bottom=195,left=25,right=350;
 const y=v=>top+(bottom-top)*(1-(v-minY)/span);
 svg.querySelectorAll('polyline').forEach(el=>el.remove());
 const now=svg.querySelector('.nowline');
 series.forEach(s=>{const el=document.createElementNS('http://www.w3.org/2000/svg','polyline');el.setAttribute('class',`g8-${s.c.toLowerCase()}`);el.setAttribute('fill','none');el.setAttribute('stroke',COLORS[s.c]);el.setAttribute('stroke-width','1.65');el.setAttribute('opacity','.94');el.setAttribute('points',s.data.map((p,i)=>`${(left+(right-left)*(i/Math.max(1,s.data.length-1))).toFixed(1)},${y(p.value).toFixed(1)}`).join(' '));svg.insertBefore(el,now||svg.querySelector('.axis'));});
 const labels=[...svg.querySelectorAll('.axis text')];
 if(labels.length>=11){for(let i=0;i<6;i++){const v=maxY-(maxY-minY)*(i/5);labels[i].textContent=`${v.toFixed(1)}%`;}const ref=series[0]?.data||[];[0,.25,.5,.75,1].forEach((q,i)=>{const p=ref[Math.min(ref.length-1,Math.round((ref.length-1)*q))];if(labels[6+i])labels[6+i].textContent=p?.date?`${MONTHS[new Date(`${p.date}T00:00:00Z`).getUTCMonth()]} ${String(p.date).slice(2,4)}`:'—';});}
 const dates=ORDER.filter(c=>valid(data?.[c])).map(c=>data[c].date).sort();
 const withheld=ORDER.filter(c=>!valid(data?.[c]));
 if(tip)tip.innerHTML=`<small>G8 · 2Y · ultimo dato valido ${dateIT(dates.at(-1))}${withheld.length?' · WITHHELD: '+withheld.join(', '):''}</small>`;
 document.documentElement.dataset.dashboardRates='G8';
}
async function main(){try{const data=await load();let busy=false;const paint=()=>{if(busy)return;busy=true;try{render(data)}finally{busy=false}};paint();setTimeout(paint,400);setTimeout(paint,1400);const legend=document.querySelector('.rates .rate-legend');if(legend)new MutationObserver(()=>{if(!busy&&legend.querySelectorAll('span').length<8)queueMicrotask(paint)}).observe(legend,{childList:true,subtree:true});}catch(e){console.warn('[GMFQ dashboard rates G8]',e)}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
