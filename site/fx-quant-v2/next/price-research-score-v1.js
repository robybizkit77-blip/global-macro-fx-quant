'use strict';
/* Price research score: reuse canonical 20 common ECB fixing rank and
 * non-overlapping 5/5 momentum. Ordinal midrank, NOT expected return. */
(function(root){
 const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
 const finite=Number.isFinite;
 const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&finite(Date.parse(x))&&new Date(Date.parse(x)).toISOString().slice(0,10)===x;
 const span=(a,b)=>day(a)&&day(b)?(Date.parse(b)-Date.parse(a))/864e5:NaN;
 function evaluate({currency,prices,today,ranker,momentum}={}){
  if(!FX.includes(currency)||!day(today)||typeof ranker!=='function'||typeof momentum!=='function'||
   prices?.schema!=='GMFQ_ECB_G8_PRICE_HISTORY_V1'||prices.status!=='CURRENT_OFFICIAL_HISTORY'||prices.base!=='EUR'||
   prices.source!=='ECB euro foreign exchange reference rates'||
   prices.source_url!=='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml'||
   !Array.isArray(prices.rows)||!day(prices.last_as_of)||span(prices.last_as_of,today)<0||span(prices.last_as_of,today)>5)return null;
  const rows=prices.rows.slice(-21);
  if(rows.length!==21||rows.at(-1).Date!==prices.last_as_of||
   rows.some((r,i)=>!day(r.Date)||r.Date>today||(i&&span(rows[i-1].Date,r.Date)<=0)||FX.some(c=>!finite(r[c])||r[c]<=0))||
   span(rows[0].Date,rows.at(-1).Date)>40)return null;
  const rank=ranker(prices,today,FX),mom=momentum(prices,today);
  if(rank?.asof!==prices.last_as_of||rank.from!==rows[0].Date||rank.commonSessions!==20||mom?.asof!==rank.asof||
   rank.items?.length!==8||mom.items?.length!==8||!FX.every(c=>rank.items.filter(x=>x.ccy===c&&finite(x.percent)).length===1&&
   mom.items.filter(x=>x.ccy===c&&[x.recent,x.prior,x.delta].every(finite)).length===1))return null;
  const r=rank.items.find(x=>x.ccy===currency),m=mom.items.find(x=>x.ccy===currency);
  // Pairwise relative strength: equal returns get the same midrank.
  // Neutral (all equal) is 5; score is independent of absolute magnitude.
  const score=10*rank.items.filter(x=>x.ccy!==currency).reduce((s,x)=>s+(Math.abs(r.percent-x.percent)<1e-10?.5:r.percent>x.percent?1:0),0)/7;
  const returns=rows.slice(1).map((b,i)=>{
   const a=rows[i];return FX.filter(c=>c!==currency).reduce((s,c)=>s+Math.log((b[c]/b[currency])/(a[c]/a[currency])),0)/7*100;
  });
  const mu=returns.reduce((a,b)=>a+b,0)/returns.length;
  const vol=Math.sqrt(returns.reduce((s,x)=>s+(x-mu)**2,0)/(returns.length-1))*Math.sqrt(252);
  return {currency,asof:rank.asof,from:rank.from,score,return20:r.percent,recent5:m.recent,prior5:m.prior,acceleration:m.delta,
   momentumLabel:m.label,momentumFrom:mom.from,momentumMid:mom.mid,annualizedVolatility:vol,
   source:prices.source,quality:'OFFICIAL_REFERENCE_FIXINGS',affectsFxRanking:false,eligibleForTrading:false};
 }
 function render(x,esc=s=>String(s??'')){
  if(!x)return '<details class="price-score-research" data-price-score-research-v1><summary>Price Score · ricerca · Non valutabile</summary><p>Servono 21 fixing BCE comuni, validi e recenti.</p></details>';
  const n=(v,d=2)=>v.toLocaleString('it-IT',{minimumFractionDigits:d,maximumFractionDigits:d});
  const s=v=>(v>0?'+':'')+n(v);
  return '<details class="price-score-research" data-price-score-research-v1><summary><strong>Price Score · ricerca</strong> · '+esc(x.currency)+' '+esc(n(x.score)+'/10')+'</summary>'+
   '<p>Fixing BCE comuni: '+esc(x.from+' → '+x.asof)+'. Score relativo basato sulla posizione del rendimento geometrico contro le altre sette valute; parità con punteggio medio. Non misura il rendimento atteso.</p>'+
   '<ul><li>Forza relativa 20 fixing: '+esc(s(x.return20))+'%</li><li>Ultimi 5 fixing: '+esc(s(x.recent5))+'%</li><li>5 fixing precedenti: '+esc(s(x.prior5))+'%</li>'+
   '<li>Accelerazione: '+esc(s(x.acceleration))+' pp · '+esc(x.momentumLabel)+'</li>'+
   '<li>Volatilità annualizzata indicativa da 20 variazioni log giornaliere del paniere: '+esc(n(x.annualizedVolatility))+'%</li></ul>'+
   '<p>Finestre 5/5 non sovrapposte: '+esc(x.momentumFrom+' → '+x.momentumMid+' → '+x.asof)+'. Il punteggio è ordinale, anche quando le differenze tra valute sono piccole. Prezzi di riferimento, non quotazioni eseguibili; nessun effetto sul ranking operativo.</p></details>';
 }
 const api={evaluate,render};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FXQuantPriceResearchScore=api;
})(typeof window==='undefined'?globalThis:window);
