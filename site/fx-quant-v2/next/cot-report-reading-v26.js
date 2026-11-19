'use strict';
/* FX Quant NEXT COT desk V26.1 — normalized G8 comparison and causal-neutral narratives.
 * Read-only view layer; CFTC V250 and weekly report stay untouched.
 * Current P104/Z104 use 104 STRICTLY PRECEDING net observations; older net
 * bridge comes from the previously archived CFTC Design Studio net series
 * (cross-checked against overlapping V250 dates, never its stale prices).
 */
(function(root){
 const finite=n=>typeof n==='number'&&Number.isFinite(n);
 const day=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s);
 const FXS=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
 const sign=(n,d=0)=>(n>0?'+':n<0?'−':'')+Math.abs(n).toLocaleString('it-IT',{minimumFractionDigits:d,maximumFractionDigits:d});
 const round=x=>Math.floor(x+0.5);
 const week=(a,b)=>(Date.parse(a+'T12:00:00Z')-Date.parse(b+'T12:00:00Z'))/86400000;
 function validatePrior(hist,arch,ccy){
  if(!FXS.includes(ccy)||!Array.isArray(hist)||hist.length<104||!arch||
     arch.schema!=='GMFQ_COT_DESIGN_STUDIO_V1'||
     arch.source!=='CFTC Legacy Non-Commercial via V250_COT_CHART_DATA')return null;
  const h=arch.currencies?.[ccy]?.history;
  if(!Array.isArray(h?.dates)||!Array.isArray(h?.net)||h.dates.length!==h.net.length||
     h.net.length<20)return null;
  if(!hist.every((x,i)=>day(x.date)&&finite(x.net)&&
    (!i||x.date>hist[i-1].date)))return null;
  const m=new Map();
  for(let i=0;i<h.dates.length;i++){
   const d=h.dates[i],n=h.net[i];
   if(!day(d)||!finite(n)||m.has(d))return null;
   m.set(d,n);
  }
  const mismatches=hist.filter(x=>m.has(x.date)&&m.get(x.date)!==x.net);
  const overlap=hist.filter(x=>m.has(x.date)).length;
  if(mismatches.length||overlap<8)return null;
  const sample=hist.slice(-104);
  if(week(sample.at(-1).date,sample.at(-2).date)>10||week(sample.at(-1).date,sample.at(-2).date)<4)return null;
  const predecessor=[...m.keys()].filter(d=>d<sample[0].date).sort().at(-1);
  if(!predecessor||week(sample[0].date,predecessor)!==7)return null;
  const prior=[m.get(predecessor),...sample.slice(0,-1).map(x=>x.net)];
  return prior.length===104&&prior.every(finite)?{
    prior,priorFirst:predecessor,priorLast:sample.at(-2).date,
    verifiedOverlaps:overlap,source:'archivio CFTC precedente verificato con V250'
  }:null;
 }
 function statistics(a,archive){
  const hist=a?.hist||[],last=hist.at(-1);
  if(!last||!finite(last.net)||!finite(last.netoi)||!finite(last.long)||!finite(last.short)||
     !finite(hist.at(-9)?.net))return null;
  const reference=validatePrior(hist,archive,a.ccy);
  const delta1=last.net-hist.at(-2).net;
  const delta4=last.net-hist.at(-5).net;
  const delta8=last.net-hist.at(-9).net;
  const dLong=last.long-hist.at(-2).long;
  const dShort=last.short-hist.at(-2).short;
  // Net/OI is published to three decimals in percent. Implied OI is an
  // approximation, never a CFTC certified standalone Open Interest.
  const impliedOI=Math.abs(last.netoi)>=0.5&&last.net!==0?
    (last.net/(last.netoi/100)):null;
  const velocity=finite(impliedOI)&&impliedOI>0?100*delta1/impliedOI:null;
  const crowd=Math.abs(Number(last.netoi.toFixed(1)))>=30;
  let p=null,z=null,mean=null,sd=null;
  if(reference){
   const v=reference.prior;
   mean=v.reduce((x,y)=>x+y,0)/104;
   sd=Math.sqrt(v.reduce((x,y)=>x+Math.pow(y-mean,2),0)/103);
   p=100*v.filter(x=>x<=last.net).length/104;
   z=sd>0?(last.net-mean)/sd:null;
  }
  const pr=finite(p)?round(p):null;
  const level=pr===null?'DA VERIFICARE':pr>=80?'EXTREME LONG':
    pr<=20?'EXTREME SHORT':'NEUTRALE';
  return {ccy:a.ccy,date:last.date,net:last.net,netoi:last.netoi,
   delta1,delta4,delta8,dLong,dShort,velocity,impliedOI,crowd,
   prior:reference,mean,sd,p,z,rounded:pr,level,price1:a.price1,
   priceState:a.priceState,priceLabel:a.priceRow?.priceLabel||null};
 }
 function flowLabel(a){
  if(a.dLong>0&&a.dShort<0)return 'Nuovi long e riduzione degli short';
  if(a.dLong<0&&a.dShort>0)return 'Nuovi short e liquidazione di long';
  if(a.dLong>0&&a.dShort>0)return 'Long e short entrambi in aumento';
  if(a.dLong<0&&a.dShort<0)return 'Long e short entrambi in riduzione';
  if(a.dLong>0)return 'Prevalgono nuovi long';
  if(a.dLong<0)return 'Prevale riduzione dei long';
  if(a.dShort>0)return 'Prevalgono nuovi short';
  if(a.dShort<0)return 'Prevalgono ricoperture short';
  return 'Variazioni lorde quasi assenti';
 }
 function speed(a){
  const avg4=a.delta4/4;
  if(a.delta1===0)return 'ultima settimana invariata';
  if(a.delta1*avg4<0)return 'la settimana inverte il segno della media delle ultime 4';
  if(Math.abs(a.delta1)>Math.abs(avg4)*1.4)return 'ritmo 1W superiore alla media 4W';
  if(Math.abs(a.delta1)<Math.abs(avg4)*.6)return 'ritmo 1W sotto la media 4W';
  return 'ritmo vicino alla media delle ultime 4 settimane';
 }
 function reading(a){
  if(!a||!finite(a.delta1))return null;
  const stock=a.net>0?'net long':a.net<0?'net short':'neutri';
  const size=finite(a.velocity)?Math.abs(a.velocity):null;
  const normalized=finite(a.velocity)?sign(a.velocity,2)+'% dell’OI stimato':'non confrontabile senza OI affidabile';
  const total=Math.abs(a.dLong)+Math.abs(a.dShort);
  const longShare=total?Math.abs(a.dLong)/total:0;
  const shortShare=total?Math.abs(a.dShort)/total:0;
  const cause=a.delta1>0?(
    a.dLong>0&&a.dShort<0?
      (shortShare>longShare?'ricoperture short prevalenti, insieme a nuovi long':'nuovi long prevalenti, insieme a ricoperture short'):
    a.dLong>0?'aumento dei long al netto dei nuovi short':
    a.dShort<0?'ricoperture short al netto delle liquidazioni long':'saldo in miglioramento senza componente lorda dominante'):
    a.delta1<0?(
    a.dLong<0&&a.dShort>0?
      (shortShare>longShare?'nuovi short prevalenti, insieme a liquidazioni long':'liquidazioni long prevalenti, insieme a nuovi short'):
    a.dShort>0?'nuovi short al netto degli acquisti long':
    a.dLong<0?'liquidazioni long al netto delle ricoperture short':'saldo in calo senza componente lorda dominante'):
    'saldo stabile nonostante i movimenti lordi';
  const stockTransition=a.net<0&&a.delta1>0?'I fondi rimangono net short: si riduce lo sbilanciamento ribassista, non si crea ancora un netto long. ':
    a.net>0&&a.delta1<0?'I fondi rimangono net long: si sta alleggerendo il netto rialzista. ':'';
  const weekTrend=a.delta1*a.delta4<0?
    'L’ultima settimana va contro il bilancio delle quattro settimane: possibile cambio di passo, non ancora svolta dimostrata. ':
    a.delta1===0?'Nessun impulso netto nell’ultima settimana. ':
    'Il verso della settimana coincide con il bilancio delle quattro settimane; '+speed(a)+'. ';
  const intensity=size===null?'Non possiamo misurare la forza relativa del flusso senza un denominatore comparabile. ':
    size<.25?'Il movimento pesa poco rispetto all’OI stimato: non va sovrainterpretato. ':
    size>=2?'Il movimento è consistente rispetto al mercato futures di questa valuta. ':
    'Il movimento è visibile rispetto all’OI stimato, ma serve continuità. ';
  const price=finite(a.price1)?
    'Fixing BCE '+a.priceLabel+' fra i due martedì: '+sign(a.price1,2)+'%. Il confronto è '+a.priceState+
    ' (non è la reazione alla pubblicazione del COT).':
    'Prezzo BCE sulla stessa settimana non validato: non attribuiamo alcuna conferma.';
  const priceJudgment=!finite(a.price1)?
    'Manca la verifica del prezzo nelle stesse date. ':
    size!==null&&size<.25?
    'Il confronto con il prezzo è poco informativo perché il netto varia appena. ':
    a.priceState==='coerente'?
    'Prezzo e cambiamento del netto sono coerenti nella settimana osservata, senza provare causalità. ':
    a.priceState==='divergente'?
    'Il prezzo non accompagna il cambiamento dei fondi: la lettura FX resta non confermata. ':
    'Il prezzo non dà una conferma conclusiva. ';
  const extreme=a.rounded===null?'Percentile storico non verificato. ':
    a.rounded>=80?'Il netto è nella parte alta dello storico P104, non necessariamente positivo. ':
    a.rounded<=20?'Il netto è nella parte bassa dello storico P104; un estremo può durare. ':'';
  const crowd=a.crowd?'Net/OI oltre ±30%: esposizione concentrata, non segnale automatico di inversione. ':'';
  const causePhrase=a.delta1>0?'miglioramento':a.delta1<0?'deterioramento':'stabilità';
  const fact='Il netto '+stock+' ('+sign(a.net)+' contratti) registra '+causePhrase+
    ' di '+sign(a.delta1)+' contratti: long '+sign(a.dLong)+
    ', short '+sign(a.dShort)+'. Motore principale: '+cause+
    '. Variazione normalizzata: '+normalized+'. Δ Net su 4W / 8W: '+
    sign(a.delta4)+' / '+sign(a.delta8)+' contratti.';
  const judgment=stockTransition+intensity+weekTrend+priceJudgment+extreme+crowd;
  const verify=a.delta1>0?
    (shortShare>longShare?
      'Controlla se il prossimo COT conferma ulteriori ricoperture e soprattutto se iniziano nuovi long persistenti. ':
      'Controlla se i nuovi long proseguono senza essere compensati da nuovi short. '):
    a.delta1<0?
    (shortShare>longShare?
      'Controlla se gli short aumentano ancora o se iniziano ricoperture. ':
      'Controlla se le liquidazioni long continuano o si stabilizzano. '):
    'Verifica quale componente lorda rompe la stabilità del netto. ';
  const monitoring=verify+(a.priceState==='divergente'?
    'Per rafforzare la tesi serve anche che il prezzo smetta di divergere e i differenziali di tasso siano coerenti.':
    'Confronta il nuovo flusso con prezzo e differenziali di tasso; una settimana opposta indebolirebbe la lettura.');
  return {headline:flowLabel(a),fact,flow:flowLabel(a),judgment,verify:monitoring,
    price,speed:speed(a),normalized,cause};
 }
 function desk(all){
  if(!Array.isArray(all)||all.length!==8||all.some(a=>!a?.deskStats)||
     new Set(all.map(a=>a.last?.date)).size!==1)return null;
  const list=all.map(a=>a.deskStats);
  if(list.some(x=>!x||x.rounded===null))return null;
  const comparable=list.every(x=>finite(x.velocity));
  const ranked=comparable?[...list].sort((a,b)=>b.velocity-a.velocity):[];
  const up=ranked.find(x=>x.velocity>0)||null;
  const down=[...ranked].reverse().find(x=>x.velocity<0)||null;
  const rises=list.filter(x=>x.delta1>0).length;
  const falls=list.filter(x=>x.delta1<0).length;
  const crowd=[...list].filter(x=>x.crowd).sort((a,b)=>Math.abs(b.netoi)-Math.abs(a.netoi));
  const divergent=list.filter(x=>x.priceState==='divergente'&&finite(x.price1)&&
    finite(x.velocity)&&Math.abs(x.velocity)>=.25);
  const format=x=>x.ccy+' ('+sign(x.velocity,2)+'% dell’OI stimato)';
  const headline=!comparable?
    'Classifica normalizzata sospesa: l’Open Interest stimato non è verificabile per tutte le otto valute.':
    up&&down?
      'Il recupero proporzionalmente più ampio è '+format(up)+
      '; la pressione ribassista relativa maggiore è '+format(down)+'.':
    up?'Prevale il recupero del netto; il maggiore è '+format(up)+'.':
    down?'Prevale il deterioramento del netto; il più intenso è '+format(down)+'.':
    'Nessuna variazione netta significativa nel G8 rispetto all’OI.';
  const summary='Nell’ultima rilevazione '+rises+' valute migliorano il netto, '+
    falls+' lo peggiorano e '+(8-rises-falls)+' restano stabili. '+
    (comparable?'La graduatoria usa Δ Net 1W / OI stimato, non i contratti assoluti dei diversi futures. ':
      'Senza denominatori comparabili non attribuiamo primati fra mercati diversi. ')+
    (crowd.length?'Concentrazione Net/OI oltre ±30%: '+crowd.map(x=>x.ccy).join(', ')+'. ':'')+
    (divergent.length?'Prezzo e netto divergono in '+divergent.map(x=>x.ccy).join(', ')+'. ':'')+
    'Sono stock di posizioni CFTC riferiti al martedì, non ordini spot odierni.';
  return {asof:all[0].last.date,up,down,comparable,crowd,divergent,all:list,headline,summary,
    question:'Il passo successivo è capire quali cambiamenti vengono da nuovi long o short e quali da chiusure. Solo persistenza, prezzo e tassi coerenti possono rafforzare la tesi FX: il COT non detta il timing.'};
 }
 root.FXQuantCOTDeskV26={validatePrior,statistics,reading,desk,flowLabel,speed,sign};
 if(typeof module!=='undefined'&&module.exports)module.exports=root.FXQuantCOTDeskV26;
})(typeof window!=='undefined'?window:{});
