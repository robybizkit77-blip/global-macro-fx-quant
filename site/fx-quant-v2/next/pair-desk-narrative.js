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

 const names={USD:'Stati Uniti',EUR:'area euro',GBP:'Regno Unito',JPY:'Giappone',
  CHF:'Svizzera',CAD:'Canada',AUD:'Australia',NZD:'Nuova Zelanda'};
 const observedSchema='GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1';
 const dayGap=(a,b)=>isDay(a)&&isDay(b)?
  Math.round((Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/864e5):null;
 const changeWord=x=>x==='UP'?'aumenta':x==='DOWN'?'diminuisce':x==='FLAT'?'è stabile':null;

 const periodMonth=x=>{
  if(typeof x!=='string')return null;
  if(/^\d{4}Q[1-4]$/.test(x))return x.slice(0,4)+'-'+String(Number(x[5])*3).padStart(2,'0');
  if(/^\d{4}-(0[1-9]|1[0-2])(?:-\d{2})?$/.test(x))return x.slice(0,7);
  return null;
 };

 const labourWord=x=>x==='UP'?'aumenta':x==='DOWN'?'diminuisce':x==='FLAT'?'resta stabile':null;
 function growthChange(row,now){
  const g=row?.growth,prior=g?.prior_documented_quarter;
  if(!g||!prior||!isDay(g.publisher_release_day)||g.publisher_release_day>now||
     !isDay(prior.publisher_release_day)||prior.publisher_release_day>now||
     typeof g.reference_quarter!=='string'||typeof prior.reference_quarter!=='string'||
     !/^20\d{2}Q[1-4]$/.test(g.reference_quarter)||
     !/^20\d{2}Q[1-4]$/.test(prior.reference_quarter)||
     g.reference_quarter<=prior.reference_quarter||
     !finite(g.nonannualized_qoq_descriptive_pct)||
     !finite(prior.nonannualized_qoq_descriptive_pct)||
     g.later_revisions_not_identical_to_first_release!==true)return null;
  const difference=g.nonannualized_qoq_descriptive_pct-prior.nonannualized_qoq_descriptive_pct;
  return {period:g.reference_quarter,
   trend:difference>0.10?'accelera':difference< -0.10?'rallenta':'è sostanzialmente stabile'};
 }
 function observedContext(doc,key,model,now){
  const pair=key.slice(0,3)+'/'+key.slice(3),a=key.slice(0,3),b=key.slice(3);
  const age=dayGap(doc?.generated_europe_rome_day,now);
  const priceLag=dayGap(doc?.fx_price_as_of,model?.price_asof);
  if(!doc||doc.schema!==observedSchema||
     doc.status!=='OBSERVED_ECONOMIC_CONTEXT_NOT_FX_SIGNAL'||
     doc.safe_to_republish_D!==false||
     doc.safe_to_recompute_structural_pair_theses!==false||
     doc.eligible_for_trading_or_forward_backtest!==false||
     doc.historic_PIT_OOS_not_certified!==true||
     doc.source_value_quality!=='OBSERVED_REVISED_SERIES_AND_PUBLISHER_WEB_GDP'||
     doc.canonical_D_macro_baseline_as_of!==model?.macro_baseline_asof||
     !Number.isInteger(age)||age<0||age>7||
     !Number.isInteger(priceLag)||priceLag<0||priceLag>7||
     doc.pair_context?.[pair]?.base!==a||doc.pair_context?.[pair]?.quote!==b||
     doc.pair_context[pair].pair_trade_bias!==null||
     doc.pair_context[pair].recalculated_structural_thesis!==false||
     doc.countries?.[a]?.FX_strength!==null||doc.countries?.[b]?.FX_strength!==null||
     doc.countries[a]?.macro_score!==null||doc.countries[b]?.macro_score!==null||
     doc.countries[a]?.not_a_trade_or_policy_signal!==true||
     doc.countries[b]?.not_a_trade_or_policy_signal!==true)return null;
  const A=doc.countries[a],B=doc.countries[b];
  for(const row of [A,B]){
   const g=row.growth;
   if(!g||!isDay(g.publisher_release_day)||g.publisher_release_day>now||
      !/^20\d{2}Q[1-4]$/.test(g.reference_quarter||'')||
      periodMonth(g.reference_quarter)>now.slice(0,7)||
      !finite(g.nonannualized_qoq_descriptive_pct)||
      g.is_growth_strength_score!==false)return null;
   for(const pillar of ['inflation','labour']){
    const x=row[pillar];
    if(!x||!finite(x.observation_value)||!periodMonth(x.observation_period)||
       periodMonth(x.observation_period)>now.slice(0,7)||
       !['UP','DOWN','FLAT'].includes(x.change_direction)||
       x.observed_history_revised_not_historic_PIT!==true||
       x.observation_period_is_not_release_instant!==true)return null;
   }
  }
  const sentences=[];
  const growthA=growthChange(A,now),growthB=growthChange(B,now);
  if(growthA&&growthB&&growthA.period===growthB.period){
   sentences.push('Sul PIL, '+names[a]+' '+growthA.trend+' e '+names[b]+' '+growthB.trend+
    ' nello stesso trimestre osservato.');
  }else if(growthA||growthB){
   const winner=growthA?a:b,loser=growthA?b:a,g=growthA||growthB;
   sentences.push('La crescita di '+names[winner]+' '+g.trend+
    ', ma per '+names[loser]+' non abbiamo un confronto trimestrale altrettanto recente.');
  }
  const labourA=A.labour.change_direction,labourB=B.labour.change_direction;
  if(labourA!==labourB){
   sentences.push('Sul lavoro, la disoccupazione '+labourWord(labourA)+
    ' in '+names[a]+' e '+labourWord(labourB)+' in '+names[b]+'.');
  }else{
   sentences.push('La disoccupazione '+labourWord(labourA)+
    ' in entrambe le economie: da sola non separa le due valute.');
  }
  if(A.inflation.change_direction!==B.inflation.change_direction){
   sentences.push('L’inflazione annua '+changeWord(A.inflation.change_direction)+
    ' in '+names[a]+' e '+changeWord(B.inflation.change_direction)+
    ' in '+names[b]+', senza implicare automaticamente una risposta dei tassi.');
  }
  const summary=sentences.join(' ')+
   ' Sono dinamiche nazionali osservate, non sorprese rispetto al consenso né una nuova valutazione della forza FX.';
  const evidence='Fotografia elaborata il '+doc.generated_europe_rome_day+
   ' da serie macro riviste e comunicazioni sul PIL. Periodi: '+
   a+' PIL '+(A.growth?.reference_quarter||'n.d.')+
   ', inflazione '+A.inflation.observation_period+
   ', lavoro '+A.labour.observation_period+'; '+
   b+' PIL '+(B.growth?.reference_quarter||'n.d.')+
   ', inflazione '+B.inflation.observation_period+
   ', lavoro '+B.labour.observation_period+
   '. Le release possono avere ritardi e definizioni diverse; non è uno storico point-in-time per backtest.';
  return {asof:doc.generated_europe_rome_day,summary,evidence};
 }

 function interpret({key,model,macro,ois,cot,profile,ratesView,observedMacro,estimatedMacro,now}){
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
  const currentMacro=observedContext(observedMacro,key,model,now);
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

  // A current estimated model is intentionally independent of the frozen
  // structural score. Reuse historical D ONLY inside the evidence audit.
  const currentEstimate=estimatedMacro?.status==='STIMA_OPERATIVA_NON_VALIDATA'?
   estimatedMacro.pairs?.find(z=>z.key===key):null;
  const estCountryA=estimatedMacro?.by?.[a],estCountryB=estimatedMacro?.by?.[b];
  if(currentEstimate&&estCountryA&&estCountryB){
   const preferred=currentEstimate.favored;
   const rateA=estCountryA.rate,rateB=estCountryB.rate;
   const market=currentEstimate.opposite?
    'Il prezzo su 20 fixing BCE ha viaggiato in direzione opposta alla tesi fondamentale.':
    currentEstimate.aligned?
    'Il prezzo sui 20 fixing BCE è coerente con la tesi, ma descrive solo il movimento passato.':
    'Il prezzo su 20 fixing BCE non offre una direzione sufficiente.';
   const shortMarket=currentEstimate.fiveState==='CONTRARIO'?
    ' Le ultime 5 sedute BCE sono contrarie: il momentum recente indebolisce il timing.':
    currentEstimate.fiveState==='COERENTE'?
    ' Anche le ultime 5 sedute BCE vanno nella stessa direzione.':
    ' Le ultime 5 sedute BCE non mostrano un segno deciso.';
   const rates='La componente monetaria usa '+a+' '+rateA.kind+' ('+rateA.quality+
    ') e '+b+' '+rateB.kind+' ('+rateB.quality+
    '). Non confrontiamo livelli di strumenti diversi come uno spread OIS certificato.';
   const head=preferred?
    'Tesi fondamentale stimata a favore di '+preferred+'. '+currentEstimate.stage+'.':
    'Nessuna direzione fondamentale sufficientemente distinta per '+a+'/'+b+'.';
   const decision='Trade Attractiveness: '+currentEstimate.tradeAttractiveness+
    '. '+currentEstimate.tradeReason+
    ' Il giudizio riguarda solo la priorità di ricerca, non un ingresso né un rendimento atteso.';
   return {available:true,key,headline:head,structural,macro:macroReading,pricing,relation,
    positioning,price:'Fixing BCE '+estimatedMacro.priceFrom+' → '+estimatedMacro.priceAsOf+
    '. Variazione su 20 fixing '+a+'/'+b+' '+signed(currentEstimate.pricePercent,2,'%')+
    '; su 5 fixing '+signed(currentEstimate.move5Percent,2,'%')+
    '. '+market+shortMarket+' Il vecchio orientamento prezzo del modello D è soltanto archivio.',
    economicPoint:'Thesis Strength: '+currentEstimate.thesisStrength+
     '. '+currentEstimate.thesisReason,
    baselineCaveat:'Nuova stima al '+estimatedMacro.asof+
     '; il punteggio strutturale del '+macroDate+' non contribuisce alla nuova classifica.',
    currentMacro,marketPoint:market+shortMarket,monetaryCaveat:rates,
    crowding:' Il COT resta una prova separata e non è stato convertito in un voto automatico.',
    invalidation:preferred?
     'Dati su crescita o disoccupazione che invertano il momentum relativo, un repricing verificato contrario, oppure prezzi persistenti contro '+preferred+
     ' indebolirebbero la tesi.':'Attendere dati macro relativi discriminanti e variazioni di tasso comparabili.',
    decisionPoint:decision,judgment:decision,watch:currentEstimate.missing,
    asof:estimatedMacro.priceAsOf,macroDate:estimatedMacro.asof,fav:preferred,
    quality:currentEstimate.quality,rateVerified:rateA.quality==='UFFICIALE'&&rateB.quality==='UFFICIALE',
    cotAsOf:[ca?.asof,cb?.asof].filter(Boolean).join(' / ')||'n.d.'};
  }
  if(estimatedMacro){
   return {available:false,judgement:'Stima corrente sospesa: '+(estimatedMacro.reason||
    'fonti non allineate')+'. La vecchia tesi del 25 settembre non viene riproposta come attuale.'};
  }
  return {available:true,key,headline,structural,macro:macroReading,pricing,relation,positioning,price,
    economicPoint,baselineCaveat,currentMacro,marketPoint,monetaryCaveat,crowding,invalidation,decisionPoint,
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
   (item.currentMacro?
    '<p class="decision-desk-current-macro"><strong>Che cosa cambia nei dati osservati.</strong> '+
    esc(item.currentMacro.summary)+'</p>':'')+
   para('Che cosa sostiene la tesi.',item.economicPoint+' '+item.baselineCaveat)+
   para('Che cosa sta confermando il mercato.',item.marketPoint+' '+item.monetaryCaveat+item.crowding)+
   para('Giudizio operativo.',item.decisionPoint)+
   '<p class="decision-desk-watch"><strong>Cosa può cambiare il giudizio.</strong> '+esc(item.invalidation)+'</p>'+
   '<details class="decision-desk-evidence"><summary>Verifica dati, date e passaggi del ragionamento</summary>'+
   '<div class="decision-desk-evidence-body">'+
   (item.currentMacro?para('Macro osservata V3 — provenienza.',item.currentMacro.evidence):'')+
   para('Macro — osservazioni per valuta.',item.macro)+
   para('Pricing — strumenti e date.',item.pricing+' '+item.relation)+
   para('Prezzo — fixing verificati.',item.price)+
   para('COT — esposizioni dichiarate.',item.positioning)+
   '<small>Snapshot coppia '+esc(item.asof)+' · baseline macro del modello '+esc(item.macroDate)+
   '. Questi dati sono verifiche del giudizio, non consenso/sorprese confermati, causalità o rendimento atteso.</small>'+
   '</div></details></div>';
 }
 if(typeof window!=='undefined')window.FXQuantPairDesk={interpret,render,countryMacro,pricingObs,cotObs,observedContext,growthChange};
 if(typeof module!=='undefined'&&module.exports)module.exports={interpret,render,countryMacro,pricingObs,cotObs,observedContext,growthChange};
})();
