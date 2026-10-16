(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const TF_LABEL={ret1w:'1W',ret1m:'1M',ret3m:'3M',ret6m:'6M',ret1y:'1Y'};
  let state={d:null,rates:null,ois:null,cot:null,tf:'ret1w'};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const fmt=(v,d=2)=>{const x=n(v);return x===null?'—':x.toFixed(d)};
  const signed=(v,d=2,s='')=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}${s}`};
  const valCls=v=>{const x=n(v);return x===null?'neu':x>0?'pos':x<0?'neg':'neu'};
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  function normalizePair(p){return String(p||'').replace(/[^A-Z]/g,'').slice(0,6)}
  function splitPair(p){const x=normalizePair(p);return [x.slice(0,3),x.slice(3,6)]}
  function rate2(c){return n(state.rates?.[c]?.['2Y'])??n(state.rates?.[c]?.current?.y2)??n(state.d?.macro?.[c]?.rate2y)}
  function ois3(c){return n(state.ois?.currencies?.[c]?.horizons?.['3m']?.rate)}
  function cotPct(c){const a=state.cot?.[c]?.percentile;return Array.isArray(a)&&a.length?n(a[a.length-1]):null}
  function relativeReading(y2,ois,base,quote){
    if(y2===null||ois===null)return {tier:0,label:'Dati parziali',cls:'flat',side:'—',strength:0};
    const sy=Math.sign(y2),so=Math.sign(ois),strength=Math.min(Math.abs(y2),Math.abs(ois));
    if(Math.abs(y2)<5&&Math.abs(ois)<5)return {tier:1,label:'Poco contrasto',cls:'flat',side:'—',strength};
    if(sy!==0&&sy===so){const side=sy>0?base:quote;return {tier:3,label:'Allineato',cls:'align',side:`favorisce ${side}`,strength};}
    return {tier:2,label:'Diviso',cls:'split',side:'rates / pricing in conflitto',strength};
  }
  function rows(){return (state.d?.pairs||[]).map(r=>{
    const pair=normalizePair(r.pair),[base,quote]=splitPair(pair),ret=n(r[state.tf]);
    const y2a=rate2(base),y2b=rate2(quote),oisa=ois3(base),oisb=ois3(quote),ca=cotPct(base),cb=cotPct(quote);
    const y2diff=y2a===null||y2b===null?null:(y2a-y2b)*100;
    const oisdiff=oisa===null||oisb===null?null:(oisa-oisb)*100;
    const cotdiff=ca===null||cb===null?null:ca-cb;
    const reading=relativeReading(y2diff,oisdiff,base,quote);
    return {...r,pair,base,quote,ret,y2diff,oisdiff,cotdiff,reading};
  })}
  function ordered(list){return [...list].sort((a,b)=>b.reading.tier-a.reading.tier||b.reading.strength-a.reading.strength||Math.abs(b.ret||0)-Math.abs(a.ret||0)||a.pair.localeCompare(b.pair))}
  function renderTop(list){
    const host=document.getElementById('top-pairs');if(!host)return;
    const picks=ordered(list).filter(x=>x.reading.tier===3).slice(0,4);
    const use=picks.length?picks:ordered(list).slice(0,4);
    host.innerHTML=use.map((x,i)=>`<a class="top-pair" href="coppia.html?pair=${x.pair}"><div class="top-pair-top"><span class="rank-medal">#${i+1}</span><span class="${valCls(x.ret)}">${signed(x.ret,2,'%')} ${TF_LABEL[state.tf]}</span></div><h3>${x.pair}</h3><div class="direction-line ${x.reading.tier===3?(x.y2diff>0?'pos':'neg'):'neu'}">${x.reading.label} · ${x.reading.side}</div><p>Il 2Y e il pricing 3M ${x.reading.tier===3?'separano la coppia nella stessa direzione':'non danno ancora una separazione pulita'}.</p><div class="top-pair-foot"><span>2Y <b>${signed(x.y2diff,0,'bp')}</b></span><span>3M <b>${signed(x.oisdiff,0,'bp')}</b></span><span>COT <b>${signed(x.cotdiff,0)}</b></span></div></a>`).join('');
  }
  function renderTable(list){
    const host=document.getElementById('pairs-table');if(!host)return;
    const sorted=ordered(list);
    host.innerHTML=sorted.map((x,i)=>`<div class="ranking-row"><span class="rank-num">${String(i+1).padStart(2,'0')}</span><b class="pair-name">${x.pair}</b><span class="reading"><i class="reading-pill ${x.reading.cls}">${x.reading.label}</i><em class="reading-side">${x.reading.side}</em></span><span class="${valCls(x.y2diff)}">${signed(x.y2diff,0,'bp')}</span><span class="${valCls(x.oisdiff)}">${signed(x.oisdiff,0,'bp')}</span><span class="${valCls(x.ret)}">${signed(x.ret,2,'%')}</span><span class="${valCls(x.cotdiff)}">${signed(x.cotdiff,0)}</span><a class="pair-open" href="coppia.html?pair=${x.pair}" aria-label="Apri ${x.pair}">→</a></div>`).join('');
    document.getElementById('tf-col').textContent=TF_LABEL[state.tf];
    const asof=document.getElementById('pairs-asof');if(asof)asof.textContent=`${list.length} pair · FX as of ${state.d?.price_asof||list[0]?.price_asof||'—'}`;
  }
  function render(){const list=rows();renderTop(list);renderTable(list);document.documentElement.dataset.coppiePage='READY'}
  function bind(){
    document.querySelectorAll('#pair-timeframes button').forEach(btn=>btn.addEventListener('click',()=>{state.tf=btn.dataset.tf;document.querySelectorAll('#pair-timeframes button').forEach(b=>b.classList.toggle('active',b===btn));render()}));
    document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));
    document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html');
  }
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  async function main(){bind();clock();setInterval(clock,30000);try{[state.d,state.rates,state.ois,state.cot]=await Promise.all([load('D.json'),load('NATIVE_RATES_DATA.json'),load('OIS_OPERATIONAL_VIEW.json'),load('V250_COT_CHART_DATA.json')]);if(!window.GMFQWebsitePrice?.hydrate)throw new Error('Canonical Price runtime adapter missing');await window.GMFQWebsitePrice.hydrate(state.d);render()}catch(e){console.warn('[GMFQ coppie]',e);document.documentElement.dataset.coppiePage='FAIL'}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
