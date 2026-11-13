'use strict';
/* Source-dated thesis monitor. A model-label change is not an observed flow or
 * a trade signal. Select only the two latest unique canonical daily snapshots.
 */
(function(root){
 const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
 const fmt=x=>day(x)?x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4):'n.d.';
 const text=x=>typeof x==='string'&&x.trim()?x:'Non classificato';
 const checks=[
  ['fav','Valuta strutturalmente favorita'],['quality','Qualità del dossier'],
  ['price.text','Prezzo'],['timing.text','Timing'],
  ['cot.text','Etichetta COT'],['liquidity.text','Liquidità']
 ];
 function field(item,key){
  return key.split('.').reduce((v,k)=>v&&typeof v==='object'?v[k]:null,item)??null;
 }
 function flatten(profile){
  const s=profile?.setup||{},f=profile?.decision_frame||s.structural||{};
  return {fav:s.structuralFav||null,quality:s.quality||null,
   price:{state:s.price?.state||null,text:s.price?.text||null},
   timing:{state:s.timing?.state||null,text:s.timing?.text||null},
   cot:{state:s.cot?.state||null,text:s.cot?.text||null},
   liquidity:{state:s.liquidity?.state||null,text:s.liquidity?.text||null},
   structural:{relation:f.relation||null,missing:f.missing||null,watch:f.watch||null}};
 }
 function validated(history,current){
  if(history?.schema!=='GMFQ_PAIR_THESIS_HISTORY_V1'||history.pair_count!==28||
    !Array.isArray(history.snapshots)||history.snapshots.length<2||
    !day(current?.price_asof)||Object.keys(current?.pairs||{}).length!==28)return null;
  const arr=history.snapshots;
  if(arr.some((x,i)=>!day(x.price_asof)||!day(x.macro_baseline_asof)||
   Object.keys(x.pairs||{}).length!==28||(i>0&&x.price_asof<=arr[i-1].price_asof)))return null;
  const latest=arr.at(-1),previous=arr.at(-2);
  // Never compare a "current" model with a previous future or stale snapshot.
  if(current.price_asof!==latest.price_asof||!day(previous.price_asof)||
   current.macro_baseline_asof!==latest.macro_baseline_asof)return null;
  if(Object.keys(current.pairs).some(k=>!latest.pairs[k]||!previous.pairs[k]))return null;
  // A same-date rebuild is NOT a day-to-day change. Preserve the genuine
  // two archived daily snapshots even if the displayed model was recomputed.
  // In that case the archive is NEVER labelled as the current live dossier.
  const recalculatedPairs=Object.keys(current.pairs).filter(k=>{
   const p=flatten(current.pairs[k]),a=latest.pairs[k];
   return checks.some(([key])=>field(p,key)!==field(a,key));
  }).sort();
  return {latest,previous,archivedOnly:recalculatedPairs.length>0,
   recalculatedPairs};
 }
 function analyze(current,history,pair){
  const snapshots=validated(history,current);
  if(!snapshots)return readiness(current,history);
  const {latest,previous,archivedOnly,recalculatedPairs}=snapshots,
   keys=Object.keys(current.pairs).sort();
  const now=archivedOnly?latest.pairs[pair]:flatten(current.pairs[pair]),
   before=previous.pairs[pair];
  if(!before||!latest.pairs[pair])return {ready:false,reason:'Coppia non presente in entrambi gli snapshot ufficiali.'};
  const details=checks.map(([key,name])=>({
   key,name,prev:field(before,key),curr:field(now,key),
   changed:field(before,key)!==field(now,key)}));
  const currentEvidence={
   fav:now.fav,quality:now.quality,priceText:now.price.text,timingText:now.timing.text,
   cotText:now.cot.text,liquidityText:now.liquidity.text,
   missing:now.structural.missing||'Conferme da verificare sul dossier corrente.',
   watch:now.structural.watch||'Attendere una nuova evidenza comparabile.',
   structural:now.structural.relation||'Struttura non classificata'};
  const changed=details.filter(x=>x.changed);
  const summary={total:keys.length,quality:0,price:0,timing:0,cot:0,fav:0,liquidity:0,
   any:0,unchanged:0};
  for(const k of keys){
   const left=previous.pairs[k],
    right=archivedOnly?latest.pairs[k]:flatten(current.pairs[k]);
   const diffs=checks.filter(([key])=>field(left,key)!==field(right,key)).map(([key])=>key);
   if(diffs.length)summary.any++;else summary.unchanged++;
   if(diffs.includes('quality'))summary.quality++;
   if(diffs.includes('price.text'))summary.price++;
   if(diffs.includes('timing.text'))summary.timing++;
   if(diffs.includes('cot.text'))summary.cot++;
   if(diffs.includes('fav'))summary.fav++;
   if(diffs.includes('liquidity.text'))summary.liquidity++;
  }
  const macroSame=previous.macro_baseline_asof===latest.macro_baseline_asof;
  const observations=changed.length?changed.map(x=>x.name+': '+text(x.prev)+' → '+text(x.curr)+'.').join(' '):
   'Le classificazioni confrontate non sono cambiate tra le due osservazioni disponibili.';
  const judgement=!changed.length?'Nessun cambiamento nelle sei classificazioni confrontabili. Non equivale a tesi confermata.':
   changed.some(x=>x.key==='fav')?'È cambiata la gamba strutturalmente favorita dal modello: ricontrollare le fonti prima di attribuirlo a una svolta macro.':
   changed.some(x=>x.key==='price.text')?'È cambiato il giudizio sintetico sul prezzo: da verificare rispetto al movimento osservato e al pricing dei tassi.':
   changed.some(x=>x.key==='quality')?'È cambiata la classificazione di qualità del dossier; non è automaticamente un miglioramento né un segnale di ingresso.':
   'Sono cambiati indicatori secondari del modello, mentre la direzione strutturale e lo stato sintetico del prezzo non hanno fornito una nuova conferma.';
  return {ready:true,asof:latest.price_asof,previousAsOf:previous.price_asof,
   baseline:latest.macro_baseline_asof,macroSame,summary,details,changed,observations,
   judgement,current:currentEvidence,pair,archivedOnly,recalculatedPairs};
 }
 function render(current,history,pair){
  const x=analyze(current,history,pair);
  if(!x.ready)return '<section class="panel thesis-monitor" id="fx-thesis-monitor"><div class="panel-head"><div><span class="mini-overline">MONITOR TESI FX / CONFRONTO STORICO</span><h2>Cosa è cambiato dall’ultima osservazione?</h2></div></div>'+
    '<p class="thesis-unavailable">'+esc(x.reason)+'</p></section>';
  const delta=x.changed.length?x.changed.map(c=>'<div class="thesis-change"><span>'+esc(c.name)+'</span><strong>'+esc(text(c.prev))+'</strong><span class="thesis-arrow" aria-label="diventa">→</span><strong>'+esc(text(c.curr))+'</strong></div>').join(''):
   '<p class="thesis-same">Nessun cambiamento nelle classificazioni confrontate: non significa che macro, prezzi e rischi siano rimasti identici in ogni dettaglio.</p>';
  const s=x.summary;
  const archiveNote=x.archivedOnly?
   '<p class="thesis-frozen"><strong>Solo confronto storico archiviato, non dossier corrente.</strong> '+
   x.recalculatedPairs.length+' coppie sono state ricalcolate sulla stessa data di fixing ('+
   esc(x.recalculatedPairs.map(k=>k.slice(0,3)+'/'+k.slice(3)).join(', '))+
   '). Le nuove etichette non rappresentano movimenti fra sedute. Per la lettura corrente usa il dossier della coppia.</p>':'';
  return '<section class="panel thesis-monitor" id="fx-thesis-monitor"><div class="panel-head"><div><span class="mini-overline">MONITOR TESI FX · 28 COPPIE</span>'+
   '<h2>Che cosa è cambiato davvero?</h2><p>Confronto tra snapshot di prezzo '+fmt(x.previousAsOf)+' → '+fmt(x.asof)+
   '. Non è una lettura intraday e non sovrappone sedute differenti.</p></div></div>'+archiveNote+
   '<div class="thesis-summary"><span><b>'+s.any+'/28</b> coppie con almeno una variazione</span>'+
   '<span><b>'+s.fav+'</b> vantaggio strutturale</span><span><b>'+s.price+'</b> prezzo</span>'+
   '<span><b>'+s.quality+'</b> qualità</span><span><b>'+s.timing+'</b> timing</span><span><b>'+s.cot+'</b> COT</span></div>'+
   '<div class="thesis-layout"><div class="thesis-detail"><div class="thesis-pair-title"><span>FOCUS · '+esc(pair.slice(0,3)+'/'+pair.slice(3,6))+'</span>'+
   '<strong>'+x.changed.length+' cambiamenti classificati</strong></div>'+
   '<h3>'+esc(x.judgement)+'</h3>'+delta+
   '<p class="thesis-frozen"><strong>Baseline macro '+fmt(x.baseline)+'.</strong> '+
    (x.macroSame?'Nessun aggiornamento della baseline macro fra i due snapshot: i cambiamenti osservati non dimostrano nuove sorprese economiche.':
    'La baseline riportata è cambiata: serve verificare i rilasci e la data di acquisizione, non inferire automaticamente una sorpresa.')+'</p></div>'+
   '<aside class="thesis-next"><span class="mini-overline">COSA VERIFICARE ADESSO</span><h3>La tesi resta diversa dal timing.</h3>'+
   '<p><strong>'+(x.archivedOnly?'Struttura nello snapshot archiviato.':'Struttura attuale.')+'</strong> '+esc(x.current.structural)+'</p>'+
   '<p><strong>Conferme mancanti.</strong> '+esc(x.current.missing)+'</p>'+
   '<p><strong>Controllare.</strong> '+esc(x.current.watch)+'</p></aside></div>'+
   '<p class="thesis-footer">Monitor descrittivo: variazioni di etichette del motore, non flussi istituzionali osservati o edge quantitativo. Il COT qui segnala soltanto una diversa lettura del posizionamento nel modello; non prova che un operatore abbia aperto o chiuso posizioni. La frequenza dipende dal fixing BCE, non dalla frequenza di aggiornamento della pagina.</p></section>';
 }
 // Daily 28-pair pulse: never equate changes of classification with new
 // macro evidence, price momentum, flows or trade attractiveness.
 function readiness(current,history){
  const latest=history?.snapshots?.at(-1);
  if(history?.schema==='GMFQ_PAIR_THESIS_HISTORY_V1'&&
     current?.price_asof&&latest?.price_asof===current.price_asof &&
     current.macro_baseline_asof===latest.macro_baseline_asof &&
     Object.keys(current.pairs||{}).length===28){
    const drift=Object.keys(current.pairs).filter(k=>{
     const old=latest.pairs?.[k];
     return !old||checks.some(([key])=>field(flatten(current.pairs[k]),key)!==field(old,key));
    });
    if(drift.length)return {ready:false,drift:drift.length,
     reason:'Confronto giornaliero non verificabile: il modello è stato ricalcolato sulla stessa seduta. '+drift.length+
      ' coppie hanno etichette diverse dallo storico archiviato. Non sono cambiamenti tra giorni e non vanno spacciati per nuovi segnali.'};
  }
  return {ready:false,drift:0,
   reason:'Confronto giornaliero non verificabile: storico e modello non ancora allineati. Nessuna variazione viene inventata.'};
 }
 function overview(current,history){
  const pairKeys=Object.keys(current?.pairs||{}).sort();
  const snapshots=validated(history,current);
  if(!snapshots)return readiness(current,history);
  const {latest,previous,archivedOnly,recalculatedPairs}=snapshots;
  const score={'fav':6,'quality':5,'price.text':4,'timing.text':3,
   'cot.text':2,'liquidity.text':1};
  const changes=[];
  const dimensions=Object.fromEntries(checks.map(([key])=>[key,0]));
  for(const pair of pairKeys){
   const previousPair=previous.pairs[pair],
    now=archivedOnly?latest.pairs[pair]:flatten(current.pairs[pair]);
   const diffs=checks.filter(([key])=>field(previousPair,key)!==field(now,key));
   if(!diffs.length)continue;
   for(const [key] of diffs)dimensions[key]++;
   changes.push({
    pair,labels:diffs.map(([,name])=>name),
    keys:diffs.map(([key])=>key),
    weight:Math.max(...diffs.map(([key])=>score[key]||0))
   });
  }
  changes.sort((a,b)=>b.weight-a.weight||b.keys.length-a.keys.length||
    a.pair.localeCompare(b.pair));
  const coreChanges=changes.filter(x=>x.keys.includes('fav')||x.keys.includes('quality'));
  const priceChanges=changes.filter(x=>x.keys.includes('price.text'));
  const secondary=changes.filter(x=>!x.keys.includes('fav')&&
   !x.keys.includes('quality')&&!x.keys.includes('price.text'));
  return {ready:true,asof:latest.price_asof,previousAsOf:previous.price_asof,
   baseline:latest.macro_baseline_asof,macroSame:previous.macro_baseline_asof===latest.macro_baseline_asof,
   total:pairKeys.length,changedCount:changes.length,coreCount:coreChanges.length,
   priceCount:priceChanges.length,secondaryCount:secondary.length,
   changes,dimensions,archivedOnly,recalculatedPairs};
 }
 function renderPulse(current,history){
  const x=overview(current,history);
  const opening='<section class="pairs-thesis-pulse" aria-label="Monitor sintetico delle tesi delle 28 coppie">'+
   '<span class="mini-overline">MONITOR TESI FX / COSA È CAMBIATO</span>';
  if(!x.ready)return opening+'<p class="pairs-thesis-pulse-unavailable">'+esc(x.reason)+
   '</p></section>';
  const first=x.changedCount===0?
   'Tra i due fixing confrontabili, nessuna delle sei classificazioni monitorate è cambiata nelle 28 coppie.':
   'Tra i due fixing confrontabili, '+x.changedCount+' delle 28 coppie mostrano almeno una classificazione diversa.';
  const meaning=x.changedCount===0?
   ' Non significa che i prezzi siano rimasti fermi, né che le tesi siano state confermate.':
   ' Sono cambiamenti del dossier, non prove di nuovi flussi o segnali di ingresso.';
  const archiveNote=x.archivedOnly?
   '<p class="pairs-thesis-pulse-unavailable">Solo storico archiviato: '+
   x.recalculatedPairs.length+' coppie ricalcolate sulla stessa seduta. Nessuna differenza di versione è trattata come movimento giornaliero.</p>':'';
  const main=opening+archiveNote+
   '<p class="pairs-thesis-pulse-story"><strong>'+esc(first)+'</strong>'+esc(meaning)+'</p>'+
   '<p class="pairs-thesis-pulse-dates">Fixing BCE '+fmt(x.previousAsOf)+' → '+fmt(x.asof)+
   ' · Riferimento macro '+fmt(x.baseline)+
   (x.macroSame?' (non aggiornato tra i due snapshot)':' (riferimento cambiato: verificare le fonti)')+
   ' · Nessun dato intraday</p>';
  if(!x.changedCount)return main+'</section>';
  const named=x.changes.slice(0,5);
  const extra=x.changedCount>5?' · altre '+(x.changedCount-5)+' coppie con differenze':'';
  return main+'<details class="pairs-thesis-pulse-details"><summary>Quali coppie richiedono una nuova verifica?'+extra+'</summary>'+
   '<div class="pairs-thesis-pulse-rows">'+named.map(item=>
    '<div class="pairs-thesis-pulse-row"><strong>'+esc(item.pair.slice(0,3)+'/'+item.pair.slice(3))+
    '</strong><span>'+esc(item.labels.join(' · '))+'</span></div>').join('')+
   '</div><p>Le coppie sono ordinate per rilevanza delle classificazioni variate; non per rendimento atteso o qualità del trade. Apri la singola coppia per la tesi e le invalidazioni.</p></details></section>';
 }
 const api={flatten,validated,analyze,render,overview,renderPulse,readiness};
 root.FXQuantThesisMonitor=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
