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
 .opMacroCard{border-color:rgba(77,145,221,.25)}.opMacroStage{font-size:12px;line-height:1.5;color:#94bde7;background:rgba(73,151,255,.07);padding:8px 10px;border-radius:9px;margin:8px 0 12px}.opMacroStats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.opMacroStats>div{padding:9px 8px;border:1px solid rgba(145,165,195,.14);border-radius:9px;min-width:0}.opMacroStats small{display:block;color:#91a4bb;font-size:10px;line-height:1.3;min-height:30px}.opMacroStats strong{display:block;font-size:15px;line-height:1.4;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.opMacroBefore,.opMacroPost{margin-top:12px;padding-top:10px;border-top:1px solid rgba(145,165,195,.13);font-size:12px}.opMacroRates{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:7px}.opMacroRate{background:rgba(255,255,255,.025);padding:7px 8px;border-radius:8px;min-width:0}.opMacroRate span,.opMacroRate small{display:block;color:#91a4bb;font-size:10px;overflow-wrap:anywhere}.opMacroRate b{display:block;margin:3px 0;font-size:12px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.opMacroNote{color:#97a8bd;font-size:11px;line-height:1.48;margin-top:10px;overflow-wrap:anywhere}.opMacroSource{display:inline-block;margin-top:9px;color:#9ec5ff;font-size:12px;overflow-wrap:anywhere}@media(max-width:460px){.opMacroStats{grid-template-columns:1fr 1fr}.opMacroStats>div:last-child{grid-column:1/-1}.opMacroStats small{min-height:0}} .opDesk{padding:22px 20px 36px;color:#e8eef8;font-family:Inter,system-ui,sans-serif}.opHero{border:1px solid rgba(130,160,210,.18);background:linear-gradient(135deg,rgba(23,45,78,.92),rgba(11,19,34,.96));border-radius:18px;padding:20px;margin-bottom:16px}.opEyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8fb5e8;font-weight:800}.opTitle{font-size:24px;line-height:1.1;margin:7px 0 6px;font-weight:850}.opSub{font-size:13px;color:#9eabc0;line-height:1.5}.opSection{margin:18px 0 10px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#92a7c4;font-weight:850}.opGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.opCard{background:#101a2b;border:1px solid rgba(135,157,190,.16);border-radius:14px;padding:15px;min-width:0}.opCard[data-kind="macro"]{border-color:rgba(127,190,255,.2)}.opTop{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.opCcy{font-size:15px;font-weight:850}.opDate{font-size:12px;color:#9bb0cd;font-variant-numeric:tabular-nums}.opCard h3{margin:0 0 8px;font-size:15px;line-height:1.3}.opMeta{font-size:12px;color:#9eaabc;line-height:1.5}.opTag{display:inline-flex;border-radius:999px;padding:4px 8px;font-size:10px;font-weight:800;letter-spacing:.04em;background:rgba(73,151,255,.12);border:1px solid rgba(73,151,255,.2);color:#9ec5ff}.opTagWarn{background:rgba(255,181,71,.09);border-color:rgba(255,181,71,.2);color:#e6c27e}.opTagOk{background:rgba(90,190,130,.09);border-color:rgba(90,190,130,.22);color:#a8e4bf}.opConsensus{margin-top:8px;padding:8px 10px;border-radius:10px;background:rgba(255,255,255,.025);border:1px solid rgba(145,165,195,.12);font-variant-numeric:tabular-nums}.opHigh{color:#a7e5bf}.opFoot{margin-top:16px;padding:12px 14px;border-radius:12px;background:rgba(255,181,71,.08);border:1px solid rgba(255,181,71,.16);font-size:12px;color:#cbb68c;line-height:1.45}@media(max-width:720px){.opDesk{padding:15px 12px 28px}.opGrid{grid-template-columns:1fr}.opTitle{font-size:21px}.opHero{padding:16px}}
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
function releaseContext(item){
 const c=item.desk_context||{};
 // Newer/unknown data schemas default to CONTEXT rather than promoting news.
 const tier=['MONITOR','REVIEW','CONTEXT'].includes(c.operational_relevance)&&
   c.analysis_basis==='SOURCE_HEADLINE_ONLY' &&
   c.market_direction==='NOT_DETERMINED' && c.market_reaction==='NOT_MEASURED'
   ?c.operational_relevance:'CONTEXT';
 return {tier,why:c.analysis_basis==='SOURCE_HEADLINE_ONLY'?(c.why_watch||''):'',
         next:c.analysis_basis==='SOURCE_HEADLINE_ONLY'?(c.verify_next||''):''};
}
function proofSummary(item){
 const p=item.reaction_evidence||{};
 if(p.status!=='NOT_VERIFIABLE_INTRADAY')return 'Reazione di mercato: non certificata.';
 const oi=p.ois_or_futures||{};
 const y=p.yield_2y||{};
 const a=(oi.status==='DAILY_CONTEXT_ONLY'&&oi.event_window_proof===false)?'Tassi attesi giornalieri al '+String(oi.date||'—'):'Tassi attesi non validati';
 const b=(y.status==='DAILY_CONTEXT_ONLY'&&y.event_window_proof===false)?'2Y giornaliero al '+String(y.date||'—'):'2Y non validato';
 return item.ccy==='ENERGY'?'Reazione non certificata: WTI pre/post evento non disponibile.':
   'Reazione non certificata: '+a+'; '+b+'; prezzi FX pre/post evento non disponibili.';
}
function renderOfficialRelease(item){
 const url=verifiedOfficialLink(item);
 if(item.quality!=='OFFICIAL_RSS_DATED_LINK'||!url)return '';
 const c=releaseContext(item);
 const label=c.tier==='MONITOR'?'DA MONITORARE':c.tier==='REVIEW'?'LEGGERE IL TESTO':'CONTESTO';
 const note=(c.why?'<div class="opConsensus"><b>Perché conta (dal solo titolo)</b><br>'+esc(c.why)+
   (c.next?'<br><b>Cosa verificare</b><br>'+esc(c.next):'')+'</div>':
   '<div class="opConsensus">Lettura operativa non verificata. Consultare la fonte, senza inferire bias o reazioni di mercato.</div>');
 return '<article class="opCard" data-kind="official-release" data-relevance="'+esc(c.tier)+'">'+
   '<div class="opTop"><div class="opCcy">'+(FLAGS[item.ccy]||'')+' '+esc(item.source)+'</div><div class="opDate">'+esc(fmtOfficialInstant(item.published_at_utc))+'</div></div>'+
   '<h3>'+esc(item.title)+'</h3><div class="opMeta"><span class="opTag">'+esc(label)+'</span> <span class="opTag">COMUNICAZIONE UFFICIALE · '+esc(item.ccy==='ENERGY'?'ENERGIA':item.ccy)+
   '</span>'+note+(c.tier==='MONITOR'?'<div class="opConsensus">'+esc(proofSummary(item))+'</div>':'')+'<br><span class="opTag">NESSUNA REAZIONE PREZZI CERTIFICATA</span><br>'+
   '<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer" style="color:#9ec5ff">Leggi sulla fonte originale</a></div></article>';
}
// Read the operational macro-event evidence lane without creating policy/FX signals.
// This view is descriptive: issuer forecast B, first observed actual, and dated daily
// rate/ECB FX context. Never convert a multiday market move into event causality.
function macroNumber(x,digits=1,alwaysSign=false){
 if(typeof x!=='number'||!Number.isFinite(x))return '—';
 const v=x.toFixed(digits);
 return (alwaysSign&&x>0?'+':'')+v;
}
function issuerActualLink(url,ccy){
 if(typeof url!=='string')return null;
 try{
  const u=new URL(url);
  const allow=ccy==='USD'?['www.bls.gov']:ccy==='CAD'?['www150.statcan.gc.ca']:[];
  return u.protocol==='https:'&&allow.includes(u.hostname)&&!u.username&&!u.password&&!u.port?u.href:null;
 }catch(e){return null}
}
const MACRO_RELEASE_STATES={
 PENDING_OFFICIAL_RELEASE:'In attesa della pubblicazione ufficiale',
 PENDING_OFFICIAL_ACTUAL_ISSUER_VERIFICATION:'Pubblicazione prevista superata: actual ufficiale non ancora verificato',
 OFFICIAL_ACTUAL_PRESENT_PRE_EVENT_MARKET_ANCHOR_ABSENT:'Actual verificato · riferimento di mercato precedente assente',
 PENDING_POST_RELEASE_DAILY_OBSERVATIONS:'Actual verificato · in attesa delle quotazioni giornaliere successive',
 DAILY_CONTEXT_ONLY_NO_EVENT_CAUSALITY:'Confronto giornaliero disponibile · non prova la reazione alla notizia'
};
function eventSourceContext(item){
 const parts=item?.post_event_daily_comparison;
 if(!parts||typeof parts!=='object')return '<div class="opMacroNote">Nessun confronto post-annuncio verificabile. Non inventiamo movimenti di mercato.</div>';
 const names=[['2Y','Titolo di Stato 2Y','bp'],
              ['10Y','Titolo di Stato 10Y','bp'],
              ['SIX_MONTH','Futures 6M','bp'],
              ['ECB_FX','Fixing BCE EUR/valuta','%']];
 const elements=names.map(([key,label,unit])=>{
   const r=parts[key];
   if(!r||r.status!=='DESCRIPTIVE_MULTIDAY_CHANGE_NOT_EVENT_CAUSAL'){
     return '<div class="opMacroRate"><span>'+esc(label)+'</span><span class="opDate">Non confrontabile</span></div>';
   }
   const raw=key==='ECB_FX'?r.eur_base_quote_change_pct:r.delta_bp;
   const amount=macroNumber(raw,key==='ECB_FX'?3:2,true);
   return '<div class="opMacroRate"><span>'+esc(label)+'</span><b>'+
      esc(amount)+' '+unit+'</b><small>'+esc(r.from)+' → '+esc(r.to)+'</small></div>';
 }).join('');
 return '<div class="opMacroPost"><b>Variazioni tra osservazioni giornaliere</b>'+
   '<div class="opMacroRates">'+elements+'</div>'+
   '<div class="opMacroNote">Movimenti su più sedute, con notizie intermedie possibili. Nessuna attribuzione causale; futures CORRA ≠ OIS.</div></div>';
}
function eventMarketBefore(item){
 const p=item?.pre_event_reference;
 if(!p)return '<div class="opMacroNote">Fotografia di mercato precedente non verificabile.</div>';
 const y2=p['2Y'],y10=p['10Y'],fx=p.fx,six=p.six_month;
 const row=(label,value,date)=>'<div class="opMacroRate"><span>'+esc(label)+'</span><b>'+
    esc(value)+'</b><small>al '+esc(date||'—')+'</small></div>';
 return '<div class="opMacroBefore"><b>Mercato prima della pubblicazione</b>'+
   '<div class="opMacroRates">'+
    row('Titolo di Stato 2Y',y2&&Number.isFinite(y2.yield_pct)?macroNumber(y2.yield_pct,2)+'%':'—',y2?.date)+
    row('Titolo di Stato 10Y',y10&&Number.isFinite(y10.yield_pct)?macroNumber(y10.yield_pct,2)+'%':'—',y10?.date)+
    row(fx?.pair||'Fixing BCE',fx&&Number.isFinite(fx.quote_per_euro)?macroNumber(fx.quote_per_euro,4):'—',fx?.date)+
    row('Attese 6M',six&&Number.isFinite(six.six_month_rate_pct)?
        macroNumber(six.six_month_rate_pct,3)+'% · futures CORRA':'Proxy non certificato',six?.date)+
    '</div><div class="opMacroNote">Fotografia datata, non ultimo prezzo prima del comunicato. 2Y/10Y sono rendimenti governativi; i futures non sono OIS.</div></div>';
}
function macroReleaseCard(item){
 const ccy=item?.currency;
 if(!['USD','CAD'].includes(ccy))return '';
 const isUsd=ccy==='USD';
 const expected=isUsd?'USD|2026-10-30|LABOUR_COST|Employment Cost Index':
                      'CAD|2026-10-30|GROWTH|Gross domestic product by industry';
 if(item.event_key!==expected)return '';
 const actual=Number.isFinite(item.official_actual_percent)?item.official_actual_percent:null;
 const forecast=Number.isFinite(item.secondary_consensus_percent)?item.secondary_consensus_percent:null;
 const surprise=Number.isFinite(item.actual_minus_frozen_consensus_pp)?item.actual_minus_frozen_consensus_pp:null;
 const validActual=(actual!==null&&forecast!==null&&surprise!==null&&
     Math.abs((actual-forecast)-surprise)<0.000001&&
     item.event_causality_verified===false&&item.eligible_for_Core_Beta_Forward===false);
 const state=MACRO_RELEASE_STATES[item.state]||'Stato operativo non verificato';
 const link=validActual?issuerActualLink(item.official_actual_source_url,ccy):null;
 const details=validActual?'<div class="opMacroStats">'+
    '<div><small>Consenso congelato (fonte B)</small><strong>'+esc(macroNumber(forecast,1,true))+'%</strong></div>'+
    '<div><small>Actual fonte ufficiale</small><strong>'+esc(macroNumber(actual,1,true))+'%</strong></div>'+
    '<div><small>Actual − consenso · p.p.</small><strong>'+esc(macroNumber(surprise,1,true))+'</strong></div></div>'+
    '<div class="opMacroNote">Differenza numerica, non un segnale hawkish/dovish né una previsione FX. Prima acquisizione del sistema: '+esc(fmtOfficialInstant(item.official_actual_captured_at_utc))+'.</div>'+
    (link?'<a class="opMacroSource" rel="noopener noreferrer" target="_blank" href="'+esc(link)+'">Comunicato ufficiale '+(isUsd?'BLS':'Statistics Canada')+'</a>':''):
    '<div class="opMacroStats"><div><small>Consenso congelato (fonte B)</small><strong>'+
      (forecast===null?'—':esc(macroNumber(forecast,1,true))+'%')+'</strong></div>'+
     '<div><small>Actual ufficiale</small><strong>In attesa</strong></div>'+
     '<div><small>Sorpresa numerica</small><strong>Non calcolabile</strong></div></div>';
 const title=isUsd?'Costo del lavoro USA · ECI Q3':'PIL mensile Canada · agosto';
 return '<article class="opCard opMacroCard" data-kind="macro-evidence" data-ccy="'+ccy+
    '" data-stage="'+esc(item.state||'UNVERIFIED')+'">'+
    '<div class="opTop"><div class="opCcy">'+FLAGS[ccy]+' '+ccy+'</div>'+
    '<div class="opDate">'+esc(fmtOfficialInstant(item.scheduled_utc))+'</div></div>'+
    '<h3>'+esc(title)+'</h3>'+
    '<div class="opMacroStage">'+esc(state)+'</div>'+
    details+eventMarketBefore(item)+
    (validActual?eventSourceContext(item):'')+
    '<div class="opMacroNote"><b>Reazione evento → mercato non dimostrata.</b> OIS intraday, CB Want/Can e segnali operativi non certificati.</div></article>';
}
function macroReleaseLane(context){
 const intro='<div class="opSection">Dati macro · consenso, pubblicazione e mercato</div>'+
   '<div class="opSub">Due eventi del 30 ottobre 2026. Previsione secondaria congelata prima dell’annuncio; actual solo da comunicati ufficiali; prezzi giornalieri distinti dalla reazione alla notizia.</div>';
 if(context?.schema!=='GMFQ_MACRO_EVENT_CONTEXT_DAILY_MATCH_V1'||!Array.isArray(context.events)){
   return intro+'<div class="opCard" data-kind="macro-evidence-unavailable">Collegamento macro non verificato: non mostrare numeri o movimenti stimati come actual.</div>';
 }
 const cards=context.events.map(macroReleaseCard).filter(Boolean).join('');
 return intro+'<div class="opGrid" data-gmfq-macro-events="2026-10-30">'+
    (cards||'<div class="opCard">Nessun evento ufficiale con consenso pre-release verificato.</div>')+
    '</div>';
}

function newsHtml(data){
 const items=(data.items||[]).map(x=>
   '<article class="opCard"><div class="opTop"><div class="opCcy">'+(FLAGS[x.ccy]||'')+' '+esc(x.ccy)+'</div><div class="opDate">'+esc(x.as_of||'—')+'</div></div><h3 class="'+(x.importance==='HIGH'?'opHigh':'')+'">'+esc(x.title)+'</h3><div class="opMeta">'+esc(x.detail)+'<br><span class="opTag">'+esc(x.category)+'</span> <span class="opTag">'+esc(x.quality||'')+'</span>'+(x.source?'<br>Fonte: '+esc(x.source):'')+'</div></article>'
 ).join('');
 const external=data.official_releases||{};
 const state=external.status||'UNAVAILABLE_NOT_CHECKED';
 const sources=(external.sources||[]).map(s=>esc(s.source)+': '+esc(s.status)).join(' · ');
 const headlines=Array.isArray(external.headlines)?external.headlines:[];
 const monitoring=headlines.filter(x=>releaseContext(x).tier==='MONITOR')
    .map(renderOfficialRelease).join('');
 const context=headlines.filter(x=>releaseContext(x).tier!=='MONITOR')
    .map(renderOfficialRelease).join('');
 const desc=state==='VERIFIED_OFFICIAL_RELEASES'?'Pubblicazioni datate da fonti ufficiali; copertura per fonte consultabile sotto':
   state==='PARTIAL_SOURCES'?'Copertura parziale: una o più fonti non rispondono':
   state==='VERIFIED_NO_RECENT_RELEASES'?'Fonti verificate, nessuna comunicazione nei dieci giorni esaminati':
   'Fonti non verificate: nessuna notizia esterna viene presentata come corrente';
 return '<div class="opDesk" data-gmfq-operational="news">'+
 '<div class="opHero"><div class="opEyebrow">What changed · source-verified research desk</div><div class="opTitle">News Pulse operativo</div><div class="opSub">Due livelli distinti: pubblicazioni ufficiali delle banche centrali G8 e dell’EIA, e movimenti misurati da fonti operative. Non è ancora un notiziario finanziario globale. Non attribuiamo causalmente i movimenti ai comunicati.</div></div>'+
 macroReleaseLane(data.macro_event_market_context)+
 '<div class="opSection">Comunicazioni ufficiali · banche centrali G8 ed energia EIA</div><div class="opMeta">'+esc(desc)+' · Ultimo controllo (Roma): '+esc(external.last_attempt_day_rome||'—')+' · '+(sources||'Nessun controllo disponibile')+'</div>'+
 '<div class="opSection">Da monitorare · tema economico riconoscibile</div><div class="opSub">Sono soltanto piste di ricerca derivate dai titoli; nessuna conclusione su orientamento delle banche centrali, sorpresa macro o prezzo.</div><div class="opGrid">'+
 (monitoring||'<div class="opCard">Nessun comunicato con rilevanza macro/energia identificabile dal solo titolo.</div>')+
 '</div><div class="opSection">Da approfondire · comunicazioni e contesto</div><div class="opSub">Interviste, notizie regolamentari e altri testi ufficiali non sono automaticamente segnali FX o petrolio.</div><div class="opGrid">'+
 (context||'<div class="opCard">Nessun altro comunicato recente verificato.</div>')+
 '</div><div class="opSection">Segnali quantitativi · OIS e futures</div><div class="opSub">Ultima osservazione di mercato: <b>'+esc(data.content_as_of||'—')+'</b>. Il giorno dell’ultimo controllo delle fonti non cambia la data economica di un segnale.</div><div class="opGrid">'+
 (items||'<div class="opCard">Nessun nuovo segnale validato disponibile.</div>')+
 '</div><div class="opFoot">Inputs quantitativi: '+esc((data.scope?.inputs||[]).join(' · '))+'. Fonti esterne limitate ai feed ufficiali di banche centrali G8 ed EIA: titoli, orari, link originali e domande di monitoraggio ricavate dai soli titoli; nessun impatto sui prezzi attribuito ai comunicati. NULL non diventa mai 0 bp.</div></div>';
}
let cache=null;
async function load(){if(cache)return cache;const [c,n]=await Promise.all([fetch('live_data/sections/CALENDAR_OPERATIONAL_VIEW.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('calendar '+r.status);return r.json()}),fetch('live_data/sections/NEWS_PULSE_OPERATIONAL.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('news '+r.status);return r.json()})]);cache={c,n};return cache;}
async function render(){css();try{const {c,n}=await load();const cal=document.getElementById('calendar'),news=document.getElementById('news');if(cal&&!cal.querySelector('[data-gmfq-operational="calendar"]'))cal.innerHTML=calendarHtml(c);if(news&&!news.querySelector('[data-gmfq-operational="news"]'))news.innerHTML=newsHtml(n);window.GMFQ_CALENDAR_NEWS_OPERATIONAL={status:'ACTIVE',calendar:c.status,news:n.status,calendar_events:(c.events||[]).length,macro_events:(c.events||[]).filter(e=>e.event_type!=='CENTRAL_BANK_DECISION').length,consensus_available:c.coverage?.consensus_available_events||0,news_items:(n.items||[]).length,content_as_of:n.content_as_of};}catch(err){console.error('calendar-news-operational',err);window.GMFQ_CALENDAR_NEWS_OPERATIONAL={status:'ERROR',error:String(err)};}}
const obs=new MutationObserver(()=>{const c=document.getElementById('calendar'),n=document.getElementById('news');if((c&&!c.querySelector('[data-gmfq-operational="calendar"]'))||(n&&!n.querySelector('[data-gmfq-operational="news"]')))render();});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{render();obs.observe(document.body,{childList:true,subtree:true});},{once:true});else{render();obs.observe(document.body,{childList:true,subtree:true});}
})();
