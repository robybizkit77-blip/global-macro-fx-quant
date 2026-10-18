(()=>{
  'use strict';
  const R='../../live_data/sections/',q=s=>document.querySelector(s),esc=s=>String(s??'—').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  const QUALITY_RANK={'PULITO':5,'CON RISCHI':4,'DA CONFERMARE':3,'DA MONITORARE':2,'NON VALUTABILE':0};
  let setup;
  const load=f=>fetch(R+f,{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject(new Error(`${f}: ${r.status}`)));
  function validateSetup(x){
    if(x?.schema!=='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1')throw new Error('Pair setup schema invalid');
    if(x?.status!=='CURRENT_CANONICAL_ENGINE')throw new Error('Pair setup status not current');
    if(x?.pair_count!==28||Object.keys(x?.pairs||{}).length!==28)throw new Error('Pair setup coverage invalid');
    if(x?.thesis_is_not_entry!==true||x?.entry_level_published!==false)throw new Error('Pair setup thesis/entry contract invalid');
    if(x?.price_audit?.status!=='PASS')throw new Error('Pair setup price audit not PASS');
    if(x?.price_audit?.as_of!==x?.price_asof || x?.price_audit?.history_asof!==x?.price_asof)throw new Error('Price/history dates inconsistent');
    const time=Date.parse(String(x.price_asof)+'T00:00:00Z');
    const now=new Date(),today=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());
    const age=Math.floor((today-time)/86400000);
    if(!Number.isFinite(age)||age<0||age>5)throw new Error('Pair setup data stale or future-dated');
  }
  function render(){
    const qual=q('#quality').value,fav=q('#fav').value;
    const rows=Object.entries(setup.pairs).map(([pair,x])=>({pair,x,s:x.setup||{}})).filter(r=>(qual==='ALL'||r.s.quality===qual)&&(fav==='ALL'||r.s.structuralFav===fav)).sort((a,b)=>(QUALITY_RANK[b.s.quality]||0)-(QUALITY_RANK[a.s.quality]||0)||(a.x.canonical_pair||a.pair).localeCompare(b.x.canonical_pair||b.pair));
    q('#rows').innerHTML=rows.map(r=>`<div class="screen-row"><b>${esc(r.x.canonical_pair||r.pair)}</b><span><strong>${esc(r.s.quality)}</strong><small style="display:block;margin-top:4px">favorisce ${esc(r.s.structuralFav||'—')}</small></span><p>${esc(r.s.structural?.relation||r.x.decision_frame?.relation||'Struttura non disponibile.')}</p><a href="coppia.html?pair=${esc(r.pair)}">Deep Dive →</a></div>`).join('')||'<p>Nessun setup corrisponde ai filtri.</p>';
    const distribution=Object.entries(QUALITY_RANK).filter(([name])=>name!=='NON VALUTABILE').map(([name])=>[name,Object.values(setup.pairs).filter(x=>x.setup?.quality===name).length]).filter(x=>x[1]>0).map(([name,count])=>name+': '+count).join(' · ');
    q('#asof').textContent=`${rows.length}/28 pair · prezzi ${setup.price_asof||'—'} · ${distribution}`;
  }
  load('PAIR_SETUP_OPERATIONAL_VIEW.json').then(b=>{
    setup=b;validateSetup(b);
    for(const v of [...new Set(Object.values(b.pairs).map(x=>x.setup?.quality).filter(Boolean))])q('#quality').insertAdjacentHTML('beforeend',`<option>${esc(v)}</option>`);
    for(const v of [...new Set(Object.values(b.pairs).map(x=>x.setup?.structuralFav).filter(Boolean))].sort())q('#fav').insertAdjacentHTML('beforeend',`<option>${esc(v)}</option>`);
    q('#quality').onchange=q('#fav').onchange=render;
    render();
    document.documentElement.dataset.screenerPage='READY';
    document.documentElement.dataset.screenerPriceAsOf=b.price_asof||'—';
  }).catch(e=>{
    console.warn('[GMFQ screener]',e);
    q('#rows').textContent='Screener non disponibile: il quadro delle 28 coppie non è aggiornato.';
    q('#asof').textContent='Non disponibile';
    document.documentElement.dataset.screenerPage='WITHHELD';
  });
})();
