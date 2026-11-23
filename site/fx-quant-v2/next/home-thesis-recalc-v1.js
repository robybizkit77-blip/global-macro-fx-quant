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
   '<p>'+safeEscape(message)+'</p></div><div class="fx-recalc-date">'+
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
 const api={render,receiptOK,sourceMatches,outputMatches};
 root.FXQuantHomeThesisRecalc=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
