(()=>{
'use strict';
const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const fmtRate=v=>v==null?'—':`${Number(v).toFixed(2)}%`;
function fmtConsensus(v,u){if(v==null||v==='')return '—';return `${esc(v)}${u?` ${esc(u)}`:''}`;}

function css(){
 if(document.getElementById('gmfq-calendar-news-operational-style'))return;
 const s=document.createElement('style');s.id='gmfq-calendar-news-operational-style';
 s.textContent=`
 .opDesk{padding:22px 20px 36px;color:#e8eef8;font-family:Inter,system-ui,sans-serif}.opHero{border:1px solid rgba(130,160,210,.18);background:linear-gradient(135deg,rgba(23,45,78,.92),rgba(11,19,34,.96));border-radius:18px;padding:20px;margin-bottom:16px}.opEyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8fb5e8;font-weight:800}.opTitle{font-size:24px;line-height:1.1;margin:7px 0 6px;font-weight:850}.opSub{font-size:13px;color:#9eabc0;line-height:1.5}.opSection{margin:18px 0 10px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#92a7c4;font-weight:850}.opGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.opCard{background:#101a2b;border:1px solid rgba(135,157,190,.16);border-radius:14px;padding:15px;min-width:0}.opCard[data-kind="macro"]{border-color:rgba(127,190,255,.2)}.opTop{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.opCcy{font-size:15px;font-weight:850}.opDate{font-size:12px;color:#9bb0cd;font-variant-numeric:tabular-nums}.opCard h3{margin:0 0 8px;font-size:15px;line-height:1.3}.opMeta{font-size:12px;color:#9eaabc;line-height:1.5}.opTag{display:inline-flex;border-radius:999px;padding:4px 8px;font-size:10px;font-weight:800;letter-spacing:.04em;background:rgba(73,151,255,.12);border:1px solid rgba(73,151,255,.2);color:#9ec5ff}.opTagWarn{background:rgba(255,181,71,.09);border-color:rgba(255,181,71,.2);color:#e6c27e}.opTagOk{background:rgba(90,190,130,.09);border-color:rgba(90,190,130,.22);color:#a8e4bf}.opConsensus{margin-top:8px;padding:8px 10px;border-radius:10px;background:rgba(255,255,255,.025);border:1px solid rgba(145,165,195,.12);font-variant-numeric:tabular-nums}.opHigh{color:#a7e5bf}.opFoot{margin-top:16px;padding:12px 14px;border-radius:12px;background:rgba(255,181,71,.08);border:1px solid rgba(255,181,71,.16);font-size:12px;color:#cbb68c;line-height:1.45}@media(max-width:720px){.opDesk{padding:15px 12px 28px}.opGrid{grid-template-columns:1fr}.opTitle{font-size:21px}.opHero{padding:16px}}
 `;document.head.appendChild(s);
}
function card(e){
 const isCB=e.event_type==='CENTRAL_BANK_DECISION';
 const tag=isCB?'OFFICIAL CB SCHEDULE':'OFFICIAL MACRO RELEASE';
 let details=isCB?`Tasso attuale <b>${fmtRate(e.current_rate)}</b><br>${esc(e.stance||'')}`:`${esc(e.reference_period||'')} ${e.time_local?`· ${esc(e.time_local)} ${esc(e.timezone||'')}`:''}<br>Source: ${esc(e.source_family||e.source_layer||'official')}`;
 let secondary='';
 if(!isCB){
   if(e.consensus_status==='AVAILABLE'){
     secondary=`<div class="opConsensus">Consensus <b>${fmtConsensus(e.consensus,e.consensus_unit)}</b> · Previous <b>${fmtConsensus(e.previous,e.consensus_unit)}</b><br><span class="opTag opTagOk">CONSENSUS SECONDARY · ${esc(e.consensus_provider||'')}</span> <span class="opTag">CONFIDENCE ${esc(e.consensus_confidence||'—')}</span></div>`;
   }else if(e.consensus_status==='PREVIOUS_ONLY'){
     secondary=`<div class="opConsensus">Previous <b>${fmtConsensus(e.previous,e.consensus_unit)}</b> · Consensus non disponibile<br><span class="opTag opTagWarn">SECONDARY PREVIOUS ONLY</span></div>`;
   }else{
     secondary='<div class="opConsensus"><span class="opTag opTagWarn">CONSENSUS SECONDARY / NOT PRESENT</span></div>';
   }
 }
 return `<article class="opCard" data-kind="${isCB?'cb':'macro'}" data-consensus-status="${esc(e.consensus_status||'')}"><div class="opTop"><div class="opCcy">${FLAGS[e.ccy]||''} ${esc(e.ccy)}</div><div class="opDate">${esc(e.date)}</div></div><h3 class="${e.importance==='HIGH'?'opHigh':''}">${esc(e.title)}</h3><div class="opMeta">${details}<br><span class="opTag">${tag}</span>${secondary}</div></article>`;
}
function calendarHtml(data){
 const cb=(data.events||[]).filter(e=>e.event_type==='CENTRAL_BANK_DECISION').map(card).join('');
 const macro=(data.events||[]).filter(e=>e.event_type!=='CENTRAL_BANK_DECISION').map(card).join('');
 return `<div class="opDesk" data-gmfq-operational="calendar"><div class="opHero"><div class="opEyebrow">Event Risk · G8</div><div class="opTitle">Calendar operativo</div><div class="opSub">Date e release restano ufficiali. Consensus e previous sono un layer secondary separato: non correggono mai data, source o score del Core.</div></div><div class="opSection">Central Banks</div><div class="opGrid">${cb||'<div class="opCard">Nessun meeting futuro disponibile.</div>'}</div><div class="opSection">Macro releases</div><div class="opGrid">${macro||'<div class="opCard">Nessuna release macro ufficiale disponibile.</div>'}</div><div class="opFoot">Coverage CB: ${esc(data.coverage?.cb_schedule_available||0)}/8 · Macro currencies: ${esc(data.coverage?.macro_ccy_coverage||0)}/8 · Upcoming macro events: ${esc(data.coverage?.upcoming_macro_events||0)} · Consensus available: ${esc(data.coverage?.consensus_available_events||0)} · Secondary layer: ${esc(data.scope?.consensus||'NOT PRESENT')} · Core impact: 0</div></div>`;
}
function verifiedOfficialLink(item){
 const hosts={
   FED_PRESS:['www.federalreserve.gov','federalreserve.gov'],
   ECB_PRESS:['www.ecb.europa.eu','ecb.europa.eu','www.ecb.int','ecb.int'],
   BOE_NEWS:['www.bankofengland.co.uk','bankofengland.co.uk'],
   BOJ_NEWS:['www.boj.or.jp','boj.or.jp'],
   SNB_POLICY:['www.snb.ch','snb.ch'],
   BOC_PRESS:['www.bankofcanada.ca','bankofcanada.ca'],
   RBA_PRESS:['www.rba.gov.au','rba.gov.au'],
   RBNZ_NEWS:['www.rbnz.govt.nz','rbnz.govt.nz'],
   EIA_ENERGY:['www.eia.gov','eia.gov']
 };
 const allowed=hosts[item.source_id]||[];
 try{const u=new URL(item.url);return u.protocol==='https:'&&allowed.includes(u.hostname)&&!u.username&&!u.password&&(u.port===''||u.port==='443')?u.href:null;}catch(e){return null;}
}
function fmtOfficialInstant(utc){
 if(typeof utc!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(utc))return '—';
 const d=new Date(utc);if(!Number.isFinite(d.getTime()))return '—';
 return new Intl.DateTimeFormat('it-IT',{timeZone:'Europe/Rome',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(d);
}
function newsHtml(data){
 const items=(data.items||[]).map(x=>
   '<article class="opCard"><div class="opTop"><div class="opCcy">'+(FLAGS[x.ccy]||'')+' '+esc(x.ccy)+'</div><div class="opDate">'+esc(x.as_of||'—')+'</div></div><h3 class="'+(x.importance==='HIGH'?'opHigh':'')+'">'+esc(x.title)+'</h3><div class="opMeta">'+esc(x.detail)+'<br><span class="opTag">'+esc(x.category)+'</span> <span class="opTag">'+esc(x.quality||'')+'</span>'+(x.source?'<br>Fonte: '+esc(x.source):'')+'</div></article>'
 ).join('');
 const external=data.official_releases||{};
 const state=external.status||'UNAVAILABLE_NOT_CHECKED';
 const sources=(external.sources||[]).map(s=>esc(s.source)+': '+esc(s.status)).join(' · ');
 const announcements=(external.headlines||[]).map(item=>{
   const url=verifiedOfficialLink(item);
   if(item.quality!=='OFFICIAL_RSS_DATED_LINK'||!url)return '';
   return '<article class="opCard" data-kind="official-release"><div class="opTop"><div class="opCcy">'+(FLAGS[item.ccy]||'')+' '+esc(item.source)+'</div><div class="opDate">'+esc(fmtOfficialInstant(item.published_at_utc))+'</div></div><h3>'+esc(item.title)+'</h3><div class="opMeta"><span class="opTag">COMUNICAZIONE UFFICIALE · '+esc(item.ccy==='ENERGY'?'ENERGIA':item.ccy)+'</span> <span class="opTag">NESSUNA REAZIONE PREZZI CERTIFICATA</span><br><a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer" style="color:#9ec5ff">Leggi sulla fonte originale</a></div></article>';
 }).join('');
 const desc=state==='VERIFIED_OFFICIAL_RELEASES'?'Pubblicazioni datate da fonti ufficiali; copertura per fonte consultabile sotto':
   state==='PARTIAL_SOURCES'?'Copertura parziale: una o più fonti non rispondono':
   state==='VERIFIED_NO_RECENT_RELEASES'?'Fonti verificate, nessuna comunicazione nei dieci giorni esaminati':
   'Fonti non verificate: nessuna notizia esterna viene presentata come corrente';
 return '<div class="opDesk" data-gmfq-operational="news">'+
 '<div class="opHero"><div class="opEyebrow">What changed · source-verified research desk</div><div class="opTitle">News Pulse operativo</div><div class="opSub">Due livelli distinti: pubblicazioni ufficiali delle banche centrali G8 e dell’EIA, e movimenti misurati da fonti operative. Non è ancora un notiziario finanziario globale. Non attribuiamo causalmente i movimenti ai comunicati.</div></div>'+
 '<div class="opSection">Comunicazioni ufficiali · banche centrali G8 ed energia EIA</div><div class="opMeta">'+esc(desc)+' · Ultimo controllo (Roma): '+esc(external.last_attempt_day_rome||'—')+' · '+(sources||'Nessun controllo disponibile')+'</div><div class="opGrid">'+
 (announcements||'<div class="opCard">Nessuna comunicazione ufficiale recente verificata. Non vengono mostrati titoli ricostruiti o notizie inventate.</div>')+
 '</div><div class="opSection">Segnali quantitativi · OIS e futures</div><div class="opSub">Ultima osservazione di mercato: <b>'+esc(data.content_as_of||'—')+'</b>. Il giorno dell’ultimo controllo delle fonti non cambia la data economica di un segnale.</div><div class="opGrid">'+
 (items||'<div class="opCard">Nessun nuovo segnale validato disponibile.</div>')+
 '</div><div class="opFoot">Inputs quantitativi: '+esc((data.scope?.inputs||[]).join(' · '))+'. Fonti esterne limitate ai feed ufficiali di banche centrali G8 ed EIA: solo titoli, orari e collegamenti originali, senza interpretazioni non verificate. NULL non diventa mai 0 bp.</div></div>';
}
let cache=null;
async function load(){if(cache)return cache;const [c,n]=await Promise.all([fetch('live_data/sections/CALENDAR_OPERATIONAL_VIEW.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('calendar '+r.status);return r.json()}),fetch('live_data/sections/NEWS_PULSE_OPERATIONAL.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('news '+r.status);return r.json()})]);cache={c,n};return cache;}
async function render(){css();try{const {c,n}=await load();const cal=document.getElementById('calendar'),news=document.getElementById('news');if(cal&&!cal.querySelector('[data-gmfq-operational="calendar"]'))cal.innerHTML=calendarHtml(c);if(news&&!news.querySelector('[data-gmfq-operational="news"]'))news.innerHTML=newsHtml(n);window.GMFQ_CALENDAR_NEWS_OPERATIONAL={status:'ACTIVE',calendar:c.status,news:n.status,calendar_events:(c.events||[]).length,macro_events:(c.events||[]).filter(e=>e.event_type!=='CENTRAL_BANK_DECISION').length,consensus_available:c.coverage?.consensus_available_events||0,news_items:(n.items||[]).length,content_as_of:n.content_as_of};}catch(err){console.error('calendar-news-operational',err);window.GMFQ_CALENDAR_NEWS_OPERATIONAL={status:'ERROR',error:String(err)};}}
const obs=new MutationObserver(()=>{const c=document.getElementById('calendar'),n=document.getElementById('news');if((c&&!c.querySelector('[data-gmfq-operational="calendar"]'))||(n&&!n.querySelector('[data-gmfq-operational="news"]')))render();});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{render();obs.observe(document.body,{childList:true,subtree:true});},{once:true});else{render();obs.observe(document.body,{childList:true,subtree:true});}
})();
