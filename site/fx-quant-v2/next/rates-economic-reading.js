'use strict';
/* Interpret dated sovereign 2Y/10Y moves versus dated money-market 6M.
 * No new indicators, no OIS conversion, no inferred policy surprise.
 */
(function(root){
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const isDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 const fmt=x=>(x>0?'+':'')+x.toFixed(1)+' pb';
 function read({country,now,asof,previous,bp2,bp10,kind,quality,h6}){
  const valid=isDay(asof)&&isDay(previous)&&asof<=now&&previous<asof&&finite(bp2)&&finite(bp10);
  const good6=h6&&isDay(h6.as_of)&&h6.as_of<=now&&finite(h6.rate);
  let headline='Non abbiamo abbastanza prove per leggere la curva.';
  let meaning='Servono almeno due osservazioni 2Y e 10Y su date comuni per classificare il movimento.';
  let watch='Recuperare fonti con date comparabili e poi verificare aspettative monetarie e prezzo.';
  if(valid){
   const age=Math.floor((Date.parse(now+'T12:00:00Z')-Date.parse(asof+'T12:00:00Z'))/864e5);
   const old=age>7,delta=bp10-bp2;
   const front=Math.abs(bp2)>Math.abs(bp10)+.5,long=Math.abs(bp10)>Math.abs(bp2)+.5;
   const bull=bp2<-.5&&bp10<-.5,bear=bp2>.5&&bp10>.5;
   const curve=bull?(delta>.5?'bull steepening':delta<-.5?'bull flattening':'discesa con pendenza pressoché stabile'):
     bear?(delta>.5?'bear steepening':delta<-.5?'bear flattening':'rialzo con pendenza pressoché stabile'):'movimento misto o limitato';
   headline=old?'La curva osservata è storica, non una reazione di oggi.'
     :Math.abs(bp2)<.5&&Math.abs(bp10)<.5?'La curva cambia poco: non forziamo una svolta.'
     :bull?(front?'Rendimenti in calo: il 2Y guida.':long?'Rendimenti in calo: il 10Y guida.':'Rendimenti in calo, causa da verificare.')
     :bear?(front?'Rendimenti in rialzo: il 2Y guida.':long?'Rendimenti in rialzo: il 10Y guida.':'Rendimenti in rialzo, causa da verificare.')
     :'2Y e 10Y non raccontano lo stesso movimento.';
   meaning='Tra '+previous+' e '+asof+' il 2Y '+country+' varia '+fmt(bp2)+' e il 10Y '+fmt(bp10)+': '+curve+'. '+
     (front?'Il breve si muove di più: è compatibile con una revisione monetaria, ma non la dimostra.':
       long?'Il lungo si muove di più: crescita, inflazione attesa, rendimenti reali e term premium sono spiegazioni alternative.':
       'Non emerge un segmento dominante: la causa non è identificata.')+
     (old?' La data è troppo lontana per descrivere la seduta corrente.':'');
   watch=front?'Verificare OIS/futures sullo stesso calendario; poi spread relativi e prezzo Forex.'
     :long?'Verificare real yields, breakeven, term premium, offerta di Treasury e credito.'
     :'Verificare tassi monetari, credito e risposta FX prima di attribuire un cambiamento alla banca centrale.';
  }
  let pricing='Non abbiamo un 6M con data e livello verificabili: il repricing monetario resta sconosciuto.';
  if(good6){
   const intro='Il 6M '+(kind||'strumento non classificato')+' ('+(quality||'qualità non classificata')+
     ') è '+h6.rate.toFixed(3)+'% al '+h6.as_of+'. ';
   pricing=!valid?intro+'Non esiste una curva governativa comparabile nelle date: nessuna conferma.'
     :asof!==h6.as_of?intro+'Il confronto governativo si ferma al '+asof+
       ': le osservazioni non sono simultanee. La variazione del 6M, se presente, riguarda la propria data.'
     :finite(h6.change_1d_bp)?intro+'Variazione 1D '+fmt(h6.change_1d_bp)+
       ' nella stessa seduta dei governativi: confronto datato, non prova causale né curva OIS universale.'
     :intro+'Manca una variazione 1D validata: il livello da solo non dimostra un cambiamento delle aspettative.';
  }
  return {headline,meaning,pricingEvidence:pricing,watch};
 }
 root.FXQuantRatesEconomic={read};
 if(typeof module!=='undefined'&&module.exports)module.exports={read};
})(typeof window!=='undefined'?window:{});
