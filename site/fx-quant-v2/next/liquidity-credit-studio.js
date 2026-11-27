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
   .filter(x=>x.label&&finite(x.value)&&(s.signedGrowth===true||x.value>0));
  return rows.slice(-80);
 }
 // Keep the approved research series distinct from the legacy native feed.
 // Only use complete, finite, ordered, non-future observations; never splice
 // two definitions or fabricate a continuous history.
 function researchCreditSeries(x,label,unit,now,signedGrowth=false){
  if(!Array.isArray(x?.dates)||!Array.isArray(x?.values)||
     x.dates.length<2||x.dates.length!==x.values.length)return null;
  const today=observationDate(now);
  if(!today||!x.dates.every((d,i)=>{
   const period=observationDate(d);
   return period&&period<=today&&(!i||d>x.dates[i-1])&&finite(x.values[i])&&(signedGrowth||x.values[i]>0);
  }))return null;
  return {label:label+' · '+unit,dates:x.dates.slice(),values:x.values.slice(),
   last_date:x.dates.at(-1),last_value:x.values.at(-1),researchOnly:true,signedGrowth};
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
   delta,observation};
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
  USD:{fx:'Per il dollaro conta se il credito sostiene la spesa abbastanza da cambiare le attese sulla Fed. Nelle fasi di stress può contare di più la domanda di dollari come rifugio.',
   watch:'Prestiti a imprese e famiglie, criteri con cui le banche li concedono e tassi USA rispetto a quelli europei.'},
  EUR:{fx:'Una ripresa dei finanziamenti può aiutare gli investimenti. Per l’euro conta se il recupero cambia le attese sui tassi della BCE rispetto a quelli della Fed.',
   watch:'Domanda di prestiti delle imprese, tassi sulle nuove erogazioni e risposta di EUR/USD.'},
  GBP:{fx:'I mutui incidono sulla spesa delle famiglie e sul mercato della casa. La sterlina può risentirne se quei cambiamenti spostano le attese sulla Bank of England.',
   watch:'Nuove richieste di mutuo, costo dei prestiti e attese sui tassi britannici rispetto a quelli dell’Eurozona.'},
  JPY:{fx:'Se il credito sostiene domanda e inflazione, le attese sui tassi giapponesi possono salire. Il cambio USD/JPY dipende anche da come si muovono i tassi USA.',
   watch:'Domanda interna, prestiti bancari e differenziale tra i rendimenti a breve di Giappone e Stati Uniti.'},
  CHF:{fx:'Per capire se il credito sostiene la crescita svizzera e può incidere sul franco, osserva i prestiti a famiglie e imprese in Svizzera. Su EUR/CHF contano anche i tassi relativi e la domanda di franco come rifugio.',
   watch:'Utilizzo delle linee verso l’estero, prestiti interni e differenziale atteso tra BCE e SNB.'},
  CAD:{fx:'Se i finanziamenti sostengono gli investimenti, può cambiare la traiettoria dei tassi canadesi. Su USD/CAD contano anche il confronto con la Fed e il petrolio.',
   watch:'Domanda delle imprese, criteri di concessione delle banche e tassi attesi in Canada e negli Stati Uniti.'},
  AUD:{fx:'Il credito alle imprese può sostenere gli investimenti. Per il dollaro australiano conta se questo cambia le attese sui tassi, insieme alla domanda cinese e alla propensione al rischio.',
   watch:'Investimenti delle imprese, costo dei finanziamenti e attese sui tassi australiani rispetto a quelli USA.'},
  NZD:{fx:'Se più credito sostiene la spesa interna, il mercato può rivedere le attese sui tassi neozelandesi. Per AUD/NZD conta come cambiano rispetto a quelli australiani.',
   watch:'Credito privato, spesa interna e differenziale atteso tra i tassi dei due paesi.'}
 };
 const monthFormat=new Intl.DateTimeFormat('it-IT',{month:'long',year:'numeric',timeZone:'UTC'});
 const dayFormat=new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'});
 const dated=period=>{
  const time=dateMs(observationDate(period));
  return finite(time)?(period.length===7?monthFormat:dayFormat).format(time):period;
 };
 const inMonth=period=>{const month=dated(period);return (/^[aeiou]/i.test(month)?'Ad ':'A ')+month;};
 const movement=(value,up,down,flat)=>value>0?up:value<0?down:flat;
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
     !/^https:\/\/www\.stat-search\.boj\.or\.jp\/ssi\/mtshtml\//.test(x.source_url))return null;
  const dates=x.dates,v=x.values;
  const continuous=dates.every((d,i)=>{
    if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(d)||!finite(v[i])||v[i]<=2000000||v[i]>=12000000)return false;
    if(i===0)return true;
    const year=Number(d.slice(0,4)),month=Number(d.slice(5));
    const py=Number(dates[i-1].slice(0,4)),pm=Number(dates[i-1].slice(5));
    return year*12+month-py*12-pm===1;
  });
  const period=observationDate(x.last_observation),today=observationDate(now);
  if(!continuous||!period||!today||dateMs(period)>dateMs(today))return null;
  const last=v.at(-1),prev=v.at(-2),two=v.at(-3);
  const move=(last/prev-1)*100,prior=(prev/two-1)*100;
  if(!finite(move)||!finite(prior)||Math.abs(move)>12||Math.abs(prior)>12)return null;
  const age=Math.round((dateMs(today)-dateMs(period))/864e5);
  const freshness=age>110?'STORICO · NUOVA PUBBLICAZIONE DA CONTROLLARE':'SERIE BOJ UFFICIALE DATATA';
  const pace=move>prior+0.025?'più alto':move<prior-0.025?'più basso':'simile';
  const creditHeading=move>0?'Lo stock dei prestiti cresce':move<0?'Lo stock dei prestiti scende':'Lo stock dei prestiti è stabile';
  const moveSigned=q=>(q>0?'+':q<0?'−':'')+fmt(Math.abs(q),2);
  const headline=movement(move,'I prestiti bancari sono aumentati','I prestiti bancari sono diminuiti','I prestiti bancari sono rimasti stabili');
  return {creditSeries:researchCreditSeries(x,'BoJ MD11 · Credito bancario','100 milioni JPY',now),headline,opening:inMonth(x.last_observation)+' il totale dei prestiti in essere è '+movement(move,'salito','sceso','rimasto stabile')+
   ' rispetto al mese precedente. La continuità del movimento e le nuove erogazioni aiutano a capire se cambia la domanda interna.',
   html:'<section class="drivers-cad-official drivers-jpy-official" aria-label="BoJ credito bancario mensile fonte ufficiale separata">'+
   '<span class="mini-overline">BANK OF JAPAN · CREDITO BANCARIO DI FINE MESE</span>'+
   '<h3>'+esc(creditHeading)+'</h3>'+
   '<p>A '+esc(x.last_observation)+' i prestiti in essere delle banche domestiche sono '+esc(fmt(last/10,2))+
   ' miliardi JPY, contro '+esc(fmt(prev/10,2))+' miliardi il mese precedente: variazione dello stock '+
   esc(moveSigned(move))+'%. Il ritmo mensile è '+esc(pace)+' rispetto a quello precedente ('+esc(moveSigned(prior))+'%).</p>'+
   '<p><b>Contesto:</b> questa serie include conti bancari, fiduciari e delle filiali estere delle banche autorizzate in Giappone; non sono nuovi prestiti e non è l’indice dei saldi presso la BoJ. Il movimento può riflettere anche composizione e fattori di bilancio: non basta per dire che la domanda interna accelera.</p>'+
   '<p><b>Per lo yen:</b> chiediamoci se crescita, inflazione e dati sul credito cambiano davvero le aspettative BoJ, il differenziale JGB/UST e il carry. Poi controlliamo USD/JPY e i cross yen. Un credito in aumento senza repricing né conferma del prezzo non è un segnale operativo.</p>'+
   '<div class="drivers-cad-source"><span>'+freshness+' · periodo '+esc(x.last_observation)+
   ' · MD11 DLCLAEDBLTTO · '+esc(x.matched_canonical_months)+
   ' mesi storici corrispondenti · livello stock, non nuove erogazioni · vintage del primo rilascio non certificata · ranking FX invariato</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: BoJ · Time-Series Data Search ↗</a></div></section>'};
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
     !/^https:\/\/www\.bankofengland\.co\.uk\/boeapps\/database\//.test(x.source_url))return null;
  const months=x.dates,values=x.values;
  const validSeries=months.every((month,i)=>
    /^\d{4}-\d{2}$/.test(month)&&
    (i===0||month>months[i-1])&&finite(values[i])&&values[i]>-15&&values[i]<25);
  const period=observationDate(months.at(-1)),today=observationDate(now);
  if(!validSeries||!period||!today||dateMs(period)>dateMs(today))return null;
  const jul=months.indexOf('2026-07'),sep=months.indexOf('2026-09');
  if(jul<0||sep<0||Math.abs(values[jul]-3.6)>.16||Math.abs(values[sep]-3.4)>.16)return null;
  const last=values.at(-1),prior=values.at(-2),delta=last-prior;
  if(!Number.isFinite(delta)||Math.abs(delta)>8)return null;
  const pace=delta<-.049?'in rallentamento':delta>.049?'in accelerazione':'sostanzialmente stabile';
  const yoyState=last>0?'continua a espandersi su base annua':last<0?'si contrae su base annua':'è invariato su base annua';
  const signed=v=>(v>0?'+':v<0?'−':'')+fmt(Math.abs(v),1);
  const age=Math.round((dateMs(today)-dateMs(period))/864e5);
  const state=age>75?'PERIODO STORICO · NON CORRENTE':'SERIE MENSILE UFFICIALE DATATA';
  const matchedRelease=x.last_observation==='2026-09'&&x.official_september_release_date==='2026-10-29';
  const opening=inMonth(x.last_observation)+' il credito legato ai mutui '+yoyState+', con un ritmo '+pace+' rispetto al mese precedente.';
  return {creditSeries:researchCreditSeries(x,'BoE LPMVTYI · Crescita annua mutui','% annua',now,true),opening,
   html:'<div class="drivers-gbp-credit-bridge" aria-label="Credito garantito BoE crescita annuale corretta per stagionalità">'+
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
    '</small></div>'};
 }
 function gbpCCSResearch(esc,fmt,now){
  const parent=root.FXQuantGBPBoESecuredCreditResearch,x=parent?.lending_conditions;
  if(parent?.schema!=='GMFQ_NEXT_GBP_BOE_SECURED_CREDIT_GROWTH_V1'||parent.publisher!=='Bank of England'||
     x?.series_id!=='BOE_CCS_CORPORATE_AVAILABILITY_ACTUAL'||x.frequency!=='Q'||x.unit!=='net_percentage_balance'||
     x.positive_means!=='increased_availability'||x.negative_means!=='decreased_availability'||
     x.first_release_pit_verified!==false||x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     !/^https:\/\/www\.bankofengland\.co\.uk\/credit-conditions-survey\/20[0-9]{2}\/20[0-9]{2}-q[1-4]$/.test(x.source_url)||
     !Array.isArray(x.dates)||x.dates.length<4||x.latest_observation!==x.dates.at(-1)||
     !x.dates.every(d=>/^20[0-9]{2}-Q[1-4]$/.test(d)))return null;
  const s=researchCreditSeries(x,'BoE CCS · Disponibilità credito imprese','saldo netto, punti',now,true);
  if(!s||!s.values.every(v=>Math.abs(v)<=100))return null;
  const serial=d=>Number(d.slice(0,4))*4+Number(d.at(-1));
  if(!s.dates.every((d,i)=>i===0||serial(d)-serial(s.dates[i-1])===1))return null;
  const latest=s.last_value,prior=s.values.at(-2),delta=latest-prior;
  const signed=v=>(v>0?'+':'')+fmt(v,1);
  const state=Math.abs(latest)<1?'sostanzialmente invariata':latest>0?'in miglioramento':'in peggioramento';
  const change=Math.abs(delta)<1?'Il saldo è pressoché stabile rispetto al trimestre precedente.':delta>0?'Il saldo è salito rispetto al trimestre precedente.':'Il saldo è sceso rispetto al trimestre precedente.';
  const opening='Nel '+s.last_date+' la disponibilità complessiva di credito alle imprese è '+state+'. '+change;
  const age=(dateMs(observationDate(now))-dateMs(observationDate(s.last_date)))/864e5;
  return {opening,conditionsSeries:s,html:'<section class="drivers-cad-official" aria-label="Indagine CCS Regno Unito"><span class="mini-overline">BANK OF ENGLAND · CREDIT CONDITIONS SURVEY</span><h3>'+esc(opening)+'</h3>'+
   '<p>Saldo netto '+esc(signed(latest))+' punti nel '+esc(s.last_date)+' contro '+esc(signed(prior))+' nel '+esc(s.dates.at(-2))+'. Variazione '+esc(signed(delta))+' punti. Positivo = maggiore disponibilità, negativo = minore disponibilità. Si tratta di risposte delle banche sui tre mesi trascorsi, non della crescita dei prestiti o delle aspettative future.</p>'+
   '<div class="drivers-cad-source"><span>'+esc(s.last_date)+' · '+(age>155?'periodo storico':'indagine trimestrale datata')+' · soglia descrittiva di stabilità: ±1 punto</span><a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">BoE · Credit Conditions Survey ↗</a></div></section>'};
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
     x.asof_canonical_overlap!=='2026-09-16'||x.value_canonical_overlap!==638012)return null;
  const period=observationDate(x.source_period),previous=observationDate(x.previous_period),
        published=observationDate(x.published_on),today=observationDate(now);
  const [latest,earlier,delta]=[x.latest_balance_million_gbp,x.previous_balance_million_gbp,x.weekly_change_million_gbp];
  if(!period||!previous||!published||!today||
     dateMs(period)>dateMs(published)||dateMs(published)>dateMs(today)||
     dateMs(period)-dateMs(previous)!==7*864e5||
     ![latest,earlier,delta].every(finite)||latest<300000||earlier<300000||
     latest-earlier!==delta||Math.abs(delta)>150000||
     !/^https:\/\/www\.bankofengland\.co\.uk\/weekly-report\/\d{4}\/\d{1,2}-[a-z]+-\d{4}$/.test(x.source_url))return null;
  const age=Math.round((dateMs(today)-dateMs(period))/864e5);
  const sign=delta>0?'+':delta<0?'−':'';
  const groupedMove=String(Math.abs(delta)).replace(/\B(?=(\d{3})+(?!\d))/g,'.');
  const direction=delta>0?'sono aumentate':delta<0?'sono diminuite':'sono rimaste invariate';
  const quality=age>25?'STORICO · NUOVO RAPPORTO DA CONTROLLARE':'RAPPORTO SETTIMANALE UFFICIALE';
  const credit=gbpBoESecuredCreditReading(esc,fmt,now);
  const headline=credit?'Riserve bancarie e mutui, due letture per la sterlina':'Le riserve bancarie '+direction;
  const opening='Al '+dated(x.source_period)+' le riserve delle banche '+direction+' rispetto alla settimana prima.';
  return {liquidityRecent:{label:'BoE RPWB56A · milioni GBP',dates:[x.previous_period,x.source_period],values:[earlier,latest],last_date:x.source_period,last_value:latest},
   creditSeries:credit?.creditSeries||null,headline,opening:opening+(credit?' '+credit.opening:''),
   html:'<section class="drivers-cad-official drivers-gbp-official" aria-label="BoE riserve bancarie fonte ufficiale separata">'+
   '<span class="mini-overline">BANK OF ENGLAND · RISERVE BANCARIE UFFICIALI</span>'+
   '<h3>Riserve bancarie '+(delta>0?'in aumento':delta<0?'in calo':'stabili')+' nella settimana</h3>'+
   '<p>Al '+esc(x.source_period)+' le riserve delle banche presso la BoE '+esc(direction)+
   ' di <b>'+sign+esc(groupedMove)+' milioni GBP</b> in una settimana: saldo '+esc(fmt(latest,0))+
   ' milioni, contro '+esc(fmt(earlier,0))+' milioni al '+esc(x.previous_period)+'.</p>'+
   '<p><b>Cosa sto osservando:</b> uno stock di passività della banca centrale, non un flusso di nuovi prestiti. Anche con riserve in aumento, non possiamo dedurre un allentamento della BoE, nuovi acquisti di asset o domanda di GBP. I prestiti garantiti sono una seconda misura economica con frequenza e periodo propri: non vanno sommati ai saldi di riserva.</p>'+
   (credit?.html||'')+
   '<p><b>Quale verifica Forex manca?</b> Il mercato deve mostrare se cambia il percorso SONIA relativo a €STR e Fed; poi cerchiamo la risposta di EUR/GBP e GBP/USD, distinguendo fattori GBP da debolezza dell’altra valuta. Senza questo collegamento non emerge un trade dalle sole riserve.</p>'+
   '<div class="drivers-cad-source"><span>'+quality+' · osservazione '+esc(x.source_period)+
   ' · pubblicazione '+esc(x.published_on)+' · RPWB56A · dati settimanali, revisioni possibili · fonte separata dal feed FX</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: BoE · Weekly Report ↗</a></div></section>'};
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
     x.value_canonical_overlap!==173965||x.asof_canonical_overlap!=='2026-09-16')return null;
  const period=observationDate(x.source_period),today=observationDate(now);
  if(!period||!today||dateMs(period)>dateMs(today)||
     !/^\d{4}-\d{2}-\d{2}$/.test(x.source_period)||
     ![x.latest_balance_million_aud,x.weekly_movement_million_aud,x.previous_implied_million_aud].every(finite)||
     x.latest_balance_million_aud<10000||x.latest_balance_million_aud>900000||
     x.previous_implied_million_aud<=0||
     x.latest_balance_million_aud-x.previous_implied_million_aud!==x.weekly_movement_million_aud||
     !/^https:\/\/www\.rba\.gov\.au\/statistics\/balance-sheet\/$/.test(x.source_url))return null;
  const age=Math.round((dateMs(today)-dateMs(period))/864e5);
  const movementValue=x.weekly_movement_million_aud;
  const signed=(movementValue>0?'+':movementValue<0?'−':'')+String(Math.abs(movementValue)).replace(/\B(?=(\d{3})+(?!\d))/g,'.');
  const observation=age>25?'STORICO · DA AGGIORNARE':'SETTIMANALE UFFICIALE';
  const opening='Nella settimana al '+dated(x.source_period)+' le riserve usate dalle banche per regolare i pagamenti '+movement(movementValue,'sono salite','sono scese','sono rimaste stabili')+'.';
  const previous=new Date(dateMs(period)-7*864e5).toISOString().slice(0,10);
  return {liquidityRecent:{label:'RBA ES · milioni AUD (precedente implicito)',dates:[previous,x.source_period],values:[x.previous_implied_million_aud,x.latest_balance_million_aud],last_date:x.source_period,last_value:x.latest_balance_million_aud},opening,
   html:'<div class="drivers-aud-es-bridge" aria-label="Riserve RBA settimanali fonte indipendente">'+
   '<b>SECONDO CANALE, NON SECONDA CONFERMA: LE RISERVE</b>'+
   '<p>Al '+esc(x.source_period)+' i saldi <em>Exchange Settlement</em> delle banche presso RBA sono '+esc(fmt(x.latest_balance_million_aud,0))+
   ' milioni AUD, '+esc(signed)+' milioni sulla settimana. Il saldo precedente di '+esc(fmt(x.previous_implied_million_aud,0))+
   ' milioni è <b>ricavato dal movimento pubblicato</b>, non una nuova osservazione indipendente.</p>'+
   '<p>Queste sono riserve di regolamento tra banche, <b>non</b> nuovi prestiti, liquidità netta trasferita ai mercati o flussi di acquisto AUD. La serie A3 AESAT giornaliera è un riferimento distinto, qui usiamo il bilancio RBA settimanale. Credito mensile e riserve settimanali non vanno sommati per creare un segnale: conta se cambiano costo del funding, attese sui tassi e prezzo Forex.</p>'+
   '<small>'+observation+' · rilevazione '+esc(x.source_period)+
   ' · ora esatta del rilascio non verificata · valore precedente implicito · nessuna modifica al ranking FX · '+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: bilancio settimanale RBA ↗</a></small></div>'};
 }
 function audF7Research(esc,fmt,now){
  const parent=root.FXQuantAUDBusinessCreditGrowthResearch,x=parent?.lending_rate_proxy;
  if(parent?.schema!=='GMFQ_NEXT_AUD_RBA_BUSINESS_CREDIT_GROWTH_V1'||parent.publisher!=='Reserve Bank of Australia'||
     x?.series_id!=='RBA_F7_BUSINESS_LENDING_RATES_SUMMARY'||x.source_url!=='https://www.rba.gov.au/statistics/interest-rates/'||
     x.frequency!=='M'||x.unit!=='percent_per_annum'||x.proxy_kind!=='loan_price_not_lending_standards'||
     x.first_release_pit_verified!==false||x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     !x.history||typeof x.history!=='object')return null;
  const dates=Object.keys(x.history).sort(),keys=['small','medium','large'];
  if(!dates.length||dates.at(-1)!==x.latest_observation||!dates.every(d=>/^20[0-9]{2}-(0[1-9]|1[0-2])$/.test(d)&&observationDate(d)<=observationDate(now)&&keys.every(k=>['new','outstanding'].every(t=>finite(x.history[d]?.[k]?.[t])&&x.history[d][k][t]>=0&&x.history[d][k][t]<=30))))return null;
  const latest=x.history[x.latest_observation],prior=dates.length>1?x.history[dates.at(-2)]:null;
  const rate=v=>fmt(v,2)+'%';
  const opening=inMonth(x.latest_observation)+' i nuovi prestiti alle piccole imprese costano il '+rate(latest.small.new)+', contro il '+rate(latest.large.new)+' per le grandi imprese.'+(prior?' Rispetto a '+dates.at(-2)+' il costo per le piccole imprese '+movement(latest.small.new-prior.small.new,'è salito','è sceso','è rimasto stabile')+'.':'');
  const s=dates.length>=2?researchCreditSeries({dates,values:dates.map(d=>x.history[d].small.new)},'RBA F7 · Nuovi prestiti piccole imprese','% annua',now,true):null;
  return {opening,conditionsSeries:s,conditionsChartLabel:'Costo del credito · proxy ufficiale',html:'<section class="drivers-cad-official" aria-label="Costo credito imprese Australia F7"><span class="mini-overline">RBA / APRA · COSTO DEL CREDITO F7</span><h3>'+esc(opening)+'</h3>'+
   '<p>Nuovi prestiti: piccole '+esc(rate(latest.small.new))+', medie '+esc(rate(latest.medium.new))+', grandi '+esc(rate(latest.large.new))+'. Prestiti in essere: piccole '+esc(rate(latest.small.outstanding))+', medie '+esc(rate(latest.medium.outstanding))+', grandi '+esc(rate(latest.large.outstanding))+'.</p>'+
   '<p>Proxy del costo dei finanziamenti, non degli standard di concessione. '+(dates.length<2?'Una sola osservazione mensile acquisita: nessuna curva storica inventata.':'')+'</p><div class="drivers-cad-source"><span>'+esc(x.latest_observation)+' · tassi annui osservati</span><a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">RBA · F7 ↗</a></div></section>'};
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
     x.unit!=='percent'||x.frequency!=='M')return null;
  const period=observationDate(x.observation_period),release=observationDate(x.release_date),today=observationDate(now);
  if(!period||!release||!today||dateMs(period)>dateMs(release)||dateMs(release)>dateMs(today)||
     !/^\d{4}-\d{2}$/.test(x.observation_period)||!/^\d{4}-\d{2}-\d{2}$/.test(x.release_date)||
     ![x.monthly_growth_pct,x.prior_month_growth_pct,x.annual_growth_pct,x.prior_year_growth_pct].every(v=>finite(v)&&v>-20&&v<30)||
     !/^https:\/\/www\.rba\.gov\.au\/statistics\/frequency\/fin-agg\/\d{4}\/fin-agg-\d{4}\.html$/.test(x.source_url))return null;
  const current=x.monthly_growth_pct,prior=x.prior_month_growth_pct,change=current-prior,
    age=Math.round((dateMs(today)-dateMs(release))/864e5);
  const diff=Math.abs(change)<0.05?'stabile rispetto al mese precedente':
    change>0?'in accelerazione rispetto al mese precedente':'in decelerazione rispetto al mese precedente';
  const move=v=>(v>0?'+':'')+fmt(v,1)+'%';
  const freshness=age>75?'COMUNICATO STORICO · NUOVO RILASCIO DA CONTROLLARE':'COMUNICATO UFFICIALE DATATO';
  const reserves=audRBAESReading(esc,fmt,now);
  const headline=movement(current,'Il credito alle imprese è cresciuto','Il credito alle imprese è diminuito','Il credito alle imprese è rimasto stabile');
  const opening=inMonth(x.observation_period)+' il credito alle imprese è '+movement(current,'cresciuto','diminuito','rimasto stabile')+
   '. La variazione mensile è '+diff+'.';
  const [year,month]=x.observation_period.split('-').map(Number);
  const priorMonth=new Date(Date.UTC(year,month-2,1)).toISOString().slice(0,7);
  const creditSeries=researchCreditSeries({dates:[priorMonth,x.observation_period],values:[prior,current]},'RBA · Crescita credito imprese (ultimi due mesi)','% mensile',now,true);
  return {liquidityRecent:reserves?.liquidityRecent||null,creditSeries,headline,opening:opening+(reserves?' '+reserves.opening:''),
   html:'<section class="drivers-cad-official drivers-aud-official" aria-label="RBA credito imprese crescita corretta">'+
   '<span class="mini-overline">RBA · CRESCITA UFFICIALE CORRETTA PER DISCONTINUITÀ</span>'+
   '<h3>Australia: il credito alle imprese '+esc(current>0?'cresce':current<0?'si riduce':'è invariato')+'; il ritmo mensile è '+esc(Math.abs(change)<0.05?'stabile':change>0?'in accelerazione':'in decelerazione')+'.</h3>'+
   '<p>Nel mese di '+esc(x.observation_period)+' il credito alle imprese cresce del <b>'+esc(move(current))+
   ' mensile</b>, contro '+esc(move(prior))+' nel mese precedente: andamento '+esc(diff)+
   '. Su dodici mesi è '+esc(move(x.annual_growth_pct))+
   ' (contro '+esc(move(x.prior_year_growth_pct))+' nello stesso mese dell’anno precedente).</p>'+
   '<p><b>Perché conta:</b> questa è la crescita RBA corretta per le rotture statistiche, <b>non</b> una percentuale ricavata dai livelli D2 e non un flusso di nuovi prestiti. Il credito resistente può aiutare l’attività, ma va confrontato con costi di finanziamento, domanda, occupazione e inflazione. Per AUD controlliamo il repricing RBA relativo a Fed/BoC, Cina e rischio globale: il credito da solo non identifica un trade.</p>'+
   (reserves?.html||'')+
   '<div class="drivers-cad-source"><span>'+freshness+' · periodo '+esc(x.observation_period)+
   ' · pubblicato '+esc(x.release_date)+' · rettifiche storiche possibili · prima vintage non certificata · feed FX invariato</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: RBA · Financial Aggregates ↗</a></div></section>'};
 }
 function eurExcessLiquidityResearch(esc,fmt,now){
  const parent=root.FXQuantEURNFCCreditResearch,x=parent?.excess_liquidity;
  if(parent?.schema!=='GMFQ_NEXT_EUR_ECB_NFC_CREDIT_RESEARCH_V1'||
     parent.publisher!=='European Central Bank / ESCB'||
     x?.series_id!=='ILM.D.U2.C.EXLIQ.U2.EUR'||
     x.source_url!=='https://data.ecb.europa.eu/data/datasets/ILM/ILM.D.U2.C.EXLIQ.U2.EUR'||
     x.frequency!=='D'||x.unit!=='milioni EUR'||x.first_release_pit_verified!==false||
     x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     !Array.isArray(x.dates)||x.latest_observation!==x.dates.at(-1)||
     !x.dates.every(d=>/^20[0-9]{2}-[0-9]{2}-[0-9]{2}$/.test(d)))return null;
  const s=researchCreditSeries(x,'BCE ILM · Liquidità in eccesso','milioni EUR',now);
  if(!s||s.dates.length<15||!s.values.every(v=>v<10000000))return null;
  const age=(dateMs(observationDate(now))-dateMs(s.last_date))/864e5;
  const delta=s.last_value-s.values.at(-2),previousDate=s.dates.at(-2);
  const weekTarget=dateMs(s.last_date)-7*864e5;
  const weekIndex=s.dates.findLastIndex(d=>dateMs(d)<=weekTarget);
  const week=weekIndex>=0&&weekTarget-dateMs(s.dates[weekIndex])<=3*864e5?s.last_value-s.values[weekIndex]:null;
  const signed=v=>(v>0?'+':'')+fmt(v/1000,2)+' mld EUR';
  const opening='Al '+dated(s.last_date)+' la liquidità in eccesso nell’Eurosistema '+movement(delta,'è aumentata','è diminuita','è rimasta stabile')+' rispetto alla rilevazione precedente'+(age>10?' (periodo storico)':'')+'.';
  return {headline:'Liquidità in eccesso BCE',opening,liquiditySeries:s,
   html:'<section class="drivers-cad-official" aria-label="Liquidità in eccesso BCE"><span class="mini-overline">BCE / EUROSISTEMA · LIQUIDITÀ IN ECCESSO</span><h3>'+esc(opening)+'</h3>'+
   '<p>Saldo '+esc(fmt(s.last_value/1000,2))+' miliardi EUR · rispetto al '+esc(previousDate)+' '+esc(signed(delta))+(week!==null?' · rispetto al '+esc(s.dates[weekIndex])+' '+esc(signed(week)):'')+'. Misura le riserve in eccesso nel sistema bancario, non i nuovi prestiti o i flussi verso EUR.</p>'+
   '<div class="drivers-cad-source"><span>'+esc(s.last_date)+' · '+(age>10?'periodo storico':'osservazione datata')+' · fonte ufficiale ILM · vintage iniziale non certificata</span><a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">BCE · Data Portal ↗</a></div></section>'};
 }
 function eurBLSResearch(esc,fmt,now){
  const parent=root.FXQuantEURNFCCreditResearch,x=parent?.lending_conditions;
  if(parent?.schema!=='GMFQ_NEXT_EUR_ECB_NFC_CREDIT_RESEARCH_V1'||parent.publisher!=='European Central Bank / ESCB'||
     x?.series_id!=='BLS.Q.U2.ALL.O.E.Z.B3.ST.S.WFNET'||x.frequency!=='Q'||x.unit!=='net_percentage_balance'||
     x.positive_means!=='tightening'||x.reference_period_is_previous_quarter!==true||
     x.first_release_pit_verified!==false||x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     x.source_url!=='https://data.ecb.europa.eu/data/datasets/BLS/BLS.Q.U2.ALL.O.E.Z.B3.ST.S.WFNET'||
     !Array.isArray(x.dates)||x.dates.length<4||x.latest_observation!==x.dates.at(-1)||
     !Array.isArray(x.publication_quarters)||x.publication_quarters.length!==x.dates.length)return null;
  const serial=d=>/^20[0-9]{2}-Q[1-4]$/.test(d)?Number(d.slice(0,4))*4+Number(d.at(-1)):NaN;
  const current=serial(now.slice(0,4)+'-Q'+Math.ceil(Number(now.slice(5,7))/3));
  if(!x.dates.every((d,i)=>serial(x.publication_quarters[i])===serial(d)+1&&
     serial(x.publication_quarters[i])<=current&&(!i||serial(d)-serial(x.dates[i-1])===1)))return null;
  const s=researchCreditSeries(x,'BCE BLS · Standard credito imprese','saldo netto, punti',now,true);
  if(!s||!s.values.every(v=>Math.abs(v)<=100))return null;
  const latest=s.last_value,prior=s.values.at(-2),delta=latest-prior;
  const signed=v=>(v>0?'+':'')+fmt(v,1);
  const state=latest>0?'più restrittivi':latest<0?'meno restrittivi':'invariati';
  const pace=Math.abs(delta)<1?'La variazione del saldo è contenuta.':delta>0?'Il saldo si è spostato verso una maggiore restrizione.':'Il saldo si è spostato verso un minore irrigidimento.';
  const opening='Nel '+s.last_date+' gli standard bancari per le imprese sono diventati '+state+'. '+pace;
  return {opening,conditionsSeries:s,html:'<section class="drivers-cad-official" aria-label="Bank Lending Survey BCE"><span class="mini-overline">BCE · BANK LENDING SURVEY</span><h3>'+esc(opening)+'</h3>'+
   '<p>Saldo netto '+esc(signed(latest))+' punti, precedente '+esc(signed(prior))+'; variazione '+esc(signed(delta))+' punti. Positivo = prevalgono le banche che irrigidiscono gli standard; negativo = prevale l’allentamento. Non misura volume o domanda dei prestiti.</p>'+
   '<div class="drivers-cad-source"><span>Periodo osservato '+esc(s.last_date)+' · trimestre di pubblicazione '+esc(x.publication_quarters.at(-1))+'</span><a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">BCE · BLS ↗</a></div></section>'};
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
     x.dates.length!==x.values.length)return null;
  const lastDate=x.dates.at(-1),last=x.values.at(-1),prev=x.values.at(-2),before2=x.values.at(-3);
  const nowDate=observationDate(now),period=observationDate(lastDate);
  if(!nowDate||!period||dateMs(period)>dateMs(nowDate)||
     lastDate!==x.latest_observation||![last,prev,before2].every(v=>finite(v)&&v>0)||
     !x.dates.every((d,i)=>/^\d{4}-\d{2}$/.test(d)&&(!i||d>x.dates[i-1])))return null;
  const pct=100*(last/prev-1),twoMonths=100*(last/before2-1),
        age=Math.round((dateMs(nowDate)-dateMs(period))/864e5);
  if(!finite(pct)||!finite(twoMonths)||Math.abs(pct)>10||Math.abs(twoMonths)>20)return null;
  const state=pct>0?'in aumento':pct<0?'in diminuzione':'invariato';
  const sign=v=>v>0?'+':v<0?'−':'';
  const historical=age>75?'SERIE STORICA, RILASCIO DA RICONTROLLARE':'ULTIMA OSSERVAZIONE DATATA';
  const reading=pct>0&&twoMonths<0?
    'L’ultimo mese recupera, ma non compensa interamente il calo precedente: non è ancora una sequenza di accelerazione del credito.':
    pct>0&&twoMonths>0?
    'Due mesi cumulati in aumento sono un dato positivo, ma non provano che le banche stiano allentando gli standard o che la domanda sia forte.':
    'La dinamica recente non è sufficiente a certificare un impulso positivo al credito; servono domanda, tassi sui nuovi prestiti e condizioni BLS.';
  const recent=x.dates.slice(-3).map(d=>dateMs(observationDate(d)));
  const partialRecovery=pct>0&&twoMonths<0&&recent[1]-recent[0]<=31*864e5&&recent[2]-recent[1]<=31*864e5;
  const headline=partialRecovery?'I prestiti alle imprese hanno recuperato parte del calo':
   movement(pct,'I prestiti alle imprese sono aumentati','I prestiti alle imprese sono diminuiti','I prestiti alle imprese sono rimasti stabili');
  const opening=inMonth(lastDate)+' i prestiti in essere sono '+movement(pct,'saliti','scesi','rimasti stabili')+
   ' rispetto alla rilevazione precedente.'+(partialRecovery?
    ' Nel complesso dei due mesi il saldo resta in calo.':' La domanda di finanziamenti aiuta a capire se il movimento può durare.');
  return {creditSeries:researchCreditSeries(x,'BCE BSI · Prestiti imprese','milioni EUR',now),headline,opening,
   html:'<section class="drivers-cad-official drivers-eur-official" aria-label="Fonte ufficiale BCE separata">'+
   '<span class="mini-overline">BCE / ESCB · SERIE UFFICIALE SEPARATA</span>'+
   '<h3>Prestiti alle imprese dell’Eurozona '+(pct===0?'invariati':state)+'</h3>'+
   '<p>Lo stock dei prestiti alle società non finanziarie è '+esc(state)+' nel '+esc(lastDate)+
   ': '+esc(fmt(last,0))+' milioni EUR, '+sign(pct)+esc(fmt(Math.abs(pct),2))+
   '% sul mese precedente. Il cumulato di due mesi è '+sign(twoMonths)+esc(fmt(Math.abs(twoMonths),2))+'%.</p>'+
   '<p><b>Lettura economica:</b> '+esc(reading)+
   ' Per EUR va inoltre verificato se la BCE e il mercato dei tassi cambiano idea rispetto alla Fed, e se EUR/USD o EUR/GBP confermano il differenziale.</p>'+
   '<div class="drivers-cad-source"><span>'+historical+' · '+esc(lastDate)+
   ' · serie BSI NFC non destagionalizzata · revisioni possibili · vintage di prima pubblicazione non verificato · feed FX invariato</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: BCE · Data Portal ↗</a></div></section>'};
 }
 function usM2Research(esc,fmt,now){
  const parent=root.FXQuantUSBanksCreditResearch,x=parent?.money_stock;
  if(parent?.schema!=='GMFQ_NEXT_US_H8_CREDIT_RESEARCH_V1'||
     parent.publisher!=='Board of Governors of the Federal Reserve System (US)'||
     x?.series_id!=='M2SL'||x.source_url!=='https://fred.stlouisfed.org/series/M2SL'||
     x.frequency!=='M'||x.unit!=='miliardi USD'||x.seasonally_adjusted!==true||
     x.first_release_pit_verified!==false||x.eligible_for_fx_core!==false||
     !Array.isArray(x.dates)||x.latest_observation!==x.dates.at(-1)||
     !x.dates.every(d=>/^20[0-9]{2}-(0[1-9]|1[0-2])$/.test(d)))return null;
  const s=researchCreditSeries(x,'Fed M2SL · Moneta ampia','miliardi USD',now);
  if(!s||s.dates.length<12||!s.values.every(v=>v>15000&&v<40000))return null;
  const age=(dateMs(observationDate(now))-dateMs(observationDate(s.last_date)))/864e5;
  const m=(s.last_value/s.values.at(-2)-1)*100;
  const y=s.values.length>=13?(s.last_value/s.values.at(-13)-1)*100:null;
  const signed=v=>(v>0?'+':'')+fmt(v,2)+'%';
  const opening=inMonth(s.last_date)+' la moneta ampia M2 '+movement(m,'è aumentata','è diminuita','è rimasta stabile')+' rispetto al mese precedente'+(age>75?' (periodo storico)':'')+'.';
  return {headline:'Moneta ampia M2',opening,liquiditySeries:s,
   html:'<section class="drivers-cad-official" aria-label="Moneta ampia M2 Fed"><span class="mini-overline">FED / FRED · M2 DESTAGIONALIZZATA</span><h3>'+esc(opening)+'</h3>'+
   '<p>'+esc(fmt(s.last_value,1))+' miliardi USD · mese '+esc(signed(m))+(y!==null?' · anno '+esc(signed(y)):'')+'. M2 misura la moneta ampia, non i saldi di riserva presso la Fed né gli acquisti di attività finanziarie.</p>'+
   '<div class="drivers-cad-source"><span>'+esc(s.last_date)+' · '+(age>75?'periodo storico':'osservazione datata')+' · M2SL · serie rivista, vintage iniziale non certificata</span><a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fed / FRED ↗</a></div></section>'};
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
     x.dates.length<2||x.dates.length!==x.values.length)return null;
  const lastDate=x.dates.at(-1),last=x.values.at(-1),prev=x.values.at(-2);
  const today=observationDate(now),observed=observationDate(lastDate);
  if(!today||!observed||dateMs(observed)>dateMs(today)||
     lastDate!==x.latest_observation||!finite(last)||!finite(prev)||
     last<=0||prev<=0||!x.dates.every((d,i)=>/^\d{4}-\d{2}-\d{2}$/.test(d)&&(!i||d>x.dates[i-1])))return null;
  const age=Math.round((dateMs(today)-dateMs(observed))/864e5);
  const move=(last/prev-1)*100,diff=last-prev;
  if(!finite(move)||Math.abs(move)>10)return null;
  const direction=diff>0?'cresce':diff<0?'si riduce':'rimane invariato';
  const stale=age>28?'PERIODO STORICO':'ULTIMA OSSERVAZIONE SETTIMANALE';
  const headline=movement(diff,'Il credito bancario è aumentato','Il credito bancario è diminuito','Il credito bancario è rimasto stabile');
  const opening='Al '+dated(lastDate)+' il totale era '+movement(diff,'in aumento','in calo','stabile')+
   ' rispetto alla rilevazione precedente. Il totale comprende prestiti e titoli detenuti dalle banche. Per capire se cambia la spesa, contano soprattutto i finanziamenti a famiglie e imprese.';
  return {creditSeries:researchCreditSeries(x,'Fed H.8 · Credito bancario totale','miliardi USD',now),headline,opening,
   html:'<section class="drivers-cad-official drivers-us-official" aria-label="Ricerca Fed H.8 separata">'+
   '<span class="mini-overline">FONTE FED H.8 / FRED · SERIE SEPARATA</span>'+
   '<h3>Lo stock del credito bancario '+direction+'</h3>'+
   '<p>Nel dato del '+esc(lastDate)+' il credito bancario totale '+direction+': '+esc(fmt(last,2))+
   ' miliardi USD, '+(diff>0?'+':diff<0?'−':'')+esc(fmt(Math.abs(diff),2))+
   ' miliardi ('+(diff>0?'+':diff<0?'−':'')+esc(fmt(Math.abs(move),2))+'%) rispetto alla settimana precedente. '+
   'Questo aggregato Fed comprende anche titoli bancari e non misura direttamente la domanda di nuovi finanziamenti.</p>'+
   '<p><b>Lettura economica:</b> per giudicare la trasmissione serve capire se crescono i prestiti, se cambiano gli standard SLOOS e se il pricing Fed relativo produce una reazione coerente di USD. Non deduciamo flussi valutari dal solo stock.</p>'+
   '<div class="drivers-cad-source"><span>'+stale+' · '+esc(lastDate)+' · H.8 TOTBKCR · fonte aggiornata via FRED, vintage iniziale non certificato</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: Federal Reserve / FRED ↗</a></div></section>'};
 }
 function usSloosResearch(esc,fmt,now){
  const x=root.FXQuantUSBanksCreditResearch?.lending_standards;
  const url='https://fred.stlouisfed.org/series/DRTSCILM';
  if(x?.series_id!=='DRTSCILM'||x.source_url!==url||x.frequency!=='Q'||
     !Array.isArray(x.observations)||x.observations.length<2)return '';
  const [prior,latest]=x.observations.slice(-2);
  const valid=row=>Array.isArray(row)&&/^\d{4}-(01|04|07|10)-01$/.test(row[0])&&
   finite(row[1])&&Math.abs(row[1])<=100;
  const today=dateMs(observationDate(now));
  if(!valid(prior)||!valid(latest)||prior[0]>=latest[0]||
     !finite(today)||dateMs(latest[0])>today)return '';
  const month=new Intl.DateTimeFormat('it-IT',{month:'long',year:'numeric',timeZone:'UTC'});
  const period=row=>month.format(dateMs(row[0]));
  const net=row=>(row[1]>0?'+':row[1]<0?'−':'')+fmt(Math.abs(row[1]),1)+'%';
  const reading=Math.abs(latest[1])<5?'Nel complesso gli standard sono rimasti pressoché invariati.':
   latest[1]>0?'Hanno prevalso le banche che hanno irrigidito gli standard.':
   'Hanno prevalso le banche che hanno allentato gli standard.';
  const stale=(today-dateMs(latest[0]))/864e5>135;
  return '<section class="drivers-cad-official drivers-us-sloos" aria-label="Standard di prestito Fed SLOOS">'+
   '<span class="mini-overline">FED SLOOS · '+(stale?'EDIZIONE STORICA':'SURVEY TRIMESTRALE')+'</span>'+
   '<h3>Standard di prestito per le imprese grandi e medie</h3>'+
   '<p>Nell’edizione di '+esc(period(latest))+' il saldo netto è '+esc(net(latest))+
   ', da '+esc(net(prior))+' a '+esc(period(prior))+'. '+reading+
   ' Il saldo è la quota di banche che hanno irrigidito gli standard meno la quota che li ha allentati, nei tre mesi coperti dal sondaggio.</p>'+
   '<div class="drivers-cad-source"><span>Prestiti commerciali e industriali · DRTSCILM</span>'+
   '<a href="'+url+'" target="_blank" rel="noopener noreferrer">Fonte: Federal Reserve / FRED ↗</a></div></section>';
 }
 function cadLynxResearch(esc,fmt,now){
  const parent=root.FXQuantCADCreditResearch,x=parent?.settlement_balances;
  if(parent?.schema!=='GMFQ_NEXT_CAD_BUSINESS_CREDIT_OFFICIAL_RESEARCH_V1'||
     parent.publisher!=='Bank of Canada'||x?.series_id!=='BOC_LYNX_ACTUAL_DAILY'||
     x.source_url!=='https://www.bankofcanada.ca/rates/indicators/market-operations-indicators/'||
     x.frequency!=='D'||x.unit!=='milioni CAD'||x.preliminary_may_be_revised!==true||
     x.canonical_monthly_equivalence_verified!==false||x.eligible_for_fx_core!==false||
     x.eligible_for_backtest!==false||!Array.isArray(x.dates)||x.latest_observation!==x.dates.at(-1)||
     !x.dates.every(d=>/^20[0-9]{2}-[0-9]{2}-[0-9]{2}$/.test(d)&&new Date(d+'T12:00:00Z').getUTCDay()%6!==0))return null;
  const s=researchCreditSeries(x,'BoC · Saldi Lynx osservati','milioni CAD',now);
  if(!s||!s.values.every(v=>v<=1000000))return null;
  // Do not connect observations across an unverified gap in the issuer history.
  let start=s.dates.length-1;
  while(start>0&&dateMs(s.dates[start])-dateMs(s.dates[start-1])<=4*864e5)start--;
  s.dates=s.dates.slice(start);s.values=s.values.slice(start);
  if(s.dates.length<2)return null;
  const delta=s.last_value-s.values.at(-2),previous=s.dates.at(-2);
  const age=(dateMs(observationDate(now))-dateMs(s.last_date))/864e5;
  const opening='Al '+dated(s.last_date)+' i saldi di regolamento Lynx '+movement(delta,'sono aumentati','sono diminuiti','sono rimasti stabili')+' rispetto alla rilevazione precedente'+(age>7?' (periodo storico)':'')+'.';
  return {headline:'Saldi di regolamento Lynx',opening,liquiditySeries:s,keepOriginalLiquidity:true,
   html:'<section class="drivers-cad-official" aria-label="Saldi di regolamento Lynx"><span class="mini-overline">BANK OF CANADA · SALDI LYNX GIORNALIERI</span><h3>'+esc(opening)+'</h3>'+
   '<p>Saldo '+esc(fmt(s.last_value/1000,3))+' miliardi CAD · rispetto al '+esc(previous)+' '+esc((delta>0?'+':'')+fmt(delta/1000,3))+' miliardi CAD. Sono saldi effettivi Lynx, esclusi i saldi RTR: non rappresentano nuovi prestiti o flussi valutari.</p>'+
   '<div class="drivers-cad-source"><span>'+esc(s.last_date)+' · '+(age>7?'periodo storico':'osservazione datata')+' · dati preliminari, equivalenza con lo storico mensile non verificata</span><a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Bank of Canada · Market operations ↗</a></div></section>'};
 }
 function cadSLOSResearch(esc,fmt,now){
  const parent=root.FXQuantCADCreditResearch,x=parent?.lending_conditions;
  if(parent?.schema!=='GMFQ_NEXT_CAD_BUSINESS_CREDIT_OFFICIAL_RESEARCH_V1'||
     parent.publisher!=='Bank of Canada'||x?.series_id!=='SLOS_BUS_LEND'||
     x.source_url!=='https://www.bankofcanada.ca/publications/slos/'||
     x.frequency!=='Q'||x.unit!=='net_balance_pct_points'||x.positive_means!=='tightening'||x.negative_means!=='easing'||
     x.first_release_pit_verified!==false||x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     !Array.isArray(x.dates)||x.latest_observation!==x.dates.at(-1)||
     !x.dates.every(d=>/^20[0-9]{2}-(01|04|07|10)-01$/.test(d)))return null;
  const s=researchCreditSeries(x,'BoC SLOS · Condizioni credito imprese','saldo netto, punti',now,true);
  if(!s||s.dates.length<4||!s.values.every(v=>Math.abs(v)<=100))return null;
  const serial=d=>Number(d.slice(0,4))*12+Number(d.slice(5,7));
  if(!s.dates.every((d,i)=>i===0||serial(d)-serial(s.dates[i-1])===3))return null;
  const latest=s.last_value,prior=s.values.at(-2),delta=latest-prior;
  const q=d=>d.slice(0,4)+'-Q'+(Math.floor((Number(d.slice(5,7))-1)/3)+1);
  const signed=v=>(v>0?'+':'')+fmt(v,2);
  const state=latest<0?'in allentamento':latest>0?'in irrigidimento':'stabili';
  const change=delta<0?'Il saldo è sceso, in direzione di condizioni meno restrittive.':delta>0?'Il saldo è salito, in direzione di condizioni più restrittive.':'Il saldo è invariato.';
  const opening='Nel '+q(s.last_date)+' le condizioni di credito alle imprese sono '+state+'. '+change;
  const age=(dateMs(observationDate(now))-dateMs(s.last_date))/864e5;
  return {opening,conditionsSeries:s,html:'<section class="drivers-cad-official" aria-label="Indagine SLOS Canada"><span class="mini-overline">BANK OF CANADA · CONDIZIONI DI CREDITO SLOS</span><h3>'+esc(opening)+'</h3>'+
    '<p>Saldo netto '+esc(signed(latest))+' punti nel '+esc(q(s.last_date))+' contro '+esc(signed(prior))+' nel '+esc(q(s.dates.at(-2)))+'. Variazione '+esc(signed(delta))+' punti. Negativo = allentamento, positivo = irrigidimento. Non è una variazione percentuale dello stock di prestiti.</p>'+
    '<div class="drivers-cad-source"><span>'+esc(q(s.last_date))+' · '+(age>220?'periodo storico':'indagine trimestrale datata')+'</span><a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">BoC · Senior Loan Officer Survey ↗</a></div></section>'};
 }
 function cadIssuerResearch(esc,fmt,now){
  const x=root.FXQuantCADCreditResearch;
  if(!x||x.schema!=='GMFQ_NEXT_CAD_BUSINESS_CREDIT_OFFICIAL_RESEARCH_V1'||
     x.publisher!=='Bank of Canada'||x.series_id!=='V122667770'||
     x.category!=='outstanding_business_loans'||x.eligible_for_fx_core!==false||
     x.eligible_for_backtest!==false||x.first_release_pit_verified!==false||
     !Array.isArray(x.dates)||!Array.isArray(x.values)||
     x.values.length!==x.dates.length||x.values.length<2)return null;
  const latest=x.dates.at(-1),last=x.values.at(-1),prev=x.values.at(-2);
  const period=observationDate(latest),today=observationDate(now);
  if(!period||!today||dateMs(period)>dateMs(today)||!finite(last)||!finite(prev)||
     last<=0||prev<=0||latest!==x.latest_observation||
     !x.dates.every((d,i)=>/^\d{4}-\d{2}$/.test(d)&&(!i||d>x.dates[i-1])))return null;
  const delta=(last/prev-1)*100,age=Math.round((dateMs(today)-dateMs(period))/864e5);
  if(!Number.isFinite(delta)||Math.abs(delta)>15)return null;
  const move=delta>0?'in aumento':delta<0?'in diminuzione':'invariati';
  const quality=age>75?'PERIODO STORICO':'ULTIMA OSSERVAZIONE DATATA';
  const headline=movement(delta,'I prestiti alle imprese sono aumentati','I prestiti alle imprese sono diminuiti','I prestiti alle imprese sono rimasti stabili');
  const opening=inMonth(latest)+' il totale dei prestiti in essere alle imprese è '+movement(delta,'salito','sceso','rimasto stabile')+
   ' rispetto alla rilevazione precedente. La domanda di nuovi prestiti aiuta a capire se stanno cambiando i piani di investimento delle aziende.';
  return {creditSeries:researchCreditSeries(x,'BoC V122667770 · Prestiti imprese','milioni CAD',now),headline,opening,
   html:'<section class="drivers-cad-official" aria-label="Fonte ufficiale canadese separata">'+
   '<span class="mini-overline">BANK OF CANADA · PRESTITI ALLE IMPRESE</span>'+
   '<h3>Prestiti alle imprese '+move+'</h3>'+
   '<p>La Bank of Canada pubblica il totale dei <b>prestiti alle imprese in essere</b>: '+esc(fmt(last,0))+
   ' milioni CAD nel '+esc(latest)+', '+move+' ('+(delta>0?'+':delta<0?'−':'')+esc(fmt(Math.abs(delta),2))+
   '%) rispetto al mese precedente. È la variazione di uno stock bancario, non il flusso di nuovi prestiti.</p>'+
   '<p>Questa osservazione aiuta a verificare l’ipotesi sulla trasmissione del credito, ma <b>non certifica</b> il canale CAD.credit operativo: definizioni, revisioni e percorso di aggiornamento restano separati. Per CAD servono anche la risposta BoC, il differenziale con la Fed e USD/CAD.</p>'+
   '<div class="drivers-cad-source"><span>'+quality+' · '+esc(latest)+' · serie V122667770 · rilascio point-in-time non verificato</span>'+
   '<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Fonte: Bank of Canada ↗</a></div></section>'};
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
  // Use the existing workbook-verified monthly window, not just its last print.
  // Require exact identity for every overlapping native observation and a
  // contiguous source window; do not interpolate or silently rebase revisions.
  const proof=release.history_backfill;
  const ordinal=p=>Number(p.slice(0,4))*12+Number(p.slice(5));
  const verified=Boolean(proof&&periods.length>=36&&
   proof.first_period===periods[0]&&periods.includes(proof.last_period)&&
   ordinal(proof.last_period)-ordinal(proof.first_period)>=35&&
   proof.overlap_display_precision_nzd_million===true&&proof.first_release_pit_verified===false&&
   proof.source_urls?.d10==='https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/d-f-r/d10/hd10.xlsx'&&
   proof.source_urls?.c50==='https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/c/c50/hc50.xlsx'&&
   ['d10','c50'].every(k=>/^[a-f0-9]{64}$/.test(proof.source_sha256?.[k]||''))&&
   periods.every((p,i)=>!i||ordinal(p)-ordinal(periods[i-1])===1));
  if(proof&&!verified)return null;
  if(verified&&!roles.every(key=>row[key].dates.every((d,i)=>
    Object.hasOwn(release.history,d)&&release.history[d][key]===row[key].values[i])))return null;
  const updated=Object.fromEntries(roles.map(key=>{
   const s=row[key];
   const pending=periods.filter(p=>p>s.last_date);
   const dates=verified?periods:[...s.dates,...pending];
   const values=verified?periods.map(p=>release.history[p][key]):[...s.values,...pending.map(p=>release.history[p][key])];
   return [key,{...s,dates,values,last_date:release.period,last_value:values.at(-1)}];
  }));
  const direction=s=>s.last_value>s.values.at(-2)?'IN AUMENTO':
   s.last_value<s.values.at(-2)?'IN CALO':'STABILE';
  return {...row,...updated,liquidity_dir:direction(updated.liquidity),credit_dir:direction(updated.credit),
   as_of:release.period+' · pubblicato il '+release.released,current_note:null,rbnzRelease:release};
 }
 function nzdCreditConditions(esc,fmt,now){
  const x=root.FXQuantNZDRBNZLiquidity?.credit_conditions;
  if(x?.series_id!=='RBNZ_C60_ACTUAL_CREDIT_AVAILABILITY'||
     x.source_url!=='https://www.rbnz.govt.nz/statistics/series/lending-and-monetary/credit-conditions'||
     x.frequency!=='H'||x.unit!=='index_points'||x.positive_means!=='easing'||
     x.first_release_pit_verified!==false||x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
     !Array.isArray(x.dates)||x.dates.length<4||x.latest_observation!==x.dates.at(-1)||
     !x.dates.every(d=>/^20[0-9]{2}-(03|09)$/.test(d))||
     !/^20[0-9]{2}-[0-9]{2}-[0-9]{2}$/.test(x.released)||!/^20[0-9]{2}-[0-9]{2}-[0-9]{2}$/.test(x.next)||
     x.released>observationDate(now)||x.next<=x.released)return null;
  const keys=['availability_corporate','availability_sme','demand_corporate','demand_sme'];
  if(!keys.every(k=>Array.isArray(x[k])&&x[k].length===x.dates.length&&x[k].every(v=>finite(v)&&Math.abs(v)<=100)))return null;
  const serial=d=>Number(d.slice(0,4))*12+Number(d.slice(5));
  if(!x.dates.every((d,i)=>i===0||serial(d)-serial(x.dates[i-1])===6))return null;
  const conditionsSeries=researchCreditSeries({dates:x.dates,values:x.availability_corporate},'RBNZ C60 · Disponibilità credito grandi imprese','punti indice',now,true);
  const additionalConditionsSeries=researchCreditSeries({dates:x.dates,values:x.availability_sme},'RBNZ C60 · Disponibilità credito PMI','punti indice',now,true);
  if(!conditionsSeries||!additionalConditionsSeries)return null;
  const [corp,sme,dc,ds]=keys.map(k=>x[k].at(-1));
  const trend=v=>v>0?'in aumento':v<0?'in calo':'invariata';
  const signed=v=>(v>0?'+':'')+fmt(v,1);
  const opening=inMonth(x.latest_observation)+' la disponibilità di credito per le grandi imprese è '+trend(corp)+', per le PMI è '+trend(sme)+'. La domanda di credito delle PMI è '+trend(ds)+'.';
  return {opening,conditionsSeries,additionalConditionsSeries,
   html:'<section class="drivers-cad-official" aria-label="Indagine C60 Nuova Zelanda"><span class="mini-overline">RBNZ · CREDIT CONDITIONS SURVEY C60</span><h3>'+esc(opening)+'</h3>'+
   '<p>Disponibilità grandi imprese: '+esc(signed(corp))+' punti; PMI: '+esc(signed(sme))+'. Domanda grandi imprese: '+esc(signed(dc))+'; PMI: '+esc(signed(ds))+'. Le risposte riguardano i sei mesi trascorsi; disponibilità e domanda sono misure distinte. Positivo indica un aumento, negativo una diminuzione.</p>'+
   '<div class="drivers-cad-source"><span>'+esc(x.latest_observation)+' · pubblicato '+esc(x.released)+' · '+(observationDate(now)<x.next?'prossimo rilascio '+esc(x.next):'nuovo rilascio da verificare')+'</span><a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">RBNZ · C60 ↗</a></div></section>'};
 }
 function nzdReleaseContext(row,today,esc,fmt){
  const release=row.rbnzRelease;
  const delta=(s,offset=1)=>(s.values.at(-offset)/s.values.at(-offset-1)-1)*100;
  const percent=n=>esc((n>0?'+':n<0?'−':'')+fmt(Math.abs(n),2))+'%';
  const cash=delta(row.liquidity),credit=delta(row.credit),priorCredit=delta(row.credit,2);
  const cashText=cash>0?'I saldi di regolamento salgono':cash<0?'I saldi di regolamento scendono':'I saldi di regolamento sono stabili';
  let creditText='il credito è stabile';
  if(credit<0)creditText='lo stock di credito cala';
  if(credit>0)creditText=!finite(priorCredit)?'il credito cresce':credit>priorCredit?'il credito accelera':credit<priorCredit?
   'il credito cresce più lentamente':'il credito cresce allo stesso ritmo';
  const headline=movement(credit,'Il credito privato è cresciuto','Il credito privato è diminuito','Il credito privato è rimasto stabile');
  const opening=inMonth(release.period)+' '+cashText.charAt(0).toLowerCase()+cashText.slice(1)+' e '+creditText+
   '. I saldi servono alle banche per pagarsi tra loro. Per la spesa interna conta come evolve il credito al settore privato.';
  return {headline,opening,
   html:'<section class="drivers-cad-official" aria-label="Dati mensili ufficiali RBNZ">'+
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
   '<a href="'+NZD_SOURCES.c50+'" target="_blank" rel="noopener noreferrer">RBNZ · C50 ↗</a></div></section>'};
 }
 function jpyReserveResearch(feed,today,esc,fmt){
  const x=feed?.lanes?.['JPY.reserve_balances'];
  const period=observationDate(x?.proxy_as_of),day=observationDate(today);
  if(feed?.schema!=='GMFQ_ESTIMATED_RESIDUAL_GAPS_V1'||feed.official_lanes_untouched!==true||
     x?.status!=='ESTIMATED_ACTIVE_AUTO_REFRESH_OFFICIAL_PROXY'||x.official_canonical_untouched!==true||
     x.source_endpoint!=='https://www.boj.or.jp/en/statistics/boj/other/mb/mblong.xlsx'||
     x.original_runtime_validation?.original_runtime_vintage_equivalence_claimed!==false||
     x.continuity_anchor?.matched!==true||x.continuity_anchor?.period!=='2026-09'||
     x.continuity_anchor?.expected_official_value!==3849859||
     !/^20[0-9]{2}-(0[1-9]|1[0-2])$/.test(x.proxy_as_of)||!period||!day||period>day||
     !finite(x.proxy_value)||x.proxy_value<1000000||x.proxy_value>8000000)return null;
  const age=(dateMs(day)-dateMs(period))/864e5;
  const change=finite(x.change_1m_pct)&&Math.abs(x.change_1m_pct)<100?x.change_1m_pct:null;
  const change3=finite(x.change_3m_pct)&&Math.abs(x.change_3m_pct)<100?x.change_3m_pct:null;
  const pct=v=>v===null?'non verificato':(v>0?'+':'')+fmt(v,2)+'%';
  const trend=change===null?'variazione mensile non verificata':Math.abs(change)<0.1?'riserve quasi stabili':movement(change,'riserve in aumento','riserve in calo','riserve stabili');
  const opening=inMonth(x.proxy_as_of)+' '+trend+' presso la BoJ'+(age>75?' (periodo storico)':'')+'.';
  return {headline:'Riserve delle banche presso la BoJ',opening,
   html:'<section class="drivers-cad-official" aria-label="Riserve BoJ fonte ufficiale alternativa"><span class="mini-overline">BANK OF JAPAN · RISERVE DI FINE MESE</span><h3>'+esc(opening)+'</h3>'+
   '<p>Saldo '+esc(fmt(x.proxy_value/10,2))+' miliardi JPY.</p>'+
   '<p>Variazione mensile '+esc(pct(change))+' · tre mesi '+esc(pct(change3))+'. Si tratta di riserve presso la banca centrale, non di nuovi prestiti o di flussi valutari.</p>'+
   '<div class="drivers-cad-source"><span>'+esc(x.proxy_as_of)+' · '+(age>75?'periodo storico':'osservazione datata')+' · fonte ufficiale alternativa; equivalenza con la vintage storica non certificata</span><a href="'+esc(x.source_endpoint)+'" target="_blank" rel="noopener noreferrer">BoJ · Monetary Base ↗</a></div></section>'};
 }
 function chfLoanPrice(feed,today,esc,fmt){
  const x=feed?.lanes?.['CHF.credit']?.lending_rate_proxy;
  if(feed?.schema!=='GMFQ_ESTIMATED_RESIDUAL_GAPS_V1'||feed.official_lanes_untouched!==true||
     x?.series_id!=='EPB@SNB.zikredlauf{FI,L16M,MP0}'||x.count_series_id!=='EPB@SNB.zikredlauf{FI,L16M,AK}'||
     x.source_url!=='https://data.snb.ch/en/topics/ziredev/cube/zikredlauf'||x.frequency!=='M'||x.unit!=='percent_per_annum'||
     x.proxy_kind!=='loan_price_not_lending_standards'||x.product!=='fixed_rate_investment_loans'||x.maturity!=='over_1_to_6_months'||
     x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||x.first_release_pit_verified!==false||
     !Array.isArray(x.dates)||x.dates.length<6||x.latest_observation!==x.dates.at(-1)||
     !x.dates.every(d=>/^20[0-9]{2}-(0[1-9]|1[0-2])$/.test(d))||
     !Array.isArray(x.values)||!x.values.every(v=>finite(v)&&v>=-5&&v<=25)||
     !Array.isArray(x.contract_counts)||x.contract_counts.length!==x.dates.length||!x.contract_counts.every(v=>Number.isInteger(v)&&v>0))return null;
  const s=researchCreditSeries(x,'SNB · Nuovi prestiti per investimenti a tasso fisso, 1–6 mesi','% annua',today,true);
  if(!s)return null;
  const previous=s.values.at(-2),delta=s.last_value-previous,age=(dateMs(observationDate(today))-dateMs(observationDate(s.last_date)))/864e5;
  const opening=inMonth(s.last_date)+' il tasso medio sui nuovi prestiti per investimenti a 1–6 mesi è '+fmt(s.last_value,2)+'%. Rispetto alla rilevazione precedente ('+s.dates.at(-2)+') il costo '+movement(delta,'è salito','è sceso','è rimasto stabile')+'.';
  return {opening,conditionsSeries:s,conditionsChartLabel:'Costo del credito · proxy ufficiale',
   html:'<section class="drivers-cad-official" aria-label="Costo finanziamenti Svizzera SNB"><span class="mini-overline">SNB · COSTO DEI NUOVI FINANZIAMENTI</span><h3>'+esc(opening)+'</h3>'+
   '<p>Tasso medio annuo '+esc(fmt(s.last_value,2))+'%, precedente '+esc(fmt(previous,2))+'%; variazione '+esc((delta>0?'+':'')+fmt(delta*100,1))+' punti base. Contratti osservati: '+esc(fmt(x.contract_counts.at(-1),0))+'.</p>'+
   '<p>Prestiti per investimenti a tasso fisso, durata superiore a un mese e fino a sei mesi. Proxy del costo del credito, non degli standard di concessione: non rappresenta tutti i prestiti, né prova un cambiamento della disponibilità bancaria.</p>'+
   '<div class="drivers-cad-source"><span>'+esc(s.last_date)+' · '+(age>155?'periodo storico':'osservazione mensile datata')+'</span><a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">SNB · Nuovi finanziamenti ↗</a></div></section>'};
 }
 function chfSNBResearch(feed,today,esc,fmt){
  const roles=[
   {key:'CHF.sight_deposits',id:'BSTA@SNB.MONA_U.BIL.AKT.FMI.GGU{U,T,T,A40}',
    label:'Depositi a vista presso la SNB · statistica bancaria mensile'},
   {key:'CHF.credit',id:'EPB@SNB.bakredinausbm{AV1,A,T1,B}',
    label:'Linee di credito verso l’estero'}
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
  const cost=chfLoanPrice(feed,today,esc,fmt);
  if(!entries.length)return cost;
  const read=entries.map(entry=>entry.html).join('');
  const byKey=Object.fromEntries(entries.map(entry=>[entry.key,entry.row]));
  const deposits=byKey['CHF.sight_deposits'],creditLines=byKey['CHF.credit'];
  const sameMonth=deposits&&creditLines&&deposits.proxy_as_of===creditLines.proxy_as_of;
  const month=sameMonth?deposits.proxy_as_of:'';
  const monthLabel=month?new Intl.DateTimeFormat('it-IT',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(month+'-01T12:00:00Z')):'';
  const monthlyDirection=value=>!finite(value)?'senza confronto mensile':
   Math.abs(value)<0.1?'quasi stabili':movement(value,'in aumento','in calo','stabili');
  const headline=sameMonth?'Depositi '+monthlyDirection(deposits.change_1m_pct)+
   ' e linee di credito verso l’estero '+monthlyDirection(creditLines.change_1m_pct):
   'Depositi e linee di credito verso l’estero';
  const creditTrend=creditLines?.change_3m_pct;
  const reading=finite(creditTrend)?'Sui tre mesi, le linee di credito verso l’estero '+
   movement(creditTrend,'sono aumentate','sono diminuite','sono rimaste stabili')+'. ':'';
  const measurement=creditLines?'<p>'+esc(reading)+'Il dato misura i limiti accordati dalle banche in Svizzera alla clientela estera. La SNB rileva separatamente gli importi utilizzati.</p>':'';
  const observations=entries.map(({key,row})=>{
   const depositsLane=key==='CHF.sight_deposits';
   const subject=depositsLane?'i depositi delle banche presso la banca centrale sono ':'le linee di credito verso l’estero sono ';
   const change=row.change_1m_pct;
   const description=finite(change)?movement(change,'in aumento','in calo','stabili')+
    ' rispetto al mese precedente':'disponibili senza un confronto mensile';
   return subject+description;
  });
  const opening=sameMonth?inMonth(month)+' '+observations.join(' e ')+'.':
   observations.map((item,i)=>inMonth(entries[i].row.proxy_as_of)+' '+item+'.').join(' ');
  return {headline,opening:opening+(cost?' '+cost.opening:''),conditionsSeries:cost?.conditionsSeries,conditionsChartLabel:cost?.conditionsChartLabel,
   html:'<section class="drivers-cad-official" aria-label="Serie mensili ufficiali SNB">'+
   '<span class="mini-overline">SWISS NATIONAL BANK · SERIE MENSILI</span>'+
   '<h3>'+esc((monthLabel?monthLabel.charAt(0).toUpperCase()+monthLabel.slice(1)+' · ':'')+headline)+'</h3>'+
   measurement+read+
   '<div class="drivers-cad-source">'+
   (deposits?'<a href="https://data.snb.ch/en/publishingSet/BSTA" target="_blank" rel="noopener noreferrer">SNB · Depositi a vista ↗</a>':'')+
   (creditLines?'<a href="https://data.snb.ch/en/topics/banken/cube/bakredinausbm" target="_blank" rel="noopener noreferrer">SNB · Linee di credito ↗</a>':'')+
   '</div></section>'+(cost?.html||'')};
 }
 // Market credit spread observations, separate from national lending and reserves.
 function creditMarket(risk,today){
  const cutoff=dateMs(observationDate(today));
  return [['IG_OAS','IG','Obbligazioni di qualità investment grade'],['HY_OAS','HY','Obbligazioni a maggior rischio']].map(([key,label,description])=>{
   const x=risk?.streams?.[key],d=observationDate(x?.date),age=(cutoff-dateMs(d))/864e5;
   const expected=key==='IG_OAS'?'BAMLC0A0CM':'BAMLH0A0HYM2';
   const ok=x?.quality==='PUBLISHED_SOURCE_RESEARCH_ONLY'&&x.not_intraday===true&&
    x.source_url==='https://fred.stlouisfed.org/graph/fredgraph.csv?id='+expected&&finite(x.value)&&finite(x.previous)&&x.value>=0&&x.previous>=0&&age>=0&&age<=7;
   const bp=ok?Math.round((x.value-x.previous)*100):null;
   return {key,label,description,ok,date:ok?d:null,level:ok?x.value:null,bp,
    tone:!ok?'unknown':bp>0?'down':bp<0?'up':'flat',source:ok?x.source_url:null};
  });
 }
 function marketFirstRead(risk,today,esc,fmt){
  const rows=creditMarket(risk,today),[ig,hy]=rows;
  const same=ig.ok&&hy.ok&&ig.date===hy.date;
  const reading=same?(ig.bp>0&&hy.bp>0?'Gli spread di entrambe le categorie si allargano: il mercato chiede più compenso per il rischio di credito.':ig.bp<0&&hy.bp<0?'Gli spread di entrambe le categorie si restringono: diminuisce il compenso richiesto per il rischio di credito.':'I due spread non si muovono nella stessa direzione: il segnale del credito di mercato è misto.'):'Le osservazioni non sono entrambe recenti e allineate: nessun giudizio congiunto.';
  const relative=same&&hy.bp>0&&hy.bp>ig.bp?' L’aumento è più marcato sul credito rischioso HY.':'';
  const cards=rows.map(x=>'<article class="liq-first-spread '+x.tone+'"><small>'+esc(x.description)+'</small><strong>'+x.label+' · '+(x.ok?esc(fmt(x.level,2))+'%':'—')+'</strong><b>'+(x.ok?esc((x.bp>0?'+':'')+x.bp+' pb')+' · '+(x.bp>0?'Si allarga':x.bp<0?'Si restringe':'Invariato'):'Confronto da verificare')+'</b><small>'+(x.ok?esc(x.date)+' · <a href="'+esc(x.source)+'" target="_blank" rel="noopener noreferrer">ICE BofA / FRED ↗</a>':'Dato recente non verificato')+'</small></article>').join('');
  return '<section class="drivers-panel liq-first-read" aria-label="Condizioni del credito di mercato"><div class="drivers-head"><div><span class="mini-overline">01 / RISCHIO DI CREDITO · USA</span><h2>Il credito di mercato si sta stringendo?</h2></div></div><p class="liq-first-judgment"><strong>Cosa vedo davvero.</strong> '+esc(reading+relative)+'</p><div class="liq-first-spreads">'+cards+'</div><p class="liq-first-note">Gli spread misurano il premio rispetto ai titoli governativi, non il rendimento totale né la quantità di prestiti. Per il Forex, un allargamento persistente può favorire la domanda di rifugio, ma va verificato con tassi, volatilità e cambi.</p><a href="#risk">Approfondisci rischio e spread ↗</a></section>';
 }
 function render(api){
  const {get,FX,FLAGS,NAMES,state,plot,pageHero,esc,fmt,date,dayNow}=api;
  const all=get('liquidity')||{},today=dayNow();
  const nzd=nzdDossier(all.NZD,today);
  const selected=validCcy(state.liqCcy)?state.liqCcy:'USD';
  const row=selected==='NZD'&&nzd?nzd:all[selected],read=interpret(row);
  const chf=selected==='CHF'?chfSNBResearch(get('residualResearch'),today,esc,fmt):null;
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
  // Reuse the source-specific dossier validators instead of presenting stale feed directions as current.
  const jpyTankan=()=>{
   const x=root.FXQuantJPYBankCreditResearch?.tankan;
   if(!x||x.frequency!=='Q'||x.unit!=='diffusion_index_points'||
    x.scope!=='all enterprises, all industries'||x.positive_lending_means!=='accommodative'||x.positive_loan_rate_means!=='rise'||
    x.first_release_pit_verified!==false||x.eligible_for_fx_core!==false||x.eligible_for_backtest!==false||
    !/^https:\/\/www\.boj\.or\.jp\/en\/statistics\/tk\/yoshi\/tk[0-9]{4}\.htm$/.test(x.source_url)||
    !Array.isArray(x.dates)||x.dates.length<2||x.dates.at(-1)!==x.latest_observation||
    !x.dates.every(d=>/^20[0-9]{2}-Q[1-4]$/.test(d)))return null;
   const keys=['lending_attitude','financial_position','loan_rate_change'];
   if(!keys.every(k=>Array.isArray(x[k])&&x[k].length===x.dates.length&&x[k].every(v=>Number.isInteger(v)&&Math.abs(v)<=100)))return null;
   const s=researchCreditSeries({dates:x.dates,values:x.lending_attitude},'BoJ Tankan · Disponibilità bancaria','punti DI',today,true);
   if(!s||!x.dates.every((d,i)=>i===0||Number(d.slice(0,4))*4+Number(d.at(-1))-(Number(x.dates[i-1].slice(0,4))*4+Number(x.dates[i-1].at(-1)))===1))return null;
   const [a,b,z]=keys.map(k=>x[k].at(-1)),[pa,pb,pz]=keys.map(k=>x[k].at(-2));
   const sign=v=>(v>0?'+':'')+fmt(v,0);
   const opening='Nel '+x.latest_observation+' la disponibilità bancaria '+movement(a-pa,'è migliorata','è peggiorata','è rimasta stabile')+'; la diffusione dei rialzi dei tassi sui prestiti '+movement(z-pz,'è aumentata','è diminuita','è rimasta stabile')+'.';
   return {opening,conditionsSeries:s,html:'<section class="drivers-cad-official" aria-label="Indagine Tankan Giappone"><span class="mini-overline">BANK OF JAPAN · TANKAN</span><h3>'+esc(opening)+'</h3>'+
   '<p>Disponibilità delle banche: '+esc(sign(a))+' punti (prima '+esc(sign(pa))+'); situazione finanziaria: '+esc(sign(b))+' (prima '+esc(sign(pb))+'); diffusione dei rialzi dei tassi sui prestiti: '+esc(sign(z))+' (prima '+esc(sign(pz))+'). Il DI misura il saldo delle risposte, non il livello dei tassi o il volume dei prestiti.</p>'+
   '<div class="drivers-cad-source"><span>'+esc(x.latest_observation)+' · tutte le imprese, tutti i settori · osservazioni effettive</span><a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">BoJ · Tankan ↗</a></div></section>'};
  };
  const jpyReading=()=>{
   const credit=jpyBOJCreditResearch(esc,fmt,today),reserves=jpyReserveResearch(get('residualResearch'),today,esc,fmt);
   const survey=jpyTankan(),available=[credit,reserves,survey].filter(Boolean);
   if(!available.length)return null;
   return {...available[0],conditionsSeries:survey?.conditionsSeries,opening:available.map(x=>x.opening).join(' '),html:available.map(x=>x.html).join('')};
  };
  const usReading=()=>{
   const credit=usFedCreditResearch(esc,fmt,today),money=usM2Research(esc,fmt,today);
   if(!credit)return money;
   if(!money)return credit;
   return {...credit,liquiditySeries:money.liquiditySeries,opening:credit.opening+' '+money.opening,html:credit.html+money.html};
  };
  const eurReading=()=>{
   const credit=eurECBLoanResearch(esc,fmt,today),liquidity=eurExcessLiquidityResearch(esc,fmt,today),survey=eurBLSResearch(esc,fmt,today);
   const available=[credit,liquidity,survey].filter(Boolean);
   if(!available.length)return null;
   return {...available[0],liquiditySeries:liquidity?.liquiditySeries,conditionsSeries:survey?.conditionsSeries,
    opening:available.map(x=>x.opening).join(' '),html:available.map(x=>x.html).join('')};
  };
  const cadReading=()=>{
   const credit=cadIssuerResearch(esc,fmt,today),liquidity=cadLynxResearch(esc,fmt,today),conditions=cadSLOSResearch(esc,fmt,today);
   const available=[credit,liquidity,conditions].filter(Boolean);
   if(!available.length)return null;
   return {...available[0],liquiditySeries:liquidity?.liquiditySeries,keepOriginalLiquidity:!!liquidity,
    conditionsSeries:conditions?.conditionsSeries,
    opening:available.map(x=>x.opening).join(' '),html:available.map(x=>x.html).join('')};
  };
  const gbpReading=()=>{
   const reserves=gbpBoEReservesResearch(esc,fmt,today),survey=gbpCCSResearch(esc,fmt,today);
   const credit=reserves?null:gbpBoESecuredCreditReading(esc,fmt,today);
   const available=[reserves,credit,survey].filter(Boolean);
   if(!available.length)return null;
   return {...available[0],conditionsSeries:survey?.conditionsSeries,opening:available.map(x=>x.opening).join(' '),html:available.map(x=>x.html).join('')};
  };
  const nzdReading=()=>{
   const monthly=nzd?nzdReleaseContext(nzd,today,esc,fmt):null,survey=nzdCreditConditions(esc,fmt,today);
   const available=[monthly,survey].filter(Boolean);if(!available.length)return null;
   return {...available[0],conditionsSeries:survey?.conditionsSeries,additionalConditionsSeries:survey?.additionalConditionsSeries,opening:available.map(x=>x.opening).join(' '),html:available.map(x=>x.html).join('')};
  };
  const audReading=()=>{
   const credit=audRBAAdjustedCredit(esc,fmt,today),cost=audF7Research(esc,fmt,today);
   const available=[credit,cost].filter(Boolean);if(!available.length)return null;
   return {...available[0],conditionsSeries:cost?.conditionsSeries,conditionsChartLabel:cost?.conditionsChartLabel,opening:available.map(x=>x.opening).join(' '),html:available.map(x=>x.html).join('')};
  };
  const issuerFor=ccy=>ccy==='CHF'?chfSNBResearch(get('residualResearch'),today,esc,fmt):
   ccy==='NZD'?nzdReading():
   ccy==='JPY'?jpyReading():
   ccy==='GBP'?gbpReading():
   ccy==='AUD'?audReading():
   ccy==='EUR'?eurReading():
   ccy==='USD'?usReading():
   ccy==='CAD'?cadReading():null;
  const cards=FX.map(ccy=>{
    const issuer=issuerFor(ccy),active=ccy===selected;
    return '<button class="drivers-country" type="button" data-liq-country="'+ccy+'" aria-controls="liquidity-dossier" aria-label="'+
     esc(ccy+' · '+(NAMES[ccy]||ccy))+'" aria-pressed="'+String(active)+'">'+
     '<span class="drivers-country-head"><b>'+esc(FLAGS[ccy]||'')+' '+ccy+'</b><small>'+esc(NAMES[ccy]||ccy)+'</small></span>'+
     '<span class="liq-country-reading">'+esc(issuer?.opening?issuer.opening.split(/(?<=[.!?])\s+/)[0]:'Osservazioni da verificare nel dossier.')+'</span><span class="liq-country-open">Apri scheda ›</span>'+'</button>';
  }).join('');
  const facts='<div class="drivers-facts">'+cell('LIQUIDITÀ',row?.liquidity,read.liquidity,'liquidity')+
   cell('CREDITO',row?.credit,read.credit,'credit')+cell('STANDARD E CONDIZIONI',row?.conditions,null,'conditions')+'</div>';
  const official=chf||
   (selected==='NZD'?nzdReading():null)||
   (selected==='JPY'?jpyReading():null)||
   (selected==='GBP'?gbpReading():null)||
   (selected==='AUD'?audReading():null)||
   (selected==='EUR'?eurReading():null)||
   (selected==='USD'?usReading():null)||
   (selected==='CAD'?cadReading():null);
  const sloos=selected==='USD'?usSloosResearch(esc,fmt,today):'';
  const headline=official?.headline||'La lettura del credito resta aperta';
  const opening=official?.opening||'Le rilevazioni disponibili non permettono di stabilire se il credito stia accelerando o frenando. Per capire come si finanziano famiglie e imprese servono osservazioni confrontabili sui prestiti e sui costi.';
  const liquidityAudit=audits[0];
  const liquidityRead=official&&!official.liquiditySeries&&['USD','EUR','JPY','CAD'].includes(selected)&&
   liquidityAudit.coverage&&liquidityAudit.state!=='DATA DA VERIFICARE'&&!policyGate('liquidity')?.withheld?
   '<p class="drivers-lead"><strong>'+esc(row.liquidity.label)+'</strong> · '+
   esc(snap(row.liquidity).replace(/T.*$/,''))+
   (liquidityAudit.state==='STORICO'?' · storico':'')+'. '+esc(liquidityAudit.observation)+'.</p>':'';
  const historicalCount=audits.filter(x=>x.state==='STORICO').length;
  const sourceStatus='<p class="drivers-source-brief">QUALITÀ TEMPORALE · '+esc(historicalCount)+
   ' serie storiche da ricontrollare · '+esc(3-covered)+' serie assenti o in verifica.</p>';
  const hasCharts=selected!=='CHF'||Boolean(official?.conditionsSeries);
  const market=marketFirstRead(get('risk'),today,esc,fmt);
  const limits=selected==='CHF'
   ?'Le serie svizzere disponibili hanno perimetri diversi. Verifica quali prestiti coprono prima di estendere il giudizio al credito interno.'
   :'Riserve, prestiti e criteri di concessione misurano aspetti diversi. La crescita dei prestiti, da sola, lascia aperta la lettura delle condizioni.';
  return pageHero('CONDIZIONI FINANZIARIE G8','Liquidità & Credito',
   'Riserve bancarie, prestiti e condizioni di concessione: la trasmissione finanziaria all’economia reale, distinta dagli spread di mercato.')+
   '<section class="drivers-panel" id="liquidity-studio"><div class="drivers-head"><div><h2>Liquidità e prestiti nelle otto economie</h2><p class="liq-first-note">Ultime osservazioni delle fonti di ricerca già verificate, con il periodo nella lettura. Non sono una graduatoria delle condizioni finanziarie.</p>'+
   '</div></div>'+
   '<div class="drivers-country-grid">'+cards+'</div></section>'+
   '<div class="liq-section-jumps pill-controls" role="group" aria-label="Vai alle analisi di liquidità e credito">'+
   '<button type="button" class="pill" data-section-jump="liquidity-dossier">Dossier paese</button>'+
   (hasCharts?'<button type="button" class="pill" data-section-jump="liquidity-charts">Grafici e serie</button>':'')+
   '<button type="button" class="pill" data-section-jump="liquidity-market">Spread IG/HY · contesto</button></div>'+
   '<section class="drivers-panel drivers-selection" id="liquidity-dossier" tabindex="-1" aria-label="Scheda liquidità e credito '+selected+'">'+
   '<div class="drivers-head"><div><span class="mini-overline">'+esc(FLAGS[selected]||'')+' '+selected+'</span>'+
   '<h2>'+esc(headline)+'</h2></div></div>'+
   '<p class="drivers-lead drivers-liquidity-opening">'+esc(opening)+'</p>'+
   '<p class="drivers-lead"><strong>Cosa frena la lettura.</strong> '+esc(limits)+'</p>'+
   (official?.html||'')+sloos+
   '<div class="drivers-story"><div><span>PERCHÉ CONTA PER IL CAMBIO</span><p>'+esc(FX_LENSES[selected]?.fx||read.fx)+'</p></div>'+
   '<div><span>COSA GUARDARE</span><p>'+esc(FX_LENSES[selected]?.watch||read.watch)+'</p></div></div>'+
   liquidityRead+
   (root.FXQuantDriverMarketAudit?.render?.({get,esc,dayNow},selected)||'')+
   '<div class="drivers-links"><a href="#macro">Scenario macro ↗</a><a href="#rates">Tassi & OIS ↗</a><a href="#risk">Rischio e credito IG/HY ↗</a><a href="#currencies">Valute G8 ↗</a></div>'+
   '<details class="drivers-source-provenance-fold"><summary>Verifica dati, copertura e fonti bancarie</summary>'+
   (selected==='CHF'?'<p>Le serie mensili SNB hanno un perimetro diverso dallo storico precedente, che resta in verifica.</p>':
    '<p>'+esc(read.headline)+' '+esc(read.meaning)+'</p>')+
   facts+sourceStatus+
   '<p>Registro delle fonti al '+esc(provenance?.as_of||'dato non verificato')+' · Copertura '+esc(covered)+'/3 serie · Contratti mappati '+esc(provenance?.verifiedContracts??'n.d.')+'/3.</p>'+
   '<ul>'+roles.map(role=>{const g=policyGate(role);return '<li><strong>'+esc(({liquidity:'Liquidità',credit:'Credito',conditions:'Standard e condizioni'})[role])+'</strong>: '+esc(g?.label||'provenienza non verificata')+'. '+esc(g?.narrative||'Verificare il registro fonti.')+'</li>'}).join('')+'</ul>'+
   '<p>Copertura storica e date riferite alle rispettive serie. Se disponibile, il grafico del credito usa la fonte ufficiale separata più recente, senza modificare il feed storico. Frequenze, definizioni e unità possono differire.'+
   (row?.current_note?' '+esc(row.current_note):'')+'</p></details></section>'+
   (hasCharts?'<section class="liq-evidence-region" id="liquidity-charts" tabindex="-1" aria-label="Grafici di liquidità e credito">'+
   '<div class="drivers-head"><div><h2>Grafici e serie del paese</h2><p class="liq-first-note">Controlla la direzione di ciascuna serie e verifica unità e periodo prima di confrontarle.</p></div></div>':'')+
   (selected==='CHF'?(official?.conditionsSeries?'<details class="drivers-panel drivers-fold"><summary>Apri grafico del costo dei finanziamenti</summary><div class="drivers-chart-grid">'+chart(official.conditionsSeries,official.conditionsChartLabel,'#95c6e9')+'</div><p class="drivers-source-note">Serie SNB separata: non rappresenta lo storico originario di liquidità o credito.</p></details>':''):'<details class="drivers-panel drivers-fold"><summary>Apri gli storici di liquidità, credito e condizioni</summary>'+
   '<div class="drivers-chart-grid">'+chart(official?.liquidityRecent||official?.liquiditySeries||row?.liquidity,official?.liquidityRecent?'Liquidità · ultima settimana':official?.liquiditySeries?'Liquidità · fonte ufficiale separata':'Liquidità','#69d5ad')+chart(official?.creditSeries||row?.credit,official?.creditSeries?'Credito · fonte ufficiale separata':'Credito','#95c6e9')+'</div>'+
   (official?.liquidityRecent?'<p class="drivers-source-note">Confronto delle ultime due settimane dalla fonte ufficiale separata. '+(selected==='AUD'?'Il saldo precedente è ricavato dal movimento settimanale pubblicato. ':'Entrambi i saldi sono pubblicati dalla BoE. ')+'Lo storico precedente rimane distinto: nessuna interpolazione fra periodi mancanti.</p><div class="drivers-chart-grid">'+chart(row?.liquidity,'Liquidità · storico originario','#69d5ad')+'</div>':'')+
   (official?.keepOriginalLiquidity?'<p class="drivers-source-note">Saldi Lynx giornalieri e storico mensile originario rimangono separati: nessuna equivalenza o interpolazione presunta.</p><div class="drivers-chart-grid">'+chart(row?.liquidity,'Liquidità · storico originario','#69d5ad')+'</div>':'')+
   (official?.conditionsSeries?'<div class="drivers-chart-grid">'+chart(official.conditionsSeries,official.conditionsChartLabel||'Condizioni di credito · fonte ufficiale separata','#95c6e9')+'</div>':'')+
   (official?.additionalConditionsSeries?'<div class="drivers-chart-grid">'+chart(official.additionalConditionsSeries,'Condizioni di credito PMI · fonte ufficiale separata','#95c6e9')+'</div>':'')+
   '<p class="drivers-source-note">I grafici conservano i valori originali nelle rispettive unità (livelli o tassi di crescita esplicitamente indicati); non confrontare direttamente scale tra paesi o fra aggregati monetari e credito. Se manca un dato, non sostituiamo una stima a un’osservazione.</p></details>')+
   (hasCharts?'</section>':'')+
   '<section class="liq-evidence-region" id="liquidity-market" tabindex="-1" aria-label="Credito di mercato e spread USA">'+market+'<p class="source-caption">Gli spread IG/HY misurano il rischio di mercato, non gli standard dei prestiti bancari. <a href="#risk">Vai al quadro cross-asset ↗</a></p></section>';
 }
 const api={series,direction,interpret,observationDate,sourceEvidence,creditMarket,marketFirstRead,nzdDossier,render};
 root.FXQuantLiquidityCredit=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
