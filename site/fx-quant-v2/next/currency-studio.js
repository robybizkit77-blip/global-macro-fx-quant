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
 const w=state.csReturnWindow===5?5:state.csReturnWindow===60?60:20;
 const number=x=>finite(x)?fmt(x,2):'—';
 const period=x=>String(x||'n.d.');
 function observedRate(k){const v=GOV[k];return v&&validDay(v.date)&&v.date<=dayNow()&&finite(v['2Y'])?v:null}
 function dataMarket(k){const a=COT[k];if(!a||!Array.isArray(a.net)||!a.net.length||!Array.isArray(a.dates))return null;
  const i=a.net.length-1;return {net:a.net[i],delta:i>0?a.net[i]-a.net[i-1]:null,percentile:a.percentile?.[i],asof:a.dates[i]};}
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
 function selector(){
  return '<div class="country-orient-list" role="group" aria-label="Scegli una delle otto valute">'
   +FX.map(k=>{const gov=observedRate(k),cotK=dataMarket(k);
    return '<button type="button" data-cs-country="'+k+'" aria-pressed="'+String(k===country)+'" class="orient-country '+(k===country?'active':'')+'">'
     +'<span>'+FLAGS[k]+' '+k+'</span><small>2Y '+(finite(gov?.['2Y'])?fmt(gov['2Y'],2)+'%':'—')+'</small>'
     +'<small>COT '+(finite(cotK?.percentile)?'P'+fmt(cotK.percentile,0):'—')+'</small></button>';
   }).join('')+'</div>';
 }
 function story(){
  let caption=finite(price20)?'Nelle ultime 20 sedute '+country+' '+priceDir+' rispetto a '+against+' del '+priceMove+' (fixing BCE, '+date(asof)+').':'Il rendimento a 20 sedute non è validato.';
  let rateText=r?'Il 2Y governativo di '+country+' è '+fmt(r['2Y'],3)+'% al '+date(r.date)+'.':'Il dato governativo 2Y non è disponibile.';
  let pos=finite(cot?.net)?'Il COT mostra una posizione '+(cot.net>0?'net long':cot.net<0?'net short':'neutra')+' al '+date(cot.asof)+'.':'Il COT non è disponibile.';
  return '<section class="orient-lead"><div class="orient-lead-copy"><span class="chapter-kicker">COUNTRY DESK / '+FLAGS[country]+' '+esc(NAMES[country]).toUpperCase()+'</span>'
    +'<h2>Prima il quadro.<br><em>Poi l’approfondimento.</em></h2>'
    +'<p>'+esc(caption+' '+rateText+' '+pos)+'</p>'
    +'<div class="orient-lead-qualifier"><span>FATTO</span> Dati con date indipendenti. <span>NON DIMOSTRATO</span> Causalità fra rendimento, COT e cambio.</div>'
    +'<div class="orient-focus-actions"><button class="action-primary" type="button" data-cs-openpair="'+country+against+'">Valuta la coppia <span>↗</span></button><a href="#macro" class="action-minimal">Studia il contesto macro →</a></div></div>'
    +'<div class="orient-spot"><span class="micro-over">FX RELATIVO · '+esc(country)+'/'+esc(against)+'</span>'
    +'<strong>'+fmt(target?.quote?.value,5)+'</strong><small>1 '+country+' = '+against+' · BCE fixing '+date(asof)+'</small>'
    +'<div class="orient-spot-parts">'+[['5 sedute',target?.move5],['20 sedute',target?.move20],['60 sedute',target?.move60]].map(([k,v])=>'<div><span>'+k+'</span><b class="'+(v<0?'orient-neg':'')+'">'+sign(v,2,'%')+'</b></div>').join('')+'</div>'
    +'<label class="orient-counterparty">Controvaluta<select class="select" id="cs-other">'+FX.filter(k=>k!==country).map(k=>'<option value="'+k+'" '+(k===against?'selected':'')+'>'+FLAGS[k]+' '+k+' — '+NAMES[k]+'</option>').join('')+'</select></label>'
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
  return pageHero('G8 / CURRENCY ORIENTATION','Otto valute. <em>Una visione chiara.</em>','Qui scegli cosa investigare. I grafici macro, le curve e le analisi COT complete restano nei laboratori specializzati, senza ripetizioni.')
   +'<div class="orient-status"><span>◉ COUNTRY ORIENTATION · '+FLAGS[country]+' '+country+'</span><span>G8 · 7 CONFRONTI · BCE '+date(FXDATA?.last_as_of||asof)+'</span></div>'
   +selector()+story()+evidence()+peers()+checkpoint()+closing()
   +'<p class="source-caption">Contesto: Macro Thermometer; NATIVE_RATES_DATA; NATIVE_CB_DATA; CFTC Legacy V250; pricing OIS/futures/proxy con fonte per valuta. Performance FX calcolata da ECB_G8_PRICE_HISTORY (EUR cross). Ogni dato è datato. La V2 operativa e i suoi segnali rimangono invariati.</p>';
 }
 return render();
}
root.FXQuantCurrencies={render:build};
})(window);
