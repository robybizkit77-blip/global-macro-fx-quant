'use strict';
/* FX Quant Next V18 — economic interpretation for ALL 28 selected pairs.
 * OBSERVATIONS are kept distinct from model hypotheses, market pricing,
 * positioning and tested trade ideas. No fabricated consensus, OIS spreads
 * across mismatched instruments, current intraday FX, or forward edge.
 */
(function(){
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const isDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 const isPeriod=x=>typeof x==='string'&&/^\d{4}-\d{2}(?:-\d{2})?$/.test(x);
 const f=(n,d=2)=>finite(n)?n.toLocaleString('it-IT',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
 const signed=(n,d=2,u='')=>finite(n)?(n>0?'+':n<0?'−':'')+f(Math.abs(n),d)+u:'—';
 const when=x=>isPeriod(x)?x.substring(0,7):'data non verificata';
 const dir=(x,verbUp,verbDown)=>!finite(x)?'non valutabile':x>0?verbUp:x<0?verbDown:'invariata';
 function snapshotObs(x,now){
  const h=x?.history,day=x?.as_of;
  if(!isPeriod(day)||day.substring(0,7)>now.substring(0,7)||!Array.isArray(h)||h.length<2||
     !finite(h.at(-1))||!finite(h.at(-2))||!finite(x?.latest_value)||
     Math.abs(h.at(-1)-x.latest_value)>0.06)return null;
  return {asof:when(day),last:x.latest_value,change:h.at(-1)-h.at(-2)};
 }
 function countryMacro(name,macro,now){
  const i=snapshotObs(macro?.[name]?.inflation,now);
  const l=snapshotObs(macro?.[name]?.labour,now);
  if(!i&&!l)return name+': mancano osservazioni storiche coerenti per valutare il cambiamento.';
  const pieces=[];
  if(i)pieces.push('inflazione '+f(i.last)+'% ('+i.asof+', '+dir(i.change,'sale','scende')+
    ' di '+f(Math.abs(i.change))+' p.p.)');
  if(l)pieces.push('disoccupazione '+f(l.last)+'% ('+l.asof+', '+dir(l.change,'sale','scende')+
    ' di '+f(Math.abs(l.change))+' p.p.)');
  return name+': '+pieces.join('; ')+'.';
 }
 function pricingObs(ccy,ois,now){
  const row=ois?.currencies?.[ccy],v=row?.horizons?.['6m'];
  if(!v||!isDay(v.as_of)||v.as_of>now||!finite(v.rate))return null;
  const kind=String(row.kind||'FONTE NON CLASSIFICATA');
  const quality=String(row.quality||'QUALITÀ NON CLASSIFICATA');
  const sourceType=kind==='OIS'?'OIS':/FUTURES|PROXY/i.test(kind)?'futures/proxy':'strumento non omogeneo';
  return {ccy,asof:v.as_of,kind,quality,sourceType,rate:v.rate,change:v.change_1d_bp};
 }
 function cotObs(ccy,history,now){
  const x=history?.[ccy],d=x?.dates,n=d?.length||0;
  if(n<2||!isDay(d[n-1])||d[n-1]>now||!isDay(d[n-2])||d[n-2]>=d[n-1]||
     !['net','long','short'].every(k=>Array.isArray(x[k])&&
      x[k].length===n&&finite(x[k][n-1])&&finite(x[k][n-2])))return null;
  return {ccy,asof:d[n-1],net:x.net[n-1],change:x.net[n-1]-x.net[n-2],
   long:x.long[n-1]-x.long[n-2],short:x.short[n-1]-x.short[n-2]};
 }
 function interpret({key,model,macro,ois,cot,profile,ratesView,now}){
  const p=model?.pairs?.[key],valid=typeof key==='string'&&/^[A-Z]{6}$/.test(key)&&
    key.substring(0,3)!==key.substring(3,6)&&p&&isDay(now);
  if(!valid)return {available:false,headline:'Confronto non verificabile',judgement:'Nessuna tesi ricostruita senza uno snapshot valido.'};
  const a=key.slice(0,3),b=key.slice(3),setup=p.setup||{},frame=p.decision_frame||{};
  const fav=frame.fav===a||frame.fav===b?frame.fav:
    setup.structuralFav===a||setup.structuralFav===b?setup.structuralFav:null;
  const quality=setup.quality||'NON VALUTABILE',aligned=Boolean(
    profile?.fresh&&profile?.asof===model.price_asof&&
    profile?.closes?.length>=22&&profile?.key===key);
  const macroDate=isDay(model.macro_baseline_asof)?model.macro_baseline_asof:'non certificata';
  const datedModel=isDay(model.price_asof)&&model.price_asof<=now;
  const macroReading=countryMacro(a,macro,now)+' '+countryMacro(b,macro,now)+
    ' Questi sono livelli e variazioni osservate, non sorprese rispetto al consenso; le definizioni e i periodi possono differire.';
  const x=pricingObs(a,ois,now),y=pricingObs(b,ois,now);
  const pricePart=z=>z.ccy+' '+z.sourceType+' 6M '+f(z.rate,3)+'% ('+z.asof+
    '; '+(finite(z.change)?'variazione 1D '+signed(z.change,1,' pb'):'variazione 1D non verificata')+
    '; '+z.quality.toLowerCase()+')';
  let pricing=(!x&&!y)?'Non abbiamo due osservazioni monetarie 6M utilizzabili, quindi nessuna conclusione sul repricing relativo.'
    :(x?pricePart(x):a+' senza 6M verificabile')+'; '+(y?pricePart(y):b+' senza 6M verificabile')+'.';
  if(x||y)pricing+=' Non calcoliamo uno spread monetario: strumenti, scadenze e date non sono necessariamente omogenei.';
  let relation='La verifica con rendimenti governativi 2Y e fixing BCE sulle stesse date non è disponibile.';
  if(ratesView?.ready&&ratesView.short){
   const m=ratesView.short,concord=m.direction==='STESSO SEGNO'?'si muovono nello stesso verso':
     m.direction==='SEGNO OPPOSTO'?'si muovono in versi opposti':'non danno un segno conclusivo';
   relation='Nei 5 intervalli con date FX/2Y comuni ('+m.start+' → '+m.end+') il cross varia '+
    signed(m.fxPct,2,'%')+' e il differenziale governativo 2Y '+signed(m.spreadBp,1,' pb')+
    ': '+concord+'. È co-movimento, non prova che i tassi abbiano causato il cambio.';
  }
  const ca=cotObs(a,cot,now),cb=cotObs(b,cot,now);
  const cotText=z=>z.ccy+' net '+signed(z.net,0)+', Δnet '+signed(z.change,0)+
    ', long '+signed(z.long,0)+', short '+signed(z.short,0)+' ('+z.asof+')';
  const positioning=ca||cb?
    'COT settimanale: '+[ca,cb].filter(Boolean).map(cotText).join('; ')+
    '. Le variazioni di long e short descrivono esposizioni dichiarate, non flussi spot né coperture dimostrate.':
    'Non abbiamo le due serie COT settimanali coerenti; il posizionamento non conferma la tesi.';
  let price='Il prezzo daily non è confrontabile con lo snapshot della coppia: sospendiamo la conferma.';
  if(aligned){
   const side=fav?'rispetto al vantaggio ipotizzato per '+fav:'senza un verso strutturale favorito';
   price='Prezzo '+a+'/'+b+' al '+model.price_asof+': 5 fixing '+signed(profile.m5,2,'%')+
    ', 20 fixing '+signed(profile.m20,2,'%')+'. '+profile.alignment.toLowerCase()+
    ' ('+side+'). Il prezzo descrive ciò che è accaduto, non un ingresso.';
  }
  const structural=frame.relation||setup.structural?.relation||'Il motore non individua una relazione strutturale chiara.';
  const headline=!datedModel?'Snapshot del motore non datato in modo verificabile':
    !fav?'Nessun vantaggio relativo sufficientemente definito per '+a+'/'+b+'.':
    quality==='PULITO'&&aligned&&!profile.horizonConflict?
    'La struttura favorisce '+fav+'; il prezzo è coerente, non è ancora un trade.':
    'La struttura favorisce '+fav+', ma le conferme restano incomplete.';
  const judgment=!datedModel?'Manca la data verificata dello snapshot: nessuna conclusione operativa.'
    :!fav?'Thesis Strength debole: non forziamo un verso. Trade Attractiveness non valutabile.'
    :quality==='NON VALUTABILE'?'Thesis Strength non verificabile: serve un confronto di fonti più solido; nessuna scelta operativa.'
    :profile?.horizonConflict&&aligned?'Thesis Strength da verificare: il prezzo su almeno un orizzonte contraddice la direzione favorita. Trade Attractiveness bassa finché manca una conferma.'
    :quality==='CON RISCHI'?'Thesis Strength parziale: esiste una preferenza del modello, ma i rischi non sono risolti. Trade Attractiveness non dimostrata.'
    :quality==='PULITO'&&aligned?'Thesis Strength favorevole nel modello; Trade Attractiveness da verificare sul timing H4/Daily, sui costi e sul rischio.'
    :'Thesis Strength ancora da confermare. Il modello da solo non dimostra un vantaggio operativo.';
  const watch=!fav?'Aspettiamo un vantaggio relativo fondato su macro e aspettative, poi la risposta del prezzo.'
    :'La tesi su '+fav+' si indebolirebbe se i driver macro/monetari relativi cambiassero verso oppure il fixing continuasse contro la direzione favorita. Prima di un trade servono nuove pubblicazioni, un vero repricing comparabile e una conferma H4/Daily.';
  // First reading: grounded in model flags, synchronized daily price, and
  // limitations of the quote feeds. Detailed observations remain below.
  const opposite=fav===a?b:fav===b?a:null;
  const economicPoint=!fav?
   'Il confronto economico e monetario non individua ancora una valuta chiaramente favorita. Forzare una direzione sarebbe prematuro.':
   frame.macroSide===fav&&frame.policySide!==fav?
    'La lettura macro del modello favorisce '+fav+' rispetto a '+opposite+
    ', ma le aspettative monetarie non offrono ancora una conferma relativa altrettanto solida. È un vantaggio parziale.':
   frame.policySide===fav&&frame.macroSide!==fav?
    'Le condizioni monetarie del modello favoriscono '+fav+', ma la macro relativa non ha ancora confermato un vantaggio altrettanto solido.':
   frame.macroSide===fav&&frame.policySide===fav?
    'Macro e politica monetaria del modello convergono a favore di '+fav+' rispetto a '+opposite+
    '. Resta comunque da verificare se questa lettura sia già riflessa nei prezzi.':
   'Il modello preferisce '+fav+' rispetto a '+opposite+
   ', ma non tutti i driver strutturali sono concordi. La preferenza è una tesi, non una nuova sorpresa.';
  const baselineCaveat='La base macro del motore è datata '+macroDate+
    ': non possiamo chiamarla accelerazione recente senza un nuovo confronto di dati e revisioni.';
  const marketPoint=!fav?
   'Senza un vantaggio relativo affidabile non attribuiamo alcuna direzione di prezzo alle aspettative monetarie.':
   !aligned?'Manca un confronto giornaliero sufficientemente allineato per stabilire se il prezzo stia confermando la tesi.':
   profile.alignment==='COERENTE SU 5 E 20 SEDUTE'?
    'Il prezzo ha già seguito il verso favorevole a '+fav+' su entrambi gli orizzonti giornalieri osservati. È una conferma del movimento passato: non dimostra che rimanga altro spazio.':
   profile.horizonConflict?
    'La risposta del prezzo non è uniforme fra i due orizzonti osservati. Il mercato non offre ancora una conferma stabile della direzione favorevole a '+fav+'.':
   'La risposta del prezzo resta inconcludente: la preferenza del modello non basta per chiamare confermata la tesi.';
  const monetaryCaveat=x&&y&&x.sourceType===y.sourceType&&x.asof===y.asof?
   'Le due indicazioni a sei mesi sono disponibili, ma senza una serie di variazioni confrontabili non attribuiamo un nuovo repricing relativo.':
   'Le osservazioni a sei mesi non sono omogenee per strumento e/o data: non abbiamo prova di un repricing relativo che possa spiegare il cambio.';
  const crowding=/estrem/i.test(setup.cot?.text||'')?
   ' Il COT del modello segnala esposizioni estreme: possibile vulnerabilità della tesi se il prezzo perde forza, non prova di acquisti o vendite spot.':
   '';
  const invalidation=!fav?
   'Servono dati macro e aspettative di tasso confrontabili fra le due valute, seguiti da una conferma del prezzo.':
   'La tesi a favore di '+fav+' si indebolirebbe con sorprese macro relative a vantaggio di '+opposite+
   ', un repricing monetario comparabile in direzione contraria, oppure una perdita persistente di coerenza del prezzo giornaliero.';
  const decisionPoint=!fav?
   'Non emerge oggi una direzione FX sufficientemente motivata. Meglio attendere una nuova prova.':
   quality==='NON VALUTABILE'?
    'La qualità del dossier non permette una conclusione operativa, anche se alcune letture puntano verso '+fav+'.':
   quality==='CON RISCHI'?
    'La tesi è interessante da monitorare ma non ancora un trade convincente: il vantaggio è parziale e il rischio di comprare una narrativa già riflessa nel prezzo resta aperto.':
   aligned&&profile.horizonConflict?
    'Il contrasto fra gli orizzonti di prezzo rende poco convincente il timing. Serve una conferma nuova, non la sola direzione preferita del modello.':
   'La preferenza di fondo è coerente con il modello, ma un ingresso richiede timing e rischio favorevoli, non la semplice conferma del prezzo.';
  return {available:true,key,headline,structural,macro:macroReading,pricing,relation,positioning,price,
    economicPoint,baselineCaveat,marketPoint,monetaryCaveat,crowding,invalidation,decisionPoint,
    judgment,watch,asof:model.price_asof,macroDate,fav,quality,rateVerified:Boolean(ratesView?.ready),
    cotAsOf:[ca?.asof,cb?.asof].filter(Boolean).join(' / ')||'n.d.'};
 }
 function render(args){
  const item=interpret(args),esc=args.esc||((x)=>String(x));
  if(!item.available)return '<div class="decision-desk-story"><p>'+esc(item.judgement)+'</p></div>';
  const para=(label,value)=>'<p><strong>'+esc(label)+'</strong> '+esc(value)+'</p>';
  return '<div class="decision-desk-story" data-serafini-pair="'+esc(item.key)+'">'+
   '<span class="decision-desk-kicker">LA LETTURA DEL DESK · '+esc(item.key.slice(0,3)+'/'+item.key.slice(3))+'</span>'+
   '<h3>'+esc(item.headline)+'</h3>'+
   para('Che cosa sostiene la tesi.',item.economicPoint+' '+item.baselineCaveat)+
   para('Che cosa sta confermando il mercato.',item.marketPoint+' '+item.monetaryCaveat+item.crowding)+
   para('Giudizio operativo.',item.decisionPoint)+
   '<p class="decision-desk-watch"><strong>Cosa può cambiare il giudizio.</strong> '+esc(item.invalidation)+'</p>'+
   '<details class="decision-desk-evidence"><summary>Verifica dati, date e passaggi del ragionamento</summary>'+
   '<div class="decision-desk-evidence-body">'+
   para('Macro — osservazioni per valuta.',item.macro)+
   para('Pricing — strumenti e date.',item.pricing+' '+item.relation)+
   para('Prezzo — fixing verificati.',item.price)+
   para('COT — esposizioni dichiarate.',item.positioning)+
   '<small>Snapshot coppia '+esc(item.asof)+' · baseline macro del modello '+esc(item.macroDate)+
   '. Questi dati sono verifiche del giudizio, non consenso/sorprese confermati, causalità o rendimento atteso.</small>'+
   '</div></details></div>';
 }
 if(typeof window!=='undefined')window.FXQuantPairDesk={interpret,render,countryMacro,pricingObs,cotObs};
 if(typeof module!=='undefined'&&module.exports)module.exports={interpret,render,countryMacro,pricingObs,cotObs};
})();
