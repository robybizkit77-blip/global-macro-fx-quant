'use strict';
/*
 * FX Quant Next — G8 macro / market-pricing / FX bridge V1.
 *
 * This is a CONDITIONAL interpretation of independently observed series,
 * NOT an estimate of a central-bank decision, cause of FX moves, surprise
 * against consensus, policy probability, or a composite trading score.
 *
 * Only canonical verified weekly 6M OIS/futures repricing earns "observed".
 * NZD bank bill is a distinct basis-bearing directional proxy.
 * Secondary futures LEVELS cannot be called 1W repricing.
 * FX is relative strength over 20 common ECB fixes, NOT event-window return.
 * Macro estimates are hypotheses and never increase verified evidenceCount.
 */
(function(root){
 const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
 const number=x=>typeof x==='number'&&Number.isFinite(x);
 const day=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&
  Number.isFinite(Date.parse(s+'T00:00:00Z'))&&
  new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
 const age=(d,now)=>day(d)&&day(now)?
  (Date.parse(now+'T00:00:00Z')-Date.parse(d+'T00:00:00Z'))/864e5:null;
 const fresh=(d,now,max)=>{const n=age(d,now);return n!==null&&n>=0&&n<=max;};
 const isPeriod=(s,now,maxAge=4)=>{
  const m=typeof s==='string'&&/^\d{4}-(?:0[1-9]|1[0-2])(?:-\d{2})?$/.test(s)?s.slice(0,7):null;
  const p=day(now)?now.slice(0,7):null;
  return m&&p&&m<=p&&(Number(p.slice(0,4))-Number(m.slice(0,4)))*12+
    Number(p.slice(5,7))-Number(m.slice(5,7))<=maxAge;
 };
 const fmt=x=>number(x)?x.toLocaleString('it-IT',{maximumFractionDigits:1,minimumFractionDigits:1}):'—';
 const signed=x=>number(x)?(x>0?'+':x<0?'−':'')+fmt(Math.abs(x)):'—';
 const dir=d=>d==='SALE'?'sale':d==='SCENDE'?'scende':d==='STABILE'?'è stabile':'non verificata';
 const correct=['SALE','SCENDE','STABILE'];
 function macro(row,now){
  const m=row?.macro;
  const i=correct.includes(m?.inflationDirection)&&isPeriod(m.inflationPeriod,now)?
   m.inflationDirection:null;
  const l=correct.includes(m?.labourDirection)&&isPeriod(m.labourPeriod,now)?
   m.labourDirection:null;
  let pressure='INCOMPLETA',title='Ipotesi macro non risolta',
      why='Mancano direzioni recenti e comparabili di inflazione o disoccupazione.';
  if(i&&l){
   if(i==='SALE'&&l==='SCENDE'){
    pressure='RESTRITTIVA_CONDIZIONALE';title='Vincolo sui prezzi e lavoro relativamente solido';
    why='Inflazione in aumento e disoccupazione in calo possono ridurre, a parità di altre condizioni, lo spazio per un allentamento monetario.';
   }else if(i==='SCENDE'&&l==='SALE'){
    pressure='DISTENSIVA_CONDIZIONALE';title='Disinflazione e raffreddamento del lavoro';
    why='Inflazione in calo e disoccupazione in aumento possono aumentare lo spazio per un allentamento, se la banca centrale giudica persistenti entrambe.';
   }else if(i==='SALE'&&l==='SALE'){
    pressure='TENSIONE_CRESCITA_PREZZI';title='Prezzi in pressione e lavoro in deterioramento';
    why='Inflazione e disoccupazione entrambe in aumento mettono in tensione crescita e vincolo inflazionistico: non determinano da sole la direzione dei tassi.';
   }else if(i==='SCENDE'&&l==='SCENDE'){
    pressure='DISINFLAZIONE_RESILIENTE';title='Inflazione in calo con lavoro resistente';
    why='Disinflazione e disoccupazione in diminuzione sono compatibili con una crescita resistente: l’effetto sui tassi dipende da aspettative, salari e composizione dei prezzi.';
   }else{
    pressure='MISTA';title='Segnali macro senza una direzione monetaria univoca';
    why='Una delle due serie è stabile oppure le direzioni non separano chiaramente i rischi per la banca centrale.';
   }
  }else if(i||l){
   pressure='PARZIALE';title='Indicazione macro parziale';
   why='Solo '+(i?'l’inflazione':'la disoccupazione')+
    ' ha una direzione verificabile e recente: serve l’altra serie prima di costruire un’ipotesi monetaria.';
  }
  const dates='Inflazione '+dir(i)+' ('+(i?m.inflationPeriod:'n.d.')+
    '); disoccupazione '+dir(l)+' ('+(l?m.labourPeriod:'n.d.')+').';
  return {pressure,title,why,observed:dates,inflation:i,labour:l,
   eligibility:'OBSERVED_MACRO_DIRECTIONS_NOT_POLICY_FORECAST'};
 }
 function pricing(row,o,now){
  // Reuse the core's strict official 6m verification, not a private
  // interpretation of a level. The official definition has been checked
  // in currency-strength-reading.js, including kind and source age.
  if(row?.pricing?.ok===true&&number(row.pricing.change)&&
     o?.quality==='FONTE UFFICIALE'&&['OIS','FUTURES'].includes(o?.kind)&&
     o?.horizons?.['6m']?.as_of===o?.as_of&&
     fresh(o.as_of,now,7)&&
     number(o.horizons['6m'].change_1w_bp)&&
     Math.abs(o.horizons['6m'].change_1w_bp-row.pricing.change)<.001){
   const bp=row.pricing.change;
   return {tier:'VERIFICATO',bp,asof:o.as_of,kind:o.kind,
    side:bp>2?'SALE':bp< -2?'SCENDE':'POCO_VARIATO',
    text:'Il riferimento '+o.kind+' a sei mesi ha registrato '+signed(bp)+
     ' punti base nella settimana fino al '+o.as_of+'. È la variazione dello strumento: non prova la causa, una decisione futura o una probabilità di rialzo/taglio.'};
  }
  // The ASX NZ BB futures are verified MARKET prices but include bank-bill
  // credit / funding basis and therefore cannot certify RBNZ OIS repricing.
  const six=o?.horizons?.['6m'];
  if(o?.quality==='PROXY DIREZIONALE'&&o?.kind==='PROXY FUTURES'&&
     o?.source==='ASX official NZ futures end-of-day total traded report'&&
     o?.as_of===six?.as_of&&fresh(o.as_of,now,7)&&
     number(six?.change_1w_bp)&&Math.abs(six.change_1w_bp)<=100&&
     typeof six?.contract==='string'&&six.contract.length>3){
   const bp=six.change_1w_bp;
   return {tier:'PROXY',bp,asof:o.as_of,kind:'ASX NZ bank bill',
    side:bp>2?'SALE':bp< -2?'SCENDE':'POCO_VARIATO',
    text:'Il futures ASX NZ bank bill sei mesi è variato di '+signed(bp)+
     ' punti base su una settimana al '+o.as_of+
     '. È un proxy direzionale con basis di credito/funding: NON misura un OIS RBNZ o il repricing certificato della banca centrale.'};
  }
  return {tier:'NON_VERIFICATO',bp:null,asof:null,kind:null,side:null,
   text:'Manca una variazione settimanale verificata del riferimento monetario a sei mesi. Un livello futures secondario, anche recente, NON dimostra come siano cambiate le aspettative.'};
 }
 function projection(growth,labour,ccy,now){
  const messages=[];
  // Scenario macro in gap: even a favourable retrospective test does not
  // equal first-release data or a central-bank reaction.
  if(growth?.pseudoOOSQualified===true&&
     growth.skillValidatedPIT===false&&
     growth.quality==='REVISED_HISTORY_NOT_POINT_IN_TIME'&&
     ['MODELLO_RETROSPETTIVO_PROMETTENTE'].includes(growth.status)&&
     typeof growth.sourcePeriod==='string'&&isPeriod(growth.sourcePeriod,now,6)&&
     number(growth.deltaFromObserved)){
   const unit=growth.reportedRate?' punti percentuali':'%';
   messages.push('Scenario '+growth.label+' '+growth.targetPeriod+': '+
    signed(growth.deltaFromObserved)+unit+
    ' dall’ultima osservazione. Test retrospettivo favorevole, ma non è crescita già pubblicata né sorpresa contro consenso.');
  }
  const l=labour?.labour;
  if(l?.pseudoOOSQualified===true&&
     l.skillValidatedPIT===false&&
     l.status==='MODELLO_RETROSPETTIVO_PROMETTENTE'&&
     l.eligibleForCore===false&&
     isPeriod(l.sourcePeriod,now)&&number(l.estimatedChangePp)&&
     Math.abs(l.estimatedChangePp)>=.02){
   messages.push('Scenario disoccupazione '+ccy+' '+l.targetPeriod+': '+
    signed(l.estimatedChangePp)+' punti percentuali rispetto a '+
    l.sourcePeriod+'. Può suggerire un cambiamento da verificare alla prossima uscita, non una svolta già osservata.');
  }
  return messages;
 }
 function compare(m,p){
  if(p.tier==='NON_VERIFICATO')return {
   state:'IMPOSSIBILE_VERIFICARE',
   text:'Senza una variazione 6M verificata non possiamo affermare che il mercato abbia già prezzato questa ipotesi macro.'};
  if(!['RESTRITTIVA_CONDIZIONALE','DISTENSIVA_CONDIZIONALE'].includes(m.pressure))
   return {state:'NON_UNIVOCO',text:'I segnali macro non individuano una direzione monetaria unica; il movimento a sei mesi non può essere attribuito a una singola pubblicazione.'};
  if(p.side==='POCO_VARIATO')
   return {state:'POCO_MOVIMENTO',text:'Il riferimento a sei mesi è cambiato poco: non emerge un repricing settimanale ampio con cui confrontare l’ipotesi macro.'};
  const restrictive=m.pressure==='RESTRITTIVA_CONDIZIONALE';
  const compatible=restrictive?(p.side==='SALE'):(p.side==='SCENDE');
  const prefix=p.tier==='PROXY'?'Il proxy bank bill':'Il riferimento monetario sei mesi';
  return {state:compatible?'SEGNI_COMPATIBILI':'DIVERGENZA_DA_STUDIARE',
   text:prefix+(compatible?
    ' si muove nella direzione che sarebbe compatibile con l’ipotesi macro, ma le finestre e i driver sono differenti.':
    ' si muove nella direzione opposta all’ipotesi macro condizionata: è una divergenza da studiare, non un errore del mercato o un segnale d’ingresso.')+
    (p.tier==='PROXY'?' La variazione include anche basis e funding.':'')};
 }
 function fxReading(row,p){
  const x=row?.price;
  if(!x?.ok||!number(x.change)||!Number.isInteger(x.position)||
     x.position<1||x.position>8)
   return {state:'NON_DISPONIBILE',text:'Prezzo relativo BCE non verificato: impossibile stabilire se la valuta stia ricevendo sostegno.',positive:null};
  const state=x.change>=.15?'FORTE':x.change<=-.15?'DEBOLE':'LATERALE';
  const text='Su 20 fixing BCE comuni, la valuta ha '+(state==='FORTE'?'guadagnato':
    state==='DEBOLE'?'perso':'variato di poco')+' '+signed(x.change)+
    '% in media contro le altre sette G8 (posizione '+x.position+'/8).'+
    (p.tier!=='NON_VERIFICATO'?
      ' È una finestra diversa dal repricing a sei mesi su una settimana: la coerenza dei segni non dimostra causalità.':
      ' Senza un repricing monetario verificato non attribuiamo questo movimento alla banca centrale.');
  return {state,text,positive:state==='FORTE'?true:state==='DEBOLE'?false:null};
 }
 function one({row,ois,growth,labour,now}){
  if(!row||!FX.includes(row.ccy)||!day(now))return null;
  const m=macro(row,now),p=pricing(row,ois,now),
    c=compare(m,p),fx=fxReading(row,p),
    projected=projection(growth,labour,row.ccy,now);
  let headline=m.title+'.';
  if(p.tier==='VERIFICATO'){
   headline+=' Sul 6M '+(p.side==='SALE'?'rendimenti in rialzo':
    p.side==='SCENDE'?'rendimenti in calo':'movimento limitato')+
     ' ('+signed(p.bp)+' pb settimanali).';
  }else if(p.tier==='PROXY'){
   headline+=' Proxy NZD 6M '+signed(p.bp)+' pb: non OIS.';
  }else headline+=' Direzione 6M non verificata.';
  const watch='Confrontare le prossime sorprese su prezzi, salari, occupazione e crescita con il consenso; '+
   (p.tier==='VERIFICATO'?
    'ricontrollare la variazione dello stesso riferimento 6M e la risposta FX sulla stessa finestra dell’evento.':
    p.tier==='PROXY'?
    'verificare il proxy bank bill, il basis e una fonte monetaria più diretta; confrontare poi la risposta FX nello stesso intervallo.':
    'cercare prima una variazione 6M omogenea e datata, poi la reazione relativa FX.')+
   ' Nessun giudizio definitivo su ciò che è già prezzato senza serie delle attese e confronti con le sorprese.';
  return {currency:row.ccy,headline,macro:m,market:p,comparison:c,price:fx,
   scenarioNotes:projected,watch,
   governance:{influencesRanking:false,influencesPairEngine:false,
    officialPolicyProbability:false,causalityClaim:false,
    needsEventAlignedStudy:true}};
 }
 function analyze({rows,ois,growth,labour,now}){
  if(!Array.isArray(rows)||!day(now))return {schema:'GMFQ_G8_TRANSMISSION_V1',currencies:{},status:'UNAVAILABLE'};
  const currencies={};
  for(const row of rows){
   if(!FX.includes(row?.ccy)||currencies[row.ccy])continue;
   currencies[row.ccy]=one({row,ois:ois?.[row.ccy],growth:growth?.[row.ccy],
    labour:labour?.[row.ccy],now});
  }
  return {schema:'GMFQ_G8_TRANSMISSION_V1',status:'INTERPRETATION_ONLY',
   asof:now,currencies,limits:'Il modello è interpretativo: scenari di ricerca ≠ sorprese; 6M 1W ≠ FX 20 fixing; nessun punteggio o probabilità.'};
 }
 const api={analyze,one,macro,pricing,fxReading,compare};
 root.FXQuantG8Transmission=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
