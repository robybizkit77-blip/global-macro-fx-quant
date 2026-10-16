(()=>{
'use strict';
const SCHEMA='GMFQ_CONTROL_ROOM_HOME_V1';
const STYLE_ID='gmfq-control-room-home-v1-style';
const ROOT_ID='gmfq-control-room-home-v1';
const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿',GLOBAL:'🌐'};
const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const fmtRate=v=>Number.isFinite(Number(v))?Number(v).toFixed(2).replace(/0+$/,'').replace(/\.$/,'')+'%':'—';
const fmtBp=v=>Number.isFinite(Number(v))?`${Number(v)>0?'+':''}${Number(v).toFixed(1)} bp`:'—';
function css(){
 if(document.getElementById(STYLE_ID))return;
 const s=document.createElement('style');s.id=STYLE_ID;s.textContent=`
 #overview.gmfq-cr-overview{display:block!important;max-width:1540px;margin:0 auto;padding:18px 28px 34px!important}
 .crHome{display:grid;gap:14px}.crStrip{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:8px}.crTile,.crPanel{background:linear-gradient(180deg,rgba(13,25,39,.96),rgba(8,17,28,.97));border:1px solid rgba(154,169,190,.14);border-radius:14px;box-shadow:0 14px 34px rgba(0,0,0,.14)}
 .crTile{padding:10px 11px;min-width:0}.crTileK{font-size:9px;color:#8090a3;letter-spacing:.08em;font-weight:800}.crTileV{font-size:15px;font-weight:850;margin-top:4px;color:#edf3f8}.crTileS{font-size:9px;color:#6f8093;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .crGridA{display:grid;grid-template-columns:1.15fr 1fr 1.2fr;gap:12px}.crPanel{padding:15px;min-width:0}.crHead{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:12px}.crTitle{font-size:15px;font-weight:850;color:#f1f5f9}.crSub{font-size:10px;color:#78899d;margin-top:3px;line-height:1.35}.crLink{font-size:9px;color:#c9aa68;font-weight:800;white-space:nowrap}
 .crChanges{display:grid;gap:8px}.crChange{padding:9px 10px;border:1px solid rgba(154,169,190,.11);border-radius:10px;background:rgba(255,255,255,.018)}.crChangeTop{display:flex;justify-content:space-between;gap:8px}.crChangeC{font-size:10px;font-weight:900}.crChangeAs{font-size:8px;color:#6d7c8e}.crChangeT{font-size:11px;font-weight:760;line-height:1.35;margin-top:4px;color:#dfe7ef}.crChangeD{font-size:9px;color:#8392a5;line-height:1.35;margin-top:3px}
 .crRank{display:grid;gap:7px}.crRankRow{display:grid;grid-template-columns:28px 44px 1fr;gap:7px;align-items:center}.crRankN{font-size:9px;color:#708195}.crRankC{font-size:11px;font-weight:850}.crRankBar{height:7px;border-radius:999px;background:#152333;overflow:hidden;position:relative}.crRankBar>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#5eb8ff,#c9aa68)}.crRankNote{font-size:8px;color:#6f8091;margin-top:8px}
 .crRates{display:grid;gap:8px}.crRateRow{display:grid;grid-template-columns:42px repeat(4,minmax(0,1fr));gap:6px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(154,169,190,.08)}.crRateRow:last-child{border-bottom:0}.crRateC{font-size:10px;font-weight:900}.crRateCell span{display:block;font-size:7px;color:#728397;text-transform:uppercase;letter-spacing:.05em}.crRateCell b{display:block;font-size:10px;color:#dce6ef;margin-top:2px}.crRateCell em{display:block;font-style:normal;font-size:7px;color:#8292a5;margin-top:1px}.crRateCell .up{color:#55d6a6}.crRateCell .down{color:#ff8a96}
 .crLegacy{margin-top:4px}.crLegacySummary{font-size:10px;color:#7f8fa2;padding:8px 2px}.crLegacyDetails{border-top:1px solid rgba(154,169,190,.12);margin-top:2px;padding-top:10px}.crLegacyDetails>summary{cursor:pointer;color:#8fa0b3;font-size:10px;font-weight:800;list-style:none}.crLegacyDetails>summary::-webkit-details-marker{display:none}.crLegacyDetails[open]>summary{margin-bottom:12px}
 @media(max-width:1180px){.crStrip{grid-template-columns:repeat(4,minmax(0,1fr))}.crGridA{grid-template-columns:1fr 1fr}.crGridA>.crPanel:last-child{grid-column:1/-1}}
 @media(max-width:760px){#overview.gmfq-cr-overview{padding:12px 14px 26px!important}.crStrip{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(118px,35vw);grid-template-columns:none;overflow-x:auto;padding-bottom:6px}.crGridA{grid-template-columns:1fr}.crGridA>.crPanel:last-child{grid-column:auto}.crPanel{padding:13px}.crRateRow{grid-template-columns:38px repeat(4,minmax(64px,1fr));overflow-x:auto}.crLegacyDetails{display:none}}
 `;document.head.appendChild(s);
}
function findSnapshot(label){
 const nodes=[...document.querySelectorAll('#overview *')].filter(x=>x.children.length===0&&String(x.textContent||'').trim()===label);
 for(const n of nodes){const box=n.closest('.gmfqExecCard,.ov387Card,.card,[class*="Card"]');if(!box)continue;const txt=box.innerText.replace(/\s+/g,' ').trim();const m=txt.match(/(?:^|\s)([-+]?\d+(?:[.,]\d+)?%?|\d+[.,]\d+)(?:\s|$)/);if(m)return {value:m[1],text:txt.slice(0,90)};}
 return {value:'—',text:'Dato disponibile nel deep-dive'};
}
function snapshotHtml(){
 const defs=[['DXY','DXY'],['EURUSD','EURUSD'],['GBPUSD','GBPUSD'],['USDJPY','USDJPY'],['US 2Y','US 2Y'],['US 10Y','US 10Y'],['GOLD','Gold'],['WTI','WTI']];
 return defs.map(([k,l])=>{const x=findSnapshot(l);return `<div class="crTile"><div class="crTileK">${esc(k)}</div><div class="crTileV">${esc(x.value)}</div><div class="crTileS">${esc(x.text)}</div></div>`}).join('');
}
function currencyRows(){
 const cards=[...document.querySelectorAll('#currencyGrid .ccy')];
 const ordered=cards.map((el,i)=>({c:el.dataset?.c||'',txt:(el.innerText||'').replace(/\s+/g,' ').trim(),i})).filter(x=>CCYS.includes(x.c));
 if(ordered.length!==8)return CCYS.map((c,i)=>({c,txt:'',i}));
 return ordered;
}
function rankHtml(){
 const rows=currencyRows();
 return rows.map((x,i)=>`<div class="crRankRow"><div class="crRankN">${i+1}</div><div class="crRankC">${FLAGS[x.c]||''} ${x.c}</div><div class="crRankBar" title="${esc(x.txt)}"><i style="width:${Math.max(16,100-i*11)}%"></i></div></div>`).join('')+`<div class="crRankNote">Ordine letto dal frame canonico corrente. Nessun ranking ricalcolato nella UI.</div>`;
}
function rateRows(ois){
 if(!ois?.currencies)return '<div class="crSub">OIS non ancora disponibile.</div>';
 return CCYS.map(c=>{const r=ois.currencies[c]||{};const h=r.horizons||{};const cell=(lab,v,d1)=>`<div class="crRateCell"><span>${lab}</span><b>${fmtRate(v)}</b><em class="${Number(d1)>0?'up':Number(d1)<0?'down':''}">${fmtBp(d1)}</em></div>`;return `<div class="crRateRow"><div class="crRateC">${c}</div>${cell('Policy',r.policy_rate,null)}${cell('3M',h['3m']?.rate,h['3m']?.change_1d_bp)}${cell('6M',h['6m']?.rate,h['6m']?.change_1d_bp)}${cell('12M',h['12m']?.rate,h['12m']?.change_1d_bp)}</div>`}).join('');
}
function changesHtml(news){
 const items=[...(news?.items||[])].sort((a,b)=>String(b?.as_of||'').localeCompare(String(a?.as_of||''))).slice(0,5);
 if(!items.length)return '<div class="crSub">Nessun nuovo cambiamento validato.</div>';
 return `<div class="crChanges">${items.map(x=>`<div class="crChange"><div class="crChangeTop"><span class="crChangeC">${FLAGS[x.ccy]||FLAGS.GLOBAL} ${esc(x.ccy||'GLOBAL')}</span><span class="crChangeAs">${esc(x.as_of||'—')}</span></div><div class="crChangeT">${esc(x.title||'Segnale validato')}</div><div class="crChangeD">${esc(x.detail||'')}</div></div>`).join('')}</div>`;
}
async function loadJson(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(path+':'+r.status);return r.json();}
async function render(){
 css();
 const overview=document.getElementById('overview');if(!overview)return false;
 overview.classList.add('gmfq-cr-overview');
 let root=document.getElementById(ROOT_ID);if(!root){root=document.createElement('section');root.id=ROOT_ID;root.className='crHome';overview.insertBefore(root,overview.firstChild);}
 let news=null,ois=null;try{[news,ois]=await Promise.all([loadJson('live_data/sections/NEWS_PULSE_OPERATIONAL.json'),loadJson('live_data/sections/OIS_OPERATIONAL_VIEW.json')]);}catch(e){console.warn('control-room-home-data',e);}
 const legacy=[...overview.children].filter(x=>x!==root);
 legacy.forEach(x=>x.style.display='none');
 root.innerHTML=`<div class="crStrip">${snapshotHtml()}</div><div class="crGridA"><section class="crPanel"><div class="crHead"><div><div class="crTitle">Cosa è cambiato</div><div class="crSub">Solo segnali validati correnti.</div></div><span class="crLink">WHAT CHANGED</span></div>${changesHtml(news)}</section><section class="crPanel"><div class="crHead"><div><div class="crTitle">Currency Hierarchy</div><div class="crSub">Ordine operativo corrente.</div></div><span class="crLink">G8</span></div><div class="crRank">${rankHtml()}</div></section><section class="crPanel"><div class="crHead"><div><div class="crTitle">Relative Rates / OIS</div><div class="crSub">Policy path 3M · 6M · 12M e repricing 1D.</div></div><span class="crLink">8/8</span></div><div class="crRates">${rateRows(ois)}</div></section></div><div class="crLegacy"><details class="crLegacyDetails"><summary>Apri overview legacy / deep-dive completo</summary><div data-cr-legacy-host></div></details></div>`;
 const host=root.querySelector('[data-cr-legacy-host]');legacy.forEach(x=>{x.style.display='';host.appendChild(x)});
 window.GMFQ_CONTROL_ROOM_HOME={schema:SCHEMA,status:'ACTIVE',scope:'PRESENTATION_ONLY',core_effect:'NONE',news_source:'NEWS_PULSE_OPERATIONAL',rates_source:'OIS_OPERATIONAL_VIEW',currency_order_source:'currencyGrid canonical DOM'};
 return true;
}
function boot(){let tries=0;const tick=()=>{tries++;if(document.getElementById('overview')&&document.querySelector('#currencyGrid .ccy')){render().catch(e=>{console.error('control-room-home',e);window.GMFQ_CONTROL_ROOM_HOME={schema:SCHEMA,status:'ERROR',error:String(e),core_effect:'NONE'};});return;}if(tries<240)setTimeout(tick,250);else window.GMFQ_CONTROL_ROOM_HOME={schema:SCHEMA,status:'WITHHELD',reason:'BOOT_TIMEOUT',core_effect:'NONE'};};tick();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();