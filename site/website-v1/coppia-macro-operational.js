(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  async function optional(f,fallback){try{return await load(f)}catch(e){console.warn('[GMFQ pair macro optional]',f,e);return fallback}}
  function pair(){return (new URLSearchParams(location.search).get('pair')||'EURUSD').replace(/[^A-Z]/g,'').slice(0,6);}
  function waitReady(){return new Promise((resolve,reject)=>{const t0=Date.now();const tick=()=>{const s=document.documentElement.dataset.coppiaPage;if(s==='READY')return resolve();if(s==='FAIL')return reject(new Error('Pair renderer failed'));if(Date.now()-t0>10000)return reject(new Error('Pair renderer timeout'));setTimeout(tick,50);};tick();});}
  function humanStatus(v){const s=String(v||'').toUpperCase();if(s.includes('PARTIAL'))return'Parziale';if(s.includes('ACTIVE')||s.includes('CURRENT')||s.includes('READY'))return'Aggiornato';return s?'Disponibile':'Non disponibile';}
  function humanDir(v){const s=String(v||'').toUpperCase();if(s==='SALE')return'Sale';if(s==='SCENDE')return'Scende';if(s==='STABILE')return'Stabile';return s?s.replaceAll('_',' ').toLowerCase().replace(/^./,m=>m.toUpperCase()):'—';}
  function humanAccel(v){const s=String(v||'').toUpperCase();if(s==='ACCELERA')return'Accelera';if(s==='RALLENTA')return'Rallenta';if(s==='STABILE')return'Stabile';return s?s.replaceAll('_',' ').toLowerCase().replace(/^./,m=>m.toUpperCase()):'—';}
  function stateLabel(thermo,ccy){return humanStatus(thermo?.currencies?.[ccy]?.status);}
  function dyn(thermo,ccy,key){const x=thermo?.currencies?.[ccy]?.[key]||{};return {label:x.label||key,dir:humanDir(x.direction),acc:humanAccel(x.acceleration),asOf:x.as_of||'—'};}
  function seriesRows(series){if(Array.isArray(series))return series;if(series&&typeof series==='object')return Object.entries(series).flatMap(([ccy,a])=>Array.isArray(a)?a.map(r=>({...r,ccy:r?.ccy||ccy})):[]);return [];}
  function rowDate(r){const d=String(r?.last_date||'');if(/^\d{4}-\d{2}(?:-\d{2})?$/.test(d))return d;const a=Array.isArray(r?.dates)?r.dates:[];return a.length?String(a.at(-1)||''):'';}
  function growth(series,ccy){const r=seriesRows(series).filter(x=>x?.ccy===ccy&&String(x?.category||'').toLowerCase()==='crescita'&&rowDate(x)).sort((a,b)=>rowDate(b).localeCompare(rowDate(a)))[0]||null;const v=num(r?.last_value),unit=String(r?.unit||'').trim(),value=v===null?'—':`${v.toLocaleString('it-IT',{maximumFractionDigits:2})}${unit==='%'?'%':unit?` ${unit}`:''}`;return {label:r?.label||'Crescita',value,date:rowDate(r)||'—'};}
  function chip(k,v){return `<span class="compare-chip">${esc(k)}<b>${esc(v)}</b></span>`;}
  async function main(){
    await waitReady();
    const [series,thermo,ctx]=await Promise.all([load('MACRO_SERIES.json'),load('MACRO_THERMOMETER_DATA.json'),optional('COUNTRY_CTX.json',{})]);
    if(!seriesRows(series).length)throw new Error('Macro series unavailable');
    if(thermo?.schema_version!=='GMFQ_MACRO_HEATMAP_V1'||thermo?.status!=='ACTIVE')throw new Error('Macro thermometer unavailable');
    const p=pair(),base=p.slice(0,3),quote=p.slice(3,6);
    const bs=stateLabel(thermo,base),qs=stateLabel(thermo,quote),bg=growth(series,base),qg=growth(series,quote);
    const bl=dyn(thermo,base,'labour'),bi=dyn(thermo,base,'inflation'),ql=dyn(thermo,quote,'labour'),qi=dyn(thermo,quote,'inflation');
    const title=document.getElementById('macro-title'),copy=document.getElementById('macro-copy'),compare=document.getElementById('macro-compare');
    if(title)title.textContent=`${base}: ${bs} · ${quote}: ${qs}`;
    if(copy)copy.textContent=`${ctx?.[base]?.summary_it||'Sintesi narrativa base non disponibile.'} ${ctx?.[quote]?.summary_it||'Sintesi narrativa quote non disponibile.'}`;
    if(compare)compare.innerHTML=[
      chip(`${base} crescita`,`${bg.label} ${bg.value} · ${bg.date}`),
      chip(`${base} lavoro`,`${bl.dir} · ${bl.acc} · ${bl.asOf}`),
      chip(`${base} infl.`,`${bi.dir} · ${bi.acc} · ${bi.asOf}`),
      chip(`${quote} crescita`,`${qg.label} ${qg.value} · ${qg.date}`),
      chip(`${quote} lavoro`,`${ql.dir} · ${ql.acc} · ${ql.asOf}`),
      chip(`${quote} infl.`,`${qi.dir} · ${qi.acc} · ${qi.asOf}`)
    ].join('');
    const map=document.getElementById('relative-map');
    if(map){const rows=[...map.querySelectorAll('.map-row')],macroRow=rows.find(r=>r.querySelector('small')?.textContent?.trim()==='Macro');if(macroRow)macroRow.innerHTML=`<small>Macro</small><b>${esc(bs)}</b><b>${esc(qs)}</b><b>—</b>`;}
    document.documentElement.dataset.pairMacro='MACRO_SERIES_THERMOMETER';
    document.documentElement.dataset.pairMacroThermometer='READY';
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>main().catch(e=>{console.warn('[GMFQ pair macro overlay]',e);document.documentElement.dataset.pairMacro='PARTIAL';}),{once:true});else main().catch(e=>{console.warn('[GMFQ pair macro overlay]',e);document.documentElement.dataset.pairMacro='PARTIAL';});
})();