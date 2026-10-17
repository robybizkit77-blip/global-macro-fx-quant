(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const OIS_MAX_AGE_DAYS=5,COT_MAX_AGE_DAYS=10;
  let state={price:null,setup:null,rates:{},ois:{},cot:{},ctx:{}};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const fmt=(v,d=2)=>{const x=n(v);return x===null?'—':x.toFixed(d)};
  const signed=(v,d=2,s='')=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}${s}`};
  const cls=v=>{const x=n(v);return x===null?'':x>0?'pos':x<0?'neg':''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  async function optional(f,fallback){try{return await load(f)}catch(e){console.warn('[GMFQ pair optional]',f,e);return fallback}}
  function ageDays(s){if(!/^\d{4}-\d{2}-\d{2}$/.test(String(s||'')))return Infinity;const d=new Date(`${s}T00:00:00Z`),now=new Date();return Math.floor((Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate())-d.getTime())/86400000)}
  function pairCode(){return (new URLSearchParams(location.search).get('pair')||'EURUSD').replace(/[^A-Z]/g,'').slice(0,6)}
  function splitPair(p){return [p.slice(0,3),p.slice(3,6)]}
  function pairRow(p){return (state.price?.pairs||[]).find(x=>String(x?.pair||'').replace(/[^A-Z]/g,'')===p)||null}
  function setupRow(p){return state.setup?.pairs?.[p]||null}
  function rate2(c){return n(state.rates?.[c]?.['2Y'])??n(state.rates?.[c]?.current?.y2)}
  function ois3(c){const x=state.ois?.currencies?.[c];if(!x||ageDays(x.as_of)>OIS_MAX_AGE_DAYS)return null;return n(x?.horizons?.['3m']?.rate)}
  function cotPct(c){const x=state.cot?.[c],dates=Array.isArray(x?.dates)?x.dates:[],a=Array.isArray(x?.percentile)?x.percentile:[];if(!dates.length||!a.length||ageDays(dates.at(-1))>COT_MAX_AGE_DAYS)return null;return n(a.at(-1))}
  function macro(c){return state.ctx?.[c]||{}}
  function summary(c){return state.ctx?.[c]?.summary_it||'Quadro macro non disponibile.'}
  function priceSeed(setup){const pairs=Object.entries(setup?.pairs||{}).map(([code,x])=>({pair:x?.canonical_pair||`${code.slice(0,3)}/${code.slice(3,6)}`}));if(pairs.length!==28)throw new Error(`Expected 28 canonical pairs, found ${pairs.length}`);return {pairs}}
  function validateSetup(x){if(x?.schema!=='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'||x?.status!=='CURRENT_CANONICAL_ENGINE')throw new Error('Pair setup contract invalid');if(x?.pair_count!==28||Object.keys(x?.pairs||{}).length!==28)throw new Error('Pair setup coverage invalid');if(x?.thesis_is_not_entry!==true||x?.entry_level_published!==false)throw new Error('Pair setup thesis/entry contract invalid');if(x?.price_audit?.status!=='PASS')throw new Error('Pair setup price audit not PASS')}
  function marketReading(y2,ois,base,quote){if(y2===null||ois===null)return {type:'partial',label:'Rates/pricing parziali',fav:null};if(Math.abs(y2)<5&&Math.abs(ois)<5)return {type:'flat',label:'Poco contrasto rates/pricing',fav:null};if(Math.sign(y2)!==0&&Math.sign(y2)===Math.sign(ois)){const fav=y2>0?base:quote;return {type:'align',label:`Rates/pricing favoriscono ${fav}`,fav}}return {type:'split',label:'Rates e pricing divisi',fav:null}}
  function qualityClass(q){q=String(q||'').toUpperCase();if(q==='PULITO')return'align';if(q==='CON RISCHI'||q==='DA CONFERMARE')return'split';return''}
  function setMove(id,v){const el=document.getElementById(id);if(!el)return;el.textContent=signed(v,2,'%');el.className=cls(v)}
  function chips(items){return items.map(x=>`<span class="compare-chip ${x.cls||''}">${esc(x.k)}<b>${esc(x.v)}</b></span>`).join('')}
  function render(){
    const p=pairCode(),snap=setupRow(p);if(!snap)throw new Error(`Pair ${p} not present in canonical setup`);
    const setup=snap.setup||{},frame=snap.decision_frame||{},[base,quote]=splitPair(p),row=pairRow(p),mb=macro(base),mq=macro(quote);
    const quality=setup.quality||frame.quality||'NON VALUTABILE',fav=setup.structuralFav||frame.fav||'—';
    const relation=setup.structural?.relation||frame.relation||'Struttura relativa non determinata.';
    const missing=setup.structural?.missing||frame.missing||'—';
    const y2b=rate2(base),y2q=rate2(quote),oib=ois3(base),oiq=ois3(quote),cotb=cotPct(base),cotq=cotPct(quote);
    const y2diff=y2b===null||y2q===null?null:(y2b-y2q)*100,oisdiff=oib===null||oiq===null?null:(oib-oiq)*100,cotdiff=cotb===null||cotq===null?null:cotb-cotq;
    const market=marketReading(y2diff,oisdiff,base,quote);
    document.title=`${p} — Global Macro FX Quant`;
    document.getElementById('pair-title').textContent=snap.canonical_pair||`${base}/${quote}`;
    const st=document.getElementById('pair-state');st.textContent=quality;st.className=`pair-state ${qualityClass(quality)}`;
    document.getElementById('pair-last').textContent=n(row?.last)===null?'—':fmt(row.last,p.includes('JPY')?3:5);
    document.getElementById('pair-asof').textContent=`as of ${row?.price_asof||state.price?.price_asof||state.setup?.price_asof||'—'}`;
    setMove('move-1w',row?.ret1w);setMove('move-1m',row?.ret1m);setMove('move-3m',row?.ret3m);

    document.getElementById('pair-thesis').textContent=fav==='—'?`${p}: tesi relativa non ancora definita`:`${fav} ha il vantaggio strutturale nella pair`;
    document.getElementById('pair-lead').textContent=`${relation} Rates, market pricing, COT e prezzo servono a verificare quanto questa tesi è confermata, divisa o già espressa.`;

    document.getElementById('thesis-snapshot').innerHTML=[
      ['TESI',quality,fav==='—'?'nessun lato favorito':`favorisce ${fav}`,qualityClass(quality)],
      ['2Y DIFFERENTIAL',signed(y2diff,0,' bp'),`${base} ${y2b===null?'—':fmt(y2b,2)+'%'} · ${quote} ${y2q===null?'—':fmt(y2q,2)+'%'}`,cls(y2diff)],
      ['PRICING 3M',signed(oisdiff,0,' bp'),`${base} ${oib===null?'—':fmt(oib,3)+'%'} · ${quote} ${oiq===null?'—':fmt(oiq,3)+'%'}`,cls(oisdiff)],
      ['COT RELATIVO',signed(cotdiff,0),`percentile: ${base} ${cotb===null?'—':fmt(cotb,0)} · ${quote} ${cotq===null?'—':fmt(cotq,0)}`,cls(cotdiff)],
      ['PREZZO 1W',signed(row?.ret1w,2,'%'),`1M ${signed(row?.ret1m,2,'%')} · 3M ${signed(row?.ret3m,2,'%')}`,cls(row?.ret1w)]
    ].map(([k,v,e,c])=>`<div class="snapshot-item"><small>${k}</small><b class="${c}">${esc(v)}</b><em>${esc(e)}</em></div>`).join('');

    document.getElementById('macro-title').textContent=`${base}: ${mb.status||'—'} · ${quote}: ${mq.status||'—'}`;
    document.getElementById('macro-copy').textContent=`${summary(base)} ${summary(quote)}`;
    document.getElementById('macro-compare').innerHTML=chips([{k:base,v:mb.status||'—'},{k:quote,v:mq.status||'—'}]);

    document.getElementById('rates-title').textContent=market.label;
    document.getElementById('rates-copy').textContent=`Il differenziale 2Y è ${signed(y2diff,0,' bp')} e il differenziale del pricing 3M è ${signed(oisdiff,0,' bp')}. Questi dati non creano una seconda tesi: mostrano se il mercato sta confermando o complicando il vantaggio strutturale ${fav==='—'?'della pair':`di ${fav}`}.`;
    document.getElementById('rates-compare').innerHTML=chips([{k:'2Y',v:signed(y2diff,0,' bp'),cls:cls(y2diff)},{k:'3M',v:signed(oisdiff,0,' bp'),cls:cls(oisdiff)},{k:base,v:y2b===null?'—':fmt(y2b,2)+'%'},{k:quote,v:y2q===null?'—':fmt(y2q,2)+'%'}]);

    document.getElementById('position-title').textContent='Positioning e prezzo: conferma, crowding e timing';
    document.getElementById('position-copy').textContent=`Il percentile COT è ${cotb===null?'—':fmt(cotb,0)} per ${base} e ${cotq===null?'—':fmt(cotq,0)} per ${quote}. Il prezzo ha mosso ${signed(row?.ret1w,2,'%')} in 1 settimana, ${signed(row?.ret1m,2,'%')} in 1 mese e ${signed(row?.ret3m,2,'%')} in 3 mesi. Sono layer di conferma e timing, non l'origine della tesi.`;
    document.getElementById('position-compare').innerHTML=chips([{k:`COT ${base}`,v:cotb===null?'—':fmt(cotb,0)},{k:`COT ${quote}`,v:cotq===null?'—':fmt(cotq,0)},{k:'1W',v:signed(row?.ret1w,2,'%'),cls:cls(row?.ret1w)},{k:'1M',v:signed(row?.ret1m,2,'%'),cls:cls(row?.ret1m)}]);

    const map=[['Tesi',quality,fav==='—'?'—':fav,''],['Macro',mb.status||'—',mq.status||'—',''],['2Y',y2b===null?'—':fmt(y2b,2)+'%',y2q===null?'—':fmt(y2q,2)+'%',signed(y2diff,0,'bp')],['Pricing 3M',oib===null?'—':fmt(oib,3)+'%',oiq===null?'—':fmt(oiq,3)+'%',signed(oisdiff,0,'bp')],['COT percentile',cotb===null?'—':fmt(cotb,0),cotq===null?'—':fmt(cotq,0),signed(cotdiff,0)]];
    document.getElementById('relative-map').innerHTML=`<div class="map-row"><small>Layer</small><b>${base}</b><b>${quote}</b><b>Diff</b></div>`+map.map(([k,a,b,d])=>`<div class="map-row"><small>${esc(k)}</small><b>${esc(a)}</b><b>${esc(b)}</b><b class="${d?cls(parseFloat(d)):''}">${esc(d)}</b></div>`).join('');

    document.getElementById('trade-readiness').innerHTML=`La <strong>tesi relativa</strong> e l'<strong>entrata</strong> restano due cose diverse. Qualità corrente: <strong>${esc(quality)}</strong> · vantaggio strutturale: <strong>${esc(fav)}</strong>.<br><br><span class="status">Nessun livello di ingresso viene inventato.</span>`;
    document.getElementById('confirm-title').textContent=fav==='—'?'La tesi acquista un lato chiaro':`${fav} mantiene il vantaggio strutturale`;
    document.getElementById('confirm-copy').textContent=`La lettura si rafforza se i driver indicati nel setup restano coerenti e rates/pricing/prezzo convergono con la tesi. Timing attuale: ${setup.timing?.text||'—'}`;
    document.getElementById('challenge-title').textContent='La struttura relativa perde qualità';
    document.getElementById('challenge-copy').textContent=`La tesi va ridotta se il vantaggio strutturale si deteriora o i layer di conferma divergono in modo persistente. Cosa manca oggi: ${missing}`;
    document.documentElement.dataset.coppiaPage='READY';
    document.documentElement.dataset.coppiaThesis='CANONICAL_PAIR_SETUP';
    document.documentElement.dataset.coppiaQuality=quality;
    document.documentElement.dataset.coppiaFav=fav;
  }
  function bind(){document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html')}
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  async function main(){
    bind();clock();setInterval(clock,30000);
    try{
      state.setup=await load('PAIR_SETUP_OPERATIONAL_VIEW.json');validateSetup(state.setup);
      const p=pairCode();if(!state.setup.pairs?.[p])throw new Error(`Pair ${p} not found`);
      if(!window.GMFQWebsitePrice?.hydrate)throw new Error('Price runtime missing');
      state.price=priceSeed(state.setup);await window.GMFQWebsitePrice.hydrate(state.price);
      [state.rates,state.ois,state.cot,state.ctx]=await Promise.all([optional('NATIVE_RATES_DATA.json',{}),optional('OIS_OPERATIONAL_VIEW.json',{}),optional('V250_COT_CHART_DATA.json',{}),optional('COUNTRY_CTX.json',{})]);
      render();
    }catch(e){console.warn('[GMFQ coppia]',e);document.getElementById('pair-thesis').textContent='Pair Deep Dive non disponibile';document.getElementById('pair-lead').textContent='Il quadro principale della pair non è disponibile o non è coerente con l’universo delle 28 coppie.';document.documentElement.dataset.coppiaPage='FAIL'}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
