(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const TF_LABEL={ret1w:'1W',ret1m:'1M',ret3m:'3M',ret6m:'6M',ret1y:'1Y'};
  let state={d:null,rates:null,ois:null,cot:null,tf:'ret1w'};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const fmt=(v,d=2)=>{const x=n(v);return x===null?'—':x.toFixed(d)};
  const fmtSigned=(v,d=2,suffix='')=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}${suffix}`};
  const cls=v=>(n(v)||0)>=0?'pos':'neg';
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  function normalizePair(p){return String(p||'').replace(/[^A-Z]/g,'').slice(0,6)}
  function splitPair(p){const x=normalizePair(p);return [x.slice(0,3),x.slice(3,6)]}
  function rate2(ccy){return n(state.rates?.[ccy]?.current?.y2)}
  function ois3(ccy){return n(state.ois?.currencies?.[ccy]?.horizons?.['3m']?.rate)}
  function cotPct(ccy){const a=state.cot?.[ccy]?.percentile;return Array.isArray(a)&&a.length?n(a[a.length-1]):null}
  function pairRows(){return (Array.isArray(state.d?.pairs)?state.d.pairs:[]).map(r=>{
    const pair=normalizePair(r.pair),[base,quote]=splitPair(pair);
    const ret=n(r[state.tf]);
    const y2a=rate2(base),y2b=rate2(quote),oisa=ois3(base),oisb=ois3(quote),ca=cotPct(base),cb=cotPct(quote);
    return {...r,pair,base,quote,ret,y2diff:y2a===null||y2b===null?null:(y2a-y2b)*100,oisdiff:oisa===null||oisb===null?null:(oisa-oisb)*100,cotdiff:ca===null||cb===null?null:ca-cb};
  })}
  function renderSummary(rows){
    const host=document.getElementById('pairs-summary'); if(!host)return;
    const valid=rows.filter(x=>x.ret!==null).sort((a,b)=>b.ret-a.ret);
    const strongest=valid[0],weakest=valid.at(-1);
    const max2y=[...rows].filter(x=>x.y2diff!==null).sort((a,b)=>Math.abs(b.y2diff)-Math.abs(a.y2diff))[0];
    const maxOis=[...rows].filter(x=>x.oisdiff!==null).sort((a,b)=>Math.abs(b.oisdiff)-Math.abs(a.oisdiff))[0];
    const cards=[
      ['Migliore '+TF_LABEL[state.tf],strongest?.pair||'—',strongest?fmtSigned(strongest.ret,2,'%'):'—'],
      ['Peggiore '+TF_LABEL[state.tf],weakest?.pair||'—',weakest?fmtSigned(weakest.ret,2,'%'):'—'],
      ['2Y diff più ampio',max2y?.pair||'—',max2y?fmtSigned(max2y.y2diff,0,'bp'):'—'],
      ['OIS 3M diff più ampio',maxOis?.pair||'—',maxOis?fmtSigned(maxOis.oisdiff,0,'bp'):'—']
    ];
    host.innerHTML=cards.map(([k,v,s])=>`<article class="pair-stat"><small>${k}</small><b>${v}</b><em>${s}</em></article>`).join('');
  }
  function renderTable(rows){
    const host=document.getElementById('pairs-table');if(!host)return;
    const sorted=[...rows].sort((a,b)=>(b.ret??-999)-(a.ret??-999));
    host.innerHTML=sorted.map(x=>`<div class="pair-row"><b>${x.pair}</b><span>${n(x.last)===null?'—':fmt(x.last,4)}</span><span class="${cls(x.ret)}">${fmtSigned(x.ret,2,'%')}</span><span class="${cls(x.y2diff)}">${fmtSigned(x.y2diff,0,'bp')}</span><span class="${cls(x.oisdiff)}">${fmtSigned(x.oisdiff,0,'bp')}</span><span class="${cls(x.cotdiff)}">${fmtSigned(x.cotdiff,0)}</span><a class="pair-open" href="coppia.html?pair=${x.pair}" aria-label="Apri ${x.pair}">→</a></div>`).join('');
    document.getElementById('tf-col').textContent=TF_LABEL[state.tf];
    const asof=document.getElementById('pairs-asof');if(asof)asof.textContent=`${rows.length} pair · FX as of ${rows[0]?.price_asof||state.d?.asOf||'—'}`;
  }
  function render(){const rows=pairRows();renderSummary(rows);renderTable(rows);document.documentElement.setAttribute('data-coppie-page','READY')}
  function bind(){
    document.querySelectorAll('#pair-timeframes button').forEach(btn=>btn.addEventListener('click',()=>{state.tf=btn.dataset.tf;document.querySelectorAll('#pair-timeframes button').forEach(b=>b.classList.toggle('active',b===btn));render()}));
    document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));
    document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html');
  }
  function clock(){const d=new Date();const date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  async function main(){bind();clock();setInterval(clock,30000);try{[state.d,state.rates,state.ois,state.cot]=await Promise.all([load('D.json'),load('NATIVE_RATES_DATA.json'),load('OIS_OPERATIONAL_VIEW.json'),load('V250_COT_CHART_DATA.json')]);render()}catch(e){console.warn('[GMFQ coppie]',e);document.documentElement.setAttribute('data-coppie-page','FAIL')}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
