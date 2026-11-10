'use strict';
/* FX Quant NEXT COT desk V26.
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
  const stock=a.net>0?'net long':a.net<0?'net short':'net neutri';
  const trend=a.delta1>0?'migliora':a.delta1<0?'peggiora':'resta invariato';
  const impulse=finite(a.velocity)&&Math.abs(a.velocity)<0.25;
  const p=a.rounded===null?'classificazione storica non verificata':
   a.level+' (P'+a.rounded+', Z '+(finite(a.z)?sign(a.z,2):'n.d.')+')';
  const fact='Il netto '+trend+' di '+sign(a.delta1)+' contratti: Δ long '+sign(a.dLong)+
    ', Δ short '+sign(a.dShort)+'. I fondi restano '+stock+' ('+sign(a.net)+
    '). Il confronto 1W / 4W / 8W è '+sign(a.delta1)+' / '+sign(a.delta4)+
    ' / '+sign(a.delta8)+'; '+speed(a)+'.';
  const price=finite(a.price1)?
   'Sul fixing BCE '+a.priceLabel+' fra i due martedì: '+sign(a.price1,2)+
   '%. Il confronto dei segni è '+(impulse?'poco informativo perché il flusso netto è quasi fermo':a.priceState)+'.':
   'Il prezzo BCE della stessa settimana non è validato: nessuna conferma o divergenza attribuibile.';
  const position= 'Il posizionamento è '+p+'. '+
   (a.net<0&&a.rounded>=80?'Fascia storica alta NON significa che i fondi siano net long. ': '')+
   (a.crowd?'Il rapporto Net/OI supera la soglia di concentrazione ±30,0%: segnala affollamento, non inversione imminente. ':'')+
   (impulse?'L’ultimo netto si è mosso poco rispetto alla dimensione stimata del mercato futures. ':'')+
   (a.delta1>0?'Il pessimismo si riduce oppure aumenta il peso dei long, ma la composizione conta.':
    a.delta1<0?'La pressione ribassista cresce oppure si riducono i long; le due cause vanno separate.':
    'Il saldo quasi fermo può nascondere variazioni importanti nelle due gambe.');
  let judgment=position+' '+price+' Un flusso CFTC non dimostra ordini spot o un cambio macro; la tesi FX resta separata dal timing.';
  let verify=a.delta1>0?
   'Confermerebbero il recupero nuovi long persistenti e/o ulteriori short in calo, accompagnati da prezzo e differenziali di tasso coerenti.':
   a.delta1<0?
   'Confermerebbero la pressione ulteriori aumenti short o liquidazioni long, insieme a debolezza del prezzo e differenziali coerenti.':
   'Serve una nuova variazione netta significativa, verificando se arriva da long, short o entrambe le gambe.';
  verify+=' Indebolirebbero questa interpretazione flussi di verso opposto e prezzo divergente; non trasformiamo il solo estremo in un ingresso.';
  return {headline:(a.delta1>0?'I fondi riducono il posizionamento ribassista / aumentano i long.':
    a.delta1<0?'I fondi aumentano la pressione netta ribassista / riducono i long.':
    'Il netto è stabile: serve leggere long e short.') ,
    fact,flow:flowLabel(a),judgment,verify,price,speed:speed(a)};
 }
 function desk(all){
  if(!Array.isArray(all)||all.length!==8||all.some(a=>!a?.deskStats)||
     new Set(all.map(a=>a.last?.date)).size!==1)return null;
  const list=all.map(statisticsWithRef).filter(Boolean);
  function statisticsWithRef(a){return a.deskStats||null;}
  if(list.length!==8||list.some(x=>x.rounded===null))return null;
  const gains=[...list].sort((a,b)=>b.delta1-a.delta1);
  const losses=[...list].sort((a,b)=>a.delta1-b.delta1);
  const crowd=[...list].filter(x=>x.crowd).sort((a,b)=>Math.abs(b.netoi)-Math.abs(a.netoi));
  const divergent=list.filter(x=>x.priceState==='divergente'&&finite(x.price1)&&
    finite(x.velocity)&&Math.abs(x.velocity)>=.25);
  const top=gains[0],down=losses[0];
  return {asof:all[0].last.date,up:top,down,crowd,divergent,all:list,
   headline:'Il maggiore recupero del netto è '+top.ccy+' ('+sign(top.delta1)+
    ' contratti); la pressione più intensa della settimana è '+down.ccy+
    ' ('+sign(down.delta1)+').',
   summary: 'La fotografia CFTC racconta movimenti diversi: '+top.ccy+
    ' guida il recupero, '+down.ccy+' il deterioramento. '+
    (crowd.length?'L’alert Net/OI ±30% riguarda '+crowd.map(x=>x.ccy).join(' e ')+'. ':'')+
    (divergent.length?'Prezzo e netto divergono in '+divergent.map(x=>x.ccy).join(', ')+'. ':'')+
    'Sono variazioni di posizioni aggregate rilevate martedì, non flussi FX di oggi.',
   question:'Per capire se la rotazione continuerà servono nuovi long o short in modo persistente, fixing FX coerenti, macro relativa e differenziali dei tassi. Prezzo e COT non dimostrano causalità.'};
 }
 root.FXQuantCOTDeskV26={validatePrior,statistics,reading,desk,flowLabel,speed,sign};
 if(typeof module!=='undefined'&&module.exports)module.exports=root.FXQuantCOTDeskV26;
})(typeof window!=='undefined'?window:{});
