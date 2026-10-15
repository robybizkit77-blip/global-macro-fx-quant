(()=>{
'use strict';
const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const H=['policy','3m','6m','12m'];
const SRC='live_data/sections/OIS_OPERATIONAL_VIEW.json';
const state={status:'INIT',data:null,error:null,loaded_at:null};
window.GMFQ_OIS_OPERATIONAL_UI=state;
function fmtRate(v){return Number.isFinite(Number(v))?Number(v).toFixed(3).replace(/0+$/,'').replace(/\.$/,'')+'%':'—';}
function fmtBp(v){if(!Number.isFinite(Number(v)))return '—';const n=Number(v);return `${n>0?'+':''}${n.toFixed(1)} bp`;}
function clsBp(v){if(!Number.isFinite(Number(v)))return 'neu';return Number(v)>0?'up':Number(v)<0?'down':'neu';}
function rowRate(r,h){if(h==='policy')return r.policy_rate;return r?.horizons?.[h]?.rate;}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function validate(d){
 if(!d||d.schema!=='GMFQ_OIS_OPERATIONAL_VIEW_V1')throw new Error('schema OIS operational inatteso');
 if(d.status!=='GREEN_8_OF_8')throw new Error('OIS operational non GREEN_8_OF_8');
 if(d?.summary?.operational_green!==8)throw new Error('copertura OIS operativa diversa da 8/8');
 for(const c of CCYS){const r=d?.currencies?.[c];if(!r)throw new Error('valuta OIS mancante: '+c);if(!['GREEN_OFFICIAL','GREEN_ESTIMATED'].includes(r.operational_status))throw new Error('status OIS invalido '+c);}
 return d;
}
function ensureHost(){
 let host=document.getElementById('v401OisBlock');
 if(host)return host;
 const desk=document.getElementById('ratesdesk');
 if(!desk)return null;
 host=document.createElement('div');
 host.id='v401OisBlock';
 host.dataset.owner='GMFQ_OIS_OPERATIONAL_UI_V1';
 host.className='gmfqOisOperationalMount';
 const anchor=document.getElementById('v233RatesGrid')||document.getElementById('v233RatesRead')||document.getElementById('v233CurrencyCards');
 if(anchor&&desk.contains(anchor)){
   const shell=anchor.closest('.v272Truth');
   if(shell&&shell.parentElement===desk) shell.insertAdjacentElement('afterend',host);
   else anchor.insertAdjacentElement('afterend',host);
 } else {
   desk.appendChild(host);
 }
 return host;
}
function style(){
 if(document.getElementById('gmfq-ois-operational-style'))return;
 const s=document.createElement('style');s.id='gmfq-ois-operational-style';s.textContent=`
 #v401OisBlock{display:block!important;margin-top:14px;max-width:100%;min-width:0;overflow:hidden;border:1px solid #173d55;background:#081723;border-radius:12px;padding:12px}#v401OisBlock .oisOp{display:grid;gap:12px;min-width:0}.oisOpHead{display:flex;gap:10px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}.oisOpTitle{font-size:16px;font-weight:900}.oisOpSub{color:#8eabba;font-size:11px;line-height:1.45;max-width:760px}.oisOpBadges{display:flex;gap:6px;flex-wrap:wrap}.oisBadge{font-size:9px;font-weight:850;border:1px solid #31536a;border-radius:999px;padding:4px 7px}.oisBadge.off{color:#20df76;border-color:rgba(32,223,118,.45);background:rgba(32,223,118,.07)}.oisBadge.est{color:#f2bb49;border-color:rgba(242,187,73,.45);background:rgba(242,187,73,.07)}
 .oisPathGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;min-width:0}.oisPathCard{border:1px solid #173d55;background:#071a28;border-radius:9px;padding:9px;min-width:0}.oisPathTop{display:flex;align-items:center;justify-content:space-between;gap:6px}.oisPathCcy{font-size:14px;font-weight:900}.oisPathMeta{font-size:8px;border-radius:999px;padding:3px 5px;border:1px solid #31536a}.oisPathMeta.off{color:#20df76;border-color:rgba(32,223,118,.4)}.oisPathMeta.est{color:#f2bb49;border-color:rgba(242,187,73,.4)}.oisPathCard svg{width:100%;height:72px;display:block;margin-top:5px}.oisPathVals{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:3px;font-size:8px;color:#7696a8}.oisPathVals b{display:block;color:#dcecf4;font-size:10px;margin-top:2px}.oisAsOf{font-size:8px;color:#6e91a2;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .oisReprice{overflow-x:auto;max-width:100%}.oisReprice table{min-width:760px;width:100%}.oisReprice th,.oisReprice td{font-size:9px;padding:6px 5px}.oisReprice td.up{color:#20df76}.oisReprice td.down{color:#b99aff}.oisReprice td.neu{color:#91aebe}.oisQuality{font-size:8px;font-weight:850;border-radius:999px;padding:3px 5px;border:1px solid #31536a}.oisQuality.off{color:#20df76;border-color:rgba(32,223,118,.4)}.oisQuality.est{color:#f2bb49;border-color:rgba(242,187,73,.4)}.oisFoot{font-size:9px;color:#7899aa;line-height:1.45}.oisFail{border:1px solid rgba(255,82,99,.45);background:rgba(255,82,99,.06);color:#ff929d;border-radius:8px;padding:10px;font-size:11px}
 @media(max-width:1050px){.oisPathGrid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.oisPathGrid{grid-template-columns:1fr}.oisPathVals{grid-template-columns:repeat(4,minmax(52px,1fr))}}
 `;document.head.appendChild(s);
}
function pathSvg(r,min,max){
 const vals=H.map(h=>rowRate(r,h));
 const W=220,HGT=72,pad=10,span=Math.max(.01,max-min);const pts=[];
 vals.forEach((v,i)=>{if(!Number.isFinite(Number(v)))return;const x=pad+i*((W-2*pad)/3);const y=pad+(max-Number(v))/span*(HGT-2*pad);pts.push([x,y,i]);});
 const poly=pts.length>1?`<polyline points="${pts.map(p=>p[0]+','+p[1]).join(' ')}" fill="none" stroke="#23b7ff" stroke-width="2"/>`:'';
 const dots=pts.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="#eef7ff" stroke="#23b7ff" stroke-width="1.5"/>`).join('');
 return `<svg viewBox="0 0 ${W} ${HGT}" aria-label="Policy path ${esc(r.operational_status)}"><line x1="10" x2="210" y1="62" y2="62" stroke="#173d55"/>${poly}${dots}</svg>`;
}
function render(){
 const host=ensureHost();if(!host)return false;style();
 if(state.status==='ERROR'){host.innerHTML=`<div class="oisFail"><b>OIS operativo non disponibile.</b><br>${esc(state.error)}. Nessun fallback stimato come dato ufficiale.</div>`;return true;}
 if(state.status!=='READY'||!state.data){host.innerHTML='<div class="oisOpSub">Caricamento OIS operativo…</div>';return true;}
 const d=state.data;const rows=CCYS.map(c=>[c,d.currencies[c]]);
 const finite=rows.flatMap(([,r])=>H.map(h=>Number(rowRate(r,h))).filter(Number.isFinite));let min=Math.min(...finite),max=Math.max(...finite);if(!finite.length){min=0;max=1;}const pad=Math.max(.15,(max-min)*.08);min-=pad;max+=pad;
 const cards=rows.map(([c,r])=>{const est=r.operational_status==='GREEN_ESTIMATED';return `<div class="oisPathCard"><div class="oisPathTop"><span class="oisPathCcy">${c}</span><span class="oisPathMeta ${est?'est':'off'}">${est?'ESTIMATED':'OFFICIAL'}</span></div>${pathSvg(r,min,max)}<div class="oisPathVals">${H.map(h=>`<span>${h==='policy'?'POLICY':h.toUpperCase()}<b>${fmtRate(rowRate(r,h))}</b></span>`).join('')}</div><div class="oisAsOf" title="${esc(r.source)}">as-of ${esc(r.as_of||'—')} · conf. ${esc(r.confidence||'—')}</div></div>`;}).join('');
 const trs=rows.map(([c,r])=>{const est=r.operational_status==='GREEN_ESTIMATED';const cells=['3m','6m','12m'].flatMap(h=>[r?.horizons?.[h]?.change_1d_bp,r?.horizons?.[h]?.change_1w_bp]).map(v=>`<td class="${clsBp(v)}">${fmtBp(v)}</td>`).join('');return `<tr><td><b>${c}</b> <span class="oisQuality ${est?'est':'off'}">${est?'EST':'OFF'}</span></td>${cells}<td>${r.change_1d_available?'SI':'NO'}/${r.change_1w_available?'SI':'NO'}</td></tr>`;}).join('');
 host.innerHTML=`<div class="oisOp"><div class="oisOpHead"><div><div class="oisOpTitle">OIS / Policy Pricing — G8 Operational</div><div class="oisOpSub">Policy path comparabile tra le 8 valute. Verde = fonte ufficiale certificata; ambra = stima operativa informativa. Gli estimated non entrano come official OIS nel backtest.</div></div><div class="oisOpBadges"><span class="oisBadge off">4 OFFICIAL</span><span class="oisBadge est">4 ESTIMATED</span><span class="oisBadge">8/8 OPERATIVO</span></div></div><div class="oisPathGrid">${cards}</div><div class="oisReprice"><table><thead><tr><th>Valuta</th><th>3M Δ1D</th><th>3M Δ1W</th><th>6M Δ1D</th><th>6M Δ1W</th><th>12M Δ1D</th><th>12M Δ1W</th><th>Storico 1D/1W</th></tr></thead><tbody>${trs}</tbody></table></div><div class="oisFoot">NULL ≠ 0 bp: “—” significa storico insufficiente o punto non disponibile. Il monitor usa esclusivamente <code>OIS_OPERATIONAL_VIEW.json</code> e non promuove gli estimated a dato ufficiale.</div></div>`;
 return true;
}
async function load(){
 try{state.status='LOADING';render();const r=await fetch(SRC,{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);state.data=validate(await r.json());state.status='READY';state.loaded_at=new Date().toISOString();state.error=null;render();}
 catch(e){state.status='ERROR';state.error=String(e?.message||e);render();}
}
window.gmfqOisOperationalUiAudit=function(){const hosts=document.querySelectorAll('#v401OisBlock');const host=hosts[0]||null;const rows=host?.querySelectorAll('.oisPathCard')?.length||0;return {status:state.status,host:!!host,host_count:hosts.length,cards:rows,ok:state.status==='READY'&&hosts.length===1&&rows===8,summary:state.data?.summary||null,error:state.error};};
const base=window.renderNativeRatesDesk;if(typeof base==='function'){window.renderNativeRatesDesk=function(){const out=base.apply(this,arguments);setTimeout(render,0);return out;};}
const prev=window.showView;if(typeof prev==='function'){window.showView=function(v){const out=prev.apply(this,arguments);if(v==='ratesdesk')setTimeout(render,0);return out;};}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',load,{once:true});else load();
})();
