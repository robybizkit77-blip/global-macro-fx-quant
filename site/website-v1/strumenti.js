(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const OIS_MAX_AGE_DAYS=5,COT_MAX_AGE_DAYS=10;
  let state={price:null,rates:null,ois:null,cot:null,setup:null,h:'3m',a:'EUR',b:'USD'};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const signed=(v,d=1,s='')=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}${s}`};
  const cls=v=>{const x=n(v);return x===null?'missing':x>0?'pos':x<0?'neg':'zero'};
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: HTTP ${r.status}`);return r.json();}
  async function optional(f){try{return await load(f)}catch(e){console.warn(`[GMFQ strumenti optional ${f}]`,e);return null}}
  function ageDays(s){if(!/^\d{4}-\d{2}-\d{2}$/.test(String(s||'')))return Infinity;const t=Date.parse(`${s}T00:00:00Z`);return Number.isFinite(t)?Math.floor((Date.now()-t)/86400000):Infinity}
  function rate2(c){return n(state.rates?.[c]?.['2Y'])??n(state.rates?.[c]?.current?.y2)}
  function ois(c,h){const x=state.ois?.currencies?.[c];if(!x||ageDays(x.as_of)>OIS_MAX_AGE_DAYS)return null;return n(x?.horizons?.[h]?.rate)}
  function cot(c){const x=state.cot?.[c],dates=Array.isArray(x?.dates)?x.dates:[],pct=Array.isArray(x?.percentile)?x.percentile:[];if(!dates.length||!pct.length||ageDays(dates.at(-1))>COT_MAX_AGE_DAYS)return null;return n(pct.at(-1))}
  function resolvePair(a,b){const x=a+b,y=b+a;return state.setup?.pairs?.[x]?x:state.setup?.pairs?.[y]?y:null}
  function pairRow(code){return (state.price?.pairs||[]).find(x=>String(x?.pair||'').replace(/[^A-Z]/g,'')===code)||null}
  function priceSeed(setup){
    const pairs=Object.entries(setup?.pairs||{}).map(([code,x])=>({pair:x?.canonical_pair||`${code.slice(0,3)}/${code.slice(3,6)}`}));
    if(pairs.length!==28)throw new Error(`Expected 28 canonical pairs, found ${pairs.length}`);
    return {pairs};
  }
  function orientedReturn(v,inverted){
    const x=n(v);if(x===null)return null;if(!inverted)return x;
    const gross=1+x/100;return gross>0?(1/gross-1)*100:null;
  }
  function renderSelectors(){
    const a=document.getElementById('tool-a'),b=document.getElementById('tool-b');
    const opts=ORDER.map(c=>`<option value="${c}">${FLAGS[c]} ${c}</option>`).join('');
    a.innerHTML=opts;b.innerHTML=opts;a.value=state.a;b.value=state.b;
  }
  function renderComparator(){
    const code=resolvePair(state.a,state.b),snap=code?state.setup.pairs[code]:null,row=code?pairRow(code):null;
    const selectedCode=`${state.a}${state.b}`;
    const inverted=Boolean(code&&code!==selectedCode);
    const base=state.a,quote=state.b,displayPair=`${base}/${quote}`;
    const y2a=rate2(base),y2b=rate2(quote),d2=y2a===null||y2b===null?null:(y2a-y2b)*100;
    const o3a=ois(base,'3m'),o3b=ois(quote,'3m'),d3=o3a===null||o3b===null?null:(o3a-o3b)*100;
    const o6a=ois(base,'6m'),o6b=ois(quote,'6m'),d6=o6a===null||o6b===null?null:(o6a-o6b)*100;
    const o12a=ois(base,'12m'),o12b=ois(quote,'12m'),d12=o12a===null||o12b===null?null:(o12a-o12b)*100;
    const ca=cot(base),cb=cot(quote),cd=ca===null||cb===null?null:ca-cb;
    const rawLast=n(row?.last),last=rawLast===null?null:(inverted?1/rawLast:rawLast);
    const r1w=orientedReturn(row?.ret1w,inverted),r1m=orientedReturn(row?.ret1m,inverted),r3m=orientedReturn(row?.ret3m,inverted),r6m=orientedReturn(row?.ret6m,inverted),r1y=orientedReturn(row?.ret1y,inverted);
    document.getElementById('compare-title').textContent=`Pair Comparator · ${displayPair}`;
    document.getElementById('compare-asof').textContent=`Price ${row?.price_asof||state.price?.price_asof||state.setup?.price_asof||'—'}`;
    document.getElementById('compare-summary').innerHTML=`<div><h2>${FLAGS[base]||''} ${displayPair} ${FLAGS[quote]||''}</h2><p>Confronto relativo nell’ordine selezionato: ${base} − ${quote}.</p></div><div class="compare-price"><b>${last===null?'—':last.toFixed(last>=100?3:5)}</b><small>1W ${signed(r1w,2,'%')} · 1M ${signed(r1m,2,'%')}</small></div>`;
    const metrics=[['2Y spread',d2,0,'bp',d2===null?'dato non disponibile':`${base} ${y2a.toFixed(2)}% · ${quote} ${y2b.toFixed(2)}%`],['OIS 3M',d3,0,'bp',d3===null?'dato non disponibile':'market pricing'],['OIS 6M',d6,0,'bp',d6===null?'dato non disponibile':'market pricing'],['OIS 12M',d12,0,'bp',d12===null?'dato non disponibile':'market pricing'],['COT diff',cd,0,'',cd===null?'dato non disponibile':'percentile 2Y'],['Price 3M',r3m,2,'%','ECB fixing return'],['Price 6M',r6m,2,'%','ECB fixing return'],['Price 1Y',r1y,2,'%','ECB fixing return']];
    document.getElementById('compare-metrics').innerHTML=metrics.map(([k,v,d,s,note])=>`<div class="tool-metric"><small>${k}</small><b class="${cls(v)}">${signed(v,d,s)}</b><em>${note}</em></div>`).join('');
    document.getElementById('compare-notes').textContent=`Tutte le differenze seguono l’ordine ${base} − ${quote}. Se il mercato quota normalmente la pair al contrario, prezzo e rendimenti vengono invertiti matematicamente solo per questa vista.`;
    const setup=snap?.setup||{},frame=snap?.decision_frame||{},canonical=snap?.canonical_pair||code||'—';
    document.getElementById('setup-view').innerHTML=`<span class="setup-badge">${esc(setup.quality||'NON VALUTABILE')}</span><h4>Valuta favorita · ${esc(setup.structuralFav||frame.fav||'—')}</h4><p>${esc(setup.structural?.relation||frame.relation||'Struttura non disponibile.')}</p><h4>Prezzo</h4><p>${esc(setup.price?.text||frame.priceReading||'—')}</p><h4>Timing</h4><p>${esc(setup.timing?.text||'—')}</p><h4>Cosa manca</h4><p>${esc(setup.structural?.missing||frame.missing||'—')}</p>${code?`<a href="coppia.html?pair=${encodeURIComponent(code)}">Apri ${esc(canonical)} Deep Dive →</a>`:''}`;
  }
  function matrixValue(kind,a,b,h){if(a===b)return 0;const va=kind==='rates'?rate2(a):ois(a,h),vb=kind==='rates'?rate2(b):ois(b,h);return va===null||vb===null?null:(va-vb)*100}
  function renderMatrix(hostId,kind,h){
    const host=document.getElementById(hostId);if(!host)return;
    let html='<div class="diff-matrix"><div class="diff-cell head"></div>'+ORDER.map(c=>`<div class="diff-cell head">${c}</div>`).join('');
    for(const a of ORDER){html+=`<div class="diff-cell rowhead">${FLAGS[a]} ${a}</div>`;for(const b of ORDER){const v=matrixValue(kind,a,b,h);html+=`<div class="diff-cell ${cls(v)}" data-row="${a}" data-col="${b}" title="${a} − ${b}">${v===null?'—':signed(v,0,'')}</div>`;}}
    html+='</div>';host.innerHTML=html;
  }
  function render(){renderComparator();renderMatrix('rates-matrix','rates');renderMatrix('ois-matrix-tools','ois',state.h);document.documentElement.dataset.strumentiPage='READY';document.documentElement.dataset.strumentiMatrix='READY';document.documentElement.dataset.strumentiData='FAIL_SOFT';}
  function bind(){
    document.getElementById('tool-a').addEventListener('change',e=>{state.a=e.target.value;if(state.a===state.b){state.b=ORDER.find(x=>x!==state.a);document.getElementById('tool-b').value=state.b}renderComparator()});
    document.getElementById('tool-b').addEventListener('change',e=>{state.b=e.target.value;if(state.a===state.b){state.a=ORDER.find(x=>x!==state.b);document.getElementById('tool-a').value=state.a}renderComparator()});
    document.querySelectorAll('#ois-horizon button').forEach(btn=>btn.addEventListener('click',()=>{state.h=btn.dataset.h;document.querySelectorAll('#ois-horizon button').forEach(x=>x.classList.toggle('active',x===btn));renderMatrix('ois-matrix-tools','ois',state.h)}));
    document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html');
  }
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  async function main(){
    clock();setInterval(clock,30000);
    try{
      state.setup=await load('PAIR_SETUP_OPERATIONAL_VIEW.json');
      if(state.setup?.schema!=='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'||state.setup?.pair_count!==28||state.setup?.status!=='CURRENT_CANONICAL_ENGINE')throw new Error('Pair setup contract invalid');
      [state.rates,state.ois,state.cot]=await Promise.all([optional('NATIVE_RATES_DATA.json'),optional('OIS_OPERATIONAL_VIEW.json'),optional('V250_COT_CHART_DATA.json')]);
      if(!window.GMFQWebsitePrice?.hydrate)throw new Error('Price runtime missing');
      state.price=priceSeed(state.setup);
      await window.GMFQWebsitePrice.hydrate(state.price);
      renderSelectors();bind();render();
    }catch(e){console.warn('[GMFQ strumenti]',e);document.documentElement.dataset.strumentiPage='FAIL'}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();