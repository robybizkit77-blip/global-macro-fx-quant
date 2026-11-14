'use strict';
/* Read-only monetary relative pricing in the selected 28-pair dossier.
 * Reuses the Rates Studio's exact 6M source/date validator; no new
 * model score, FX signal, OIS fabrication or same-day price inference.
 */
(function(root){
 const validKey=k=>typeof k==='string'&&/^[A-Z]{6}$/.test(k);
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
 const fmt=x=>typeof x==='number'&&Number.isFinite(x)?
  (x>0?'+':x<0?'−':'')+Math.abs(x).toFixed(2).replace('.',','):'—';
 const d=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)?
  x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4):'n.d.';
 const source=k=>k==='OIS'?'OIS ufficiali':k==='FUTURES'?'futures ufficiali':
  k==='FUTURES SECONDARI'?'futures secondari':k==='PROXY FUTURES'?'proxy bank-bill':'qualità non verificata';
 const legible=k=>k.slice(0,3)+'/'+k.slice(3);
 function evaluate({pair,favored,today,ois,operational,research,nzd,history,pairs,prices}){
  const model=pairs?.pairs||{},api=root.FXQuantRelativePricing;
  if(!validKey(pair)||!model[pair]||!api?.read)return {ready:false,pair,reason:'Coppia non verificata nel modello delle 28 coppie.'};
  const base=pair.slice(0,3),quote=pair.slice(3);
  const inputs={ccy:base,other:quote,today,snapshot:ois,operational,research,nzd,history,pairs};
  const one=api.read({...inputs,window:'1d'});
  const week=api.read({...inputs,window:'1w'});
  if(!one||!week)return {ready:false,pair,reason:'Mancano fonti monetarie datate confrontabili.'};
  const lead=one.live?{period:'1D',data:one.live}:
   week.live?{period:'1W',data:week.live}:null;
  const last=one.latestCommon||null;
  const priceAsOf=typeof prices?.last_as_of==='string'?prices.last_as_of:
   typeof pairs?.price_asof==='string'?pairs.price_asof:null;
  const favor=favored===base||favored===quote?favored:null;
  const directional=lead?.data?.grade==='MATCHED_EXACT_INTERVAL'&&favor&&
   Math.abs(lead.data.relativeBp)>=.05?
   ((lead.data.relativeBp>0&&favor===base)||(lead.data.relativeBp<0&&favor===quote)
     ?'COERENTE_CON_VIEW_MACRO':'IN_TENSIONE_CON_VIEW_MACRO'):null;
  return {ready:true,pair,base,quote,one,week,lead,last,favored:favor,directional,priceAsOf,
   kinds:{base:source(one.a?.kind),quote:source(one.b?.kind)}};
 }
 function render(args){
  const m=evaluate(args);
  if(!m.ready)return '<section class="pair-monetary-bridge" data-pair-monetary-status="UNAVAILABLE">'+
   '<span class="pair-monetary-kicker">TASSI RELATIVI · 6M</span><p>'+esc(m.reason)+
   ' Nessun contributo monetario viene aggiunto alla tesi Forex.</p></section>';
  const {base,quote,pair,one,week,lead,last,priceAsOf,favored,directional,kinds}=m;
  const label=x=>x.live?(fmt(x.live.relativeBp)+' pb'):'non allineato';
  const state=x=>!x.live?'NON CONFRONTABILE':
   x.live.grade==='MATCHED_EXACT_INTERVAL'?'DATE INIZIALI E FINALI COMUNI':
   'SOLO DATA FINALE COMUNE';
  const sourceDates=base+' '+d(one.ar?.asof)+' · '+quote+' '+d(one.br?.asof);
  let headline,meaning;
  if(lead){
   const v=lead.data.relativeBp;
   headline=Math.abs(v)<.05?'Nessun vantaggio evidente nel repricing 6M.':
    v>0?'Il 6M '+base+' è salito relativamente più del '+quote+'.':
    'Il 6M '+quote+' è salito relativamente più del '+base+'.';
   meaning=lead.period+' · '+base+' '+fmt(lead.data.aBp)+' pb contro '+quote+
    ' '+fmt(lead.data.bBp)+' pb · differenza '+fmt(v)+' pb. '+
    (lead.data.grade==='MATCHED_EXACT_INTERVAL'?
     'La variazione confronta lo stesso intervallo certificato.':
     'La data finale coincide, ma non disponiamo di entrambe le date iniziali certificate: lettura indicativa.');
  }else if(last){
   headline='Le ultime variazioni 6M non sono confrontabili sulla stessa seduta.';
   meaning='Ultimo intervallo storico comune: '+d(last.from)+' → '+d(last.to)+
    ', Δ relativo '+fmt(last.bp)+' pb. È un riferimento storico, NON il repricing di oggi.';
  }else{
   headline='Le ultime variazioni 6M non sono confrontabili.';
   meaning='Mancano due date comuni consecutive e fonti sufficienti. Nessun valore viene dedotto dai livelli attuali.';
  }
  const macro=directional==='COERENTE_CON_VIEW_MACRO'?
    'Il segno del repricing è coerente con la valuta '+favored+' favorita dalla view macro. È una coerenza, non una conferma causale.':
   directional==='IN_TENSIONE_CON_VIEW_MACRO'?
    'Il movimento relativo va contro '+favored+', favorita dalla view macro: un elemento di tensione da verificare sul prezzo.':
   favored?
    'La view macro favorisce '+favored+', ma il confronto monetario non ha qualità temporale sufficiente per confermarla o contraddirla.':
    'Non abbiamo una preferenza macro validata da confrontare: questa rimane una lettura monetaria descrittiva.';
  const pxCheck=priceAsOf?
   'Ultimo fixing BCE '+d(priceAsOf)+(lead&&priceAsOf===lead.data.asof?
     ': stessa data finale del pricing, ma non una prova di causalità.':
     ': data diversa dal riferimento monetario, quindi nessuna reazione FX contemporanea attribuita.') :
   'Fixing BCE non verificabile: il prezzo non conferma il movimento dei tassi.';
  const card=(period,x)=>'<div class="pair-monetary-kpi" data-pair-monetary-window="'+period.toLowerCase()+
    '" data-pair-monetary-verified="'+(x.live?.grade||'NOT_ALIGNED')+'">'+
    '<span>Δ6M RELATIVO · '+period+'</span><strong class="'+
    (x.live?.relativeBp>0?'positive':x.live?.relativeBp<0?'negative':'')+'">'+
    esc(label(x))+'</strong><small>'+esc(state(x))+
    (x.live?' · '+d(x.live.asof):'')+'</small></div>';
  return '<section class="pair-monetary-bridge" data-pair-monetary-status="'+
    (lead?esc(lead.data.grade):'NOT_ALIGNED')+'" data-pair-monetary-pair="'+esc(pair)+
    '" aria-label="Repricing monetario relativo a sei mesi per '+esc(legible(pair))+'">'+
    '<div class="pair-monetary-top"><div><span class="pair-monetary-kicker">MACRO → PRICING → PREZZO · '+esc(legible(pair))+
    '</span><h3>Il mercato monetario sta sostenendo la tesi?</h3></div>'+
    '<button type="button" data-pair-open-rates="'+esc(pair)+'" aria-label="Apri Tassi e OIS per '+esc(legible(pair))+
    '">Apri confronto OIS <span aria-hidden="true">↗</span></button></div>'+
    '<div class="pair-monetary-body"><div class="pair-monetary-reading"><h4>'+esc(headline)+
    '</h4><p>'+esc(meaning)+'</p><p><strong>Rispetto alla tesi macro.</strong> '+
    esc(macro)+'</p><p><strong>La verifica sul Forex.</strong> '+esc(pxCheck)+
    '</p></div><div class="pair-monetary-values">'+card('1D',one)+card('1W',week)+'</div></div>'+
    '<details class="pair-monetary-source"><summary>Date, strumenti e limiti</summary>'+
    '<p>'+esc(base)+' · '+esc(kinds.base)+'; '+esc(quote)+' · '+esc(kinds.quote)+
    '. Ultimi 6M: '+esc(sourceDates)+'.</p>'+
    '<p>Il differenziale è la differenza fra due <em>variazioni</em> 6M di strumenti diversi. Non equivale a uno spread OIS negoziabile, a un carry realizzabile o a un segnale di ingresso. Le variazioni con date iniziali non certificate restano indicative.</p>'+
    '</details></section>';
 }
 const api={evaluate,render};
 root.FXQuantPairMonetary=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
