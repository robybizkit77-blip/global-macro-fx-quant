(()=>{
'use strict';
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const validNum=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const num=(v,d=2)=>validNum(v)?Number(v).toFixed(d):'—';
const pct=v=>validNum(v)?`${Number(v)>=0?'+':''}${Number(v).toFixed(2)}%`:'—';
function css(){if(document.getElementById('gmfq-risk-operational-style'))return;const s=document.createElement('style');s.id='gmfq-risk-operational-style';s.textContent=`
.rkOp{padding:22px 20px 38px;color:#e8eef8;font-family:Inter,system-ui,sans-serif}.rkHero{border:1px solid rgba(110,158,220,.2);background:linear-gradient(135deg,rgba(18,43,78,.95),rgba(9,17,31,.98));border-radius:18px;padding:20px;margin-bottom:16px}.rkEye{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#91b9ec;font-weight:850}.rkTitle{font-size:25px;font-weight:880;line-height:1.08;margin:7px 0}.rkSub{font-size:13px;color:#9baac0;line-height:1.5;max-width:920px}.rkGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.rkCard{background:#101a2a;border:1px solid rgba(135,160,195,.16);border-radius:15px;padding:16px;min-width:0}.rkCard[data-kind="secondary"]{border-color:rgba(225,175,79,.24);background:linear-gradient(145deg,rgba(31,28,21,.72),rgba(13,22,36,.98))}.rkTop{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.rkName{font-size:16px;font-weight:900}.rkBadge{font-size:9px;letter-spacing:.06em;text-transform:uppercase;border:1px solid rgba(90,186,127,.24);color:#a9e6bf;background:rgba(90,186,127,.06);border-radius:999px;padding:4px 7px;font-weight:850}.rkBadge.secondary{color:#e3c587;border-color:rgba(225,175,79,.25);background:rgba(225,175,79,.06)}.rkValue{font-size:27px;font-weight:900;margin:15px 0 5px}.rkAs{font-size:11px;color:#8497b2}.rkMoves{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px}.rkMove{border:1px solid rgba(130,155,190,.13);border-radius:10px;padding:9px;background:rgba(255,255,255,.015)}.rkMove span{display:block;font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:#8194af;font-weight:800}.rkMove b{display:block;font-size:14px;margin-top:3px}.rkMeta{margin-top:12px;font-size:11px;line-height:1.45;color:#8fa0b8}.rkWarn{margin-top:16px;border:1px solid rgba(225,175,79,.2);border-radius:11px;padding:11px 12px;color:#cbb58c;background:rgba(225,175,79,.04);font-size:11px;line-height:1.45}.rkFoot{margin-top:15px;font-size:10px;color:#7588a3;line-height:1.5}@media(max-width:820px){.rkGrid{grid-template-columns:1fr}.rkOp{padding:15px 12px 28px}.rkHero{padding:16px}.rkTitle{font-size:21px}}
`;document.head.appendChild(s)}
function delta(series,days){
 const ds=Array.isArray(series?.dates)?series.dates:[],vs=Array.isArray(series?.values)?series.values:[];
 if(!ds.length||ds.length!==vs.length)return null;const last=Number(vs.at(-1));if(!Number.isFinite(last))return null;
 if(days===1){if(vs.length<2)return null;const prev=Number(vs.at(-2));return Number.isFinite(prev)&&prev!==0?(last/prev-1)*100:null;}
 const end=new Date(`${ds.at(-1)}T00:00:00Z`);if(Number.isNaN(end.getTime()))return null;const target=end.getTime()-days*86400000;
 let idx=-1;for(let i=ds.length-2;i>=0;i--){const t=new Date(`${ds[i]}T00:00:00Z`).getTime();if(Number.isFinite(t)&&t<=target){idx=i;break;}}
 if(idx<0)return null;const prev=Number(vs[idx]);return Number.isFinite(prev)&&prev!==0?(last/prev-1)*100:null;
}
// Official historical data are not necessarily fresh. Match the Risk 3-day limit.
function seriesStatus(series){
 const ds=series?.dates,vs=series?.values;
 if(!Array.isArray(ds)||!Array.isArray(vs)||!ds.length||ds.length!==vs.length)return {status:'UNVERIFIED',date:null,value:null};
 const date=ds.at(-1),value=vs.at(-1);
 if(series.last_date!==date||!validNum(series.last_value)||!validNum(value)||Number(series.last_value)!==Number(value))
   return {status:'UNVERIFIED',date:null,value:null};
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date))return {status:'UNVERIFIED',date:null,value:null};
 const parsed=new Date(date+'T00:00:00Z');
 if(Number.isNaN(parsed.getTime())||parsed.toISOString().slice(0,10)!==date)
   return {status:'UNVERIFIED',date:null,value:null};
 const now=new Date(),today=Date.UTC(now.getFullYear(),now.getMonth(),now.getDate());
 const age=(today-parsed.getTime())/86400000;
 if(age<0)return {status:'UNVERIFIED',date:null,value:null};
 return {status:age>3?'STALE':'FRESH',date,value:Number(value)};
}
function officialCard(name,series,unit){
 const state=seriesStatus(series),last=state.value,date=state.date;
 const label=state.status==='FRESH'?'Official runtime':state.status==='STALE'?'Dato storico · non corrente':'WITHHELD · dato non verificato';
 const badge=state.status==='FRESH'?'rkBadge':'rkBadge secondary';
 return `<article class="rkCard" data-risk="${name}" data-freshness="${state.status}"><div class="rkTop"><div class="rkName">${name}</div><span class="${badge}">${label}</span></div><div class="rkValue">${num(last)}${state.status==='UNVERIFIED'?'':unit||''}</div><div class="rkAs">as-of ${esc(date||'—')}</div><div class="rkMoves"><div class="rkMove"><span>Δ 1 obs</span><b>${state.status==='UNVERIFIED'?'—':pct(delta(series,1))}</b></div><div class="rkMove"><span>Δ ~1W</span><b>${state.status==='UNVERIFIED'?'—':pct(delta(series,7))}</b></div></div><div class="rkMeta">Source: ${esc(series?.source|| (name==='VIX'?'Cboe official runtime':'U.S. Energy Information Administration'))}</div></article>`;
}
function brentCard(b){return `<article class="rkCard" data-kind="secondary" data-risk="BRENT"><div class="rkTop"><div class="rkName">Brent market proxy</div><span class="rkBadge secondary">Secondary · NON OFFICIAL</span></div><div class="rkValue">$${num(b?.value)}</div><div class="rkAs">as-of ${esc(b?.proxy_as_of||'—')}</div><div class="rkMoves"><div class="rkMove"><span>Δ 1D</span><b>${pct(b?.change_1d_pct)}</b></div><div class="rkMove"><span>Δ 1W</span><b>${pct(b?.change_1w_pct)}</b></div></div><div class="rkMeta">${esc(b?.source||'Secondary Brent futures market proxy')}</div></article>`}
function oldestDate(vix,wti,b){const dates=[vix?.last_date,wti?.last_date,b?.proxy_as_of];return dates.every(x=>/^\d{4}-\d{2}-\d{2}$/.test(x||''))?dates.sort()[0]:'—'}
function html(d,res){
 const vix=d?.risk?.VIX||{},wti=d?.risk?.WTI||{},b=res?.lanes?.['BRENT.market_proxy']||{};
 return `<div class="rkOp" data-gmfq-operational="risk"><div class="rkHero"><div class="rkEye">Cross-asset risk monitor</div><div class="rkTitle">Risk operativo</div><div class="rkSub">Superficie corrente basata sui layer persistiti. VIX e WTI restano dati ufficiali/runtime; Brent è mostrato separatamente come proxy di mercato secondario e non sostituisce la lane ufficiale WITHHELD.</div></div><div class="rkGrid">${officialCard('VIX',vix,'')}${officialCard('WTI',wti,'')}${brentCard(b)}</div><div class="rkWarn"><b>Brent official:</b> WITHHELD. Il proxy BZ=F serve solo per livello/direzione di mercato e non è eleggibile come fonte ufficiale o backtest ufficiale.</div><div class="rkFoot">Oldest required source date: ${esc(oldestDate(vix,wti,b))} · Core / bias / sizing effect: NONE · Nessuna serie viene promossa o trasformata dalla UI.</div></div>`;
}
let cache=null,rendering=false;
async function load(){if(cache)return cache;const [a,b]=await Promise.all([fetch('live_data/sections/D.json',{cache:'no-store'}),fetch('live_data/sections/ESTIMATED_RESIDUAL_GAPS.json',{cache:'no-store'})]);if(!a.ok)throw new Error(`D.json:${a.status}`);if(!b.ok)throw new Error(`ESTIMATED_RESIDUAL_GAPS:${b.status}`);cache=[await a.json(),await b.json()];return cache;}
async function render(){if(rendering)return;rendering=true;css();try{const [d,res]=await load();const el=document.getElementById('risk');if(el&&!el.querySelector('[data-gmfq-operational="risk"]')){el.innerHTML=html(d,res);const v=d?.risk?.VIX||{},w=d?.risk?.WTI||{},b=res?.lanes?.['BRENT.market_proxy']||{};window.GMFQ_RISK_OPERATIONAL={status:'ACTIVE',schema:'GMFQ_RISK_OPERATIONAL_UI_V1',vix_as_of:v.last_date||null,vix_freshness:seriesStatus(v).status,wti_as_of:w.last_date||null,wti_freshness:seriesStatus(w).status,brent_as_of:b.proxy_as_of||null,brent_official_status:'WITHHELD',core_effect:'NONE'};}}catch(err){console.error('risk-operational',err);window.GMFQ_RISK_OPERATIONAL={status:'ERROR',error:String(err),core_effect:'NONE'};}finally{rendering=false}}
const obs=new MutationObserver(()=>{const el=document.getElementById('risk');if(el&&!el.querySelector('[data-gmfq-operational="risk"]'))render()});if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{render();obs.observe(document.body,{childList:true,subtree:true})},{once:true});else{render();obs.observe(document.body,{childList:true,subtree:true})}
})();
