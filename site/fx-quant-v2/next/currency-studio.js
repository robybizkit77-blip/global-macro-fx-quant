'use strict';
/**
 * FX Quant NEXT — G8 Currency Orientation Desk.
 * One section, one job: country context + cross-currency relative movement.
 * Full charts, historical series, OIS tenors and COT audits belong in their
 * respective specialized studios, not repeated here.
 *
 * ECB quote convention: A/B = rate_B_per_EUR / rate_A_per_EUR.
 * CFTC: weekly snapshot, never presented as current positioning.
 * Rate and macro snapshots retain their own dates.
 */
(function(root){
function build(api){
 const {get,FX,FLAGS,NAMES,state,pageHero,esc,fmt,sign,date,finite,validDay,dayNow}=api;
 const country=FX.includes(state.ccy)?state.ccy:'USD';
 const against=FX.includes(state.csOther)&&state.csOther!==country?state.csOther:FX.find(k=>k!==country);
 const FXDATA=get('currencyPrices'),GOV=get('rates')||{},CB=get('cb')||{};
 const OIS=get('ois')?.currencies||{},M=get('macro')?.currencies||{},COT=get('cotHistory')||{},PAIRS=get('pairs')?.pairs||{};
 const G8CONTEXT=root.FXQuantCurrencyFallback?.evaluate?.({macroSeries:get('macroSeries'),estimated:get('cbEstimated'),
   rates:GOV,chfResearch:get('chfResearch'),nzdResearch:get('nzdPostroll'),now:dayNow()})||null;
 const G8SHADOW=root.FXQuantGrowthShadow?.analyze?.({macroSeries:get('macroSeries'),now:dayNow()})||null;
 const G8RATESHADOW=root.FXQuantG8RatesShadow?.analyze?.({research:G8CONTEXT,
  chfHistory:get('chfResearch'),spot:get('chfSpot'),
  nzdResearch:get('nzdPostroll'),nzdMarket:get('nzdDirectionalProxy'),
  now:dayNow()})||null;
 const isShadowRate=e=>e&&['STIMA_MODELLO_RICERCA','STIMA_SCENARIO_NON_CALIBRATA'].includes(e.status)&&
    e.eligibleForCore===false&&finite(e.estimate2Y);
 const w=state.csReturnWindow===5?5:state.csReturnWindow===60?60:20;
 const number=x=>finite(x)?fmt(x,2):'—';
 const period=x=>String(x||'n.d.');
 function observedRate(k){const v=GOV[k];return v&&validDay(v.date)&&v.date<=dayNow()&&finite(v['2Y'])?v:null}
 function dataMarket(k){const a=COT[k];if(!a||!Array.isArray(a.net)||a.net.length<2||
   !Array.isArray(a.dates)||a.dates.length!==a.net.length)return null;
  const i=a.net.length-1;
  if(!validDay(a.dates[i])||a.dates[i]>dayNow()||
     !finite(a.net[i])||!finite(a.net[i-1]))return null;
  return {net:a.net[i],delta:a.net[i]-a.net[i-1],
    percentile:finite(a.percentile?.[i])?a.percentile[i]:null,asof:a.dates[i]};}
 function prices(a,b){
  if(!Array.isArray(FXDATA?.rows)||FXDATA?.source!=='ECB euro foreign exchange reference rates')return [];
  return FXDATA.rows.filter(row=>validDay(row.Date)&&row.Date<=dayNow()
     &&finite(row[a])&&row[a]>0&&finite(row[b])&&row[b]>0)
    .map(row=>({asof:row.Date,value:row[b]/row[a]}))
    .sort((x,y)=>x.asof.localeCompare(y.asof));
 }
 function move(p,n){return p.length>n&&p.at(-n-1)?.value>0
    ?(p.at(-1).value/p.at(-n-1).value-1)*100:null;}
 function assess(k){
  const p=prices(country,k),rate=observedRate(k),hist=dataMarket(k);
  return {ccy:k,quote:p.at(-1),move5:move(p,5),move20:move(p,20),move60:move(p,60),r2:rate?.['2Y'],rateDate:rate?.date,cot:hist};
 }
 const counterparts=FX.filter(k=>k!==country).map(assess);
 const target=counterparts.find(x=>x.ccy===against)||counterparts[0];
 const r=observedRate(country),cot=dataMarket(country),macro=M[country],bank=CB[country],ois=OIS[country],six=ois?.horizons?.['6m'];
 const asof=target?.quote?.asof;
 const price20=target?.move20;
 const cpi=macro?.inflation,unemp=macro?.labour;
 const priceDir=finite(price20)?price20>0?'si è apprezzata':price20<0?'si è indebolita':'non ha cambiato valore':'non è valutabile';
 const priceMove=finite(price20)?fmt(Math.abs(price20),2)+'%':'—';
 const facts=[
  {key:'macro',n:'01',title:'Macro',subtitle:'COME STA CAMBIANDO L’ECONOMIA',hint:'Contesto, non sorpresa',metric:finite(cpi?.latest_value)?fmt(cpi.latest_value,2)+'%':'—',label:'Inflazione · '+period(cpi?.as_of),detail:'Inflazione '+(cpi?.direction||'n.d.').toLowerCase()+', disoccupazione '+(unemp?.direction||'n.d.').toLowerCase()+' ('+(finite(unemp?.latest_value)?fmt(unemp.latest_value,2)+'%':'—')+' · '+period(unemp?.as_of)+'.',dest:'macro',action:'Apri gli storici macro'},
  {key:'rates',n:'02',title:'Tassi & policy',subtitle:'IL FRONT-END E LE ATTESE',hint:ois?.quality||'Qualità da verificare',metric:finite(r?.['2Y'])?fmt(r['2Y'],3)+'%':'—',label:'Government 2Y · '+date(r?.date),detail:(bank?.bank||'Banca centrale')+': '+(bank?.rate_text||'—')+'. Pricing 6M '+(finite(six?.rate)?fmt(six.rate,3)+'%':'—')+' ('+(ois?.kind||'non disponibile')+', '+date(six?.as_of)+').',dest:'rates',action:'Esplora curve e OIS'},
  {key:'cot',n:'03',title:'Positioning',subtitle:'COME SONO ESPOSTI I FONDI',hint:'Dato CFTC settimanale',metric:finite(cot?.net)?sign(cot.net,0):'—',label:'Net contratti · '+date(cot?.asof),detail:'Flusso 1W '+sign(cot?.delta,0)+' contratti · percentile P'+fmt(cot?.percentile,1)+'. P alto non significa automaticamente net long.',dest:'cot',action:'Apri l’analisi COT'},
  {key:'price',n:'04',title:'Prezzo relativo',subtitle:'IL CAMBIO CONFERMA?',hint:'Fixing BCE, non intraday',metric:finite(price20)?sign(price20,2,'%'):'—',label:country+'/'+against+' · ultime 20 sedute',detail:'Ultimo fixing '+fmt(target?.quote?.value,5)+' al '+date(asof)+'. Il rendimento osservato non dimostra quale driver lo abbia causato.',dest:'pairs',action:'Apri la tesi della coppia'}
 ];
 function strengthView(){
  return root.FXQuantCurrencyStrength?.analyze?.({
   prices:FXDATA,macro:M,rates:GOV,ois:OIS,cot:COT,now:dayNow(),
   rankingFn:root.FXQuantPairRankings?.currencyRanking,fallback:G8CONTEXT
  })||{rows:[],priceRanking:null,asof:null};
 }
 function strengthBoard(){
  const result=strengthView();
  const rankDate=result.priceRanking?
   'BCE '+date(result.priceRanking.from)+' → '+date(result.priceRanking.asof):
   'Mancano i fixing BCE comuni per una classifica completa';
  const rows=(result.rows||[]).map(x=>{
   const tone=x.reading.tone,rank=x.price.position?'#'+x.price.position:'—';
   const split=x.macro.text.split(' · ');
   const growth=x.context?.growth;
   const proxy=x.context?.pricingProxy;
   const ratesContext=x.context?.ratesResearch;
   const estRate=G8RATESHADOW?.currencies?.[x.ccy];
   const estimated2Y=!x.rates.ok&&isShadowRate(estRate);
   const research2Y=!x.rates.ok&&['STORICO_UFFICIALE_NON_OPERATIVO','RICERCA_MANUALE_NON_CERTIFICATA'].includes(ratesContext?.status);
   const twoLabel=estimated2Y?fmt(estRate.estimate2Y,3)+'% · STIMA':research2Y?ratesContext.label:x.rates.label;
   const twoMeta=estimated2Y?('Scenario · '+date(estRate.asof)+' · non osservato'):research2Y?'Ricerca · '+date(ratesContext.asof):x.rates.asof?date(x.rates.asof):'Base non recente';
   const twoHeading=estimated2Y?'2Y · stima (non quotazione)':research2Y?'2Y · contesto datato':'2Y · variazione 1W';
   const proxyReady=!x.pricing.ok&&proxy?.status==='PROXY_INFORMATIVO';
   const sixLabel=x.pricing.ok?x.pricing.label:proxyReady?proxy.label:x.pricing.label;
   const sixDate=x.pricing.ok?date(x.pricing.asof):proxyReady?'Indicativo · '+date(proxy.asof):'Non certificato';
   const growLabel=growth?.status==='STORICO_DESCRITTIVO'?growth.label:split[0];
   return '<button class="strength-row '+(x.ccy===country?'selected ':'')+tone+'" type="button" data-cs-country="'+x.ccy+'" aria-pressed="'+String(x.ccy===country)+'" aria-label="Seleziona '+x.ccy+' per approfondire">'+
    '<span class="strength-name"><b>'+rank+'</b><strong>'+FLAGS[x.ccy]+' '+x.ccy+'</strong></span>'+
    '<span class="strength-axis"><small>Crescita · dato storico</small><strong>'+esc(growLabel)+'</strong><em>'+esc(growth?.status==='STORICO_DESCRITTIVO'?split[0]+' · '+(split[1]||''):split[1]||'')+'</em></span>'+
    '<span class="strength-axis '+(x.rates.ok?'':'unverified')+'"><small>'+esc(twoHeading)+'</small><strong>'+esc(twoLabel)+'</strong><em>'+esc(twoMeta)+'</em></span>'+
    '<span class="strength-axis '+(x.pricing.ok?'':'unverified')+(proxyReady?' context-proxy':'')+'"><small>'+ (x.pricing.ok?'Attese 6M · Δ 1W':'Futures 6M · contesto')+'</small><strong>'+esc(sixLabel)+'</strong><em>'+esc(sixDate)+'</em></span>'+
    '<span class="strength-axis '+(x.price.change>0?'fxpositive':x.price.change<0?'fxnegative':'')+'"><small>Prezzo · 20 fixing</small><strong>'+esc(x.price.label)+'</strong><em>vs le altre G8</em></span>'+
    '<span class="strength-reading '+tone+'"><strong>'+esc(x.reading.label)+'</strong><small>Apri '+x.ccy+' ›</small></span></button>';
  }).join('');
  return '<section class="strength-board" id="orient-strength-board" aria-label="Mappa G8 Macro Tassi Aspettative Prezzo">'+
   '<div class="strength-board-head"><div><span class="chapter-kicker">01 / MACRO → TASSI → ATTESE → PREZZO</span>'+
   '<h2>Quali valute hanno <em>più sostegno verificabile?</em></h2>'+
   '<p>Macro, rendimenti, aspettative monetarie e prezzo: osservazioni datate, <strong>proxy e stime dichiarate</strong> dove mancano fonti aggiornate. Il numero ordina soltanto il prezzo.</p></div>'+
   '<small>'+esc(rankDate)+'</small></div>'+
   '<div class="strength-columns" aria-hidden="true"><span>VALUTA</span><span>MACRO</span><span>2Y</span><span>ATTESE 6M</span><span>PREZZO</span><span>GIUDIZIO</span></div>'+
   '<div class="strength-rows">'+rows+'</div>'+
   '<p class="strength-note">Crescita: osservazioni storiche, non PIL stimato. 2Y: variazione settimanale solo se verificata; le stime CHF/NZD sono <strong>scenari di ricerca, non rendimenti osservati</strong> e non entrano nei segnali. 6M: variazione ufficiale se verificata, altrimenti futures indicativi datati, non repricing monetario certificato. Il ranking resta esclusivamente di prezzo; proxy e stime non aumentano le prove operative.</p></section>';
 }
 function shadowResearch(){
  const t=G8SHADOW?.currencies?.[country];
  if(!t)return '';
  const label=t.status==='RESEARCH_CANDIDATE'?'Modello promettente, non ancora operativo':
   t.status==='NO_BENCHMARK_EDGE'?'Nessun vantaggio storico sufficiente':
   t.status==='INSUFFICIENT_SAMPLE'?'Campione di test insufficiente':
   t.status==='STALE_INPUT'?'Dati troppo datati':'Proiezione non disponibile';
  const metrics=t.backtest;
  const skill=metrics&&Number.isFinite(metrics.improvementPct)?
    'Test su '+metrics.testObservations+' previsioni storiche successive: errore medio del modello '+
    fmt(metrics.meanAbsoluteError,3)+' '+(t.changeUnit||'')+
    ', benchmark senza variazione '+fmt(metrics.baselineMAE,3)+' '+(t.changeUnit||'')+
    ', miglioramento '+sign(metrics.improvementPct,1,'%')+
    ', direzioni corrette '+fmt(metrics.directionalAgreementPct,1)+'%.':'';
  const forecast=t.candidate&&t.forecast?
    '<p class="strength-shadow-projection">Proiezione della <strong>prossima variazione della serie</strong> ('+
     esc(t.nextObservationPeriod)+'): <strong>'+esc(sign(t.forecast.nextChange,2,t.forecast.unit))+
    '</strong>. Ultima osservazione disponibile: '+esc(t.latestPeriod)+'. Non è una stima del PIL complessivo né una notizia di oggi.</p>':
    '<p class="strength-shadow-projection">La previsione resta <strong>non pubblicata</strong>: '+
     esc(label.toLowerCase())+'.</p>';
  return '<details class="strength-shadow-fold"><summary><strong>Ricerca Quant · stima sperimentale</strong>'+
   '<span>'+esc(label)+' · nessun effetto sul ranking FX</span></summary>'+
   '<div class="strength-shadow-body"><p class="strength-shadow-kicker">MODELLO SHADOW · NON POINT-IN-TIME · NON OPERATIVO</p>'+
   '<p>Serie: <strong>'+esc(t.label||country)+'</strong>. Stimiamo un solo passo avanti usando la media fissa delle ultime sei variazioni; il confronto è con una previsione di variazione zero.</p>'+
   forecast+(skill?'<p>'+esc(skill)+'</p>':'')+
   '<p class="strength-shadow-caveat">I dati storici possono essere revisionati e mancano le date di prima pubblicazione. Il test walk-forward è retrospettivo e non dimostra un vantaggio in tempo reale. Non genera segnali, probabilità di banca centrale o punteggi G8.</p>'+
   '</div></details>';
 }
 function strengthFocus(){
  const x=strengthView().rows.find(r=>r.ccy===country);
  if(!x)return '<p>La lettura G8 non è disponibile finché mancano dati verificabili.</p>';
  const cb=CB[country]||{};
  const growth=x.context?.growth;
  const proxy=x.context?.pricingProxy;
  const ratesContext=x.context?.ratesResearch;
  const estRate=G8RATESHADOW?.currencies?.[country];
  const estimated2Y=!x.rates.ok&&isShadowRate(estRate);
  const dated2Y=!x.rates.ok&&['STORICO_UFFICIALE_NON_OPERATIVO','RICERCA_MANUALE_NON_CERTIFICATA'].includes(ratesContext?.status);
  const rateEstimateText=estimated2Y?
   ' STIMA '+fmt(estRate.estimate2Y,3)+'% al '+date(estRate.asof)+
   ' (intervallo di sensibilità/errore indicativo '+fmt(estRate.lower2Y,3)+'–'+fmt(estRate.upper2Y,3)+'%). '+
   estRate.note+(estRate.currency==='CHF'?
    ' Test retrospettivo: '+estRate.pseudoOOSCount+' previsioni, errore medio '+fmt(estRate.modelMAEBp,2)+
    ' pb contro '+fmt(estRate.flatBaselineMAEBp,2)+' pb mantenendo il 2Y invariato.': '')+
   ' Non è una nuova quotazione 2Y, né un segnale FX.':'';
  const growthText=growth?.status==='STORICO_DESCRITTIVO'?growth.description:
   'Non ci sono osservazioni recenti sufficienti per un confronto con il ciclo.';
  const pricingText=x.pricing.ok?x.pricing.text:
   proxy?.status==='PROXY_INFORMATIVO'?x.pricing.text+' '+proxy.description:x.pricing.text;
  const cards=[
   ['MACRO · CRESCITA / LAVORO / PREZZI',growthText+' '+x.macro.text,
    'Serie storiche con periodo di osservazione, non nowcast, sorprese macro o pubblicazioni odierne.'],
   ['TASSI 2Y',x.rates.text+(dated2Y?' '+ratesContext.description:'')+rateEstimateText,
    estimated2Y?'STIMA NON OSSERVATA. La banda non è un intervallo di confidenza e non influenza le 4 conferme operative.':dated2Y?'Storico/lettura manuale non è un tasso live e non aumenta le prove disponibili.':'Movimento di mercato, non prova di decisioni future.'],
   ['ASPETTATIVE 6M',pricingText,'I proxy sono informativi e non sostituiscono l’OIS ufficiale né i suoi cambiamenti.'],
   ['PREZZO',x.price.text+' '+x.price.label+(x.price.position?' · posizione '+x.price.position+'/8.':''),'La forza osservata non identifica il driver.']
  ];
  const cbText=validDay(cb.last_date)&&cb.last_date<=dayNow()?
   '<p><strong>Ultima decisione '+esc(cb.bank||country)+':</strong> '+esc(cb.action||'n.d.')+' · '+date(cb.last_date)+'. Non coincide necessariamente con ciò che il mercato prezza adesso.</p>':'';
  const cotText=x.cot?'<p><strong>COT settimanale:</strong> net '+sign(x.cot.net,0)+' contratti, variazione '+sign(x.cot.delta,0)+' al '+date(x.cot.asof)+'. Non sono flussi spot.</p>':'';
  return '<section class="strength-focus" id="orient-strength-focus"><div class="strength-focus-head"><div>'+
   '<span class="chapter-kicker">02 / DOSSIER VALUTA · '+FLAGS[country]+' '+country+'</span>'+
   '<h2>'+FLAGS[country]+' '+country+': '+esc(x.reading.label.toLowerCase())+'</h2>'+
   '<p>'+esc(x.reading.text)+'</p></div><div class="strength-coverage">Prove disponibili '+x.evidenceCount+'/4'+
   '<small>Solo fonti verificate · contesto storico/proxy separato</small></div></div>'+
   '<div class="strength-cards">'+cards.map(([label,main,note],i)=>'<article class="strength-card"><span>0'+(i+1)+' / '+esc(label)+'</span><p>'+esc(main)+'</p><small>'+esc(note)+'</small></article>').join('')+'</div>'+
   '<div class="strength-additional">'+cbText+cotText+'</div>'+
   '<nav class="strength-links"><a href="#macro">Macro completa</a><a href="#rates">Tassi &amp; OIS</a><a href="#cot">COT</a><a href="#pairs">Coppie FX</a></nav>'+shadowResearch()+'</section>';
 }
 function ranking(){
  // Same G8/20-common-fixing methodology used by the 28-pair page.
  // Price strength is not macro strength, carry, a signal or a forecast.
  const view=root.FXQuantPairRankings?.currencyRanking?.(FXDATA,dayNow(),FX);
  if(!view)return '<section class="orient-ranking orient-ranking-unavailable"><h2>Forza relativa G8</h2>'+
   '<p>La classifica richiede almeno 21 fixing BCE comuni verificabili. Seleziona una valuta qui sotto per la sua analisi.</p>'+
   selector()+'</section>';
  const scale=Math.max(.00001,...view.items.map(x=>Math.abs(x.percent)));
  const here=view.items.findIndex(x=>x.ccy===country);
  const rows=view.items.map((x,i)=>{
   const tone=x.percent>0.00001?'positive':x.percent<-.00001?'negative':'neutral';
   return '<button type="button" class="orient-rank-row '+(x.ccy===country?'selected ':'')+tone+
     '" data-cs-country="'+x.ccy+'" aria-pressed="'+String(x.ccy===country)+
     '" aria-label="'+(i+1)+' posizione '+x.ccy+', '+sign(x.percent,2,'%')+
     ', seleziona per approfondire">'+
     '<span class="orient-rank-order">'+(i+1)+'</span>'+
     '<strong>'+esc(FLAGS[x.ccy]||'')+' '+x.ccy+'</strong>'+
     '<span class="orient-rank-track"><i style="width:'+
        Math.max(2,Math.abs(x.percent)/scale*100).toFixed(1)+'%"></i></span>'+
     '<b>'+esc(sign(x.percent,2,'%'))+'</b></button>';
  }).join('');
  return '<section class="orient-ranking" id="orient-ranking" aria-label="Graduatoria relativa delle otto valute">'+
   '<div class="orient-ranking-head"><div><span class="chapter-kicker">01 / PARTI DALLA CLASSIFICA</span>'+
   '<h2>Quali valute stanno <em>guadagnando o perdendo terreno?</em></h2>'+
   '<p>Ordine dalla più forte alla più debole contro le altre sette valute. Seleziona una riga per capire cosa sappiamo e cosa manca.</p></div>'+
   '<div class="orient-ranking-current"><small>VALUTA SELEZIONATA</small><strong>'+
   esc(FLAGS[country]||'')+' '+country+'</strong><span>Posizione '+(here>=0?here+1:'—')+' di 8</span></div></div>'+
   '<div class="orient-ranking-list">'+rows+'</div>'+
   '<p class="orient-ranking-foot">Forza di <strong>prezzo osservata</strong>, media geometrica su '+
   view.commonSessions+' intervalli BCE comuni · '+date(view.from)+' → '+date(view.asof)+
   '. Non misura la qualità macro o la convenienza di un trade.</p></section>';
 }
 function selector(){
  return '<div class="country-orient-list" role="group" aria-label="Scegli una delle otto valute">'
   +FX.map(k=>{const gov=observedRate(k),cotK=dataMarket(k);
    return '<button type="button" data-cs-country="'+k+'" aria-pressed="'+String(k===country)+'" class="orient-country '+(k===country?'active':'')+'">'
     +'<span>'+FLAGS[k]+' '+k+'</span><small>2Y '+(finite(gov?.['2Y'])?fmt(gov['2Y'],2)+'%':'—')+'</small>'
     +'<small>COT '+(finite(cotK?.percentile)?'P'+fmt(cotK.percentile,0):'—')+'</small></button>';
   }).join('')+'</div>';
 }
 function story(){
  const price=finite(price20),positive=price&&price20>0.025,negative=price&&price20<-.025;
  const headline=positive?country+' sta guadagnando terreno su '+against+'.'
    :negative?country+' sta perdendo terreno contro '+against+'.'
    :'Per '+country+'/'+against+' non emerge ancora un movimento netto.';
  const opening=price?'Negli ultimi 20 fixing BCE, '+country+'/'+against+' è passato a '+fmt(target?.quote?.value,5)+
    ', con una variazione di '+sign(price20,2,'%')+' fino al '+date(asof)+'.'
    :'Il confronto su 20 fixing BCE non è disponibile: non attribuiamo una direzione al prezzo.';
  const relative=root.FXQuantCurrencyRelative?.read?.({
    base:country,quote:against,macro:M,gov:GOV,ois:get('ois'),
    cot:COT,now:dayNow(),price20,priceAsOf:asof
  })||null;
  const macroText=relative?.available?relative.macroStory:
    'Manca il confronto bilaterale delle due economie.';
  const ratesText=relative?.available?relative.govStory+' '+relative.moneyStory:
    'Tassi e aspettative monetarie non verificati per entrambe le valute.';
  const cotText=relative?.available?relative.cotStory:
    'COT bilaterale non verificato.';
  const judgement=relative?.available?relative.verdict+' '+relative.timing+' '+relative.watch:
    'Il prezzo osservato non basta a dimostrare una tesi operativa.';
  const verdict=positive?'PREZZO FAVOREVOLE A '+country:
    negative?'PREZZO SFAVOREVOLE A '+country:'PREZZO DA CONFERMARE';
  const last5=target?.move5;
  const shortVsMedium=finite(last5)&&finite(price20)?
    price20>.025&&last5<-.025?'Il prezzo ha guadagnato sulle 20 sedute, ma nelle ultime 5 è arretrato: il movimento recente non conferma quello più ampio.':
    price20<-.025&&last5>.025?'Le 20 sedute restano negative, ma nelle ultime 5 il cambio recupera: è un tentativo di ripresa, non ancora una svolta confermata.':
    price20>.025&&last5>.025?'Le ultime 5 e le ultime 20 sedute sono entrambe positive. La continuità del prezzo è osservata; la causa rimane da verificare.':
    price20<-.025&&last5<-.025?'Le ultime 5 e le ultime 20 sedute sono entrambe negative. Il prezzo mostra debolezza relativa persistente nei due intervalli.':
    'La variazione recente non identifica ancora una tendenza chiara.':
    'Per confrontare breve e medio termine servono fixing BCE sufficienti e allineati.';
  const otherRate=observedRate(against);
  const shared2Y=r&&otherRate&&r.date===otherRate.date;
  const differential=shared2Y?(r['2Y']-otherRate['2Y'])*100:null;
  const ratesBrief=shared2Y?
    'Al '+date(r.date)+' il differenziale governativo a 2 anni '+country+'−'+against+
    ' è '+sign(differential,1,' punti base')+
    '. È una fotografia del rendimento relativo, non un repricing di banca centrale né una spiegazione automatica del cambio.':
    'Non abbiamo un confronto 2Y '+country+'−'+against+
    ' riferito alla stessa seduta. Non attribuiamo quindi il movimento del cambio ai differenziali di rendimento.';
  const nextStep=finite(last5)&&finite(price20)&&
    ((last5>0&&price20<0)||(last5<0&&price20>0))?
    'La prima conferma è capire se il movimento delle ultime 5 sedute prosegue o si esaurisce. Poi verificare aspettative monetarie comparabili e nuove sorprese macro.':
    'Cercare persistenza nei fixing e aggiornamenti macro/rates sulle stesse date. Il COT è settimanale e da solo non conferma i movimenti di oggi.';
  return '<section class="orient-lead orient-voice"><div class="orient-lead-copy"><span class="chapter-kicker">IL DESK / '+FLAGS[country]+' '+esc(NAMES[country])+' CONTRO '+against+'</span>'
    +'<span class="orient-verdict">'+esc(verdict)+'</span>'
    +'<h2>'+esc(headline)+'</h2>'
    +'<div class="orient-first-read" aria-label="Lettura immediata della coppia">'
    +'<div><span>01 / COSA VEDIAMO</span><p>'+esc(opening)+' '+esc(shortVsMedium)+'</p></div>'
    +'<div><span>02 / COSA DICONO I TASSI</span><p>'+esc(ratesBrief)+'</p></div>'
    +'<div><span>03 / COSA CONTROLLARE</span><p>'+esc(nextStep)+'</p></div></div>'
    +'<details class="orient-thesis-details"><summary><strong>Perché? Apri macro, pricing, COT e giudizio completo</strong>'
    +'<small>Dati e spiegazioni con la propria data, separati dal movimento del prezzo</small></summary>'
    +'<div class="orient-thesis-body">'
    +'<p class="orient-context"><strong>Macro relativa.</strong> '+esc(macroText)+'</p>'
    +'<p class="orient-context"><strong>Tassi e aspettative.</strong> '+esc(ratesText)+'</p>'
    +'<p class="orient-context"><strong>Posizionamento.</strong> '+esc(cotText)+'</p>'
    +'<p class="orient-desk-judgment"><strong>Il giudizio del desk.</strong> '+esc(judgement)+'</p>'
    +'</div></details>'
    +'<div class="orient-focus-actions"><button class="action-primary" type="button" data-cs-openpair="'+country+against+'">Apri la tesi '+country+'/'+against+' <span>↗</span></button><a href="#macro" class="action-minimal">Approfondisci la macro →</a></div></div>'
    +'<div class="orient-spot"><span class="micro-over">IL PREZZO · '+country+'/'+against+'</span><strong>'+fmt(target?.quote?.value,5)+'</strong><small>1 '+country+' = '+against+' · BCE fixing '+date(asof)+'</small>'
    +'<div class="orient-spot-parts">'+[['5 sedute',target?.move5],['20 sedute',target?.move20],['60 sedute',target?.move60]].map(([k,v])=>'<div><span>'+k+'</span><b class="'+(v<0?'orient-neg':'')+'">'+sign(v,2,'%')+'</b></div>').join('')+'</div>'
    +'<label class="orient-counterparty">Confronta con<select class="select" id="cs-other">'+FX.filter(k=>k!==country).map(k=>'<option value="'+k+'" '+(k===against?'selected':'')+'>'+FLAGS[k]+' '+k+' — '+NAMES[k]+'</option>').join('')+'</select></label>'
    +'</div></section>';
 }
 function evidence(){
  return '<section class="orient-chapter"><div class="orient-chapter-head"><div><span class="chapter-kicker">01 / QUATTRO LENTI, ZERO DUPLICAZIONI</span><h2>Il contesto <em>in quattro letture.</em></h2></div><p>Qui trovi ciò che serve a orientarti. Grafici, storici, curve OIS e tabelle CFTC sono nei laboratori dedicati.</p></div>'
   +'<div class="orient-evidence">'+facts.map(f=>'<article class="orient-evidence-item" data-evidence="'+f.key+'"><div class="orient-evidence-intro"><span class="orient-index">'+f.n+'</span><div><strong>'+esc(f.title)+'</strong><small>'+esc(f.subtitle)+'</small></div></div>'
    +'<div class="orient-number">'+esc(f.metric)+'</div><div class="orient-data-label">'+esc(f.label)+'</div><p>'+esc(f.detail)+'</p>'
    +'<div class="orient-evidence-bottom"><span>'+esc(f.hint)+'</span>'+(f.key==='price'?'<button class="orient-investigate" type="button" data-cs-openpair="'+country+against+'">'+esc(f.action)+' ↗</button>':'<a href="#'+f.dest+'">'+esc(f.action)+' ↗</a>')+'</div></article>').join('')+'</div></section>';
 }
 function bar(x,max){
  if(!finite(x))return '<span class="orient-bar-none">—</span>';
  const width=Math.max(2,Math.min(100,Math.abs(x)/(max||1)*100));
  return '<span class="orient-diverge"><i class="'+(x<0?'negative':'positive')+'" style="width:'+width+'%"></i></span>';
 }
 function peers(){
  const selectedSort=['currency','return','yield'].includes(state.csSort)?state.csSort:'return';
  const vals=[...counterparts],v=x=>x['move'+w];
  vals.sort((a,b)=>selectedSort==='currency'?a.ccy.localeCompare(b.ccy):
    selectedSort==='yield'?(finite(r?.['2Y'])&&finite(b.r2)?b.r2:-Infinity)-(finite(r?.['2Y'])&&finite(a.r2)?a.r2:-Infinity):
    (finite(v(b))?v(b):-Infinity)-(finite(v(a))?v(a):-Infinity));
  const max=Math.max(1,...vals.map(x=>Math.abs(v(x)||0)));
  return '<section class="orient-chapter orient-compare"><div class="orient-chapter-head"><div><span class="chapter-kicker">02 / L’UNICO GRAFICO DEL COUNTRY DESK</span>'
   +'<h2>Come si comporta '+country+' <em>contro le altre sette?</em></h2></div><p>Performance relativa ricavata dagli stessi fixing BCE, non un indice di forza proprietario né un segnale FX.</p></div>'
   +'<div class="orient-peer-panel"><div class="orient-peer-controls"><div class="pill-controls">'+[5,20,60].map(n=>'<button type="button" data-cs-returnwindow="'+n+'" class="pill '+(w===n?'active':'')+'" aria-pressed="'+String(w===n)+'">'+n+' sedute</button>').join('')+'</div>'
   +'<div class="pill-controls">'+[['return','Performance'],['currency','Valuta'],['yield','2Y controparte']].map(([k,l])=>'<button type="button" data-cs-sort="'+k+'" class="pill '+(selectedSort===k?'active':'')+'" aria-pressed="'+String(selectedSort===k)+'">'+l+'</button>').join('')+'</div></div>'
   +'<div class="orient-peer-legend"><span>← '+country+' perde terreno</span><span>'+country+' guadagna terreno →</span></div>'
   +'<div class="orient-peer-rows">'+vals.map(x=>'<button type="button" data-cs-other="'+x.ccy+'" class="orient-peer-row '+(against===x.ccy?'selected':'')+'" aria-pressed="'+String(against===x.ccy)+'">'
    +'<span class="peer-name">'+FLAGS[x.ccy]+' '+country+'/'+x.ccy+'</span>'
    +'<span class="peer-negative-zone">'+(finite(v(x))&&v(x)<0?bar(v(x),max):'')+'</span><span class="peer-zero"></span>'
    +'<span class="peer-positive-zone">'+(finite(v(x))&&v(x)>=0?bar(v(x),max):'')+'</span>'
    +'<strong class="'+(v(x)<0?'orient-neg':'')+'">'+sign(v(x),2,'%')+'</strong>'
    +'<small>'+fmt(x.quote?.value,4)+'</small></button>').join('')+'</div>'
   +'<div class="orient-peer-footer"><p>Stesso giorno di fixing per tutte le coppie selezionate: <b>'+date(FXDATA?.last_as_of||asof)+'</b>. '
   +'Il grafico mostra il rendimento di '+country+' contro ciascuna controvaluta, non la performance futura. '
   +'I tassi 2Y non entrano in questo calcolo.</p><button type="button" data-cs-openpair="'+country+against+'" class="orient-pair-action">Apri '+country+'/'+against+' nel Pair Deep Dive ↗</button></div></div></section>';
 }
 function checkpoint(){
  const mixedMacro=!!(cpi?.as_of&&unemp?.as_of&&cpi.as_of!==unemp.as_of);
  const priceDate=asof,cotDate=cot?.asof,govDate=r?.date,good=priceDate===govDate&&priceDate===cotDate;
  const quality=ois?.quality||'n.d.';
  return '<section class="orient-checkpoint"><div><span class="chapter-kicker">03 / COSA MONITORARE</span><h2>Qual è il prossimo<br><em>controllo utile?</em></h2>'
   +'<p>Una valutazione relativa richiede più di una fotografia. Apri la sezione specializzata in cui verificare l’ipotesi, senza rileggere gli stessi grafici.</p></div>'
   +'<div class="orient-issues">'+
    '<div><span class="orient-issue-icon">01</span><p><strong>Allineamento temporale</strong><small>FX '+date(priceDate)+' · GOV '+date(govDate)+' · COT '+date(cotDate)+'. '+(good?'Le date coincidono, ma gli strumenti restano diversi.':'Non confrontare questi movimenti come una reazione simultanea.')+'</small></p></div>'+
    '<div><span class="orient-issue-icon">02</span><p><strong>Macro level vs change</strong><small>Inflazione '+period(cpi?.as_of)+'; lavoro '+period(unemp?.as_of)+'. '+(mixedMacro?'Periodi differenti: nessuna accelerazione aggregata deducibile.':'Verificare composizione e nuove rilevazioni nel Macro Lab.')+'</small></p></div>'+
    '<div><span class="orient-issue-icon">03</span><p><strong>Qualità del pricing</strong><small>'+esc(ois?.kind||'n.d.')+' · '+esc(quality)+' · 6M '+date(six?.as_of)+'. Non equiparare futures/proxy e OIS.</small></p></div>'+
    '</div></section>';
 }
 function closing(){
  return '<section class="orient-closing"><div><span class="chapter-kicker">IL PERCORSO CORRETTO</span><h2>Orientamento qui.<br><em>Profondità dove serve.</em></h2><p>Macro Lab contiene gli storici economici; Tassi & OIS le curve e i tenori; COT i posizionamenti; Coppie FX mette insieme le evidenze.</p></div>'
   +'<div class="orient-route-links"><a href="#macro">Macro Lab ↗</a><a href="#rates">Tassi & OIS ↗</a><a href="#cot">COT ↗</a><a href="#pairs">Coppie FX ↗</a></div></section>';
 }
 function render(){
  return pageHero('FX G8 / VALUTE','Otto valute, <em>quattro prove.</em>','Prima economia, rendimenti, aspettative prezzate e conferma del prezzo. Poi approfondisci solo ciò che merita attenzione.')
   +strengthBoard()+strengthFocus()
   +'<details class="strength-pair-fold"><summary><strong>Confronta '+country+' con una seconda valuta</strong><span>La tesi bilaterale, il grafico delle sette controparti e le verifiche specifiche</span></summary>'
   +story()+peers()+'</details>'
   +'<details class="strength-method-fold"><summary><strong>Verifica la classifica di prezzo e tutte le fonti</strong><span>Graduatoria BCE, storico macro, tassi, COT e limiti temporali</span></summary>'
   +ranking()+evidence()+checkpoint()+'</details>'
   +'<p class="source-caption">Contesto: Macro Thermometer; NATIVE_RATES_DATA; NATIVE_CB_DATA; CFTC Legacy V250; pricing OIS/futures/proxy con fonte per valuta. Performance FX calcolata da ECB_G8_PRICE_HISTORY (EUR cross). Ogni dato è datato. La V2 operativa e i suoi segnali rimangono invariati.</p>';
 }
 return render();
}
root.FXQuantCurrencies={render:build};
})(window);
