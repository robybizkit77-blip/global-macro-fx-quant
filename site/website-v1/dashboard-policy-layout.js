(()=>{
'use strict';
const ROOT='../../live_data/sections/';
const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
const n=v=>Number.isFinite(Number(v))?Number(v):null;
const fmt=v=>n(v)===null?'—':`${n(v).toFixed(2)}%`;
const bp=v=>n(v)===null?'—':`${n(v)>0?'+':''}${n(v).toFixed(0)}bp`;
async function load(){const r=await fetch(ROOT+'OIS_OPERATIONAL_VIEW.json',{cache:'no-store'});if(!r.ok)throw new Error(`OIS HTTP ${r.status}`);return r.json();}
function style(){if(document.getElementById('dashboard-policy-style'))return;const s=document.createElement('style');s.id='dashboard-policy-style';s.textContent=`
.ois-dashboard .ois-summary{padding:8px 12px 10px;display:grid;gap:5px}.ois-dashboard .ois-row{display:grid;grid-template-columns:62px repeat(4,minmax(54px,1fr)) 58px;align-items:center;gap:6px;min-height:24px;border-bottom:1px solid rgba(71,105,128,.18);font-size:9px}.ois-dashboard .ois-row.head{color:#718b9e;font-size:8px;text-transform:uppercase;letter-spacing:.06em}.ois-dashboard .ois-row b{font-size:10px;color:#e5edf3}.ois-dashboard .ois-row span{color:#b8c7d2;text-align:right}.ois-dashboard .ois-row em{font-style:normal;text-align:right}.ois-dashboard .ois-row em.up{color:#45d9a2}.ois-dashboard .ois-row em.down{color:#ff7185}.ois-dashboard .ois-note{display:flex;justify-content:space-between;gap:10px;padding-top:5px;color:#6f899b;font-size:8px}.row2b{grid-template-columns:minmax(0,1.12fr) minmax(0,.88fr)!important}.row3{grid-template-columns:minmax(0,1.05fr) minmax(0,.95fr)!important}.row4{grid-template-columns:1fr!important}.rates .rate-legend{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));gap:3px 8px!important}.rates .rate-legend span{font-size:8px!important;white-space:nowrap}.rates .rate-tip{min-height:18px!important}
@media(max-width:900px){.ois-dashboard .ois-summary{overflow-x:auto}.ois-dashboard .ois-row{min-width:560px}.row2b{grid-template-columns:1fr!important}.rates .rate-legend{grid-template-columns:repeat(2,minmax(0,1fr))}}
`;document.head.appendChild(s)}
function layout(){
 const row2=document.querySelector('.row2'),rates=row2?.querySelector('.rates'),cbs=row2?.querySelector('.cbs');
 const row3=document.querySelector('.row3'),cot=row3?.querySelector('.cot-card'),setups=row3?.querySelector('.setups');
 const row4=document.querySelector('.row4'),calendar=row4?.querySelector('.calendar'),watch=row4?.querySelector('.watch');
 if(!row2||!rates||!cbs||!row3||!cot||!setups||!row4)return null;
 const ois=document.createElement('article');ois.className='card ois-dashboard';ois.innerHTML='<div class="card-head"><h2>OIS / Market Pricing · G8</h2><a href="tassi.html">Apri curve OIS →</a></div><div class="ois-summary"><div class="ois-row head"><b>CCY</b><span>Policy</span><span>3M</span><span>6M</span><span>12M</span><em>12M Δ</em></div><div class="ois-body"></div><div class="ois-note"><span>Policy → 3M → 6M → 12M</span><em>—</em></div></div>';
 row2.insertBefore(ois,cbs);rates.remove();
 const row2b=document.createElement('section');row2b.className='row row2b decision-row';row2.parentNode.insertBefore(row2b,row3);row2b.append(rates,cot);
 if(calendar)row3.append(calendar);
 if(watch){row4.innerHTML='';row4.append(watch)}
 rates.querySelector('.card-head h2').textContent='2Y G8 · Conferma front-end';
 rates.querySelector('.card-head a').textContent='Apri Tassi →';
 return ois;
}
function render(host,data){const body=host.querySelector('.ois-body'),note=host.querySelector('.ois-note em');const ccys=data?.currencies||{};body.innerHTML=ORDER.map(c=>{const x=ccys[c]||{},p=n(x.policy_rate),m3=n(x.horizons?.['3m']?.rate),m6=n(x.horizons?.['6m']?.rate),m12=n(x.horizons?.['12m']?.rate),d12=n(x.horizons?.['12m']?.policy_delta_bp);const cls=d12===null?'':d12>=0?'up':'down';return `<div class="ois-row"><b>${FLAGS[c]} ${c}</b><span>${fmt(p)}</span><span>${fmt(m3)}</span><span>${fmt(m6)}</span><span>${fmt(m12)}</span><em class="${cls}">${bp(d12)}</em></div>`}).join('');const dates=ORDER.map(c=>ccys[c]?.as_of).filter(Boolean).sort();if(note)note.textContent=dates.length?`ultimo dato ${dates.at(-1)}`:'dati non disponibili';document.documentElement.dataset.dashboardOis='G8'}
async function main(){style();const host=layout();if(!host)return;try{render(host,await load())}catch(e){console.warn('[GMFQ dashboard OIS]',e);host.querySelector('.ois-body').innerHTML='<div class="ois-row"><b>OIS</b><span>—</span><span>—</span><span>—</span><span>—</span><em>—</em></div>';}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
