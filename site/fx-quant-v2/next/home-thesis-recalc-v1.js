'use strict';
/* FX Quant Next — presentation-only, source-dated receipt for the independent
 * estimated G8/28 research layer. No changes to scoring or trading decisions.
 */
(function(root){
 const SCHEMA='GMFQ_NEXT_ESTIMATED_FX_RECALC_RECEIPT_V1';
 const STATUSES=new Set(['BASELINE_RECALC','NO_MATERIAL_THESIS_CHANGE','RECALCULATED_WITH_CHANGES']);
 const SOURCES={observed:'Macro G8',prices:'Prezzi BCE',ois:'OIS / futures',rates:'Rendimenti',model:'Modello 28 coppie'};
 const DAY=/^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$/;
 const FXS=new Set(['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD']);
 const iso=s=>typeof s==='string'&&DAY.test(s)&&
  !Number.isNaN(Date.parse(s+'T12:00:00Z'))&&
  new Date(s+'T12:00:00Z').toISOString().slice(0,10)===s;
 const finite=n=>typeof n==='number'&&Number.isFinite(n);
 const safeEscape=x=>String(x??'').replace(/[&<>"']/g,c=>({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
 })[c]);
 const safeDate=d=>iso(d)?d.slice(8,10)+'/'+d.slice(5,7)+'/'+d.slice(0,4):'n.d.';
 const asPair=k=>k.slice(0,3)+'/'+k.slice(3);
 const receiptOK=r=>{
  if(!r||r.schema!==SCHEMA||!STATUSES.has(r.status)||
   !iso(r.checkedDay)||!iso(r.fixingAsOf)||!iso(r.macroAsOf)||
   !Number.isFinite(Date.parse(r.checkedAtUtc))||
   r.fixingAsOf>r.checkedDay||r.macroAsOf>r.checkedDay||
   r.coverage?.currencies!==8||r.coverage?.pairs!==28||
   !Array.isArray(r.currencies)||r.currencies.length!==8||
   !r.pairs||Object.keys(r.pairs).length!==28||
   !r.governance||r.governance.estimatedNotValidated!==true||
   r.governance.recomputedCanonicalD!==false||
   r.governance.recomputedStructuralTheses!==false||
   r.governance.backtestCertified!==false||
   r.governance.tradeSignal!==false||
   !r.sourceHashes||Object.keys(SOURCES).some(k=>!/^[a-f0-9]{64}$/.test(r.sourceHashes[k]||''))||
   (r.inputChanges!==null&&(!Array.isArray(r.inputChanges)||
    r.inputChanges.some(k=>!Object.hasOwn(SOURCES,k))))||
   (r.changedPairs!==null&&!Array.isArray(r.changedPairs))||
   (r.changedRanks!==null&&!Array.isArray(r.changedRanks))||
   (r.factorChanges!==undefined&&r.factorChanges!==null&&
    (!Array.isArray(r.factorChanges)||r.factorChanges.some(x=>
     !FXS.has(x.ccy)||!r.currencies.some(c=>c.ccy===x.ccy&&c.rank===x.rank?.current)||
     !['score','macroScore','policyScore','priceScore'].every(k=>
      finite(x.changes?.[k]?.previous)&&
      finite(x.changes?.[k]?.current)&&finite(x.changes?.[k]?.delta)&&
      score(x.changes[k].current-x.changes[k].previous)===x.changes[k].delta)
    )))||
   (r.status==='NO_MATERIAL_THESIS_CHANGE'&&
     (r.changedPairs?.length>0||r.changedRanks?.length>0))||
   (r.status==='RECALCULATED_WITH_CHANGES'&&
     !(r.changedPairs?.length>0||r.changedRanks?.length>0)))
   return false;
  const seen=new Set();
  if(!r.currencies.every(c=>FXS.has(c.ccy)&&!seen.has(c.ccy)&&
    (seen.add(c.ccy),Number.isInteger(c.rank)&&c.rank>=1&&c.rank<=8&&
     finite(c.score)&&typeof c.monetaryQuality==='string')))
   return false;
  if(new Set(r.currencies.map(c=>c.rank)).size!==8)return false;
  if(!Object.keys(r.pairs).every(k=>/^[A-Z]{6}$/.test(k)&&
     FXS.has(k.slice(0,3))&&FXS.has(k.slice(3))&&k.slice(0,3)!==k.slice(3)))
   return false;
  return true;
 };
 // Content proof: even if dates agree, a new same-day macro/OIS/FX input
 // must invalidate the previous receipt until the producer has recalculated.
 const sourceMatches=(receipt,sourceHashes)=>Boolean(sourceHashes&&
  Object.keys(SOURCES).every(k=>typeof sourceHashes[k]==='string'&&
   sourceHashes[k]===receipt.sourceHashes[k]));
 const score=n=>finite(n)?Number(n.toFixed(6)):null;
 const outputMatches=(receipt,estimate)=>{
  if(estimate?.schema!=='GMFQ_MACRO_STRENGTH_ESTIMATED_V1'||
   !Array.isArray(estimate.pairs)||estimate.pairs.length!==28||
   !Array.isArray(estimate.currencies)||estimate.currencies.length!==8||
   estimate.coverage?.official6M!==receipt.coverage.official6M||
   estimate.coverage?.withGDPAcceleration!==receipt.coverage.withGDPAcceleration)
   return false;
  const pairs=new Map(estimate.pairs.map(p=>[p.key,p]));
  if(pairs.size!==28||Object.entries(receipt.pairs).some(([k,v])=>{
   const current=pairs.get(k);
   return !current||v.favored!==current.favored||
    v.thesis!==current.thesisStrength||v.timing!==current.tradeAttractiveness;
  }))return false;
  const currencies=new Map(estimate.currencies.map(c=>[c.ccy,c]));
  return currencies.size===8&&receipt.currencies.every(stored=>{
   const c=currencies.get(stored.ccy);
   return c&&stored.rank===c.rank&&stored.score===score(c.score)&&
    stored.macroScore===score(c.macroScore)&&
    stored.policyScore===score(c.policyScore)&&
    stored.priceScore===score(c.priceScore)&&
    stored.monetaryQuality===c.rate?.quality&&
    stored.monetaryAsOf===(c.rate?.asof??null)&&stored.partial===c.partial;
  });
 };
 // An estimated-model factor is not proof of economic causation of spot FX.
 const signed=x=>(x>0?'+':'')+String(Number(x.toFixed(2))).replace('.',',');
 function driverReading(r,estimate){
  if(r.status!=='RECALCULATED_WITH_CHANGES')return null;
  const changed=r.inputChanges||[];
  const unique=changed.length===1&&!r.methodChanged?changed[0]:null;
  const common=[...FXS].filter(ccy=>
   (r.changedPairs||[]).length>0&&r.changedPairs.every(p=>p.key.includes(ccy)));
  // One changed pair has two currencies: infer neither unless exactly one
  // has the relevant government 2Y proxy used by this rates-only calculation.
  const proxyCommon=common.filter(ccy=>
   estimate?.currencies?.find(c=>c.ccy===ccy)?.rate?.kind==='GOV_2Y_PROXY');
  const shared=common.length===1?common[0]:
   unique==='rates'&&proxyCommon.length===1?proxyCommon[0]:null;
  const raw=estimate?.currencies?.find(c=>c.ccy===shared);
  let reason='';
  if(r.methodChanged)reason='È cambiata anche la metodologia: non è possibile attribuire le revisioni a una sola fonte di mercato.';
  else if(unique==='rates'){
   reason='È cambiato soltanto il dataset dei rendimenti governativi; macro, pricing OIS/futures a 6 mesi e fixing BCE sono rimasti invariati. Nel modello i governativi 2Y contano solo dove sostituiscono un riferimento monetario ufficiale.';
   if(raw?.rate?.kind==='GOV_2Y_PROXY'&&finite(raw.rate.changeBp)&&finite(raw.policyScore)&&shared)
    reason+=' Per '+shared+' il 2Y settimanale è '+signed(raw.rate.changeBp)+
     ' pb, con contributo monetario '+signed(raw.policyScore)+
     ' (soglia direzionale ±5 pb): è un proxy, NON un OIS.';
  }else if(unique==='ois')reason='È cambiata la fonte OIS/futures 6M. Il modello usa variazioni settimanali dello stesso strumento, non confronti di livelli nominali tra paesi; i proxy rimangono distinti dalle fonti ufficiali.';
  else if(unique==='observed')reason='Sono cambiate le osservazioni macro G8. Il modello ricalcola il momentum relativo; revisioni delle serie non equivalgono necessariamente a nuove sorprese pubblicate oggi.';
  else if(unique==='prices')reason='Sono cambiati i fixing BCE: possono spostare forza relativa e timing, ma non dimostrano perché si sia mosso il prezzo.';
  else if(unique==='model')reason='È cambiato il catalogo dei modelli/coppie: la revisione non è attribuibile a una nuova sorpresa di mercato.';
  else reason='Sono cambiate più famiglie di dati, oppure manca un confronto univoco: la ricevuta identifica gli input senza dimostrare una singola causa di mercato.';
  // The first real receipt predates detailed factor-delta capture: do not
  // invent scores from an unrecorded previous period.
  const factors=(r.factorChanges||[]).filter(x=>
   x&&['macroScore','policyScore','priceScore'].some(k=>x.changes?.[k]?.delta!==0));
  const details=factors.slice(0,3).map(x=>{
   const labels={macroScore:'macro',policyScore:'monetaria',priceScore:'prezzo'};
   const deltas=['macroScore','policyScore','priceScore'].filter(k=>
    x.changes[k].delta!==0).map(k=>labels[k]+' '+signed(x.changes[k].previous)+
     ' → '+signed(x.changes[k].current)+' (Δ '+signed(x.changes[k].delta)+')');
   return x.ccy+': '+deltas.join('; ');
  });
  if(details.length&&!r.methodChanged)
   reason+=' Confronto misurato dei punteggi: '+details.join(' · ')+
    '. Questi sono contributi interni al modello, non cause dimostrate del prezzo.';
  const rankOnly=(r.factorChanges||[]).filter(x=>
   x.rank.previous!==x.rank.current&&
   ['score','macroScore','policyScore','priceScore'].every(k=>x.changes[k].delta===0));
  if(rankOnly.length)reason+=' '+rankOnly.map(x=>x.ccy).join(', ')+
   ' cambia posizione per effetto relativo, senza incremento del proprio punteggio.';
  else if(!r.factorChanges&&(r.changedRanks||[]).length)
   reason+=' Un cambio di posizione non prova da solo un rafforzamento autonomo della valuta.';
  const challenge=unique==='rates'?
   'Controlla il prossimo fixing FX e il 6M OIS ufficiale confrontabile: se divergono dal nuovo vantaggio relativo, la tesi resta fragile. Il 2Y governativo non misura soltanto le attese della banca centrale.':
   unique==='ois'?
   'Verifica strumento e contratto comparabili, poi valuta reazione del cambio e differenziali relativi: il repricing OIS non è automaticamente un trade.':
   unique==='prices'?
   'Servono conferme da macro e tassi comparabili: il trend dei fixing non dimostra una tesi fondamentale.':
   'Servono evidenze successive coerenti, differenziali comparabili e conferma del cambio: un nuovo punteggio non è un segnale d’ingresso.';
  const restricted=(r.changedPairs||[]).filter(p=>
   ['NON VALUTABILE','BASSA ORA','NON SUPPORTATA'].includes(p.current?.timing)).length;
  return {reason,challenge:challenge+(restricted?
   ' '+restricted+' tesi riviste hanno ancora attrattività bassa, non valutabile o non supportata.':'')};
 }
 const fallback=(reason,d)=>'<section class="fx-recalc-pulse fx-recalc-unverified" id="fx-recalc-pulse" data-recalc-state="UNVERIFIED" aria-label="Verifica ricalcolo FX">'+
   '<div class="fx-recalc-head"><span class="fx-recalc-overline">MONITOR TESI · G8 / 28 COPPIE</span>'+
   '<span class="fx-recalc-state">VERIFICA SOSPESA</span></div>'+
   '<p>Il ricalcolo delle tesi FX non è attestato sulla fotografia corrente. '+safeEscape(reason)+
   '</p><small>'+safeEscape(d||'Non confondere un indice rimasto invariato con un controllo eseguito.')+'</small></section>';
 function render({receipt,observed,prices,estimate,sourceHashes,today}={}){
  if(!receiptOK(receipt))return fallback('Ricevuta assente o non valida.');
  if(!iso(today)||receipt.checkedDay>today||
    (Date.parse(today+'T12:00:00Z')-Date.parse(receipt.checkedDay+'T12:00:00Z'))/864e5>7)
   return fallback('La verifica non è recente o la sua data è successiva alla seduta.',receipt.checkedDay);
  const checkedDay=receipt.checkedDay,fixing=receipt.fixingAsOf,macro=receipt.macroAsOf;
  if(observed?.generated_europe_rome_day!==macro||
    prices?.last_as_of!==fixing||
    estimate?.status!=='STIMA_OPERATIVA_NON_VALIDATA'||
    estimate?.asof!==macro||estimate?.priceAsOf!==fixing||
    estimate?.coverage?.currencies!==8||estimate?.coverage?.pairs!==28)
   return fallback('La ricevuta non coincide con le date o con la copertura delle fonti attualmente caricate.',
    'Ricevuta: Macro '+safeDate(macro)+' · FX '+safeDate(fixing)+'.');
  if(!sourceMatches(receipt,sourceHashes))
   return fallback('Uno o più file sorgente sono cambiati, oppure non sono stati verificati byte per byte. Serve una nuova ricevuta di ricalcolo.',
    'Il semplice allineamento delle date non certifica che le tesi FX siano invariate.');
  if(!outputMatches(receipt,estimate))
   return fallback('La classifica G8 o i giudizi delle 28 coppie non coincidono con il ricalcolo corrente.',
    'Il confronto usa il motore stimato di base, prima dei proxy aggiuntivi di ricerca.');
  const cp=receipt.changedPairs,cr=receipt.changedRanks;
  const interpretation=driverReading(receipt,estimate);
  const pairCount=Array.isArray(cp)?cp.length:null;
  const rankCount=Array.isArray(cr)?cr.length:null;
  const isBaseline=receipt.status==='BASELINE_RECALC';
  const unchanged=receipt.status==='NO_MATERIAL_THESIS_CHANGE';
  const message=isBaseline?
   'Prima fotografia verificata del modello stimato: 8 valute e 28 coppie ricalcolate. Il confronto con il ranking G8 precedente non è ancora disponibile.':
   unchanged?
   'Ricalcolo eseguito: nessuna delle 28 tesi FX stimate ha cambiato direzione, forza della tesi o attrattività rispetto allo storico disponibile.':
   'Ricalcolo eseguito: '+String(pairCount??0)+' tesi FX e '+String(rankCount??0)+
   ' posizioni nel ranking G8 della stima di base risultano cambiate.';
  const note=isBaseline?'Prima ricevuta, nessuna variazione da attribuire.':
   rankCount===null?'La variazione delle posizioni G8 non è confrontabile nella prima ricevuta.':
   rankCount===0?'Nessun cambio di posizione nella classifica G8 della stima di base.':
   String(rankCount)+' valute hanno cambiato posizione nella classifica G8 della stima di base.';
  const sources=receipt.inputChanges===null?
   'Confronto delle singole fonti disponibile dalle ricevute successive.':
   receipt.inputChanges.length?
   'Nuove impronte nei file: '+receipt.inputChanges.map(k=>SOURCES[k]).join(', ')+'.':
   'Nessuna modifica nelle impronte dei cinque input dal controllo precedente.';
  const sourceDates=receipt.previousMacroAsOf&&receipt.previousMacroAsOf!==macro?
   'Fotografia Macro '+safeDate(receipt.previousMacroAsOf)+' → '+safeDate(macro)+
   ' (non implica che ogni dato macro sia stato pubblicato oggi).':
   'Macro al '+safeDate(macro)+'.';
  const clean=x=>safeEscape(String(x??'—'));
  const pairChanges=(cp||[]).slice(0,4).map(change=>{
   if(!/^[A-Z]{6}$/.test(change.key||''))return '';
   const before=change.previous||{},after=change.current||{};
   const detail=[];
   if(before.favored!==after.favored)detail.push('preferenza '+clean(before.favored)+' → '+clean(after.favored));
   if(before.thesis!==after.thesis)detail.push('tesi '+clean(before.thesis)+' → '+clean(after.thesis));
   if(before.timing!==after.timing)detail.push('attrattività '+clean(before.timing)+' → '+clean(after.timing));
   return '<li><a href="#pairs?pair='+clean(change.key)+'">'+clean(asPair(change.key))+
     '</a>: '+(detail.join('; ')||'giudizio modificato')+'</li>';
  }).filter(Boolean).join('');
  const ranks=(cr||[]).slice(0,4).map(c=>{
   if(!FXS.has(c.ccy))return '';
   return '<li>'+clean(c.ccy)+': '+clean(c.previous)+' → '+clean(c.current)+'</li>';
  }).filter(Boolean).join('');
  const changes=(pairChanges||ranks)?
   '<div class="fx-recalc-changes"><strong>Cambiamenti da verificare</strong>'+
   (pairChanges?'<ul>'+pairChanges+'</ul>':'')+
   (ranks?'<ul>'+ranks+'</ul>':'')+
   (((cp||[]).length>4||(cr||[]).length>4)?'<p>Altri cambiamenti disponibili nei dossier e nella ricevuta completa.</p>':'')+'</div>':'';
  const state=unchanged?'same':isBaseline?'baseline':'changed';
  return '<section class="fx-recalc-pulse" id="fx-recalc-pulse" data-recalc-state="'+state+
   '" aria-label="Ricalcolo verificato delle tesi Forex">'+
   '<div class="fx-recalc-head"><span class="fx-recalc-overline">MONITOR TESI · G8 / 28 COPPIE</span>'+
   '<span class="fx-recalc-state">'+(unchanged?'TESI INVARIATE':isBaseline?'PRIMA RICEVUTA':'TESI RIVISTE')+'</span></div>'+
   '<div class="fx-recalc-core"><div><h2>Che cosa cambia nelle nostre tesi FX?</h2>'+
   '<p>'+safeEscape(message)+'</p>'+
   (interpretation?'<p class="fx-recalc-driver"><strong>Che cosa ha modificato la stima:</strong> '+
    safeEscape(interpretation.reason)+'</p>'+
    '<p class="fx-recalc-invalidation"><strong>Cosa potrebbe smentirla:</strong> '+
    safeEscape(interpretation.challenge)+'</p>':'')+
   '</div><div class="fx-recalc-date">'+
   '<span>Controllo '+safeDate(checkedDay)+'</span><strong>FX '+safeDate(fixing)+'</strong>'+
   '</div></div>'+
   '<div class="fx-recalc-links"><a href="#currencies">Valute G8</a>'+
   '<a href="#pairs">Classifica 28 coppie</a></div>'+
   '<details class="fx-recalc-details"><summary>Come lo sappiamo? Date, fonti e variazioni</summary>'+
   '<div class="fx-recalc-detail-body"><p>'+safeEscape(note)+'</p>'+
   '<p>'+safeEscape(sourceDates)+'</p><p>'+safeEscape(sources)+'</p>'+
   changes+
   '<p class="fx-recalc-caveat">Questa ricevuta riguarda il motore euristico stimato, non i punteggi canonici o un backtest. '+
   'La classifica finale del sito può integrare verifiche aggiuntive, per esempio sul CHF. '+
   'Input aggiornato non significa automaticamente causa dimostrata del movimento dei cambi.</p>'+
   '<a class="fx-recalc-proof" href="https://github.com/robybizkit77-blip/global-macro-fx-quant/blob/main/site/fx-quant-v2/next/pair-estimate-recalc-receipt-v1.json" '+
   'target="_blank" rel="noopener noreferrer">Verifica la ricevuta originale su GitHub</a>'+
   '</div></details></section>';
 }
 const api={render,receiptOK,sourceMatches,outputMatches,driverReading};
 root.FXQuantHomeThesisRecalc=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
