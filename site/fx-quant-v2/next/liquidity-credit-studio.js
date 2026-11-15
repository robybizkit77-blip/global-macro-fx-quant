'use strict';
/* FX Quant Next — Liquidity & Credit, read-only G8 research.
 * Source dates and individual credit gaps are never upgraded by publication.
 * The page explains possible FX transmission, not a mechanical FX signal.
 */
(function(root){
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const validCcy=x=>/^(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)$/.test(x||'');
 const short=x=>String(x??'').trim();
 const norm=s=>short(s).toUpperCase();
 function series(s){
  if(!Array.isArray(s?.dates)||!Array.isArray(s?.values))return [];
  const rows=s.dates.map((label,i)=>({label:short(label),value:s.values[i]}))
   .filter(x=>x.label&&finite(x.value)&&x.value>0);
  return rows.slice(-80);
 }
 function direction(raw,exists){
  if(!exists)return {label:'NON DISPONIBILE',tone:'unknown'};
  const d=norm(raw);
  if(d.includes('AUMENTO')||d.includes('CRESCITA'))return {label:'IN AUMENTO',tone:'up'};
  if(d.includes('CALO')||d.includes('DISCESA'))return {label:'IN CALO',tone:'down'};
  if(d.includes('STABILE'))return {label:'STABILE',tone:'flat'};
  return {label:'DA VERIFICARE',tone:'unknown'};
 }
 const MONTHS={jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12};
 function observationDate(label){
  const x=short(label);
  const q=x.match(/^(\d{4})-Q([1-4])$/);
  if(q)return new Date(Date.UTC(Number(q[1]),Number(q[2])*3,0)).toISOString().slice(0,10);
  const month=x.match(/^(\d{4})-(\d{2})$/);
  if(month)return new Date(Date.UTC(Number(month[1]),Number(month[2]),0)).toISOString().slice(0,10);
  const iso=x.match(/^(\d{4}-\d{2}-\d{2})(?:T.*)?$/);
  if(iso)return iso[1];
  const european=x.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if(european)return european[3]+'-'+european[2]+'-'+european[1];
  const british=x.match(/^(\d{1,2}) ([A-Za-z]{3}) (\d{4})$/);
  if(british&&MONTHS[british[2].toLowerCase()]){
   return british[3]+'-'+String(MONTHS[british[2].toLowerCase()]).padStart(2,'0')+'-'+british[1].padStart(2,'0');
  }
  return null;
 }
 const dateMs=d=>d?Date.parse(d+'T12:00:00Z'):NaN;
 function sourceEvidence(row,now){
  if(!row?.label||!finite(row.last_value))return {coverage:false,state:'ASSENTE',tone:'unknown',message:'Serie numerica non disponibile: una direzione dichiarata nel dataset non costituisce prova.',delta:null};
  const last=observationDate(row.last_date),today=observationDate(now);
  const history=Array.isArray(row.dates)?row.dates:[];
  const prior=history.length>1?observationDate(history.at(-2)):null;
  const cadence=last&&prior?Math.round((dateMs(last)-dateMs(prior))/864e5):null;
  const limit=cadence!==null&&cadence>70?135:cadence!==null&&cadence>15?70:21;
  const age=last&&today?Math.round((dateMs(today)-dateMs(last))/864e5):null;
  const valid=age!==null&&age>=0;
  const overdue=valid&&age>limit;
  const staleText=!valid?'Data non classificabile':overdue?'Serie storica: aggiornamento da verificare':'Ultima osservazione datata';
  const values=Array.isArray(row.values)?row.values:[];
  const previous=values.length>1?values.at(-2):null;
  const delta=finite(previous)&&finite(row.last_value)?row.last_value-previous:null;
  let observation='Ultima variazione non verificabile';
  if(finite(delta)){
   const survey=/SLOOS|SLOS|Tankan|BLS|standard|lending attitude|disponibilità credito|condizioni credito/i.test(row.label);
   const isRate=/yoy|a\/a|percent|%/i.test(row.label);
   const move=survey||isRate?delta:(Math.abs(previous)>0?100*delta/Math.abs(previous):null);
   if(finite(move))observation=(move>0?'+':move<0?'−':'')+Math.abs(move).toLocaleString('it-IT',{maximumFractionDigits:2})+
    (survey?' punti della survey':isRate?' punti percentuali':'%')+' dall’osservazione precedente'+
    (survey?' (segno da interpretare secondo la definizione della survey)':'');
  }
  return {coverage:true,state:overdue?'STORICO':valid?'DATATO':'DATA DA VERIFICARE',tone:overdue?'warn':'neutral',
   message:staleText+' · '+short(row.last_date)+' · '+observation+
    '. La direzione di scenario può riferirsi a più osservazioni, non a questa singola variazione.',
   delta};
 }
 function interpret(row){
  if(!row)return {headline:'Dati G8 non disponibili',meaning:'Nessuna lettura è ricostruita artificialmente.',fx:'Non emerge un collegamento verificabile con il Forex.',watch:'Recuperare la fonte originale e le date.',liquidity:direction('',false),credit:direction('',false)};
  const liq=direction(row.liquidity_dir,Boolean(row.liquidity?.label&&finite(row.liquidity?.last_value)));
  const cr=direction(row.credit_dir,Boolean(row.credit?.label&&finite(row.credit?.last_value)));
  let headline,meaning;
  if(liq.tone==='down'&&cr.tone==='up'){
   headline='Nelle rispettive serie storiche, liquidità in calo e credito in espansione.';
   meaning='I due canali divergono: il credito osservato non conferma una stretta generalizzata, ma la minore liquidità potrebbe aumentare la sensibilità a shock futuri.';
  }else if(liq.tone==='up'&&cr.tone==='up'){
   headline='Le due serie storiche indicano liquidità e credito in crescita.';
   meaning='È una combinazione compatibile con condizioni finanziarie meno restrittive, ma servono standard di prestito, domanda e tassi per verificarlo.';
  }else if(liq.tone==='down'&&cr.tone==='down'){
   headline='Le due serie storiche indicano liquidità e credito in calo.';
   meaning='Potenziale freno alla trasmissione finanziaria: la persistenza va verificata con attività economica, spread e politica monetaria.';
  }else if(liq.tone==='flat'&&cr.tone==='up'){
   headline='Credito in crescita, liquidità stabile nell’ultima classificazione storica.';
   meaning='La creazione di credito e la liquidità di banca centrale non misurano la stessa cosa: non sono due conferme indipendenti di allentamento.';
  }else if(liq.tone==='up'&&cr.tone==='flat'){
   headline='Liquidità in crescita, credito classificato stabile nello storico.';
   meaning='La disponibilità di riserve o moneta non implica automaticamente maggiore domanda e concessione di prestiti.';
  }else if(cr.tone==='unknown'){
   headline='Liquidità storica disponibile, ma senza serie numerica del credito.';
   meaning='La direzione della liquidità da sola non basta a descrivere la trasmissione all’economia reale. Le survey possono offrire soltanto un contesto distinto.';
  }else{
   headline='I canali di liquidità e credito non danno una conferma univoca.';
   meaning='Il livello, la direzione e la frequenza delle due serie vanno tenuti separati. Non sommiamo aggregati di natura diversa.';
  }
  return {headline,meaning,
   fx:'Per il Forex conta se questa combinazione cambia la crescita relativa, il percorso atteso della banca centrale o la domanda di valuta rifugio. È una trasmissione possibile, non una causalità già dimostrata.',
   watch:'Controllare nuove pubblicazioni del credito, survey sugli standard, differenziali monetari, spread IG/HY e la risposta della valuta.',
   liquidity:liq,credit:cr};
 }
 const FX_LENSES={
 USD:{fx:'Se la liquidità cresce ma il credito non prende velocità, la trasmissione alla domanda USA potrebbe restare contenuta. Per USD servono Fed pricing relativo e dollaro osservato: in caso di stress la domanda di liquidità rifugio può compensare rendimenti più bassi.',
  watch:'Nuovo H.8 credito bancario, SLOOS e crescita; confrontare il 6M USA con EUR e JPY su date coerenti, poi EUR/USD e USD/JPY.'},
 EUR:{fx:'Nella zona euro, credito alle imprese ed eccesso di liquidità BCE descrivono canali diversi. Un recupero dei prestiti potrebbe sostenere la crescita, ma per EUR conta la reazione del pricing BCE rispetto a Fed e BoE.',
  watch:'Prestiti imprese e survey BLS, attività manifatturiera e variazioni €STR/futures; verificare EUR/USD e EUR/GBP.'},
 GBP:{fx:'Le riserve BoE non sono un indicatore diretto della domanda di mutui. La crescita del credito garantito è un pezzo del quadro, da collegare a consumi e aspettative BoE prima di dedurre forza GBP.',
  watch:'Nuove serie su credito famiglie e imprese, survey condizioni e pricing SONIA rispetto a €STR; monitorare EUR/GBP e GBP/USD.'},
 JPY:{fx:'Riserve BoJ in riduzione e credito bancario in crescita non provano da sole una stretta dell’economia. Per JPY il meccanismo decisivo resta il differenziale con gli altri paesi, insieme al rischio di riduzione del carry.',
  watch:'Decisioni BoJ, prestiti e riserve, 2Y relativo USA/JPY e futures; osservare USD/JPY e AUD/JPY in fasi risk-off.'},
 CHF:{fx:'I depositi a vista presso SNB possono variare per molte ragioni, incluse le operazioni monetarie: il calo da solo non prova un cambio di policy. La dinamica CHF può essere dominata dalla domanda di beni rifugio.',
  watch:'Nuovi sight deposits, credito e tono SNB, differenziale EUR/CHF e condizioni di rischio europee.'},
 CAD:{fx:'Manca una serie numerica del credito nel layer disponibile. La liquidità di regolamento da sola non dimostra se il credito canadese sta espandendosi. Per CAD servono BoC, domanda interna, petrolio e rischio globale.',
  watch:'Ripristinare la fonte del credito bancario, nuova SLOS e pricing BoC relativo alla Fed; osservare USD/CAD e AUD/CAD.'},
 AUD:{fx:'Saldi di regolamento RBA e credito alle imprese rappresentano canali diversi. Un impulso del credito non è sufficiente a sostenere AUD se aspettative RBA, crescita cinese o propensione al rischio divergono.',
  watch:'Credito imprese, domanda cinese, futures RBA contro Fed e BoC; verificare AUD/USD e AUD/CAD.'},
 NZD:{fx:'Per il NZD conta se la crescita del credito si riflette nella domanda interna e cambia le attese sui tassi RBNZ. I saldi di regolamento risentono anche delle operazioni della banca centrale e del governo. Su AUD/NZD serve poi conferma dal differenziale atteso RBA–RBNZ e dal prezzo.',
  watch:'Aggiornamenti RBNZ su settlement cash e credito, confronto monetario con RBA e comportamento AUD/NZD e NZD/USD.'}
 };
 function jpyBOJCreditResearch(esc,fmt,now){
  const x=root.FXQuantJPYBankCreditResearch;
  if(!x||x.schema!=='GMFQ_NEXT_JPY_BOJ_BANK_CREDIT_RESEARCH_V1'||
     x.status!=='VERIFIED_BOJ_MD11_MONTHLY_BANK_CREDIT_RESEARCH_ONLY'||
     x.publisher!=='Bank of Japan'||x.database!=='MD11'||
     x.series_id!=='DLCLAEDBLTTO'||
     x.category!=='bank_credit_end_period_stock'||
     x.unit!=='100 milioni JPY'||x.frequency!=='M'||
     x.end_of_period!==true||
     x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     x.first_release_pit_verified!==false||
     x.original_canonical_last!=='2026-07'||
     x.original_canonical_value!==6764306||
     !Number.isInteger(x.matched_canonical_months)||x.matched_canonical_months<12||
     !Array.isArray(x.dates)||!Array.isArray(x.values)||
     x.dates.length<3||x.dates.length!==x.values.length||
     x.dates.at(-1)!==x.last_observation||
     !/^https:\/\/www\.stat-search\.boj\.or\.jp\/ssi\/mtshtml\//.test(x.source_url))return '';
  const dates=x.dates,v=x.values;
  const continuous=dates.every((d,i)=>{
    if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(d)||!finite(v[i])||v[i]<=2000000||v[i]>=12000000)return false;
    if(i===0)return true;
    const year=Number(d.slice(0,4)),month=Number(d.slice(5));
    const py=Number(dates[i-1].slice(0,4)),pm=Number(dates[i-1].slice(5));
    return year*12+month-py*12-pm===1;
  });
  const period=observationDate(x.last_observation),today=observationDate(now);
  if(!continuous||!period||!today||dateMs(period)>dateMs(today))return '';
  const last=v.at(-1),prev=v.at(-2),two=v.at(-3);
  const move=(last/prev-1)*100,prior=(prev/two-1)*100;
  if(!finite(move)||!finite(prior)||Math.abs(move)>12||Math.abs(prior)>12)return '';
  const age=Math.round((dateMs(today)-dateMs(period))/864e5);
  const freshness=age>110?'STORICO · NUOVA PUBBLICAZIONE DA CONTROLLARE':'SERIE BOJ UFFICIALE DATATA';
  const pace=move>prior+0.025?'più rapido':move<prior-0.025?'meno rapido':'simile';
  const moveSigned=q=>(q>0?'+':q<0?'−':'')+fmt(Math.abs(q),2);
  return '<section class="drivers-cad-official drivers-jpy-official" aria-label="BoJ credito bancario mensile fonte ufficiale separata">'+
   '<span class="mini-overline">BANK OF JAPAN · CREDITO BANCARIO DI FINE MESE</span>'+
   '<h3>Giappone: lo stock dei prestiti sale, ma va verificata la trasmissione all’economia.</h3>'+
   '<p>A '+esc(x.last_observation)+' i prestiti in essere delle banche domestiche sono '+esc(fmt(last/10,2))+
   ' miliardi JPY, contro '+esc(fmt(prev/10,2))+' miliardi il mese precedente: variazione dello stock '+
   esc(moveSigned(move))+'%. Il ritmo mensile è '+esc(pace)+' rispetto a quello precedente ('+esc(moveSigned(prior))+'%).</p>'+
   '<p><b>Contesto:</b> questa serie include conti bancari, fiduciari e delle filiali estere delle banche autorizzate in Giappone; non sono nuovi prestiti e non è l’indice dei saldi presso la BoJ. Il movimento può riflettere anche composizione e fattori di bilancio: non basta per dire che la domanda interna accelera.</p>'+
   '<p><b>Per lo yen:</b> chiediamoci se crescita, inflazione e dati sul credito cambiano davvero le aspettative BoJ, il differenziale JGB/UST e il carry. Poi controlliamo USD/JPY e i cross yen. Un credito in aumento senza repricing né conferma del prezzo non è un segnale operativo.</p>'+
   '<div class="drivers-cad-source"><span>'+freshness+' · periodo '+esc(x.last_observation)+
   ' · MD11 DLCLAEDBLTTO · '+esc(x.matched_canonical_months)+
   ' mesi storici corrispondenti · livello stock, non nuove erogazioni · vintage del primo rilascio non certificata · ranking FX invariato</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: BoJ · Time-Series Data Search ↗</a></div></section>';
 }
 function gbpBoESecuredCreditReading(esc,fmt,now){
  const x=root.FXQuantGBPBoESecuredCreditResearch;
  if(!x||x.schema!=='GMFQ_NEXT_GBP_BOE_SECURED_CREDIT_GROWTH_V1'||
     x.status!=='VERIFIED_BOE_LPMVTYI_SECURED_GROWTH_RESEARCH_ONLY'||
     x.publisher!=='Bank of England'||x.series_id!=='LPMVTYI'||
     x.category!=='secured_household_credit_yoy_growth'||
     x.unit!=='percent_yoy'||x.frequency!=='M'||
     x.seasonally_adjusted!==true||x.first_release_pit_verified!==false||
     x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     !Array.isArray(x.dates)||!Array.isArray(x.values)||
     x.dates.length<3||x.values.length!==x.dates.length||
     x.last_observation!==x.dates.at(-1)||
     !/^https:\/\/www\.bankofengland\.co\.uk\/boeapps\/database\//.test(x.source_url))return '';
  const months=x.dates,values=x.values;
  const validSeries=months.every((month,i)=>
    /^\d{4}-\d{2}$/.test(month)&&
    (i===0||month>months[i-1])&&finite(values[i])&&values[i]>-15&&values[i]<25);
  const period=observationDate(months.at(-1)),today=observationDate(now);
  if(!validSeries||!period||!today||dateMs(period)>dateMs(today))return '';
  const jul=months.indexOf('2026-07'),sep=months.indexOf('2026-09');
  if(jul<0||sep<0||Math.abs(values[jul]-3.6)>.16||Math.abs(values[sep]-3.4)>.16)return '';
  const last=values.at(-1),prior=values.at(-2),delta=last-prior;
  if(!Number.isFinite(delta)||Math.abs(delta)>8)return '';
  const pace=delta<-.049?'in rallentamento':delta>.049?'in accelerazione':'sostanzialmente stabile';
  const yoyState=last>0?'continua a espandersi su base annua':last<0?'si contrae su base annua':'è invariato su base annua';
  const signed=v=>(v>0?'+':v<0?'−':'')+fmt(Math.abs(v),1);
  const age=Math.round((dateMs(today)-dateMs(period))/864e5);
  const state=age>75?'PERIODO STORICO · NON CORRENTE':'SERIE MENSILE UFFICIALE DATATA';
  const matchedRelease=x.last_observation==='2026-09'&&x.official_september_release_date==='2026-10-29';
  return '<div class="drivers-gbp-credit-bridge" aria-label="Credito garantito BoE crescita annuale corretta per stagionalità">'+
    '<b>SECONDO CANALE · CREDITO ALLE FAMIGLIE, NON RISERVE</b>'+
    '<p>Il credito garantito alle famiglie '+esc(yoyState)+': <strong>'+esc(fmt(last,1))+
    '% annuo nel '+esc(x.last_observation)+'</strong>, rispetto al '+esc(fmt(prior,1))+
    '% del mese precedente. La variazione del tasso è '+esc(signed(delta))+
    ' <b>punti percentuali</b>: ritmo '+esc(pace)+'. Non è una contrazione del credito quando la crescita resta positiva.</p>'+
    (matchedRelease?'<p>Il comunicato BoE del 29 ottobre sullo stesso settembre segnala anche nuovi mutui netti per 3,9 miliardi GBP (4,2 ad agosto) e approvazioni per l’acquisto di casa scese a 53.400. È una conferma circoscritta al mercato ipotecario, <b>non</b> al credito aziendale.</p>':'')+
    '<p>Confronto corretto: le riserve BoE sono uno stock settimanale di passività della banca centrale; questa è la crescita annua mensile dei prestiti ipotecari. Date e perimetri diversi: non sono due misure confrontabili di un unico flusso, né due conferme automatiche su GBP.</p>'+
    '<small>'+state+' · periodo '+esc(x.last_observation)+
    ' · LPMVTYI destagionalizzato · vintage iniziale non certificato · feed canonico GBP invariato · '+
    '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Serie BoE LPMVTYI ↗</a>'+
    (matchedRelease?' · <a href="'+esc(x.official_september_2026_release)+'" target="_blank" rel="noopener noreferrer">Money and Credit · 29 ottobre ↗</a>':'')+
    '</small></div>';
 }
 function gbpBoEReservesResearch(esc,fmt,now){
  const x=root.FXQuantGBPBoEReservesResearch;
  if(!x||x.schema!=='GMFQ_NEXT_GBP_BOE_WEEKLY_RESERVES_V1'||
     x.status!=='VERIFIED_BOE_WEEKLY_RESERVE_STOCK_RESEARCH_ONLY'||
     x.publisher!=='Bank of England'||x.series_id!=='RPWB56A'||
     x.source_contract!=='BoE Weekly Report / Sterling Liabilities / Reserves balances'||
     x.unit!=='milioni GBP'||x.frequency!=='W'||
     x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     x.first_release_pit_verified!==false||x.seasonally_adjusted!==false||
     x.asof_canonical_overlap!=='2026-09-16'||x.value_canonical_overlap!==638012)return '';
  const period=observationDate(x.source_period),previous=observationDate(x.previous_period),
        published=observationDate(x.published_on),today=observationDate(now);
  const [latest,earlier,delta]=[x.latest_balance_million_gbp,x.previous_balance_million_gbp,x.weekly_change_million_gbp];
  if(!period||!previous||!published||!today||
     dateMs(period)>dateMs(published)||dateMs(published)>dateMs(today)||
     dateMs(period)-dateMs(previous)!==7*864e5||
     ![latest,earlier,delta].every(finite)||latest<300000||earlier<300000||
     latest-earlier!==delta||Math.abs(delta)>150000||
     !/^https:\/\/www\.bankofengland\.co\.uk\/weekly-report\/\d{4}\/\d{1,2}-[a-z]+-\d{4}$/.test(x.source_url))return '';
  const age=Math.round((dateMs(today)-dateMs(period))/864e5);
  const sign=delta>0?'+':delta<0?'−':'';
  const groupedMove=String(Math.abs(delta)).replace(/\B(?=(\d{3})+(?!\d))/g,'.');
  const direction=delta>0?'sono aumentate':delta<0?'sono diminuite':'sono rimaste invariate';
  const quality=age>25?'STORICO · NUOVO RAPPORTO DA CONTROLLARE':'RAPPORTO SETTIMANALE UFFICIALE';
  return '<section class="drivers-cad-official drivers-gbp-official" aria-label="BoE riserve bancarie fonte ufficiale separata">'+
   '<span class="mini-overline">BANK OF ENGLAND · RISERVE BANCARIE UFFICIALI</span>'+
   '<h3>GBP: le riserve cambiano, ma non è una prova di credito più facile.</h3>'+
   '<p>Al '+esc(x.source_period)+' le riserve delle banche presso la BoE '+esc(direction)+
   ' di <b>'+sign+esc(groupedMove)+' milioni GBP</b> in una settimana: saldo '+esc(fmt(latest,0))+
   ' milioni, contro '+esc(fmt(earlier,0))+' milioni al '+esc(x.previous_period)+'.</p>'+
   '<p><b>Cosa sto osservando:</b> uno stock di passività della banca centrale, non un flusso di nuovi prestiti. Anche con riserve in aumento, non possiamo dedurre un allentamento della BoE, nuovi acquisti di asset o domanda di GBP. I prestiti garantiti sono una seconda misura economica con frequenza e periodo propri: non vanno sommati ai saldi di riserva.</p>'+
   gbpBoESecuredCreditReading(esc,fmt,now)+
   '<p><b>Quale verifica Forex manca?</b> Il mercato deve mostrare se cambia il percorso SONIA relativo a €STR e Fed; poi cerchiamo la risposta di EUR/GBP e GBP/USD, distinguendo fattori GBP da debolezza dell’altra valuta. Senza questo collegamento non emerge un trade dalle sole riserve.</p>'+
   '<div class="drivers-cad-source"><span>'+quality+' · osservazione '+esc(x.source_period)+
   ' · pubblicazione '+esc(x.published_on)+' · RPWB56A · dati settimanali, revisioni possibili · fonte separata dal feed FX</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: BoE · Weekly Report ↗</a></div></section>';
 }
 function audRBAESReading(esc,fmt,now){
  const x=root.FXQuantAUDESBalancesResearch;
  if(!x||x.schema!=='GMFQ_NEXT_AUD_RBA_ES_BALANCES_V1'||
     x.status!=='VERIFIED_RBA_WEEKLY_ES_BALANCE_RESEARCH_ONLY'||
     x.publisher!=='Reserve Bank of Australia'||
     x.source_contract!=='RBA weekly balance sheet / Exchange Settlement balances'||
     x.frequency!=='W'||x.unit!=='milioni AUD'||
     x.first_release_pit_verified!==false||
     x.source_release_timestamp_verified!==false||
     x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     x.value_canonical_overlap!==173965||x.asof_canonical_overlap!=='2026-09-16')return '';
  const period=observationDate(x.source_period),today=observationDate(now);
  if(!period||!today||dateMs(period)>dateMs(today)||
     !/^\d{4}-\d{2}-\d{2}$/.test(x.source_period)||
     ![x.latest_balance_million_aud,x.weekly_movement_million_aud,x.previous_implied_million_aud].every(finite)||
     x.latest_balance_million_aud<10000||x.latest_balance_million_aud>900000||
     x.previous_implied_million_aud<=0||
     x.latest_balance_million_aud-x.previous_implied_million_aud!==x.weekly_movement_million_aud||
     !/^https:\/\/www\.rba\.gov\.au\/statistics\/balance-sheet\/$/.test(x.source_url))return '';
  const age=Math.round((dateMs(today)-dateMs(period))/864e5);
  const movement=x.weekly_movement_million_aud;
  const signed=(movement>0?'+':movement<0?'−':'')+String(Math.abs(movement)).replace(/\B(?=(\d{3})+(?!\d))/g,'.');
  const observation=age>25?'STORICO · DA AGGIORNARE':'SETTIMANALE UFFICIALE';
  return '<div class="drivers-aud-es-bridge" aria-label="Riserve RBA settimanali fonte indipendente">'+
   '<b>SECONDO CANALE, NON SECONDA CONFERMA: LE RISERVE</b>'+
   '<p>Al '+esc(x.source_period)+' i saldi <em>Exchange Settlement</em> delle banche presso RBA sono '+esc(fmt(x.latest_balance_million_aud,0))+
   ' milioni AUD, '+esc(signed)+' milioni sulla settimana. Il saldo precedente di '+esc(fmt(x.previous_implied_million_aud,0))+
   ' milioni è <b>ricavato dal movimento pubblicato</b>, non una nuova osservazione indipendente.</p>'+
   '<p>Queste sono riserve di regolamento tra banche, <b>non</b> nuovi prestiti, liquidità netta trasferita ai mercati o flussi di acquisto AUD. La serie A3 AESAT giornaliera è un riferimento distinto, qui usiamo il bilancio RBA settimanale. Credito mensile e riserve settimanali non vanno sommati per creare un segnale: conta se cambiano costo del funding, attese sui tassi e prezzo Forex.</p>'+
   '<small>'+observation+' · rilevazione '+esc(x.source_period)+
   ' · ora esatta del rilascio non verificata · valore precedente implicito · nessuna modifica al ranking FX · '+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: bilancio settimanale RBA ↗</a></small></div>';
 }
 function audRBAAdjustedCredit(esc,fmt,now){
  const x=root.FXQuantAUDBusinessCreditGrowthResearch;
  if(!x||x.schema!=='GMFQ_NEXT_AUD_RBA_BUSINESS_CREDIT_GROWTH_V1'||
     x.status!=='VERIFIED_RBA_FIN_AGG_BUSINESS_GROWTH_RESEARCH_ONLY'||
     x.publisher!=='Reserve Bank of Australia'||
     x.category!=='business_credit_growth_adjusted'||
     x.breaks_adjusted!==true||x.seasonally_adjusted!==true||
     x.is_credit_stock!==false||x.first_release_pit_verified!==false||
     x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     x.unit!=='percent'||x.frequency!=='M')return '';
  const period=observationDate(x.observation_period),release=observationDate(x.release_date),today=observationDate(now);
  if(!period||!release||!today||dateMs(period)>dateMs(release)||dateMs(release)>dateMs(today)||
     !/^\d{4}-\d{2}$/.test(x.observation_period)||!/^\d{4}-\d{2}-\d{2}$/.test(x.release_date)||
     ![x.monthly_growth_pct,x.prior_month_growth_pct,x.annual_growth_pct,x.prior_year_growth_pct].every(v=>finite(v)&&v>-20&&v<30)||
     !/^https:\/\/www\.rba\.gov\.au\/statistics\/frequency\/fin-agg\/\d{4}\/fin-agg-\d{4}\.html$/.test(x.source_url))return '';
  const current=x.monthly_growth_pct,prior=x.prior_month_growth_pct,change=current-prior,
    age=Math.round((dateMs(today)-dateMs(release))/864e5);
  const diff=Math.abs(change)<0.05?'stabile rispetto al mese precedente':
    change>0?'in accelerazione rispetto al mese precedente':'in decelerazione rispetto al mese precedente';
  const move=v=>(v>0?'+':'')+fmt(v,1)+'%';
  const freshness=age>75?'COMUNICATO STORICO · NUOVO RILASCIO DA CONTROLLARE':'COMUNICATO UFFICIALE DATATO';
  return '<section class="drivers-cad-official drivers-aud-official" aria-label="RBA credito imprese crescita corretta">'+
   '<span class="mini-overline">RBA · CRESCITA UFFICIALE CORRETTA PER DISCONTINUITÀ</span>'+
   '<h3>Australia: il credito alle imprese '+esc(current>0?'cresce':current<0?'si riduce':'è invariato')+'; il ritmo mensile è '+esc(Math.abs(change)<0.05?'stabile':change>0?'in accelerazione':'in decelerazione')+'.</h3>'+
   '<p>Nel mese di '+esc(x.observation_period)+' il credito alle imprese cresce del <b>'+esc(move(current))+
   ' mensile</b>, contro '+esc(move(prior))+' nel mese precedente: andamento '+esc(diff)+
   '. Su dodici mesi è '+esc(move(x.annual_growth_pct))+
   ' (contro '+esc(move(x.prior_year_growth_pct))+' nello stesso mese dell’anno precedente).</p>'+
   '<p><b>Perché conta:</b> questa è la crescita RBA corretta per le rotture statistiche, <b>non</b> una percentuale ricavata dai livelli D2 e non un flusso di nuovi prestiti. Il credito resistente può aiutare l’attività, ma va confrontato con costi di finanziamento, domanda, occupazione e inflazione. Per AUD controlliamo il repricing RBA relativo a Fed/BoC, Cina e rischio globale: il credito da solo non identifica un trade.</p>'+
   audRBAESReading(esc,fmt,now)+
   '<div class="drivers-cad-source"><span>'+freshness+' · periodo '+esc(x.observation_period)+
   ' · pubblicato '+esc(x.release_date)+' · rettifiche storiche possibili · prima vintage non certificata · feed FX invariato</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: RBA · Financial Aggregates ↗</a></div></section>';
 }
 function eurECBLoanResearch(esc,fmt,now){
  const x=root.FXQuantEURNFCCreditResearch;
  if(!x||x.schema!=='GMFQ_NEXT_EUR_ECB_NFC_CREDIT_RESEARCH_V1'||
     x.status!=='VERIFIED_ECB_BSI_NFC_STOCK_RESEARCH_ONLY'||
     x.publisher!=='European Central Bank / ESCB'||
     x.series_id!=='BSI.M.U2.N.A.A20.A.1.U2.2240.Z01.E'||
     x.category!=='nfc_loans_stock'||x.frequency!=='M'||
     x.seasonally_adjusted!==false||x.eligible_for_fx_core!==false||
     x.eligible_for_backtest!==false||x.first_release_pit_verified!==false||
     !Array.isArray(x.dates)||!Array.isArray(x.values)||x.dates.length<3||
     x.dates.length!==x.values.length)return '';
  const lastDate=x.dates.at(-1),last=x.values.at(-1),prev=x.values.at(-2),before2=x.values.at(-3);
  const nowDate=observationDate(now),period=observationDate(lastDate);
  if(!nowDate||!period||dateMs(period)>dateMs(nowDate)||
     lastDate!==x.latest_observation||![last,prev,before2].every(v=>finite(v)&&v>0)||
     !x.dates.every((d,i)=>/^\d{4}-\d{2}$/.test(d)&&(!i||d>x.dates[i-1])))return '';
  const pct=100*(last/prev-1),twoMonths=100*(last/before2-1),
        age=Math.round((dateMs(nowDate)-dateMs(period))/864e5);
  if(!finite(pct)||!finite(twoMonths)||Math.abs(pct)>10||Math.abs(twoMonths)>20)return '';
  const state=pct>0?'in aumento':pct<0?'in diminuzione':'invariato';
  const sign=v=>v>0?'+':v<0?'−':'';
  const historical=age>75?'SERIE STORICA, RILASCIO DA RICONTROLLARE':'ULTIMA OSSERVAZIONE DATATA';
  const reading=pct>0&&twoMonths<0?
    'L’ultimo mese recupera, ma non compensa interamente il calo precedente: non è ancora una sequenza di accelerazione del credito.':
    pct>0&&twoMonths>0?
    'Due mesi cumulati in aumento sono un dato positivo, ma non provano che le banche stiano allentando gli standard o che la domanda sia forte.':
    'La dinamica recente non è sufficiente a certificare un impulso positivo al credito; servono domanda, tassi sui nuovi prestiti e condizioni BLS.';
  return '<section class="drivers-cad-official drivers-eur-official" aria-label="Fonte ufficiale BCE separata">'+
   '<span class="mini-overline">BCE / ESCB · SERIE UFFICIALE SEPARATA</span>'+
   '<h3>Prestiti alle imprese dell’Eurozona: conta la persistenza, non il solo ultimo mese.</h3>'+
   '<p>Lo stock dei prestiti alle società non finanziarie è '+esc(state)+' nel '+esc(lastDate)+
   ': '+esc(fmt(last,0))+' milioni EUR, '+sign(pct)+esc(fmt(Math.abs(pct),2))+
   '% sul mese precedente. Il cumulato di due mesi è '+sign(twoMonths)+esc(fmt(Math.abs(twoMonths),2))+'%.</p>'+
   '<p><b>Lettura economica:</b> '+esc(reading)+
   ' Per EUR va inoltre verificato se la BCE e il mercato dei tassi cambiano idea rispetto alla Fed, e se EUR/USD o EUR/GBP confermano il differenziale.</p>'+
   '<div class="drivers-cad-source"><span>'+historical+' · '+esc(lastDate)+
   ' · serie BSI NFC non destagionalizzata · revisioni possibili · vintage di prima pubblicazione non verificato · feed FX invariato</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: BCE · Data Portal ↗</a></div></section>';
 }
 function usFedCreditResearch(esc,fmt,now){
  const x=root.FXQuantUSBanksCreditResearch;
  if(!x||x.schema!=='GMFQ_NEXT_US_H8_CREDIT_RESEARCH_V1'||
     x.status!=='VERIFIED_FED_H8_FRED_MIRROR_RESEARCH_ONLY'||
     x.publisher!=='Board of Governors of the Federal Reserve System (US)'||
     x.series_id!=='TOTBKCR'||x.category!=='bank_credit_stock'||
     x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     x.first_release_pit_verified!==false||x.frequency!=='W'||
     !Array.isArray(x.dates)||!Array.isArray(x.values)||
     x.dates.length<2||x.dates.length!==x.values.length)return '';
  const lastDate=x.dates.at(-1),last=x.values.at(-1),prev=x.values.at(-2);
  const today=observationDate(now),observed=observationDate(lastDate);
  if(!today||!observed||dateMs(observed)>dateMs(today)||
     lastDate!==x.latest_observation||!finite(last)||!finite(prev)||
     last<=0||prev<=0||!x.dates.every((d,i)=>/^\d{4}-\d{2}-\d{2}$/.test(d)&&(!i||d>x.dates[i-1])))return '';
  const age=Math.round((dateMs(today)-dateMs(observed))/864e5);
  const move=(last/prev-1)*100,diff=last-prev;
  if(!finite(move)||Math.abs(move)>10)return '';
  const direction=diff>0?'cresce':diff<0?'si riduce':'rimane invariato';
  const stale=age>28?'PERIODO STORICO':'ULTIMA OSSERVAZIONE SETTIMANALE';
  return '<section class="drivers-cad-official drivers-us-official" aria-label="Ricerca Fed H.8 separata">'+
   '<span class="mini-overline">FONTE FED H.8 / FRED · SERIE SEPARATA</span>'+
   '<h3>Credito bancario USA: cosa cambia nello stock, non necessariamente nei nuovi prestiti.</h3>'+
   '<p>Nel dato del '+esc(lastDate)+' il credito bancario totale '+direction+': '+esc(fmt(last,2))+
   ' miliardi USD, '+(diff>0?'+':diff<0?'−':'')+esc(fmt(Math.abs(diff),2))+
   ' miliardi ('+(diff>0?'+':diff<0?'−':'')+esc(fmt(Math.abs(move),2))+'%) rispetto alla settimana precedente. '+
   'Questo aggregato Fed comprende anche titoli bancari e non misura direttamente la domanda di nuovi finanziamenti.</p>'+
   '<p><b>Lettura economica:</b> per giudicare la trasmissione serve capire se crescono i prestiti, se cambiano gli standard SLOOS (attualmente sospesi per discrepanza tra varianti) e se il pricing Fed relativo produce una reazione coerente di USD. Non deduciamo flussi valutari dal solo stock.</p>'+
   '<div class="drivers-cad-source"><span>'+stale+' · '+esc(lastDate)+' · H.8 TOTBKCR · fonte aggiornata via FRED, vintage iniziale non certificato</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: Federal Reserve / FRED ↗</a></div></section>';
 }
 function cadIssuerResearch(esc,fmt,now){
  const x=root.FXQuantCADCreditResearch;
  if(!x||x.schema!=='GMFQ_NEXT_CAD_BUSINESS_CREDIT_OFFICIAL_RESEARCH_V1'||
     x.publisher!=='Bank of Canada'||x.series_id!=='V122667770'||
     x.category!=='outstanding_business_loans'||x.eligible_for_fx_core!==false||
     x.eligible_for_backtest!==false||x.first_release_pit_verified!==false||
     !Array.isArray(x.dates)||!Array.isArray(x.values)||
     x.values.length!==x.dates.length||x.values.length<2)return '';
  const latest=x.dates.at(-1),last=x.values.at(-1),prev=x.values.at(-2);
  const period=observationDate(latest),today=observationDate(now);
  if(!period||!today||dateMs(period)>dateMs(today)||!finite(last)||!finite(prev)||
     last<=0||prev<=0||latest!==x.latest_observation||
     !x.dates.every((d,i)=>/^\d{4}-\d{2}$/.test(d)&&(!i||d>x.dates[i-1])))return '';
  const delta=(last/prev-1)*100,age=Math.round((dateMs(today)-dateMs(period))/864e5);
  if(!Number.isFinite(delta)||Math.abs(delta)>15)return '';
  const move=delta>0?'in aumento':delta<0?'in diminuzione':'invariati';
  const quality=age>75?'PERIODO STORICO':'ULTIMA OSSERVAZIONE DATATA';
  return '<section class="drivers-cad-official" aria-label="Fonte ufficiale canadese separata">'+
   '<span class="mini-overline">FONTI · APPROFONDIMENTO UFFICIALE SEPARATO</span>'+
   '<h3>Canada: il credito alle imprese è osservabile, ma non è ancora integrato nel feed G8.</h3>'+
   '<p>La Bank of Canada pubblica il totale dei <b>prestiti alle imprese in essere</b>: '+esc(fmt(last,0))+
   ' milioni CAD nel '+esc(latest)+', '+move+' ('+(delta>0?'+':delta<0?'−':'')+esc(fmt(Math.abs(delta),2))+
   '%) rispetto al mese precedente. È la variazione di uno stock bancario, non il flusso di nuovi prestiti.</p>'+
   '<p>Questa osservazione aiuta a verificare l’ipotesi sulla trasmissione del credito, ma <b>non certifica</b> il canale CAD.credit operativo: definizioni, revisioni e percorso di aggiornamento restano separati. Per CAD servono anche la risposta BoC, il differenziale con la Fed e USD/CAD.</p>'+
   '<div class="drivers-cad-source"><span>'+quality+' · '+esc(latest)+' · serie V122667770 · rilascio point-in-time non verificato</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: Bank of Canada ↗</a></div></section>';
 }
 const NZD_SOURCES={
  d10:'https://www.rbnz.govt.nz/statistics/series/reserve-bank/influences-on-settlement-cash',
  c50:'https://www.rbnz.govt.nz/statistics/series/lending-and-monetary/depository-corporations-money-and-credit-aggregates'
 };
 const NZD_RELEASE={
  period:'2026-09',released:'2026-10-30',next:'2026-11-30',
  history:{
   '2026-08':{liquidity:26460,money:454671,credit:624663},
   '2026-09':{liquidity:27036,money:459840,credit:630847}
  }
 };
 function nzdDossier(row,today){
  const release=root.FXQuantNZDRBNZLiquidity||NZD_RELEASE;
  const day=observationDate(today),roles=['liquidity','money','credit'];
  if(!row||!day||!release.released||day<release.released||!release.history)return null;
  const periods=Object.keys(release.history).sort();
  if(periods.at(-1)!==release.period||periods.length<2||
     !periods.every(p=>/^20\d{2}-(0[1-9]|1[0-2])$/.test(p)&&roles.every(key=>
      finite(release.history[p]?.[key])&&release.history[p][key]>0)))return null;
  if(!roles.every(key=>{
   const series=row[key];
   return Array.isArray(series?.dates)&&Array.isArray(series?.values)&&
    series.dates.length===series.values.length&&series.dates.at(-1)===series.last_date&&
    series.values.at(-1)===series.last_value&&series.unit==='NZD mln'&&
    series.last_date<release.period&&release.history[series.last_date]?.[key]===series.last_value;
  }))return null;
  const updated=Object.fromEntries(roles.map(key=>{
   const s=row[key];
   const pending=periods.filter(p=>p>s.last_date);
   const appended=pending.map(p=>release.history[p][key]);
   return [key,{...s,dates:[...s.dates,...pending],values:[...s.values,...appended],
    last_date:release.period,last_value:appended.at(-1)}];
  }));
  const direction=s=>s.last_value>s.values.at(-2)?'IN AUMENTO':
   s.last_value<s.values.at(-2)?'IN CALO':'STABILE';
  return {...row,...updated,liquidity_dir:direction(updated.liquidity),credit_dir:direction(updated.credit),
   as_of:release.period+' · pubblicato il '+release.released,current_note:null,rbnzRelease:release};
 }
 function nzdReleaseContext(row,today,esc,fmt){
  const release=row.rbnzRelease;
  const delta=(s,offset=1)=>(s.values.at(-offset)/s.values.at(-offset-1)-1)*100;
  const percent=n=>esc((n>0?'+':n<0?'−':'')+fmt(Math.abs(n),2))+'%';
  const cash=delta(row.liquidity),credit=delta(row.credit),priorCredit=delta(row.credit,2);
  const cashText=cash>0?'I saldi di regolamento salgono':cash<0?'I saldi di regolamento scendono':'I saldi di regolamento sono stabili';
  let creditText='il credito è stabile';
  if(credit<0)creditText='lo stock di credito cala';
  if(credit>0)creditText=credit>priorCredit?'il credito accelera':credit<priorCredit?
   'il credito cresce più lentamente':'il credito cresce allo stesso ritmo';
  return '<section class="drivers-cad-official" aria-label="Dati mensili ufficiali RBNZ">'+
   '<span class="mini-overline">RESERVE BANK OF NEW ZEALAND · D10 E C50</span>'+
   '<h3>'+cashText+' e '+creditText+'.</h3>'+
   '<p>Nel '+esc(release.period)+' i saldi medi di regolamento variano del '+percent(cash)+
   ' sul mese. La moneta ampia è a '+esc(fmt(row.money.last_value/1000,2))+' miliardi NZD ('+
   percent(delta(row.money))+'). Il credito al settore privato segna '+percent(credit)+
   ' dopo '+percent(priorCredit)+'. Lo stock comprende prestiti, titoli e altre componenti.</p>'+
   '<div class="drivers-cad-source"><span>Pubblicato il '+esc(release.released)+
   ' · '+(observationDate(today)<release.next?'prossimo rilascio previsto il '+esc(release.next):
    'nuovo rilascio da verificare')+'</span>'+
   '<a href="'+NZD_SOURCES.d10+'" target="_blank" rel="noopener noreferrer">RBNZ · D10 ↗</a>'+
   '<a href="'+NZD_SOURCES.c50+'" target="_blank" rel="noopener noreferrer">RBNZ · C50 ↗</a></div></section>';
 }
 function chfSNBResearch(feed,today,esc,fmt){
  const roles=[
   {key:'CHF.sight_deposits',id:'BSTA@SNB.MONA_U.BIL.AKT.FMI.GGU{U,T,T,A40}',
    label:'Depositi a vista presso la SNB · statistica bancaria mensile'},
   {key:'CHF.credit',id:'EPB@SNB.bakredinausbm{AV1,A,T1,B}',
    label:'Credito bancario utilizzato · selezione SNB'}
  ];
  const day=observationDate(today);
  const entries=roles.flatMap(({key,id,label})=>{
   const row=feed?.lanes?.[key];
   if(!day||row?.timeseries_key!==id||row.source_metadata?.frequency!=='P1M'||
      row.official_canonical_untouched!==true||!/^20\d{2}-(0[1-9]|1[0-2])$/.test(row.proxy_as_of)||
      observationDate(row.proxy_as_of)>day||!finite(row.proxy_value)||row.proxy_value<=0)return [];
   const pct=value=>finite(value)?esc((value>0?'+':'')+fmt(value,2))+'%':'dato assente';
   const age=(dateMs(day)-dateMs(observationDate(row.proxy_as_of)))/864e5;
   return [{key,row,html:'<p data-chf-snb-lane="'+esc(key)+'"><b>'+esc(label)+'</b> · '+esc(row.proxy_as_of)+
    ' · '+esc(fmt(row.proxy_value/1000,2))+' miliardi CHF. Sul mese '+pct(row.change_1m_pct)+
    ' · in tre mesi '+pct(row.change_3m_pct)+(age>70?' · dato storico.':'.')+'</p>'}];
  });
  if(!entries.length)return '<p class="drivers-lead">I dati mensili SNB sono temporaneamente indisponibili.</p>';
  const read=entries.map(entry=>entry.html).join('');
  const byKey=Object.fromEntries(entries.map(entry=>[entry.key,entry.row]));
  const deposits=byKey['CHF.sight_deposits'],credit=byKey['CHF.credit'];
  const sameMonth=deposits&&credit&&deposits.proxy_as_of===credit.proxy_as_of;
  const month=sameMonth?deposits.proxy_as_of:'';
  const monthLabel=month?new Intl.DateTimeFormat('it-IT',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(month+'-01T12:00:00Z')):'';
  const rateText=(value,label)=>!finite(value)?label+' senza confronto mensile':
   Math.abs(value)<0.1?label+' quasi ferm'+(label==='Depositi'?'i':'o'):
   label+(value>0?' in aumento':' in calo');
  const headline=sameMonth?rateText(deposits.change_1m_pct,'Depositi')+' e '+rateText(credit.change_1m_pct,'credito'):
   'Depositi e credito secondo le ultime osservazioni disponibili';
  const creditTrend=credit?.change_3m_pct;
  const reading=finite(creditTrend)?'Sui tre mesi il credito '+(creditTrend>0?'risulta ancora in crescita':creditTrend<0?'risulta in calo':'è stabile')+'. ':'';
  return '<section class="drivers-cad-official" aria-label="Serie mensili ufficiali SNB">'+
   '<span class="mini-overline">SWISS NATIONAL BANK · SERIE MENSILI</span>'+
   '<h3>'+esc((monthLabel?monthLabel.charAt(0).toUpperCase()+monthLabel.slice(1)+' · ':'')+headline)+'</h3>'+
   '<p>'+esc(reading)+'Per capire se le condizioni del credito stanno peggiorando, servono più mesi e informazioni sulla facilità di ottenere prestiti.</p>'+
   read+
   '<div class="drivers-cad-source"><a href="https://data.snb.ch/en/publishingSet/BSTA" target="_blank" rel="noopener noreferrer">Fonte: SNB · Statistiche bancarie mensili ↗</a></div></section>';
 }
 function render(api){
  const {get,FX,FLAGS,NAMES,state,plot,pageHero,esc,fmt,date,dayNow}=api;
  const all=get('liquidity')||{},today=dayNow();
  const nzd=nzdDossier(all.NZD,today);
  const selected=validCcy(state.liqCcy)?state.liqCcy:'USD';
  const row=selected==='NZD'&&nzd?nzd:all[selected],read=interpret(row);
  const chf=selected==='CHF'?chfSNBResearch(get('residualResearch'),today,esc,fmt):'';
  const provenance=root.FXQuantLiquiditySourcePolicy?.review(selected)||null;
  const policyGate=(role)=>root.FXQuantLiquiditySourcePolicy?.check(selected,role)||null;
  const roles=['liquidity','credit','conditions'];
  const audits=roles.map(role=>({role,...sourceEvidence(row?.[role],today)}));
  const covered=audits.filter(x=>x.coverage&&!policyGate(x.role)?.withheld).length;
  const snap=(s)=>s?.last_date||'data non disponibile';
  const cell=(label,s,d,role)=>{
   const gate=policyGate(role),blocked=gate?.withheld===true;
   const exists=Boolean(s?.label&&finite(s.last_value))&&!blocked,audit=sourceEvidence(s,today);
   const isYoY=/yoy|a\/a/i.test(s?.label||'');
   const info=blocked?'Dato sospeso · variante da armonizzare':
    exists?('Ultimo '+esc(snap(s))+' · '+esc(fmt(s.last_value,2))+(s.unit?' '+esc(s.unit):isYoY?'%':'') ):'Misura non verificabile';
   return '<div class="drivers-fact" data-liq-role="'+role+'" data-source-safety="'+(blocked?'withheld':gate?.ready?'mapped':'pending')+'"><span>'+esc(label)+'</span><strong>'+esc(s?.label||'Serie non disponibile')+'</strong>'+
    '<small>'+info+'</small>'+
    '<b class="drivers-tone" data-tone="'+(blocked?'unknown':audit.tone==='warn'?'unknown':esc(audit.tone))+'">'+esc(blocked?'IN VERIFICA':audit.state)+'</b>'+
    '<small class="drivers-observation">'+esc(blocked?gate.narrative:audit.message)+'</small>'+
    (gate?'<small class="drivers-source-provenance">'+esc(gate.label)+' · Registro '+esc(provenance?.as_of||'non verificato')+'</small>':'')+
    (!blocked&&d?'<b class="drivers-mini-state" data-tone="'+esc(d.tone)+'">Direzione del dataset: '+esc(d.label)+'</b>':'')+'</div>';
  };
    const chart=(s,label,color)=>{
   const pts=series(s);
   return '<article class="drivers-chart"><div class="drivers-chart-label"><strong>'+esc(label)+'</strong><small>'+esc(s?.label||'Serie assente')+' · '+esc(snap(s))+'</small></div>'+
    (pts.length>=2?plot({lines:[{name:s.label,color,values:pts}],label:label+' '+selected}):
     '<div class="drivers-empty">Storico numerico insufficiente: nessuna curva inventata.</div>')+'</article>';
  };
  const cards=FX.map(ccy=>{
    const item=ccy==='NZD'&&nzd?nzd:all[ccy],reading=interpret(item),active=ccy===selected;
    return '<button class="drivers-country" type="button" data-liq-country="'+ccy+'" aria-pressed="'+String(active)+'">'+
     '<span class="drivers-country-head"><b>'+esc(FLAGS[ccy]||'')+' '+ccy+'</b><small>'+esc(NAMES[ccy]||ccy)+'</small></span>'+
     (ccy==='CHF'?'<span class="drivers-mini-state" data-tone="neutral">Apri scheda CHF</span>':
      '<span class="drivers-mini-state" data-tone="'+reading.liquidity.tone+'">Liquidità · '+esc(reading.liquidity.label)+'</span>'+
      '<span class="drivers-mini-state" data-tone="'+reading.credit.tone+'">Credito · '+esc(reading.credit.label)+'</span>')+'</button>';
  }).join('');
  const facts='<div class="drivers-facts">'+cell('LIQUIDITÀ',row?.liquidity,read.liquidity,'liquidity')+
   cell('CREDITO',row?.credit,read.credit,'credit')+cell('STANDARD E CONDIZIONI',row?.conditions,null,'conditions')+'</div>';
  return pageHero('FINANCIAL CONDITIONS / G8','Liquidità & Credito. <em>Il denaro arriva all’economia?</em>',
   'Il denaro può aumentare senza generare nuovi prestiti. Osserviamo i due canali per capire se cambiano crescita, pricing e valute.')+
   '<section class="drivers-panel" id="liquidity-studio"><div class="drivers-head"><div><span class="mini-overline">01 / MAPPA G8</span><h2>Otto economie, due canali distinti</h2><p>Seleziona un paese. Le frecce sono classificazioni delle singole serie storiche, non un indice di liquidità globale né un ranking FX.</p></div><span class="drivers-source-mark">FONTI CON DATE INDIPENDENTI</span></div>'+
   '<div class="drivers-country-grid">'+cards+'</div></section>'+
   '<section class="drivers-panel drivers-selection" aria-label="Dossier liquidità e credito '+selected+'">'+
   '<div class="drivers-head"><div><span class="mini-overline">02 / LETTURA ECONOMICA · '+esc(FLAGS[selected]||'')+' '+selected+'</span>'+
   '<h2>'+esc(selected==='CHF'?'Liquidità e credito in Svizzera':read.headline)+'</h2></div>'+
   (selected==='CHF'?'':'<span class="drivers-status" data-tone="'+(covered===3?'neutral':'unknown')+'">COPERTURA '+covered+'/3 SERIE</span>')+'</div>'+
   (selected==='CHF'?chf:'<p class="drivers-lead">'+esc(read.meaning)+'</p>'+
   '<p class="drivers-source-brief">QUALITÀ TEMPORALE · '+esc(audits.filter(x=>x.state==='STORICO').length)+' serie storiche da ricontrollare · '+esc(3-covered)+' serie assenti o in verifica. Nessuna conclusione sulla liquidità di oggi dalle sole osservazioni pregresse.</p>'+
   facts)+
   (selected==='NZD'&&nzd?nzdReleaseContext(nzd,today,esc,fmt):'')+
   (selected==='JPY'?jpyBOJCreditResearch(esc,fmt,today):'')+
   (selected==='GBP'?gbpBoEReservesResearch(esc,fmt,today):'')+
   (selected==='AUD'?audRBAAdjustedCredit(esc,fmt,today):'')+
   (selected==='EUR'?eurECBLoanResearch(esc,fmt,today):'')+
   (selected==='USD'?usFedCreditResearch(esc,fmt,today):'')+
   (selected==='CAD'?cadIssuerResearch(esc,fmt,today):'')+
   '<div class="drivers-story"><div><span>IPOTESI DI TRASMISSIONE AL FOREX</span><p>'+esc(FX_LENSES[selected]?.fx||read.fx)+'</p></div><div><span>COSA MONITORARE</span><p>'+esc(FX_LENSES[selected]?.watch||read.watch)+'</p></div></div>'+
   (root.FXQuantDriverMarketAudit?.render?.({get,esc,dayNow},selected)||'')+
   '<div class="drivers-links"><a href="#macro">Scenario macro ↗</a><a href="#rates">Tassi & OIS ↗</a><a href="#risk">Rischio e credito IG/HY ↗</a><a href="#currencies">Valute G8 ↗</a></div>'+
   '<details class="drivers-source-provenance-fold"><summary>'+(selected==='CHF'?'Fonti e storico':'Provenienza e limiti dell’aggiornamento automatico')+'</summary>'+
   (selected==='CHF'?'<p>Le serie mensili SNB hanno un perimetro diverso dallo storico precedente, che resta in verifica.</p>'+facts:'')+
    '<p>Il registro delle fonti è una fotografia al '+esc(provenance?.as_of||'data non verificata')+', non la prova che la pipeline abbia aggiornato oggi tutte le serie. Contratti mappati: '+esc(provenance?.verifiedContracts??'n.d.')+'/3. Un contratto pronto non equivale a un dato recente.</p>'+
    '<ul>'+roles.map(role=>{const g=policyGate(role);return '<li><strong>'+esc(({liquidity:'Liquidità',credit:'Credito',conditions:'Standard e condizioni'})[role])+'</strong>: '+esc(g?.label||'provenienza non verificata')+'. '+esc(g?.narrative||'Verificare il registro fonti.')+'</li>'}).join('')+'</ul></details>'+
   (selected==='CHF'?'':'<div class="drivers-source-note">Ultimo riferimento della scheda: '+esc(row?.as_of||'non dichiarato')+
   '. Copertura storica non significa aggiornamento corrente. Le serie possono avere frequenze, definizioni, unità e date non omogenee.'+
   (row?.current_note?' Contesto della fonte: '+esc(row.current_note):'')+'</div>')+'</section>'+
   (selected==='CHF'?'':'<details class="drivers-panel drivers-fold"><summary>Apri grafici, osservazioni e limiti delle fonti</summary>'+
   '<div class="drivers-chart-grid">'+chart(row?.liquidity,'Liquidità','#69d5ad')+chart(row?.credit,'Credito','#95c6e9')+'</div>'+
   '<p class="drivers-source-note">I grafici conservano i livelli originali nelle rispettive unità; non confrontare direttamente scale tra paesi o fra aggregati monetari e credito. Se manca un dato, non sostituiamo una stima a un’osservazione.</p></details>');
 }
 const api={series,direction,interpret,observationDate,sourceEvidence,render};
 root.FXQuantLiquidityCredit=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
