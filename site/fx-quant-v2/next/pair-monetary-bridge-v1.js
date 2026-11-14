'use strict';
/* Source-first FX monetary evidence. Always show the best dated evidence:
 * exact 1D/1W source delta, dated common historical interval, or two published
 * levels. Historical and proxy levels NEVER masquerade as today's repricing.
 * Does not change the FX score, model signals, OIS feed or price history.
 */
(function(root){
 const CURRENCIES=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
 const validKey=k=>typeof k==='string'&&/^[A-Z]{6}$/.test(k)&&CURRENCIES.includes(k.slice(0,3))&&CURRENCIES.includes(k.slice(3));
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const esc=x=>String(x??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[ch]));
 const fmt=x=>finite(x)?(x>0?'+':x<0?'−':'')+Math.abs(x).toFixed(2).replace('.',','):'—';
 const rate=x=>finite(x)?x.toFixed(3).replace('.',',')+'%':'senza livello';
 const date=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)?
  x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4):'n.d.';
 const validDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&
  !Number.isNaN(Date.parse(x+'T12:00:00Z'))&&new Date(Date.parse(x+'T12:00:00Z')).toISOString().slice(0,10)===x;
 const days=(a,b)=>Math.round((Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/864e5);
 const source=k=>k==='OIS'?'OIS ufficiali':k==='FUTURES'?'futures ufficiali':
  k==='FUTURES SECONDARI'?'futures secondari':k==='PROXY FUTURES'?'proxy bank-bill':'fonte non classificata';
 const legible=k=>k.slice(0,3)+'/'+k.slice(3);
 function validLeg(before,after,currency){
  if(!before||!after||!validDay(before.date)||!validDay(after.date)||
   !finite(before.rate)||!finite(after.rate)||before.date>=after.date)return null;
  if(before.derived||after.derived){
   if(currency!=='NZD'||!before.derived||after.derived||
    before.source_class!=='BANK_BILL_PROXY_DELTA_REFERENCE'||
    after.source_class!=='BANK_BILL_PROXY'||!before.contract||
    before.contract!==after.contract)return null;
   return 'PROXY_DELTA_RECONSTRUCTED';
  }
  if(before.source_class!==after.source_class)return null;
  if(before.source_class==='SECONDARY_SAME_CONTRACT')
   return before.contract&&before.contract===after.contract?'SAME_LISTED_CONTRACT':null;
  if(before.source_class==='OFFICIAL_TENOR')
   return 'OFFICIAL_TENOR_ARCHIVE';
  return null;
 }
 function historicalWindow(history,base,quote,today,period){
  const archive=root.FXQuantPricingHistory;
  if(!archive?.country||!validDay(today)||!validKey(base+quote))return null;
  const A=archive.country(history,base,60),B=archive.country(history,quote,60);
  const p=A?.tenors?.['6m']||[],q=B?.tenors?.['6m']||[];
  if(!p.length||!q.length)return null;
  const byQ=new Map(q.filter(x=>x.date<=today).map(x=>[x.date,x]));
  const common=p.filter(x=>x.date<=today&&byQ.has(x.date))
   .map(x=>({date:x.date,a:x,b:byQ.get(x.date)}));
  const matches=[];
  for(let i=1;i<common.length;i++){
   for(let j=0;j<i;j++){
    const before=common[j],after=common[i],gap=days(before.date,after.date);
    if(period==='1d'?(gap<1||gap>4):(gap<5||gap>9))continue;
    const aMethod=validLeg(before.a,after.a,base),bMethod=validLeg(before.b,after.b,quote);
    if(!aMethod||!bMethod)continue;
    const aBp=Math.round((after.a.rate-before.a.rate)*10000)/100;
    const bBp=Math.round((after.b.rate-before.b.rate)*10000)/100;
    const reconstructed=aMethod==='PROXY_DELTA_RECONSTRUCTED'||bMethod==='PROXY_DELTA_RECONSTRUCTED';
    matches.push({period,from:before.date,to:after.date,days:gap,
     aBp,bBp,relativeBp:Math.round((aBp-bBp)*100)/100,
     aMethod,bMethod,reconstructed,
     grade:reconstructed?'HISTORICAL_PROXY_REFERENCE':'HISTORICAL_COMMON',
     type:reconstructed?'PROXY_RICOSTRUITO':'STORICO_DATATO',
     provenance:'DUE_DATE_COMUNI'});
   }
  }
  matches.sort((x,y)=>y.to.localeCompare(x.to)||
   (period==='1w'?Math.abs(x.days-7)-Math.abs(y.days-7):x.days-y.days)||
   y.from.localeCompare(x.from));
  return matches[0]||null;
 }
 function asEvidence(live,period){
  if(!live||!finite(live.relativeBp))return null;
  return {period,relativeBp:live.relativeBp,aBp:live.aBp,bBp:live.bBp,
   from:live.from||null,to:live.asof,grade:live.grade,type:'FONTE_ULTIMA_RILEVAZIONE',
   provenance:live.grade==='MATCHED_EXACT_INTERVAL'?'DUE_DATE_COMUNI':'BASE_DI_CONFRONTO_INDICATIVA',
   reconstructed:false};
 }
 function evaluate({pair,favored,today,ois,operational,research,nzd,history,pairs,prices}){
  const model=pairs?.pairs||{},api=root.FXQuantRelativePricing;
  if(!validKey(pair)||!model[pair]||!api?.read)
   return {ready:false,pair,reason:'Non è presente una coppia riconosciuta nel modello FX.'};
  const base=pair.slice(0,3),quote=pair.slice(3);
  const inputs={ccy:base,other:quote,today,snapshot:ois,operational,research,nzd,history,pairs};
  const one=api.read({...inputs,window:'1d'}),week=api.read({...inputs,window:'1w'});
  if(!one||!week)return {ready:false,pair,reason:'Nessuna fonte monetaria accessibile per questa coppia.'};
  const oneEvidence=asEvidence(one.live,'1d')||historicalWindow(history,base,quote,today,'1d');
  const weekEvidence=asEvidence(week.live,'1w')||historicalWindow(history,base,quote,today,'1w');
  const lead=oneEvidence||weekEvidence||null;
  const favor=favored===base||favored===quote?favored:null;
  const directional=lead?.grade==='MATCHED_EXACT_INTERVAL'&&favor&&
   Math.abs(lead.relativeBp)>=.05?
   ((lead.relativeBp>0&&favor===base)||(lead.relativeBp<0&&favor===quote)
    ?'COERENTE_CON_VIEW_MACRO':'IN_TENSIONE_CON_VIEW_MACRO'):null;
  const priceAsOf=typeof prices?.last_as_of==='string'?prices.last_as_of:
   typeof pairs?.price_asof==='string'?pairs.price_asof:null;
  return {ready:true,pair,base,quote,one,week,oneEvidence,weekEvidence,lead,
   directional,favored:favor,priceAsOf,
   kinds:{base:source(one.a?.kind),quote:source(one.b?.kind)},
   levels:{base:{rate:one.ar?.rate,asof:one.ar?.asof},quote:{rate:one.br?.rate,asof:one.br?.asof}},
   historyAsOf:history?.as_of||null};
 }
 function render(args){
  const m=evaluate(args);
  if(!m.ready)return '<section class="pair-monetary-bridge" data-pair-monetary-status="SOURCE_MISSING">'+
    '<span class="pair-monetary-kicker">TASSI RELATIVI · 6M</span><p>'+esc(m.reason)+
    '</p></section>';
  const {base,quote,pair,oneEvidence,weekEvidence,lead,priceAsOf,directional,favored,kinds,levels}=m;
  const dated=lead?.type==='STORICO_DATATO'||lead?.type==='PROXY_RICOSTRUITO';
  const archived=Boolean(dated);
  let headline,meaning;
  if(lead){
   const x=lead.relativeBp;
   const higher=Math.abs(x)<.05?null:x>0?base:quote;
   headline=higher?'Nell’ultimo confronto '+(archived?'storico ':'')+
    'il repricing 6M è stato maggiore per '+higher+'.':
    'Le due variazioni 6M hanno avuto un’entità pressoché uguale.';
   const origins=lead.from?date(lead.from)+' → '+date(lead.to):
    'rilevazione finale '+date(lead.to);
   meaning=(archived?'Ultimo intervallo comune archivistico: ':'Confronto delle ultime variazioni: ')+
    origins+'. '+base+' '+fmt(lead.aBp)+' pb contro '+quote+' '+fmt(lead.bBp)+
    ' pb; differenza relativa '+fmt(x)+' pb. '+
    (lead.reconstructed?'Il riferimento del proxy bank-bill è ricostruito dai delta della fonte, non osservato indipendentemente. ':
     lead.grade==='HISTORICAL_COMMON'?'Sono due date comuni dell’archivio, non un repricing della seduta corrente. ':
     lead.grade==='SAME_END_REFERENCE_UNVERIFIED'?
      'La data finale è comune, ma non sono certificate entrambe le date iniziali. ':'');
  }else{
   headline='Il 6M è documentato per entrambe le valute; il confronto delle variazioni richiede date comuni.';
   meaning='Ultimi livelli: '+base+' '+rate(levels.base.rate)+' ('+date(levels.base.asof)+
    '), '+quote+' '+rate(levels.quote.rate)+' ('+date(levels.quote.asof)+
    '). Sono livelli distinti, non un differenziale di repricing.';
  }
  const macro=directional==='COERENTE_CON_VIEW_MACRO'?
   'Il movimento relativo è coerente con la valuta '+favored+' favorita dalla view macro. È un riscontro di segno, non una prova causale.':
   directional==='IN_TENSIONE_CON_VIEW_MACRO'?
   'Il repricing relativo è contrario alla valuta '+favored+' favorita dalla view macro: una tensione da approfondire sul prezzo.':
   favored&&lead?
   'La view macro favorisce '+favored+'. Il confronto monetario disponibile è '+
     (dated?'storico':'indicativo')+': contribuisce al contesto, ma non certifica la forza attuale del cambio.':
   favored?
   'La view macro favorisce '+favored+', ma i due livelli 6M non consentono un confronto contemporaneo delle variazioni.':
   'La preferenza macro non è definita: il movimento monetario resta descrittivo.';
  const px=priceAsOf?
    'Ultimo fixing BCE '+date(priceAsOf)+'. '+
    (lead&&lead.to===priceAsOf?
      'La data finale coincide con quella monetaria; restano da analizzare direzione e persistenza del prezzo.':
      'Il fixing e l’intervallo monetario non sono allineati: nessuna reazione FX viene attribuita a quei tassi.') :
    'Il fixing BCE non è disponibile con una data verificabile: nessuna conferma di prezzo.';
  const evidenceCard=(key,e)=>{
   if(e){
    const label=e.type==='FONTE_ULTIMA_RILEVAZIONE'?'ULTIMA RILEVAZIONE':
     e.reconstructed?'PROXY RICOSTRUITO':'ULTIMO INTERVALLO COMUNE';
    const range=e.from?date(e.from)+' → '+date(e.to):'Fine '+date(e.to);
    return '<div class="pair-monetary-kpi" data-pair-monetary-window="'+key+
     '" data-pair-monetary-evidence="'+esc(e.grade)+'">'+
     '<span>Δ6M RELATIVO · '+key.toUpperCase()+'</span><strong class="'+
     (e.relativeBp>0?'positive':e.relativeBp<0?'negative':'')+'">'+esc(fmt(e.relativeBp))+
     ' pb</strong><small>'+esc(label)+' · '+esc(range)+'</small></div>';
   }
   return '<div class="pair-monetary-kpi" data-pair-monetary-window="'+key+
    '" data-pair-monetary-evidence="LEVEL_CONTEXT">'+
    '<span>CONTESTO 6M · '+key.toUpperCase()+'</span><strong>'+esc(base)+
    ' '+esc(rate(levels.base.rate))+'</strong><strong>'+esc(quote)+' '+
    esc(rate(levels.quote.rate))+'</strong>'+
    '<small>Rilevazioni separate: '+date(levels.base.asof)+' / '+date(levels.quote.asof)+'</small></div>';
  };
  const srcLinks='<div class="pair-monetary-links">'+
    '<a href="./rates-pricing-history-v1.json" target="_blank" rel="noopener noreferrer">Storico G8 · JSON ↗</a>'+
    '<a href="../ois-pricing-snapshot.json" target="_blank" rel="noopener noreferrer">Livelli OIS/futures · JSON ↗</a>'+
    '<a href="../ois-same-contract-repricing-research.json" target="_blank" rel="noopener noreferrer">Contratti futures · JSON ↗</a>'+
    '<a href="../../../live_data/sections/OIS_OPERATIONAL_VIEW.json" target="_blank" rel="noopener noreferrer">Fonte operativa · JSON ↗</a>'+
    '</div>';
  return '<section class="pair-monetary-bridge" data-pair-monetary-status="'+
    (lead?esc(lead.grade):'LEVEL_CONTEXT')+'" data-pair-monetary-pair="'+esc(pair)+
    '" aria-label="Repricing monetario relativo sei mesi '+esc(legible(pair))+'">'+
   '<div class="pair-monetary-top"><div><span class="pair-monetary-kicker">MACRO → PRICING → PREZZO · '+esc(legible(pair))+
   '</span><h3>Cosa racconta il repricing monetario 6M?</h3></div>'+
   '<button type="button" data-pair-open-rates="'+esc(pair)+'">Esplora Tassi & OIS <span aria-hidden="true">↗</span></button></div>'+
   '<div class="pair-monetary-body"><div class="pair-monetary-reading">'+
   '<h4>'+esc(headline)+'</h4><p>'+esc(meaning)+'</p>'+
   '<p><strong>Rispetto alla tesi macro.</strong> '+esc(macro)+'</p>'+
   '<p><strong>La verifica sul Forex.</strong> '+esc(px)+'</p></div>'+
   '<div class="pair-monetary-values">'+evidenceCard('1d',oneEvidence)+
     evidenceCard('1w',weekEvidence)+'</div></div>'+
   '<details class="pair-monetary-source"><summary>Esamina date, metodi e fonti originali</summary>'+
   '<p>'+esc(base)+' · '+esc(kinds.base)+' · '+date(levels.base.asof)+
     '; '+esc(quote)+' · '+esc(kinds.quote)+' · '+date(levels.quote.asof)+'.</p>'+
   '<p>Il Δ è base meno quotata: cambiamenti dei tenori monetari, NON uno spread OIS negoziabile. '+
   'Nelle serie futures ufficiali senza ID di scadenza, il confronto è del tenore rappresentativo e non prova la continuità del contratto. '+
   'Gli archivi retrospettivi non costituiscono dati point-in-time per backtest; un proxy ricostruito non è un’osservazione indipendente.</p>'+
   srcLinks+'</details></section>';
 }
 const api={evaluate,historicalWindow,validLeg,render};
 root.FXQuantPairMonetary=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
