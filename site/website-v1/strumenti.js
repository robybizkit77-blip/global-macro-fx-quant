(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  let state={price:null,rates:null,ois:null,cot:null,setup:null,h:'3m',a:'EUR',b:'USD'};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const signed=(v,d=1,s='')=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}${s}`};
  const cls=v=>{const x=n(v);return x===null?'missing':x>0?'pos':x<0?'neg':'zero'};
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: HTTP ${r.status}`);return r.json();}
  function rate2(c){return n(state.rates?.[c]?.['2Y'])??n(state.rates?.[c]?.current?.y2)}
  function ois(c,h){return n(state.ois?.currencies?.[c]?.horizons?.[h]?.rate)}
  function cot(c){const x=state.cot?.[c]?.percentile;return Array.isArray(x)&&x.length?n(x.at(-1)):null}
  function resolvePair(a,b){const x=a+b,y=b+a;return state.setup?.pairs?.[x]?x:state.setup?.pairs?.[y]?y:null}
  function pairRow(code){return (state.price?.pairs||[]).find(x=>String(x?.pair||'').replace(/[^A-Z]/g,'')===code)||null}
  function priceSeed(setup){
    const pairs=Object.entries(setup?.pairs||{}).map(([code,x])=>({pair:x?.canonical_pair||`${code.slice(0,3)}/${code.slice(3,6)}`}));
    if(pairs.length!==28)throw new Error(`Expected 28 canonical pairs, found ${pairs.length}`);
    return {pairs};
  }
  function renderSelectors(){
    const a=document.getElementById('tool-a'),b=document.getElementById('tool-b');
    const opts=ORDER.map(c=>`<option value="${c}">${FLAGS[c]} ${c}</option>`).join('');
    a.innerHTML=opts;b.innerHTML=opts;a.value=state.a;b.value=state.b;
  }
  function renderComparator(){
    const code=resolvePair(state.a,state.b),snap=code?state.setup.pairs[code]:null,row=code?pairRow(code):null;
    const canonical=snap?.canonical_pair||`${state.a}/${state.b}`;
    const [base,quote]=canonical.split('/');
    const y2a=rate2(base),y2b=rate2(quote),d2=y2a===null||y2b===null?null:(y2a-y2b)*100;
    const d3=ois(base,'3m')===null||ois(quote,'3m')===null?null:(ois(base,'3m')-ois(quote,'3m'))*100;
    const d6=ois(base,'6m')===null||ois(quote,'6m')===null?null:(ois(base,'6m')-ois(quote,'6m'))*100;
    const d12=ois(base,'12m')===null||ois(quote,'12m')===null?null:(ois(base,'12m')-ois(quote,'12m'))*100;
    const cd=cot(base)===null||cot(quote)===null?null:cot(base)-cot(quote);
    document.getElementById('compare-title').textContent=`Pair Comparator · ${canonical}`;
    document.getElementById('compare-asof').textContent=`Price ${row?.price_asof||state.price?.price_asof||'—'}`;
    document.getElementById('compare-summary').innerHTML=`<div><h2>${FLAGS[base]||''} ${base}/${quote} ${FLAGS[quote]||''}</h2><p>Orientamento canonico della pair disponibile nel motore.</p></div><div class="compare-price"><b>${n(row?.last)===null?'—':n(row.last).toFixed(n(row.last)>=100?3:5)}</b><small>1W ${signed(row?.ret1w,2,'%')} · 1M ${signed(row?.ret1m,2,'%')}</small></div>`;
    const metrics=[['2Y spread',d2,0,'bp',`${base} ${y2a===null?'—':y2a.toFixed(2)+'%'} · ${quote} ${y2b===null?'—':y2b.toFixed(2)+'%'}`],['OIS 3M',d3,0,'bp','market pricing'],['OIS 6M',d6,0,'bp','market pricing'],['OIS 12M',d12,0,'bp','market pricing'],['COT diff',cd,0,'','percentile 2Y'],['Price 3M',row?.ret3m,2,'%','ECB fixing return'],['Price 6M',row?.ret6m,2,'%','ECB fixing return'],['Price 1Y',row?.ret1y,2,'%','ECB fixing return']];
    document.getElementById('compare-metrics').innerHTML=metrics.map(([k,v,d,s,note])=>`<div class="tool-metric"><small>${k}</small><b class="${cls(v)}">${signed(v,d,s)}</b><em>${note}</em></div>`).join('');
    document.getElementById('compare-notes').textContent=`Le differenze sono sempre ${base} − ${quote}. Un valore positivo indica un livello maggiore sul lato base; non equivale automaticamente a un segnale FX.`;
    const setup=snap?.setup||{},frame=snap?.decision_frame||{};
    document.getElementById('setup-view').innerHTML=`<span class="setup-badge">${esc(setup.quality||'NON VALUTABILE')}</span><h4>Vantaggio strutturale · ${esc(setup.structuralFav||frame.fav||'—')}</h4><p>${esc(setup.structural?.relation||frame.relation||'Struttura non disponibile.')}</p><h4>Prezzo</h4><p>${esc(setup.price?.text||frame.priceReading||'—')}</p><h4>Timing</h4><p>${esc(setup.timing?.text||'—')}</p><h4>Cosa manca</h4><p>${esc(setup.structural?.missing||frame.missing||'—')}</p>${code?`<a href="coppia.html?pair=${code}">Apri Pair Deep Dive →</a>`:''}`;
  }
  function matrixValue(kind,a,b,h){if(a===b)return 0;const va=kind==='rates'?rate2(a):ois(a,h),vb=kind==='rates'?rate2(b):ois(b,h);return va===null||vb===null?null:(va-vb)*100}
  function renderMatrix(hostId,kind,h){
    const host=document.getElementById(hostId);if(!host)return;
    let html='<div class="diff-matrix"><div class="diff-cell head"></div>'+ORDER.map(c=>`<div class="diff-cell head">${c}</div>`).join('');
    for(const a of ORDER){html+=`<div class="diff-cell rowhead">${FLAGS[a]} ${a}</div>`;for(const b of ORDER){const v=matrixValue(kind,a,b,h);html+=`<div class="diff-cell ${cls(v)}" data-row="${a}" data-col="${b}">${v===null?'—':signed(v,0,'')}</div>`;}}
    html+='</div>';host.innerHTML=html;
  }
  function render(){renderComparator();renderMatrix('rates-matrix','rates');renderMatrix('ois-matrix-tools','ois',state.h);document.documentElement.dataset.strumentiPage='READY';document.documentElement.dataset.strumentiMatrix='READY';document.documentElement.dataset.strumentiData='CANONICAL_ONLY';}
  function bind(){
    document.getElementById('tool-a').addEventListener('change',e=>{state.a=e.target.value;if(state.a===state.b){state.b=ORDER.find(x=>x!==state.a);document.getElementById('tool-b').value=state.b}renderComparator()});
    document.getElementById('tool-b').addEventListener('change',e=>{state.b=e.target.value;if(state.a===state.b){state.a=ORDER.find(x=>x!==state.b);document.getElementById('tool-a').value=state.a}renderComparator()});
    document.querySelectorAll('#ois-horizon button').forEach(btn=>btn.addEventListener('click',()=>{state.h=btn.dataset.h;document.querySelectorAll('#ois-horizon button').forEach(x=>x.classList.toggle('active',x===btn));renderMatrix('ois-matrix-tools','ois',state.h)}));
    document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html');
  }
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  async function main(){clock();setInterval(clock,30000);try{[state.rates,state.ois,state.cot,state.setup]=await Promise.all([load('NATIVE_RATES_DATA.json'),load('OIS_OPERATIONAL_VIEW.json'),load('V250_COT_CHART_DATA.json'),load('PAIR_SETUP_OPERATIONAL_VIEW.json')]);if(state.setup?.schema!=='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'||state.setup?.pair_count!==28)throw new Error('Pair setup contract invalid');if(!window.GMFQWebsitePrice?.hydrate)throw new Error('Canonical Price runtime missing');state.price=priceSeed(state.setup);await window.GMFQWebsitePrice.hydrate(state.price);renderSelectors();bind();render()}catch(e){console.warn('[GMFQ strumenti]',e);document.documentElement.dataset.strumentiPage='FAIL'}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();