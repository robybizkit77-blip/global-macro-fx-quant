(()=>{
'use strict';
const SCHEMA='GMFQ_CONTROL_ROOM_SNAPSHOT_V1';
const PAIRS=['EUR/USD','GBP/USD','USD/JPY'];
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function latestPriceRow(){
  if(typeof D==='undefined'||!Array.isArray(D.prices)||!D.prices.length)return null;
  return [...D.prices].filter(x=>x&&x.Date).sort((a,b)=>String(a.Date).localeCompare(String(b.Date))).at(-1)||null;
}
function crossPrice(pair,row){
  if(!row)return null;
  const [a,b]=pair.split('/');
  const ra=Number(row[a]),rb=Number(row[b]);
  if(!(ra>0)||!(rb>0))return null;
  return rb/ra;
}
function fmtPair(pair,v){return Number.isFinite(v)?v.toFixed(pair.includes('JPY')?3:5):null;}
function rate2y(){
  try{
    const s=window.rate2YSeries?.('USD');
    const v=Number(s?.values?.at?.(-1));
    return Number.isFinite(v)?{value:v.toFixed(3)+'%',asof:s?.dates?.at?.(-1)||'—'}:null;
  }catch(e){return null;}
}
function parseNumber(text){
  const nums=String(text||'').match(/[-+]?\d{1,4}(?:[.,]\d+)?%?/g)||[];
  for(const raw of nums){
    const n=Number(raw.replace('%','').replace(',','.'));
    if(Number.isFinite(n))return raw;
  }
  return null;
}
function legacyMetric(aliases){
  const legacy=document.querySelector('[data-cr-legacy-host]');
  if(!legacy)return null;
  const nodes=[...legacy.querySelectorAll('*')];
  for(const el of nodes){
    const own=(el.children.length===0?String(el.textContent||'').trim():'');
    if(!own)continue;
    if(!aliases.some(a=>own.toLowerCase().includes(a.toLowerCase())))continue;
    const box=el.closest('.gmfqExecCard,.ov387Card,.card,[class*="Card"],[class*="panel"],[class*="Panel"]');
    if(!box)continue;
    const txt=String(box.innerText||box.textContent||'').replace(/\s+/g,' ').trim();
    const stripped=txt.replace(own,' ');
    const value=parseNumber(stripped);
    if(value)return {value,text:txt.slice(0,105)};
  }
  return null;
}
function tile(k,value,sub,status='LIVE'){
  const withheld=status==='WITHHELD';
  return `<div class="crTile" data-snapshot="${esc(k)}" data-status="${status}"><div class="crTileK">${esc(k)}</div><div class="crTileV${withheld?' neu':''}">${esc(value)}</div><div class="crTileS">${esc(sub)}</div></div>`;
}
function build(){
  const row=latestPriceRow();
  const pair=(p)=>{const v=crossPrice(p,row);return Number.isFinite(v)?tile(p.replace('/',''),fmtPair(p,v),`ECB fixing · ${row?.Date||'—'}`):tile(p.replace('/',''),'WITHHELD','Prezzo canonico non disponibile','WITHHELD');};
  const y2=rate2y();
  const dxy=legacyMetric(['dxy','dollar index']);
  const y10=legacyMetric(['us 10y','10y treasury','treasury 10y','10y yield']);
  const gold=legacyMetric(['gold','xau']);
  const wti=legacyMetric(['wti','oil']);
  return [
    dxy?tile('DXY',dxy.value,dxy.text):tile('DXY','WITHHELD','Fonte canonica non esposta nella home','WITHHELD'),
    pair('EUR/USD'),pair('GBP/USD'),pair('USD/JPY'),
    y2?tile('US 2Y',y2.value,`Canonical 2Y · ${y2.asof}`):tile('US 2Y','WITHHELD','2Y non disponibile','WITHHELD'),
    y10?tile('US 10Y',y10.value,y10.text):tile('US 10Y','WITHHELD','Fonte canonica non esposta nella home','WITHHELD'),
    gold?tile('GOLD',gold.value,gold.text):tile('GOLD','WITHHELD','Fonte canonica non esposta nella home','WITHHELD'),
    wti?tile('WTI',wti.value,wti.text):tile('WTI','WITHHELD','Fonte canonica non esposta nella home','WITHHELD')
  ].join('');
}
function sync(){
  const strip=document.querySelector('#gmfq-control-room-home-v1 .crStrip');
  if(!strip)throw new Error('CONTROL_ROOM_SNAPSHOT_STRIP_MISSING');
  strip.innerHTML=build();
  const live=[...strip.querySelectorAll('.crTile')].filter(x=>x.dataset.status!=='WITHHELD').length;
  window.GMFQ_CONTROL_ROOM_SNAPSHOT={schema:SCHEMA,status:'ACTIVE',scope:'PRESENTATION_ONLY',core_effect:'NONE',tiles:8,live,withheld:8-live,sources:['D.prices(runtime)','rate2YSeries(runtime)','legacy validated presentation fallback']};
  return window.GMFQ_CONTROL_ROOM_SNAPSHOT;
}
function boot(){let tries=0;const tick=()=>{tries++;if(window.GMFQ_CONTROL_ROOM_HOME?.status==='ACTIVE'&&document.querySelector('#gmfq-control-room-home-v1 .crStrip')){try{sync();}catch(e){window.GMFQ_CONTROL_ROOM_SNAPSHOT={schema:SCHEMA,status:'ERROR',error:String(e),core_effect:'NONE'};}return;}if(tries<240)setTimeout(tick,250);else window.GMFQ_CONTROL_ROOM_SNAPSHOT={schema:SCHEMA,status:'WITHHELD',reason:'BOOT_TIMEOUT',core_effect:'NONE'};};tick();}
window.gmfqControlRoomSnapshotSync=sync;
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();