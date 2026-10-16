(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  let state={d:null,rates:null,ois:null,cot:null,cb:null};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const fmt=(v,d=2)=>{const x=n(v);return x===null?'—':x.toFixed(d)};
  const signed=(v,d=2,s='')=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}${s}`};
  const cls=v=>(n(v)||0)>=0?'pos':'neg';
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  function pairCode(){return (new URLSearchParams(location.search).get('pair')||'EURUSD').replace(/[^A-Z]/g,'').slice(0,6)}
  function splitPair(p){return [p.slice(0,3),p.slice(3,6)]}
  function pairRow(p){return (state.d?.pairs||[]).find(x=>String(x?.pair||'').replace(/[^A-Z]/g,'')===p)||null}
  function rate2(c){return n(state.rates?.[c]?.current?.y2)}
  function ois3(c){return n(state.ois?.currencies?.[c]?.horizons?.['3m']?.rate)}
  function cotPct(c){const a=state.cot?.[c]?.percentile;return Array.isArray(a)&&a.length?n(a[a.length-1]):null}
  function macro(c){return state.d?.macro?.[c]||{}}
  function render(){
    const p=pairCode(),[base,quote]=splitPair(p),row=pairRow(p),mb=macro(base),mq=macro(quote);
    document.title=`${p} — Global Macro FX Quant`;
    document.getElementById('pair-title').textContent=p;
    document.getElementById('pair-last').textContent=n(row?.last)===null?'—':fmt(row.last,4);
    document.getElementById('pair-asof').textContent=`as of ${row?.price_asof||state.d?.asOf||'—'}`;
    const y2b=rate2(base),y2q=rate2(quote),oib=ois3(base),oiq=ois3(quote),cb=cotPct(base),cq=cotPct(quote);
    const y2diff=y2b===null||y2q===null?null:(y2b-y2q)*100;
    const oisdiff=oib===null||oiq===null?null:(oib-oiq)*100;
    const cotdiff=cb===null||cq===null?null:cb-cq;
    const layers=[
      ['Macro',`${base}: ${mb.cycle_it||mb.cycle||'—'}`,`${quote}: ${mq.cycle_it||mq.cycle||'—'}`],
      ['Rates',`2Y diff ${signed(y2diff,0,'bp')}`,`${base} ${y2b===null?'—':fmt(y2b,2)+'%'} · ${quote} ${y2q===null?'—':fmt(y2q,2)+'%'}`],
      ['Market Pricing',`3M diff ${signed(oisdiff,0,'bp')}`,`${base} ${oib===null?'—':fmt(oib,3)+'%'} · ${quote} ${oiq===null?'—':fmt(oiq,3)+'%'}`],
      ['Positioning',`COT percentile Δ ${signed(cotdiff,0)}`,`${base} ${cb===null?'—':fmt(cb,0)} · ${quote} ${cq===null?'—':fmt(cq,0)}`],
      ['Price',`${signed(row?.ret1w,2,'%')} 1W`,`${signed(row?.ret1m,2,'%')} 1M · ${signed(row?.ret3m,2,'%')} 3M`],
      ['Trigger','Non pubblicato','Il front-end non inventa livelli tecnici o trigger operativi.']
    ];
    document.getElementById('layer-grid').innerHTML=layers.map(([k,v,d])=>`<article class="layer-card"><small>${k}</small><h3>${v}</h3><p>${d}</p></article>`).join('');
    const map=[
      ['Macro cycle',mb.cycle_it||mb.cycle||'—',mq.cycle_it||mq.cycle||'—',''],
      ['2Y',y2b===null?'—':fmt(y2b,2)+'%',y2q===null?'—':fmt(y2q,2)+'%',signed(y2diff,0,'bp')],
      ['OIS 3M',oib===null?'—':fmt(oib,3)+'%',oiq===null?'—':fmt(oiq,3)+'%',signed(oisdiff,0,'bp')],
      ['COT percentile',cb===null?'—':fmt(cb,0),cq===null?'—':fmt(cq,0),signed(cotdiff,0)]
    ];
    document.getElementById('relative-map').innerHTML=`<div class="map-row"><small>Layer</small><b>${base}</b><b>${quote}</b><b>Diff</b></div>`+map.map(([k,a,b,d])=>`<div class="map-row"><small>${k}</small><b>${a}</b><b>${b}</b><b class="${cls(parseFloat(d))}">${d}</b></div>`).join('');
    document.getElementById('trade-readiness').innerHTML=`Questa pagina separa <strong>tesi</strong> da <strong>esecuzione</strong>. I layer macro-finanziari sono già visibili; il blocco Trigger resta volutamente non valorizzato finché non arriva da un input tecnico canonico o da una regola esplicita.<br><br><span class="status">Nessun livello operativo inventato dal sito.</span>`;
    document.documentElement.setAttribute('data-coppia-page','READY');
  }
  function bind(){document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html')}
  function clock(){const d=new Date();const date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  async function main(){bind();clock();setInterval(clock,30000);try{[state.d,state.rates,state.ois,state.cot,state.cb]=await Promise.all([load('D.json'),load('NATIVE_RATES_DATA.json'),load('OIS_OPERATIONAL_VIEW.json'),load('V250_COT_CHART_DATA.json'),load('NATIVE_CB_DATA.json')]);render()}catch(e){console.warn('[GMFQ coppia]',e);document.documentElement.setAttribute('data-coppia-page','FAIL')}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
