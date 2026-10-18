(()=>{
'use strict';
const SCHEMA='GMFQ_CBDESK_OPERATIONAL_UI_V1';
const SRC='live_data/sections/OIS_OPERATIONAL_VIEW.json';
const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const state={status:'INIT',data:null,error:null,selected:null};
window.GMFQ_CBDESK_OPERATIONAL=state;

function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function num(v){return v===null||v===undefined||v===''?null:Number.isFinite(Number(v))?Number(v):null;}
function fmtRate(v){const n=num(v);return n===null?'—':n.toFixed(3).replace(/0+$/,'').replace(/\.$/,'')+'%';}
function fmtBp(v){const n=num(v);return n===null?'—':`${n>0?'+':''}${n.toFixed(1)} bp`;}
function selected(){return document.querySelector('#v234CurrencyCards .v234CurrencyCard.active')?.dataset?.c||String(document.getElementById('v234CountryName')?.textContent||'').match(/\b(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)\b/)?.[1]||null;}
function cbData(c){return window.__GMFQ_DATA?.NATIVE_CB_DATA?.[c]||null;}
function oisData(c){return state.data?.currencies?.[c]||null;}
function twoY(c){try{const s=window.rate2YSeries?.(c);return {last:s?.values?.at?.(-1)??null,date:s?.dates?.at?.(-1)??null};}catch(e){return {last:null,date:null};}}
function validate(d){
 if(!d||d.schema!=='GMFQ_OIS_OPERATIONAL_VIEW_V1'||!['GREEN_8_OF_8','PARTIAL_WITHHELD'].includes(d.status)||d?.summary?.g8_total!==8||d.summary.operational_green+d.summary.operational_withheld!==8)throw new Error('OIS_OPERATIONAL_COVERAGE_INVALID');
 for(const c of CCYS){const r=d?.currencies?.[c];if(!r||!['GREEN_OFFICIAL','GREEN_ESTIMATED','WITHHELD'].includes(r.operational_status))throw new Error('OIS_OPERATIONAL_INVALID_'+c);}
 return d;
}
function quality(r,c){
 if(r?.operational_status==='WITHHELD')return {label:'OIS WITHHELD · curva non disponibile',cls:'warn',kind:'WITHHELD'};
 if(c==='NZD'&&r?.market_direction_proxy)return {label:'Pricing operativo · NON OIS proxy',cls:'warn',kind:'NON_OIS'};
 if(r?.operational_status==='GREEN_OFFICIAL')return {label:'Pricing operativo · OFFICIAL',cls:'pos',kind:'OFFICIAL'};
 return {label:'Pricing operativo · ESTIMATED',cls:'warn',kind:'ESTIMATED'};
}
function pathState(r,c){
 if(r?.operational_status==='WITHHELD')return {title:'Curva OIS non disponibile',detail:'Dati OIS scaduti o incompleti: nessun percorso di politica monetaria certificabile. Il proxy ASX, se presente, resta separato e non sostituisce la curva OIS.'};
 if(c==='NZD'&&r?.market_direction_proxy){
   const p=r.market_direction_proxy;const vals=['3m','6m','12m'].map(h=>num(p?.horizons?.[h]?.change_1w_bp)).filter(v=>v!==null);
   const avg=vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:null;
   return {title:avg===null?'Proxy direzionale NZD disponibile':avg>1?'Proxy direzionale: tassi di mercato in salita':avg<-1?'Proxy direzionale: tassi di mercato in discesa':'Proxy direzionale: tassi di mercato quasi stabili',detail:`ASX Bank Bill · NON OIS · 1W 3M ${fmtBp(p?.horizons?.['3m']?.change_1w_bp)}, 6M ${fmtBp(p?.horizons?.['6m']?.change_1w_bp)}, 12M ${fmtBp(p?.horizons?.['12m']?.change_1w_bp)} · as-of ${esc(p.as_of||r.as_of||'—')}. Non genera policy delta.`};
 }
 const ds=['3m','6m','12m'].map(h=>num(r?.horizons?.[h]?.policy_delta_bp)).filter(v=>v!==null);
 const avg=ds.length?ds.reduce((a,b)=>a+b,0)/ds.length:null;
 const title=avg===null?'Percorso policy disponibile':avg>5?'Il mercato prezza un percorso sopra il tasso attuale':avg<-5?'Il mercato prezza un percorso sotto il tasso attuale':'Il mercato prezza un percorso vicino al tasso attuale';
 const tag=r?.operational_status==='GREEN_OFFICIAL'?'OFFICIAL':'ESTIMATED';
 const detail=`${tag} · 3M ${fmtRate(r?.horizons?.['3m']?.rate)} (${fmtBp(r?.horizons?.['3m']?.policy_delta_bp)}), 6M ${fmtRate(r?.horizons?.['6m']?.rate)} (${fmtBp(r?.horizons?.['6m']?.policy_delta_bp)}), 12M ${fmtRate(r?.horizons?.['12m']?.rate)} (${fmtBp(r?.horizons?.['12m']?.policy_delta_bp)}) · as-of ${esc(r?.as_of||'—')}.`;
 return {title,detail};
}
function patchChangeMap(q,p){
 const map=document.getElementById('v234ChangeMap');if(!map)return;
 const card=[...map.querySelectorAll('div')].find(x=>/LIMITE DEL DATO|OIS non confrontabile|curva OIS\/forward/i.test(x.innerText||'')&&x.querySelector('b')&&x.querySelector('small'));
 if(!card)return;
 const b=card.querySelector('b');const sm=card.querySelector('small');
 if(b)b.textContent=q.label;
 if(sm)sm.textContent=p.detail;
 card.setAttribute('data-gmfq-cb-pricing-patched','true');
}
function patchPolicyRead(p){
 const el=document.getElementById('v234PolicyRead');if(!el)return;
 let t=String(el.textContent||'');
 t=t.replace(/Nessuna curva OIS\/forward omogenea disponibile\.[\s\S]*?è soltanto una lettura separata del repricing\./g,p.detail+' Il 2Y resta una conferma separata, non sostituisce il pricing policy.');
 el.textContent=t;
}
function patchPricingGrid(c,r,p,q){
 const grid=document.getElementById('v234PricingGrid');if(!grid)return;
 const y=twoY(c);
 const mode=c==='NZD'&&r?.market_direction_proxy?'NON OIS · solo direzione':(r.operational_status==='GREEN_OFFICIAL'?'OFFICIAL':'ESTIMATED · informativo');
 grid.innerHTML=`<div class="v234PricingCard wide" data-gmfq-cb-pricing="market"><span>COSA PREZZA IL MERCATO</span><b>${esc(p.title)}</b><small>${esc(p.detail)}</small></div><div class="v234PricingCard" data-gmfq-cb-pricing="2y"><span>CONFERMA FRONT-END</span><b>2Y ${fmtRate(y.last)}</b><small>As-of ${esc(y.date||'—')} · conferma separata del repricing, non sostituisce OIS/policy pricing.</small></div><div class="v234PricingCard" data-gmfq-cb-pricing="quality"><span>QUALITÀ / METODO</span><b>${esc(q.label)}</b><small>${esc(mode)} · conf. ${esc(r.confidence||'—')} · ${esc(r.source||'fonte non indicata')}</small></div>`;
}
function patch(c){
 const root=document.getElementById('cbdesk');const r=oisData(c);const d=cbData(c);if(!root||!r||!d)throw new Error('CB_BINDING_MISSING_'+c);
 const q=quality(r,c),p=pathState(r,c);
 const country=document.getElementById('v234CountryName');if(!country)throw new Error('CB_OWNER_ANCHOR_MISSING');
 country.setAttribute('data-gmfq-operational','cbdesk');country.setAttribute('data-owner',SCHEMA);
 const pq=document.getElementById('v234PricingQuality');if(pq){pq.textContent=q.label;pq.className='v234PricingQuality '+q.cls;pq.dataset.pricingKind=q.kind;}
 const market=document.getElementById('v234Market');if(market)market.textContent=p.title;
 const why=document.getElementById('v234MarketWhy');if(why)why.textContent=p.detail;
 patchPolicyRead(p);patchPricingGrid(c,r,p,q);patchChangeMap(q,p);
 root.dataset.gmfqCbPricingAsOf=r.as_of||'';root.dataset.gmfqCbPricingKind=q.kind;
 state.selected=c;
 return {c,q,p,r};
}
function audit(){
 const root=document.getElementById('cbdesk');const cards=[...document.querySelectorAll('#v234CurrencyCards .v234CurrencyCard')].map(x=>x.dataset.c).filter(Boolean);const unique=[...new Set(cards)];const c=selected();const r=oisData(c);const q=r?quality(r,c):null;const policy=typeof window.corePolicyIntegrity==='function'?window.corePolicyIntegrity():null;const owner=root?.querySelectorAll('#v234CountryName[data-gmfq-operational="cbdesk"]').length||0;const text=String(root?.innerText||'');const issues=[];
 if(owner!==1)issues.push('OWNER_COUNT_'+owner);
 if(cards.length!==8||unique.length!==8||CCYS.some(x=>!unique.includes(x)))issues.push('G8_SELECTOR');
 if(!c||!CCYS.includes(c)||!String(document.getElementById('v234CountryName')?.textContent||'').includes(c))issues.push('SELECTION_SYNC');
 if(policy?.ok!==true)issues.push('CORE_POLICY_INTEGRITY');
 if(!state.data||state.data?.summary?.g8_total!==8||state.data.summary.operational_green+state.data.summary.operational_withheld!==8)issues.push('OIS_OPERATIONAL_COVERAGE');
 if(!r||!q)issues.push('SELECTED_PRICING');
 if(/Pricing non comparabile|OIS non confrontabile|Nessuna curva OIS\/forward omogenea disponibile/.test(text))issues.push('STALE_PRICING_NARRATIVE');
 if(document.querySelectorAll('#v234PricingGrid [data-gmfq-cb-pricing]').length!==3)issues.push('PRICING_GRID_BINDING');
 return {schema:SCHEMA,status:issues.length?'FAIL':'ACTIVE',core_effect:'NONE',owner_type:'HYBRID_CANONICAL_PRICING_ADAPTER',owner_count:owner,currencies:unique,coverage:unique.length,selected_currency:c,pricing_kind:q?.kind||null,pricing_as_of:r?.as_of||null,ois_summary:state.data?.summary||null,policy_integrity:policy,canonical_sources:['NATIVE_CB_DATA(runtime)','corePolicyIntegrity(runtime)','OIS_OPERATIONAL_VIEW.json','rate2YSeries(runtime)'],issues};
}
function sync(){const c=selected();if(!c)throw new Error('CB_SELECTED_CURRENCY_MISSING');patch(c);const a=audit();Object.assign(state,a,{data:state.data,error:null});if(a.status!=='ACTIVE')throw new Error('CBDESK_OPERATIONAL_'+a.issues.join('_'));return state;}
function wrap(name){const old=window[name];if(typeof old!=='function'||old.__gmfqCbOperationalWrapped)return;const wrapped=function(){const out=old.apply(this,arguments);setTimeout(()=>{try{if(state.data)sync();}catch(e){state.status='FAIL';state.error=String(e?.message||e);}},0);return out;};wrapped.__gmfqCbOperationalWrapped=true;window[name]=wrapped;}
async function boot(){
 try{
   let tries=0;while(tries++<240){if(window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true&&typeof window.corePolicyIntegrity==='function'&&typeof window.renderNativeCbDesk==='function'&&typeof window.selectNativeCb==='function')break;await new Promise(r=>setTimeout(r,250));}
   if(tries>=240)throw new Error('CBDESK_OPERATIONAL_BOOT_TIMEOUT');
   const res=await fetch(SRC,{cache:'no-store'});if(!res.ok)throw new Error('OIS_HTTP_'+res.status);state.data=validate(await res.json());state.status='LOADED';
   wrap('renderNativeCbDesk');wrap('selectNativeCb');
   try{window.renderNativeCbDesk();}catch(e){}
   sync();
 }catch(e){state.status='FAIL';state.error=String(e?.message||e);}
}
window.gmfqCbDeskOperationalAudit=audit;window.gmfqSyncCbDeskOperational=sync;
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
