'use strict';
/* CFTC Tuesday snapshots compared with *same-Tuesday* ECB fixing observations.
 * No stale cached COT price pack, no forward-fill, no inferred publication-time
 * reaction. Contract changes describe reported positions, not proven spot flows.
 */
(function(root){
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 function priceEvidence(ccy,history,fx,today){
  const none={prices:[],price1:null,priceState:'non conclusivo',
    priceRow:null,aligned:false,matchedDates:0};
  if(!/^[A-Z]{3}$/.test(ccy||'')||!Array.isArray(history)||history.length<2||
     !Array.isArray(fx?.rows)||fx.source!=='ECB euro foreign exchange reference rates')return none;
  const relevant=new Map(fx.rows.filter(r=>day(r.Date)&&r.Date<=today).map(r=>[r.Date,r]));
  const label=ccy==='USD'?'USD/EUR':ccy+'/USD';
  const q=r=>{
   if(!r)return null;
   const numerator=ccy==='USD'?r.EUR:r.USD;
   const denominator=r[ccy];
   return finite(numerator)&&numerator>0&&finite(denominator)&&denominator>0?numerator/denominator:null;
  };
  const prices=history.flatMap(h=>{
   const v=q(relevant.get(h.date));
   return finite(v)?[{label:h.date,value:v}]:[];
  });
  const a=history.at(-2),b=history.at(-1);
  if(!day(a.date)||!day(b.date)||b.date>today||!finite(a.net)||!finite(b.net))return none;
  const p0=q(relevant.get(a.date)),p1=q(relevant.get(b.date));
  if(!finite(p0)||!finite(p1)||p0<=0)return {...none,prices,matchedDates:prices.length};
  const diff=(p1/p0-1)*100,flow=b.net-a.net;
  return {
   prices,priceRow:{priceLabel:label,as_of:b.date,net:b.net},
   price1:diff,priceState:diff===0||flow===0?'non conclusivo':
     Math.sign(diff)===Math.sign(flow)?'coerente':'divergente',
   aligned:true,matchedDates:prices.length
  };
 }
 function flowReading(a){
  const h=a?.hist||[],end=h.at(-1),prev=h.at(-2),prior=h.at(-3),month=h.at(-5);
  if(!end||!prev||!prior||!month||
    ![end.net,prev.net,prior.net,month.net,end.long,prev.long,end.short,prev.short].every(finite))
   return {headline:'Il flusso non è verificabile.',detail:'Servono rilevazioni CFTC settimanali coerenti.',monitor:'Verificare posizione netta, long e short.'};
  const n=end.net-prev.net,l=end.long-prev.long,s=end.short-prev.short,old=prev.net-prior.net,m=end.net-month.net;
  const signs=h.slice(-4).map((r,i)=>r.net-h[h.length-5+i].net);
  const same=signs.filter(x=>n>0?x>0:n<0?x<0:x===0).length;
  const persistence=n===0?'L’ultima settimana è stabile, anche se le quattro settimane precedenti possono raccontare altro.':
   same===4?'Il netto si è mosso nello stesso verso in tutte le ultime quattro settimane.':
   same===3?'Tre delle ultime quattro settimane hanno lo stesso verso dell’ultima.':
   'Il movimento non è persistente sulle ultime quattro settimane.';
  const tempo=n===0?'Nessuna nuova variazione netta nell’ultima settimana.':
   Math.sign(n)===Math.sign(old)&&old!==0?
    (Math.abs(n)>Math.abs(old)+.5?'L’ultima variazione è più ampia della precedente.':
     Math.abs(n)<Math.abs(old)-.5?'L’ultima variazione perde ampiezza.':'L’ampiezza è simile a quella precedente.'):
    'Il verso dell’ultima variazione differisce da quello precedente, ma una settimana non conferma un’inversione.';
  let component='Il netto cambia senza una componente dominante verificabile.';
  if(l>0&&s<0)component='Aumentano i contratti long e diminuiscono gli short: due contributi al miglioramento netto.';
  else if(l<0&&s>0)component='Diminuiscono i contratti long e aumentano gli short: due contributi al peggioramento netto.';
  else if(l>0&&s>0)component=l>s?
    'Aumentano sia long sia short: prevale la crescita dei long.' :
    s>l?'Aumentano sia long sia short: prevale la crescita degli short.':
    'Long e short aumentano della stessa quantità: il saldo non si muove.';
  else if(l<0&&s<0)component=-s>-l?
    'Si riducono entrambe le esposizioni: la chiusura di short pesa di più.':
    -l>-s?'Si riducono entrambe le esposizioni: la liquidazione di long pesa di più.':
    'Long e short si riducono allo stesso modo, lasciando invariato il netto.';
  else if(l>0&&s===0)component='La crescita dei long spiega il miglioramento del saldo, senza aumento degli short.';
  else if(l<0&&s===0)component='La riduzione dei long spiega il peggioramento del saldo.';
  else if(s>0&&l===0)component='L’aumento degli short peggiora il netto senza movimento dei long.';
  else if(s<0&&l===0)component='La copertura degli short migliora il netto senza aumento dei long.';
  const headline=n>0?(l>0&&s<0?'Long in aumento e short in riduzione.':
    l>0&&s>=0?'Il netto migliora grazie soprattutto ai long.':
    s<0?'Il netto migliora grazie soprattutto alle ricoperture.':'Il netto migliora, ma non è un ingresso validato.'):
   n<0?(l<0&&s>0?'Long in riduzione e short in aumento.':
    s>0&&l>=0?'Il netto peggiora soprattutto per nuovi short.':
    l<0?'Il netto peggiora soprattutto per liquidazioni long.':'Il netto peggiora, ma non è un segnale FX.'):
   'Il netto non cambia: controlla entrambi i lati.';
  const detail=component+' '+persistence+' '+tempo+
   ' Il saldo di quattro settimane '+(m>0?'aumenta':m<0?'diminuisce':'non varia')+
   '; queste sono differenze fra stock CFTC, non ordini spot osservati.';
  const monitor=n!==0?'Valutare se il movimento continua o perde ampiezza nelle prossime rilevazioni; incrociare fixing BCE e tassi senza inferire causalità.':
   'Verificare se la stabilità del saldo nasconde aumenti o riduzioni contemporanee di long e short.';
  return {headline,detail,monitor,delta1:n,delta4:m,persistence:same};
 }
 root.FXQuantCOTEvidence={priceEvidence,flowReading};
 if(typeof module!=='undefined'&&module.exports)module.exports={priceEvidence,flowReading};
})(typeof window!=='undefined'?window:{});
