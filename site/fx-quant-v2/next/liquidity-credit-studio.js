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
 NZD:{fx:'Lo storico disponibile della liquidità NZD è breve e non consente inferenze robuste sui flussi. Credito privato in aumento e settlement cash in calo sono una divergenza da testare contro RBNZ e rischio globale.',
  watch:'Aggiornamenti RBNZ su settlement cash e credito, confronto monetario con RBA e comportamento AUD/NZD e NZD/USD.'}
 };
 function render(api){
  const {get,FX,FLAGS,NAMES,state,plot,pageHero,esc,fmt,date,dayNow}=api;
  const all=get('liquidity')||{};
  const selected=validCcy(state.liqCcy)?state.liqCcy:'USD';
  const row=all[selected],read=interpret(row),today=dayNow();
  const audits=[row?.liquidity,row?.credit,row?.conditions].map(v=>sourceEvidence(v,today));
  const covered=audits.filter(x=>x.coverage).length;
  const snap=(s)=>s?.last_date||'data non disponibile';
  const cell=(label,s,d)=>{
   const exists=Boolean(s?.label&&finite(s.last_value)),audit=sourceEvidence(s,today);
   const isYoY=/yoy|a\/a/i.test(s?.label||'');
   return '<div class="drivers-fact"><span>'+esc(label)+'</span><strong>'+esc(s?.label||'Serie non disponibile')+'</strong>'+
    '<small>'+(exists?('Ultimo '+esc(snap(s))+' · '+esc(fmt(s.last_value,2))+(s.unit?' '+esc(s.unit):isYoY?'%':'') ):'Misura non verificabile')+'</small>'+
    '<b class="drivers-tone" data-tone="'+(audit.tone==='warn'?'unknown':esc(audit.tone))+'">'+esc(audit.state)+'</b>'+
    '<small class="drivers-observation">'+esc(audit.message)+'</small>'+
    (d?'<b class="drivers-mini-state" data-tone="'+esc(d.tone)+'">Direzione del dataset: '+esc(d.label)+'</b>':'')+'</div>';
  };
  const chart=(s,label,color)=>{
   const pts=series(s);
   return '<article class="drivers-chart"><div class="drivers-chart-label"><strong>'+esc(label)+'</strong><small>'+esc(s?.label||'Serie assente')+' · '+esc(snap(s))+'</small></div>'+
    (pts.length>=2?plot({lines:[{name:s.label,color,values:pts}],label:label+' '+selected}):
     '<div class="drivers-empty">Storico numerico insufficiente: nessuna curva inventata.</div>')+'</article>';
  };
  const cards=FX.map(ccy=>{
    const item=all[ccy],reading=interpret(item),active=ccy===selected;
    return '<button class="drivers-country" type="button" data-liq-country="'+ccy+'" aria-pressed="'+String(active)+'">'+
     '<span class="drivers-country-head"><b>'+esc(FLAGS[ccy]||'')+' '+ccy+'</b><small>'+esc(NAMES[ccy]||ccy)+'</small></span>'+
     '<span class="drivers-mini-state" data-tone="'+reading.liquidity.tone+'">Liquidità · '+esc(reading.liquidity.label)+'</span>'+
     '<span class="drivers-mini-state" data-tone="'+reading.credit.tone+'">Credito · '+esc(reading.credit.label)+'</span></button>';
  }).join('');
  return pageHero('FINANCIAL CONDITIONS / G8','Liquidità & Credito. <em>Il denaro arriva all’economia?</em>',
   'Il denaro può aumentare senza generare nuovi prestiti. Osserviamo i due canali per capire se cambiano crescita, pricing e valute.')+
   '<section class="drivers-panel" id="liquidity-studio"><div class="drivers-head"><div><span class="mini-overline">01 / MAPPA G8</span><h2>Otto economie, due canali distinti</h2><p>Seleziona un paese. Le frecce sono classificazioni delle singole serie storiche, non un indice di liquidità globale né un ranking FX.</p></div><span class="drivers-source-mark">FONTI CON DATE INDIPENDENTI</span></div>'+
   '<div class="drivers-country-grid">'+cards+'</div></section>'+
   '<section class="drivers-panel drivers-selection" aria-label="Dossier liquidità e credito '+selected+'">'+
   '<div class="drivers-head"><div><span class="mini-overline">02 / LETTURA ECONOMICA · '+esc(FLAGS[selected]||'')+' '+selected+'</span>'+
   '<h2>'+esc(read.headline)+'</h2></div><span class="drivers-status" data-tone="'+(covered===3?'neutral':'unknown')+'">COPERTURA '+covered+'/3 SERIE</span></div>'+
   '<p class="drivers-lead">'+esc(read.meaning)+'</p>'+
   '<p class="drivers-source-brief">QUALITÀ TEMPORALE · '+esc(audits.filter(x=>x.state==='STORICO').length)+' serie storiche da ricontrollare · '+esc(3-covered)+' serie mancanti. Nessuna conclusione sulla liquidità di oggi dalle sole osservazioni pregresse.</p>'+
   '<div class="drivers-facts">'+cell('LIQUIDITÀ',row?.liquidity,read.liquidity)+cell('CREDITO',row?.credit,read.credit)+cell('STANDARD E CONDIZIONI',row?.conditions,null)+'</div>'+
   '<div class="drivers-story"><div><span>IPOTESI DI TRASMISSIONE AL FOREX</span><p>'+esc(FX_LENSES[selected]?.fx||read.fx)+'</p></div><div><span>COSA MONITORARE</span><p>'+esc(FX_LENSES[selected]?.watch||read.watch)+'</p></div></div>'+
   (root.FXQuantDriverMarketAudit?.render?.({get,esc,dayNow},selected)||'')+
   '<div class="drivers-links"><a href="#macro">Scenario macro ↗</a><a href="#rates">Tassi & OIS ↗</a><a href="#risk">Rischio e credito IG/HY ↗</a><a href="#currencies">Valute G8 ↗</a></div>'+
   '<div class="drivers-source-note">Ultimo riferimento della scheda: '+esc(row?.as_of||'non dichiarato')+
   '. Copertura storica non significa aggiornamento corrente. Le serie possono avere frequenze, definizioni, unità e date non omogenee.'+
   (row?.current_note?' Contesto della fonte: '+esc(row.current_note):'')+'</div></section>'+
   '<details class="drivers-panel drivers-fold"><summary>Apri grafici, osservazioni e limiti delle fonti</summary>'+
   '<div class="drivers-chart-grid">'+chart(row?.liquidity,'Liquidità','#69d5ad')+chart(row?.credit,'Credito','#95c6e9')+'</div>'+
   '<p class="drivers-source-note">I grafici conservano i livelli originali nelle rispettive unità; non confrontare direttamente scale tra paesi o fra aggregati monetari e credito. Se manca un dato, non sostituiamo una stima a un’osservazione.</p></details>';
 }
 const api={series,direction,interpret,observationDate,sourceEvidence,render};
 root.FXQuantLiquidityCredit=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
