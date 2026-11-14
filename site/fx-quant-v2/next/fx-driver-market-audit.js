'use strict';
/* FX Quant Next — factual market verification for G8 macro driver dossiers.
 * Research read-only. Does not promote the restricted G8 credit V4 research,
 * convert futures/proxies to comparable OIS, infer flows or issue FX entries.
 */
(function(root){
 const CROSSES={USD:'EURUSD',EUR:'EURGBP',GBP:'EURGBP',JPY:'USDJPY',
  CHF:'EURCHF',CAD:'AUDCAD',AUD:'AUDCAD',NZD:'AUDNZD'};
 const iso=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const elapsed=(d,now)=>iso(d)&&iso(now)?
  Math.round((Date.parse(now+'T12:00:00Z')-Date.parse(d+'T12:00:00Z'))/86400000):null;
 function policy(ccy,ois,now){
  const o=ois?.currencies?.[ccy],h=o?.horizons?.['6m'];
  const age=elapsed(h?.as_of,now),instrument=o?.kind||'non classificato';
  if(!finite(h?.rate)||age===null||age<0)
   return {ready:false,text:'Nessuna misura 6M con livello e data verificabili: non attribuiamo un repricing.',asof:null};
  const ageLabel=age>8?'Storico: ':'';
  const deltas=[['1D',h.change_1d_bp],['1W',h.change_1w_bp]]
   .filter(([,v])=>finite(v)).map(([window,v])=>
    window+' '+(v>0?'+':v<0?'−':'')+Math.abs(v).toLocaleString('it-IT',{maximumFractionDigits:1})+' pb');
  const actual=deltas.length?
   'Variazioni riportate dallo strumento: '+deltas.join(' · ')+'.':
   'È disponibile un livello, ma non una variazione 1D/1W certificata: nessuna nuova aspettativa può essere dedotta.';
  return {ready:true,asof:h.as_of,level:h.rate,instrument,quality:o?.quality||'da verificare',
   text:ageLabel+'Riferimento monetario 6M '+ccy+' al '+h.as_of+' ('+instrument+
    ', qualità '+(o?.quality||'da verificare')+'). '+actual+
    ' OIS, futures e proxy non sono intercambiabili e non provano la causa del movimento FX.'};
 }
 function fx(ccy,model,now){
  const key=CROSSES[ccy],row=model?.pairs?.[key],asof=model?.price_asof;
  const age=elapsed(asof,now),s=row?.setup;
  if(!s||age===null||age<0||age>10)
   return {ready:false,pair:key,text:'Nessuna lettura FX sufficientemente datata per questa valuta: il prezzo resta da verificare.'};
  const name=key.slice(0,3)+'/'+key.slice(3);
  const quality=s.quality||'NON VALUTABILE',fav=s.structuralFav;
  const state=s.price?.state,words=state==='GOOD'?'coerente con la direzione favorita dal modello':
   state==='BAD'?'in contrasto con la direzione favorita dal modello':
   'senza conferma direzionale netta nel modello';
  const verdict=fav&&['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'].includes(fav)?
   'La tesi del modello privilegia '+fav+', con qualità '+quality+'; il prezzo è '+words+'.':
   'Il modello non offre un vantaggio strutturale FX utilizzabile; qualità '+quality+'.';
  return {ready:true,pair:key,asof,quality,text:
   'Su '+name+' ('+asof+'): '+verdict+
   ' È una lettura del modello, non prova che liquidità o politica monetaria abbiano causato il movimento.'};
 }
 function riskCheck(risk,now){
  const v=risk?.streams?.VIX,h=risk?.streams?.HY_OAS;
  const vAge=elapsed(v?.date,now),hAge=elapsed(h?.date,now);
  if(!finite(v?.value)||!finite(h?.value)||vAge===null||hAge===null||vAge<0||hAge<0)
   return 'VIX e HY non sono entrambi verificabili: nessuna diagnosi dei flussi di rischio.';
  if(vAge>7||hAge>7)
   return 'VIX e credito HY hanno osservazioni datate: non utilizziamo questi livelli per dichiarare il regime di rischio corrente.';
  if(v.date!==h.date)
   return 'VIX ('+v.date+') e credito HY ('+h.date+') non hanno la stessa data: nessuna conferma sincronizzata di risk-on/risk-off.';
  const dv=finite(v.previous)?v.value-v.previous:null;
  const dh=finite(h.previous)?h.value-h.previous:null;
  if(!finite(dv)||!finite(dh))
   return 'VIX e HY hanno la stessa data, ma mancano variazioni precedenti verificabili.';
  const trend=dv>0&&dh>0?'entrambe in aumento: pressione sul rischio da verificare':
   dv<0&&dh<0?'entrambe in calo: possibile distensione da confermare':
   'non concordi: il regime non è univoco';
  return 'VIX e HY al '+v.date+': variazioni '+trend+'. Non dimostrano chi stia comprando o vendendo FX.';
 }
 function review(ccy,inputs){
  const now=inputs?.now||'';
  return {policy:policy(ccy,inputs?.ois,now),
   fx:fx(ccy,inputs?.pairs,now),
   risk:riskCheck(inputs?.risk,now)};
 }
 function render(api,ccy){
  const {get,esc,dayNow}=api;
  const r=review(ccy,{now:dayNow(),ois:get('ois'),pairs:get('pairs'),risk:get('risk')});
  const a='<div class="drivers-market-item"><span>01 / PRICING MONETARIO</span><p>'+esc(r.policy.text)+'</p></div>';
  const b='<div class="drivers-market-item"><span>02 / PREZZO E TESI FX</span><p>'+esc(r.fx.text)+'</p></div>';
  return '<section class="drivers-market-audit" aria-label="Verifica dei prezzi di mercato '+esc(ccy)+'">'+
   '<div class="drivers-market-head"><strong>Cosa conferma davvero il mercato?</strong>'+
   '<small>DATI E DATE · TESI ≠ INGRESSO</small></div>'+
   '<div class="drivers-market-grid">'+a+b+'</div>'+
   '<p class="drivers-market-risk"><b>CHI POTREBBE REAGIRE?</b> '+esc(r.risk)+
   ' Eventuali ricoperture, riduzioni di carry o flussi rifugio restano ipotesi da verificare, non posizioni osservate.</p></section>';
 }
 const api={policy,fx,riskCheck,review,render};
 root.FXQuantDriverMarketAudit=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
