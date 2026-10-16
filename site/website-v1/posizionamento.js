(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  let state={chart:null,stories:null,selected:'USD'};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const fmtInt=v=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${Math.round(x).toLocaleString('en-US')}`;};
  const fmtPct=(v,d=1)=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}%`;};
  async function load(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}
  function latest(ccy,key){const a=state.chart?.[ccy]?.[key];return Array.isArray(a)&&a.length?a[a.length-1]:null;}
  function prev(ccy,key){const a=state.chart?.[ccy]?.[key];return Array.isArray(a)&&a.length>1?a[a.length-2]:null;}
  function signal(p){const x=n(p);if(x===null)return {label:'NEUTRALE',cls:'neutral'};if(x>=80)return {label:'EXTREME LONG',cls:'long'};if(x<=20)return {label:'EXTREME SHORT',cls:'short'};return {label:'NEUTRALE',cls:'neutral'};}
  function card(ccy){
    const pct=latest(ccy,'percentile'), netoi=latest(ccy,'netoi'), net=latest(ccy,'net'), d1=(n(net)!==null&&n(prev(ccy,'net'))!==null)?n(net)-n(prev(ccy,'net')):null;
    const s=signal(pct), hot=Math.abs(n(netoi)||0)>=30;
    return `<article class="cot-card"><div class="cot-top"><div class="cot-name"><span class="flag">${FLAGS[ccy]}</span><div><b>${ccy}</b><small>CFTC Legacy Non-Commercial</small></div></div><span class="cot-signal ${s.cls}">${s.label}</span></div><div class="cot-main"><div class="cot-metric"><small>Net</small><b>${fmtInt(net)}</b></div><div class="cot-metric"><small>Net/OI</small><b>${fmtPct(netoi)}</b></div><div class="cot-metric"><small>Pct 2Y</small><b>${n(pct)===null?'—':n(pct).toFixed(1)}</b></div></div><div class="cot-alert ${hot?'hot':''}">${hot?'⚠ Squilibrio |Net/OI| ≥30% · ':''}Δ Net 1W ${fmtInt(d1)}</div></article>`;
  }
  function renderGrid(){const h=document.getElementById('cot-grid');if(h)h.innerHTML=ORDER.map(card).join('');}
  function renderSelect(){const h=document.getElementById('cot-select');if(!h)return;h.innerHTML=ORDER.map(c=>`<button data-ccy="${c}" class="${c===state.selected?'active':''}"><span class="flag">${FLAGS[c]}</span>${c}</button>`).join('');h.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{state.selected=b.dataset.ccy;renderSelect();renderChart();}));}
  function renderExtremes(){const h=document.getElementById('extremes-list');if(!h)return;const rows=ORDER.map(c=>({c,p:n(latest(c,'percentile'))})).filter(x=>x.p!==null).sort((a,b)=>b.p-a.p);h.innerHTML=rows.map(x=>{const s=signal(x.p);return `<div class="extreme-row"><b>${FLAGS[x.c]} ${x.c}</b><i><span style="width:${Math.max(1,Math.min(100,x.p)).toFixed(1)}%"></span></i><em class="${s.cls}">${x.p.toFixed(1)}</em></div>`;}).join('');}
  function renderFlow(){const h=document.getElementById('flow-table');if(!h)return;const rows=ORDER.map(c=>{const last=n(latest(c,'net')), p=n(prev(c,'net'));return {c,last,d:last!==null&&p!==null?last-p:null,pct:n(latest(c,'percentile'))};}).sort((a,b)=>Math.abs(b.d||0)-Math.abs(a.d||0));h.innerHTML=rows.map(x=>`<div class="flow-row"><span>${FLAGS[x.c]} ${x.c}</span><small>Net ${fmtInt(x.last)}</small><b class="${(x.d||0)>=0?'pos':'neg'}">${fmtInt(x.d)}</b><em>Pct ${x.pct===null?'—':x.pct.toFixed(1)}</em></div>`).join('');}
  function renderChart(){
    const c=state.selected,d=state.chart?.[c],svg=document.getElementById('cot-chart');if(!d||!svg)return;
    const vals=(d.net||[]).slice(-104), dates=(d.dates||[]).slice(-104); if(!vals.length)return;
    const W=900,H=280,pad={l:52,r:14,t:12,b:28}; const min=Math.min(...vals,0),max=Math.max(...vals,0),span=Math.max(1,max-min);
    const x=i=>pad.l+i*(W-pad.l-pad.r)/Math.max(1,vals.length-1); const y=v=>pad.t+(max-v)*(H-pad.t-pad.b)/span;
    let path=vals.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
    const area=`M${x(0).toFixed(1)},${y(0).toFixed(1)} `+vals.map((v,i)=>`L${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')+` L${x(vals.length-1).toFixed(1)},${y(0).toFixed(1)} Z`;
    const grids=[0,.25,.5,.75,1].map(f=>{const v=max-span*f;const yy=pad.t+(H-pad.t-pad.b)*f;return `<line class="chart-grid" x1="${pad.l}" x2="${W-pad.r}" y1="${yy}" y2="${yy}"/><text class="axis-text" x="4" y="${yy+3}">${Math.round(v/1000)}k</text>`;}).join('');
    const zero=y(0); const ticks=[0,.25,.5,.75,1].map(f=>{const i=Math.min(vals.length-1,Math.round((vals.length-1)*f));return `<text class="axis-text" x="${x(i)-18}" y="${H-7}">${esc((dates[i]||'').slice(0,7))}</text>`;}).join('');
    svg.innerHTML=`${grids}<line class="chart-zero" x1="${pad.l}" x2="${W-pad.r}" y1="${zero}" y2="${zero}"/><path class="chart-area" d="${area}"/><path class="chart-line" d="${path}"/>${ticks}`;
    const t=document.getElementById('chart-title');if(t)t.textContent=`${FLAGS[c]} ${c} · COT 104W`;
  }
  function renderMeta(){const d=state.chart?.USD?.dates;const asof=Array.isArray(d)&&d.length?d[d.length-1]:'—';const h=document.getElementById('cot-asof');if(h)h.textContent=`CFTC · as of ${asof}`;}
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d);}
  function bind(){document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));const c=document.querySelector('.pro-card button');if(c)c.addEventListener('click',()=>location.href='index.html');}
  async function main(){bind();clock();setInterval(clock,30000);try{[state.chart,state.stories]=await Promise.all([load(ROOT+'V250_COT_CHART_DATA.json'),load(ROOT+'V247_COT_STORIES.json')]);renderGrid();renderSelect();renderExtremes();renderFlow();renderChart();renderMeta();document.documentElement.setAttribute('data-positioning-page','READY');}catch(e){console.warn('[GMFQ positioning]',e);document.documentElement.setAttribute('data-positioning-page','FAIL');}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
