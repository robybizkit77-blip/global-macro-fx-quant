(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  function pair(){return (new URLSearchParams(location.search).get('pair')||'EURUSD').replace(/[^A-Z]/g,'').slice(0,6);}
  function waitReady(){return new Promise((resolve,reject)=>{const t0=Date.now();const tick=()=>{const s=document.documentElement.dataset.coppiaPage;if(s==='READY')return resolve();if(s==='FAIL')return reject(new Error('Pair renderer failed'));if(Date.now()-t0>10000)return reject(new Error('Pair renderer timeout'));setTimeout(tick,50);};tick();});}
  function stateLabel(ctx,thermo,ccy){const raw=String(ctx?.[ccy]?.status||thermo?.currencies?.[ccy]?.status||'OPERATIVO').toUpperCase();if(raw.includes('PARTIAL'))return 'Parziale';if(raw.includes('ACTIVE'))return 'Attivo';return raw.replaceAll('_',' ');}
  function dyn(thermo,ccy,key){const x=thermo?.currencies?.[ccy]?.[key]||{};const dir=String(x.direction||'—').replaceAll('_',' ');const acc=String(x.acceleration||'—').replaceAll('_',' ');return {label:x.label||key,dir,acc,asOf:x.as_of||'—'};}
  function chip(k,v){return `<span class="compare-chip">${esc(k)}<b>${esc(v)}</b></span>`;}
  async function main(){
    await waitReady();
    const [ctx,thermo]=await Promise.all([load('COUNTRY_CTX.json'),load('MACRO_THERMOMETER_DATA.json')]);
    if(thermo?.schema_version!=='GMFQ_MACRO_HEATMAP_V1'||thermo?.status!=='ACTIVE')throw new Error('Macro thermometer contract invalid');
    const p=pair(),base=p.slice(0,3),quote=p.slice(3,6);
    const bs=stateLabel(ctx,thermo,base),qs=stateLabel(ctx,thermo,quote);
    const bl=dyn(thermo,base,'labour'),bi=dyn(thermo,base,'inflation'),ql=dyn(thermo,quote,'labour'),qi=dyn(thermo,quote,'inflation');
    const title=document.getElementById('macro-title'),copy=document.getElementById('macro-copy'),compare=document.getElementById('macro-compare');
    if(title)title.textContent=`${base}: ${bs} · ${quote}: ${qs}`;
    if(copy)copy.textContent=`${ctx?.[base]?.summary_it||'Quadro macro base non disponibile.'} ${ctx?.[quote]?.summary_it||'Quadro macro quote non disponibile.'}`;
    if(compare)compare.innerHTML=[chip(base,bs),chip(`${base} lavoro`,`${bl.dir} · ${bl.acc}`),chip(`${base} infl.`,`${bi.dir} · ${bi.acc}`),chip(quote,qs),chip(`${quote} lavoro`,`${ql.dir} · ${ql.acc}`),chip(`${quote} infl.`,`${qi.dir} · ${qi.acc}`)].join('');
    const map=document.getElementById('relative-map');
    if(map){const first=map.querySelector('.map-row:not(:first-child)');if(first){first.innerHTML=`<small>Macro operativo</small><b>${esc(bs)}</b><b>${esc(qs)}</b><b>—</b>`;}}
    document.documentElement.dataset.pairMacro='OPERATIONAL_CONTEXT';
    document.documentElement.dataset.pairMacroThermometer='READY';
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>main().catch(e=>{console.warn('[GMFQ pair macro overlay]',e);document.documentElement.dataset.pairMacro='WITHHELD';}),{once:true});else main().catch(e=>{console.warn('[GMFQ pair macro overlay]',e);document.documentElement.dataset.pairMacro='WITHHELD';});
})();
