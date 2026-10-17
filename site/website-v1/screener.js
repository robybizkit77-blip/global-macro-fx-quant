(()=>{
  'use strict';
  const R='../../live_data/sections/',q=s=>document.querySelector(s),esc=s=>String(s??'—').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  let d,setup;
  const load=f=>fetch(R+f,{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject(new Error(`${f}: ${r.status}`)));
  function validateSetup(x){
    if(x?.schema!=='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1')throw new Error('Pair setup schema invalid');
    if(x?.status!=='CURRENT_CANONICAL_ENGINE')throw new Error('Pair setup status not current');
    if(x?.pair_count!==28||Object.keys(x?.pairs||{}).length!==28)throw new Error('Pair setup coverage invalid');
    if(x?.thesis_is_not_entry!==true||x?.entry_level_published!==false)throw new Error('Pair setup thesis/entry contract invalid');
    if(x?.price_audit?.status!=='PASS')throw new Error('Pair setup price audit not PASS');
  }
  function render(){
    const qual=q('#quality').value,fav=q('#fav').value;
    const rows=Object.entries(setup.pairs).map(([pair,x])=>({pair,x,s:x.setup||{}})).filter(r=>(qual==='ALL'||r.s.quality===qual)&&(fav==='ALL'||r.s.structuralFav===fav));
    q('#rows').innerHTML=rows.map(r=>`<div class="screen-row"><b>${esc(r.x.canonical_pair||r.pair)}</b><span>${esc(r.s.quality)}</span><p>${esc(r.s.structural?.relation||r.x.decision_frame?.relation||'Struttura non disponibile.')}</p><a href="coppia.html?pair=${esc(r.pair)}">Deep Dive →</a></div>`).join('')||'<p>Nessun setup corrisponde ai filtri.</p>';
    q('#asof').textContent=`${rows.length}/28 pair · setup + prezzo ${setup.price_asof||'—'}`;
  }
  Promise.all([load('D.json'),load('PAIR_SETUP_OPERATIONAL_VIEW.json')]).then(async([a,b])=>{
    d=a;setup=b;validateSetup(b);
    if(!window.GMFQWebsitePrice?.hydrate)throw new Error('Canonical Price runtime adapter missing');
    await window.GMFQWebsitePrice.hydrate(d);
    if(!d?.price_asof||b.price_asof!==d.price_asof)throw new Error(`Pair setup / Price mismatch: ${b.price_asof||'—'} vs ${d?.price_asof||'—'}`);
    for(const v of [...new Set(Object.values(b.pairs).map(x=>x.setup?.quality).filter(Boolean))])q('#quality').insertAdjacentHTML('beforeend',`<option>${esc(v)}</option>`);
    for(const v of [...new Set(Object.values(b.pairs).map(x=>x.setup?.structuralFav).filter(Boolean))])q('#fav').insertAdjacentHTML('beforeend',`<option>${esc(v)}</option>`);
    q('#quality').onchange=q('#fav').onchange=render;
    render();
    document.documentElement.dataset.screenerPage='READY';
    document.documentElement.dataset.screenerContract='CURRENT_CANONICAL_ENGINE';
    document.documentElement.dataset.screenerPriceAsOf=b.price_asof;
  }).catch(e=>{
    console.warn('[GMFQ screener]',e);
    q('#rows').textContent='Screener WITHHELD: setup canonico o allineamento Price non valido.';
    q('#asof').textContent='WITHHELD';
    document.documentElement.dataset.screenerPage='WITHHELD';
  });
})();
