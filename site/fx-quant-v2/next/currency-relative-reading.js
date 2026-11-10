'use strict';
/* Next V21: an orientation story for two economies, not two isolated currency
 * scores. Observations remain dated, unrevised source vintages are NOT assumed,
 * and neither relative macro direction nor 2Y spread is a validated FX trade.
 */
(function(root){
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const isDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 const isPeriod=x=>typeof x==='string'&&/^\d{4}-\d{2}(?:-\d{2})?$/.test(x);
 const fmt=(v,d=2)=>finite(v)?v.toLocaleString('it-IT',{minimumFractionDigits:d,maximumFractionDigits:d}):'n.d.';
 const signed=(v,d=2,unit='')=>finite(v)?(v>0?'+':v<0?'−':'')+fmt(Math.abs(v),d)+unit:'n.d.';
 const day=x=>isPeriod(x)?x.slice(0,7):'periodo non verificato';
 function macroAxis(country,kind,macro,now){
  const x=macro?.[country]?.[kind],history=x?.history;
  if(!x||!isPeriod(x.as_of)||x.as_of>now||!finite(x.latest_value)||
    !Array.isArray(history)||history.length<2||!finite(history.at(-1))||
    !finite(history.at(-2))||Math.abs(history.at(-1)-x.latest_value)>.06)return null;
  return {period:day(x.as_of),value:x.latest_value,change:history.at(-1)-history.at(-2)};
 }
 function describeChange(x){
  if(!x)return 'non verificabile';
  return (x.change>.025?'sale':x.change<-.025?'scende':'è pressoché stabile')+
    ' ('+signed(x.change,2,' p.p.')+', '+x.period+')';
 }
 function rates(c,gov,now){
  const r=gov?.[c];
  if(!r||!isDay(r.date)||r.date>now||!finite(r['2Y']))return null;
  return {ccy:c,date:r.date,level:r['2Y'],quality:r.quality||'non classificata'};
 }
 function money(c,ois,now){
  const row=ois?.currencies?.[c],h=row?.horizons?.['6m'];
  if(!h||!isDay(h.as_of)||h.as_of>now||!finite(h.rate))return null;
  return {date:h.as_of,kind:row.kind||'non classificato',quality:row.quality||'non classificata'};
 }
 function flow(c,cot,now){
  const x=cot?.[c],d=x?.dates,n=d?.length||0;
  if(n<2||!isDay(d.at(-1))||d.at(-1)>now||!Array.isArray(x.net)||
    x.net.length!==n||!finite(x.net.at(-1))||!finite(x.net.at(-2)))return null;
  return {date:d.at(-1),net:x.net.at(-1),delta:x.net.at(-1)-x.net.at(-2)};
 }
 const flowDir=x=>x.delta>0?'aumenta':x.delta<0?'diminuisce':'non varia';
 function read({base,quote,macro,gov,ois,cot,now,price20,priceAsOf}){
  if(!/^[A-Z]{3}$/.test(base||'')||!/^[A-Z]{3}$/.test(quote||'')||
    base===quote||!isDay(now))return {available:false};
  const infA=macroAxis(base,'inflation',macro,now),infB=macroAxis(quote,'inflation',macro,now);
  const labA=macroAxis(base,'labour',macro,now),labB=macroAxis(quote,'labour',macro,now);
  const macroPairs=[
   infA&&infB?'Inflazione: '+base+' '+describeChange(infA)+'; '+quote+' '+describeChange(infB)+'.':
    'Inflazione: le due sequenze non sono entrambe verificabili.',
   labA&&labB?'Disoccupazione: '+base+' '+describeChange(labA)+'; '+quote+' '+describeChange(labB)+'.':
    'Disoccupazione: manca una delle due serie confrontabili.'
  ];
  const macroStory=macroPairs.join(' ')+' Sono variazioni delle rispettive rilevazioni, non sorprese simultanee: definizioni e mesi possono differire.';
  const rA=rates(base,gov,now),rB=rates(quote,gov,now);
  let govStory;
  if(rA&&rB&&rA.date===rB.date){
   govStory='Al '+rA.date+' il differenziale governativo 2Y '+base+'−'+quote+' è '+
    signed((rA.level-rB.level)*100,1,' pb')+'. Le date coincidono: è uno spread sovrano storico, non uno spread OIS né una prova di vantaggio futuro.';
  }else{
   govStory='Non calcolo uno spread 2Y corrente: '+base+' '+(rA?.date||'data mancante')+
    ', '+quote+' '+(rB?.date||'data mancante')+'. Due rendimenti di date diverse non sono un confronto simultaneo.';
  }
  const oA=money(base,ois,now),oB=money(quote,ois,now);
  const moneyStory=oA&&oB?'Riferimenti 6M: '+base+' '+oA.kind+' ('+oA.quality+', '+oA.date+
    '); '+quote+' '+oB.kind+' ('+oB.quality+', '+oB.date+
    '). Non li sottraggo: sottostante e qualità non garantiscono una curva monetaria omogenea.':
    'Il pricing 6M non è documentato in modo completo per entrambe le economie; non deduco un repricing relativo.';
  const a=flow(base,cot,now),b=flow(quote,cot,now);
  const cotStory=a&&b?
   'COT settimanale: net '+base+' '+flowDir(a)+' ('+signed(a.delta,0)+'), net '+quote+' '+flowDir(b)+
   ' ('+signed(b.delta,0)+')'+(a.date===b.date?' al '+a.date:' nelle rispettive date '+a.date+' e '+b.date)+
   '. Variazioni dei net non equivalgono a flussi spot; le due serie non sono quantità direttamente confrontabili.':
   'COT bilaterale incompleto: nessuna conferma di flussi contemporanei.';
  const move=finite(price20)&&isDay(priceAsOf)&&priceAsOf<=now?price20:null;
  const fav=finite(move)&&Math.abs(move)>.025?(move>0?base:quote):null;
  const verdict=fav?'Il prezzo degli ultimi 20 fixing BCE favorisce '+fav+' contro '+(fav===base?quote:base)+
   '. Questo descrive forza relativa osservata, non dimostra se prevalgano macro, tassi o coperture.':
   'I fixing disponibili non offrono una direzione relativa abbastanza chiara: non forzo un vantaggio.';
  const timing='Thesis Strength ancora da verificare con sorprese, pricing omogeneo e risposta del prezzo; Trade Attractiveness non dimostrata.';
  const watch=fav?'Per rafforzare la lettura su '+fav+' servono persistenza del movimento e nuove osservazioni comparative. Un’inversione nei fixing, senza conferma monetaria, la indebolirebbe.':
   'Servono una differenza macro verificabile, date monetarie comparabili e successiva conferma dei fixing prima di definire una tesi.';
  return {available:true,macroStory,govStory,moneyStory,cotStory,verdict,timing,watch,priceFav:fav,
   spreadComparable:!!(rA&&rB&&rA.date===rB.date),cotAligned:!!(a&&b&&a.date===b.date)};
 }
 root.FXQuantCurrencyRelative={read,macroAxis,rates,money,flow};
 if(typeof module!=='undefined'&&module.exports)module.exports={read,macroAxis,rates,money,flow};
})(typeof window!=='undefined'?window:{});
