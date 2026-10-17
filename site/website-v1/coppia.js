(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  let state={price:null,setup:null,rates:null,ois:null,cot:null,ctx:{}};
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const fmt=(v,d=2)=>{const x=n(v);return x===null?'—':x.toFixed(d)};
  const signed=(v,d=2,s='')=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}${s}`};
  const cls=v=>{const x=n(v);return x===null?'':x>0?'pos':x<0?'neg':''};
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  async function optional(f,fallback){try{return await load(f)}catch(e){console.warn('[GMFQ pair optional]',f,e);return fallback}}
  function pairCode(){return (new URLSearchParams(location.search).get('pair')||'EURUSD').replace(/[^A-Z]/g,'').slice(0,6)}
  function splitPair(p){return [p.slice(0,3),p.slice(3,6)]}
  function pairRow(p){return (state.price?.pairs||[]).find(x=>String(x?.pair||'').replace(/[^A-Z]/g,'')===p)||null}
  function rate2(c){return n(state.rates?.[c]?.['2Y'])??n(state.rates?.[c]?.current?.y2)}
  function ois3(c){return n(state.ois?.currencies?.[c]?.horizons?.['3m']?.rate)}
  function cotPct(c){const a=state.cot?.[c]?.percentile;return Array.isArray(a)&&a.length?n(a[a.length-1]):null}
  function macro(c){return state.ctx?.[c]||{}}
  function summary(c){return state.ctx?.[c]?.summary_it||'Quadro macro non disponibile.'}
  function priceSeed(setup){const pairs=Object.entries(setup?.pairs||{}).map(([code,x])=>({pair:x?.canonical_pair||`${code.slice(0,3)}/${code.slice(3,6)}`}));if(pairs.length!==28)throw new Error(`Expected 28 canonical pairs, found ${pairs.length}`);return {pairs};}
  function reading(y2,ois,base,quote){
    if(y2===null||ois===null)return {type:'partial',label:'Dati parziali',fav:null};
    if(Math.abs(y2)<5&&Math.abs(ois)<5)return {type:'flat',label:'Poco contrasto',fav:null};
    if(Math.sign(y2)!==0&&Math.sign(y2)===Math.sign(ois)){const fav=y2>0?base:quote;return {type:'align',label:'Rates e pricing allineati',fav};}
    return {type:'split',label:'Rates e pricing divisi',fav:null};
  }
  function setMove(id,v){const el=document.getElementById(id);if(!el)return;el.textContent=signed(v,2,'%');el.className=cls(v)}
  function chips(items){return items.map(x=>`<span class="compare-chip ${x.cls||''}">${x.k}<b>${x.v}</b></span>`).join('')}
  function render(){
    const p=pairCode(),[base,quote]=splitPair(p),row=pairRow(p),mb=macro(base),mq=macro(quote);
    const y2b=rate2(base),y2q=rate2(quote),oib=ois3(base),oiq=ois3(quote),cotb=cotPct(base),cotq=cotPct(quote);
    const y2diff=y2b===null||y2q===null?null:(y2b-y2q)*100;
    const oisdiff=oib===null||oiq===null?null:(oib-oiq)*100;
    const cotdiff=cotb===null||cotq===null?null:cotb-cotq;
    const r=reading(y2diff,oisdiff,base,quote);
    document.title=`${p} — Global Macro FX Quant`;
    document.getElementById('pair-title').textContent=p;
    const st=document.getElementById('pair-state');st.textContent=r.label;st.className=`pair-state ${r.type==='align'?'align':r.type==='split'?'split':''}`;
    document.getElementById('pair-last').textContent=n(row?.last)===null?'—':fmt(row.last,p.includes('JPY')?3:5);
    document.getElementById('pair-asof').textContent=`as of ${row?.price_asof||state.price?.price_asof||state.setup?.price_asof||'—'}`;
    setMove('move-1w',row?.ret1w);setMove('move-1m',row?.ret1m);setMove('move-3m',row?.ret3m);

    const thesis=document.getElementById('pair-thesis'),lead=document.getElementById('pair-lead');
    if(r.type==='align'){
      thesis.textContent=`${r.fav} ha il vantaggio relativo nel front-end e nel pricing 3M`;
      lead.textContent=`Il 2Y e il market pricing separano ${base} e ${quote} nella stessa direzione. È una struttura relativa da approfondire; macro, positioning e prezzo dicono quanto è completa e quanto è già espressa.`;
    }else if(r.type==='split'){
      thesis.textContent=`${p} non ha ancora un contrasto macro-finanziario pulito`;
      lead.textContent='Il front-end e il market pricing non puntano nella stessa direzione. La coppia resta interessante da monitorare, ma la lettura relativa è meno pulita e richiede convergenza dei driver.';
    }else{
      thesis.textContent=`${p}: separazione relativa ancora limitata`;
      lead.textContent='I dati disponibili non mostrano ancora una distanza sufficiente e coerente tra le due valute. La lettura resta neutra finché i driver non si separano meglio.';
    }

    document.getElementById('thesis-snapshot').innerHTML=[
      ['2Y DIFFERENTIAL',signed(y2diff,0,' bp'),`${base} ${y2b===null?'—':fmt(y2b,2)+'%'} · ${quote} ${y2q===null?'—':fmt(y2q,2)+'%'}`,cls(y2diff)],
      ['PRICING 3M',signed(oisdiff,0,' bp'),`${base} ${oib===null?'—':fmt(oib,3)+'%'} · ${quote} ${oiq===null?'—':fmt(oiq,3)+'%'}`,cls(oisdiff)],
      ['COT RELATIVO',signed(cotdiff,0),`percentile: ${base} ${cotb===null?'—':fmt(cotb,0)} · ${quote} ${cotq===null?'—':fmt(cotq,0)}`,cls(cotdiff)],
      ['PREZZO 1W',signed(row?.ret1w,2,'%'),`1M ${signed(row?.ret1m,2,'%')} · 3M ${signed(row?.ret3m,2,'%')}`,cls(row?.ret1w)]
    ].map(([k,v,e,c])=>`<div class="snapshot-item"><small>${k}</small><b class="${c}">${v}</b><em>${e}</em></div>`).join('');

    document.getElementById('macro-title').textContent=`${base}: ${mb.status||'—'} · ${quote}: ${mq.status||'—'}`;
    document.getElementById('macro-copy').textContent=`${summary(base)} ${summary(quote)}`;
    document.getElementById('macro-compare').innerHTML=chips([{k:base,v:mb.status||'—'},{k:quote,v:mq.status||'—'}]);

    document.getElementById('rates-title').textContent=r.type==='align'?`Front-end e pricing favoriscono ${r.fav}`:r.type==='split'?'Front-end e pricing non sono allineati':'Il contrasto tassi è contenuto';
    document.getElementById('rates-copy').textContent=`Il differenziale 2Y è ${signed(y2diff,0,' bp')} e il differenziale del pricing 3M è ${signed(oisdiff,0,' bp')}. Il 2Y fotografa il repricing del front-end; il 3M mostra ciò che il mercato incorpora più direttamente sulla traiettoria di policy.`;
    document.getElementById('rates-compare').innerHTML=chips([{k:'2Y',v:signed(y2diff,0,' bp'),cls:cls(y2diff)},{k:'3M',v:signed(oisdiff,0,' bp'),cls:cls(oisdiff)},{k:base,v:y2b===null?'—':fmt(y2b,2)+'%'},{k:quote,v:y2q===null?'—':fmt(y2q,2)+'%'}]);

    document.getElementById('position-title').textContent=`Positioning e prezzo: contesto, non origine della tesi`;
    document.getElementById('position-copy').textContent=`Il percentile COT è ${cotb===null?'—':fmt(cotb,0)} per ${base} e ${cotq===null?'—':fmt(cotq,0)} per ${quote}. Il prezzo della coppia ha mosso ${signed(row?.ret1w,2,'%')} in 1 settimana, ${signed(row?.ret1m,2,'%')} in 1 mese e ${signed(row?.ret3m,2,'%')} in 3 mesi. Questi layer servono a capire conferma, crowding e timing, non a riscrivere da soli il quadro macro-finanziario.`;
    document.getElementById('position-compare').innerHTML=chips([{k:`COT ${base}`,v:cotb===null?'—':fmt(cotb,0)},{k:`COT ${quote}`,v:cotq===null?'—':fmt(cotq,0)},{k:'1W',v:signed(row?.ret1w,2,'%'),cls:cls(row?.ret1w)},{k:'1M',v:signed(row?.ret1m,2,'%'),cls:cls(row?.ret1m)}]);

    const map=[['Macro',mb.status||'—',mq.status||'—',''],['2Y',y2b===null?'—':fmt(y2b,2)+'%',y2q===null?'—':fmt(y2q,2)+'%',signed(y2diff,0,'bp')],['Pricing 3M',oib===null?'—':fmt(oib,3)+'%',oiq===null?'—':fmt(oiq,3)+'%',signed(oisdiff,0,'bp')],['COT percentile',cotb===null?'—':fmt(cotb,0),cotq===null?'—':fmt(cotq,0),signed(cotdiff,0)]];
    document.getElementById('relative-map').innerHTML=`<div class="map-row"><small>Layer</small><b>${base}</b><b>${quote}</b><b>Diff</b></div>`+map.map(([k,a,b,d])=>`<div class="map-row"><small>${k}</small><b>${a}</b><b>${b}</b><b class="${d?cls(parseFloat(d)):''}">${d}</b></div>`).join('');

    document.getElementById('trade-readiness').innerHTML=`La <strong>tesi relativa</strong> e l'<strong>entrata</strong> restano due cose diverse. Questa pagina organizza la struttura macro-finanziaria; il trigger tecnico viene valutato separatamente.<br><br><span class="status">Nessun livello di ingresso viene inventato.</span>`;
    if(r.type==='align'){
      document.getElementById('confirm-title').textContent=`${r.fav} mantiene il vantaggio relativo`;
      document.getElementById('confirm-copy').textContent='La lettura si rafforza se 2Y e pricing 3M restano orientati sullo stesso lato e il prezzo smette di divergere o continua ad allinearsi senza deterioramento macro.';
      document.getElementById('challenge-title').textContent='Il contrasto relativo si rompe';
      document.getElementById('challenge-copy').textContent='La tesi perde qualità se front-end e pricing iniziano a divergere tra loro o se il quadro macro della valuta favorita si deteriora rispetto all’altra.';
    }else{
      document.getElementById('confirm-title').textContent='I driver iniziano a convergere';
      document.getElementById('confirm-copy').textContent='La coppia diventa più interessante quando 2Y e pricing 3M iniziano a favorire lo stesso lato e il macro non contraddice quella separazione.';
      document.getElementById('challenge-title').textContent='La divisione tra i layer persiste';
      document.getElementById('challenge-copy').textContent='Se rates, pricing e macro continuano a raccontare storie diverse, non c’è motivo di forzare una tesi direzionale sulla coppia.';
    }
    document.documentElement.dataset.coppiaPage='READY';
  }
  function bind(){document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html')}
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d)}
  async function main(){bind();clock();setInterval(clock,30000);try{[state.setup,state.rates,state.ois,state.cot,state.ctx]=await Promise.all([load('PAIR_SETUP_OPERATIONAL_VIEW.json'),load('NATIVE_RATES_DATA.json'),load('OIS_OPERATIONAL_VIEW.json'),load('V250_COT_CHART_DATA.json'),optional('COUNTRY_CTX.json',{})]);if(state.setup?.pair_count!==28||Object.keys(state.setup?.pairs||{}).length!==28)throw new Error('Pair setup coverage invalid');if(!window.GMFQWebsitePrice?.hydrate)throw new Error('Price runtime adapter missing');state.price=priceSeed(state.setup);await window.GMFQWebsitePrice.hydrate(state.price);render()}catch(e){console.warn('[GMFQ coppia]',e);document.getElementById('pair-thesis').textContent='Pair Deep Dive non disponibile';document.getElementById('pair-lead').textContent='Uno dei dati principali non è disponibile. Riprova dopo il prossimo aggiornamento.';document.documentElement.dataset.coppiaPage='FAIL'}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
