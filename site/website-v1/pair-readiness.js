(()=>{
  'use strict';
  const SOURCE='../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json';
  const code=()=>String(new URLSearchParams(location.search).get('pair')||'EURUSD').replace(/[^A-Z]/g,'').slice(0,6);
  const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const waitReady=()=>new Promise((resolve,reject)=>{
    const started=Date.now();
    const tick=()=>{
      const s=document.documentElement.dataset.coppiaPage;
      if(s==='READY')return resolve();
      if(s==='FAIL')return reject(new Error('Pair Deep Dive base page failed'));
      if(Date.now()-started>15000)return reject(new Error('Pair Deep Dive readiness timeout'));
      setTimeout(tick,80);
    };
    tick();
  });
  const line=(label,text)=>`<span class="compare-chip"><b>${esc(label)}</b> ${esc(text)}</span>`;
  function validateSnapshot(x){
    if(x?.schema!=='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1')throw new Error('snapshot schema invalid');
    if(x?.status!=='CURRENT_CANONICAL_ENGINE')throw new Error('snapshot status not current');
    if(x?.pair_count!==28||Object.keys(x?.pairs||{}).length!==28)throw new Error('snapshot coverage invalid');
    if(x?.price_audit?.status!=='PASS')throw new Error('snapshot price audit not PASS');
    if(x?.thesis_is_not_entry!==true||x?.entry_level_published!==false)throw new Error('contratto tesi/entrata non valido');
  }
  function withheld(el,msg){
    el.innerHTML=`La <strong>tesi relativa</strong> e l'<strong>entrata</strong> restano due cose diverse.<br><br><span class="status">Execution Readiness non pubblicata: ${esc(msg)}. Nessun livello d'ingresso viene inventato dal frontend.</span>`;
    document.documentElement.dataset.executionReadiness='WITHHELD';
  }
  function render(el,snapshot){
    const pair=code(),row=snapshot?.pairs?.[pair],setup=row?.setup;
    if(!setup)return withheld(el,`setup canonico ${pair} non disponibile`);
    const priceAsOf=document.documentElement.getAttribute('data-website-price-asof')||null;
    if(!priceAsOf||snapshot.price_asof!==priceAsOf)return withheld(el,`Price non allineato (${snapshot.price_asof||'—'} vs ${priceAsOf||'—'})`);
    const quality=setup.quality||'NON VALUTABILE';
    const fav=setup.structuralFav||row?.decision_frame?.fav||'—';
    const structural=setup.structural?.relation||row?.decision_frame?.relation||'Struttura relativa non determinata.';
    const details=[['Prezzo',setup.price?.text],['Timing',setup.timing?.text],['Estensione',setup.extension?.text],['COT',setup.cot?.text],['Liquidità',setup.liquidity?.text]].filter(([,v])=>v);
    el.innerHTML=`<strong>${esc(quality)}</strong><br><span class="status">Vantaggio strutturale: ${esc(fav)} · as of ${esc(snapshot.price_asof)}</span><br><br>${esc(structural)}<div class="compare-line">${details.map(([k,v])=>line(k,v)).join('')}</div><br><span class="status">Questa è qualità del setup, non un segnale d'ingresso. Nessun BUY/SELL e nessun livello operativo vengono pubblicati qui.</span>`;
    document.documentElement.dataset.executionReadiness='READY';
    document.documentElement.dataset.executionReadinessContract='CURRENT_CANONICAL_ENGINE';
    document.documentElement.dataset.executionReadinessQuality=quality;
    document.documentElement.dataset.executionReadinessPair=pair;
    document.documentElement.dataset.executionReadinessAsOf=snapshot.price_asof;
  }
  async function main(){
    const el=document.getElementById('trade-readiness');if(!el)return;
    try{
      await waitReady();
      const r=await fetch(SOURCE,{cache:'no-store'});if(!r.ok)throw new Error(`snapshot HTTP ${r.status}`);
      const x=await r.json();validateSnapshot(x);render(el,x);
    }catch(e){console.warn('[GMFQ Pair Readiness]',e);withheld(el,e?.message||'dato non disponibile');}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
