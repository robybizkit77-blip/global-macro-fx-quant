'use strict';
/* FX Quant Next — Macro Strength estimated desk V1, not a certified trading
 * model. This is a NEW CURRENT heuristic, not a regenerated historical D.json.
 *
 * Fixed score design (unitless [-1,+1], illustrative, not fitted):
 *   50% domestic economic momentum  (0.45 GDP acceleration +
 *                                    0.20 GDP positive/negative level +
 *                                    0.35 change in unemployment)
 *   30% near-term policy repricing   (official same-instrument 6M weekly move;
 *                                    fallback: 0.5x qualified govt 2Y move)
 *   20% relative FX price            (20 matched ECB sessions, basket rank).
 * Missing factors contribute zero but are NEVER called observed zero:
 * they reduce coverage and are exposed in narrative/metadata.
 * No inflation-to-FX sign: inflation pressure is displayed separately.
 * No cross-country GDP-level comparison, probabilities or fitted parameters.
 */
(function(root){
 const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
 const SCHEMA='GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1';
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&!Number.isNaN(Date.parse(x+'T12:00:00Z'));
 const days=(a,b)=>day(a)&&day(b)?Math.round((Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/864e5):null;
 const within=(a,b,max)=>{const n=days(a,b);return n!==null&&n>=0&&n<=max};
 const month=x=>typeof x==='string'&&/^\d{4}-(?:0[1-9]|1[0-2])(?:-\d{2})?$/.test(x);
 const quarter=x=>typeof x==='string'&&/^\d{4}Q[1-4]$/.test(x);
 const qnum=x=>quarter(x)?Number(x.slice(0,4))*4+Number(x.slice(-1)):NaN;
 const qend=x=>quarter(x)?x.slice(0,4)+'-'+String(Number(x.slice(-1))*3).padStart(2,'0'):null;
 const clamp=x=>Math.max(-1,Math.min(1,x));
 const signed=x=>x>0?1:x<0?-1:0;
 const scoreBand=x=>x>=0.25?'favorevole':x<=-0.25?'sfavorevole':'misto';
 const fails=reason=>({status:'STIMA_SOSPESA',reason,currencies:[],pairs:[],asof:null,coverage:null,
  methodology:'Pesi euristici fissi, non regressione né backtest validato'});
 function sourceOK(doc,price,now){
  if(!doc||doc.schema!==SCHEMA||doc.status!=='OBSERVED_ECONOMIC_CONTEXT_NOT_FX_SIGNAL'||
    doc.safe_to_recompute_structural_pair_theses!==false||doc.safe_to_republish_D!==false||
    doc.historic_PIT_OOS_not_certified!==true||
    doc.eligible_for_trading_or_forward_backtest!==false||
    doc.summary?.currencies!==8||doc.summary?.pairs!==28||
    !within(doc.generated_europe_rome_day,now,7)||
    !within(doc.fx_price_as_of,now,5)||
    doc.fx_price_as_of!==price?.last_as_of||
    price?.source!=='ECB euro foreign exchange reference rates'||
    !Array.isArray(price.rows)||!FX.every(c=>doc.countries?.[c]?.FX_strength===null&&
      doc.countries?.[c]?.macro_score===null&&
      doc.countries?.[c]?.not_a_trade_or_policy_signal===true))
    return false;
  const expected=new Set();
  for(let i=0;i<FX.length;i++)for(let j=i+1;j<FX.length;j++)
   expected.add([FX[i],FX[j]].sort().join('/'));
  return Object.keys(doc.pair_context||{}).length===28&&
    [...expected].every(k=>{
      const p=doc.pair_context[k];
      return p?.base===k.slice(0,3)&&p?.quote===k.slice(4)&&
       p.recalculated_structural_thesis===false&&p.pair_trade_bias===null;
    });
 }
 function inputCountry(v,now){
  if(!v||!v.growth||!v.labour||!v.inflation)return null;
  const g=v.growth,l=v.labour,i=v.inflation;
  if(!quarter(g.reference_quarter)||qend(g.reference_quarter)>now.slice(0,7)||
     !day(g.publisher_release_day)||g.publisher_release_day>now||
     !finite(g.nonannualized_qoq_descriptive_pct)||
     g.is_growth_strength_score!==false)return null;
  for(const a of [l,i]){
   if(!finite(a.observation_value)||!finite(a.change_over_three_observation_intervals_pp)||
      !['UP','DOWN','FLAT'].includes(a.change_direction)||
      !(month(a.observation_period)||quarter(a.observation_period))||
      (quarter(a.observation_period)?qend(a.observation_period):a.observation_period.slice(0,7))>now.slice(0,7)||
      a.observed_history_revised_not_historic_PIT!==true||
      a.observation_period_is_not_release_instant!==true)return null;
  }
  let gTrend=null;
  const p=g.prior_documented_quarter;
  if(p&&quarter(p.reference_quarter)&&qnum(g.reference_quarter)-qnum(p.reference_quarter)===1&&
     day(p.publisher_release_day)&&p.publisher_release_day<=now&&
     finite(p.nonannualized_qoq_descriptive_pct)&&
     g.later_revisions_not_identical_to_first_release===true){
    const d=g.nonannualized_qoq_descriptive_pct-p.nonannualized_qoq_descriptive_pct;
    gTrend=d>0.1?1:d< -0.1?-1:0;
  }
  const gLevel=g.nonannualized_qoq_descriptive_pct>0.2?1:
    g.nonannualized_qoq_descriptive_pct< -0.2?-1:0;
  const unemployment=l.change_over_three_observation_intervals_pp;
  const labour=unemployment>=0.1?-1:unemployment<=-0.1?1:0;
  const econ=0.45*(gTrend===null?0:gTrend)+0.20*gLevel+0.35*labour;
  return {econ,labour,gLevel,gTrend,gdp:g.reference_quarter,gdpRelease:g.publisher_release_day,
   unemploymentPeriod:l.observation_period,unemploymentChange:unemployment,
   inflationPeriod:i.observation_period,inflationChange:i.change_over_three_observation_intervals_pp,
   inflationDirection:i.change_direction,
   evidence:['GDP level (non-comparable across countries)','Labour change (3 observation intervals)']
    .concat(gTrend===null?[]:['GDP within-country acceleration']),
   missing:gTrend===null?['GDP acceleration not certified from adjacent quarters']:[],
   domesticVintages:'Serie correnti riviste; non storico di prima pubblicazione.'};
 }
 function repricing(ccy,ois,rates,now){
  const o=ois?.currencies?.[ccy],h=o?.horizons?.['6m'];
  if(o?.quality==='FONTE UFFICIALE'&&['OIS','FUTURES'].includes(o.kind)&&
     day(h?.as_of)&&day(o?.as_of)&&h.as_of===o.as_of&&within(h.as_of,now,7)&&
     finite(h.change_1w_bp)){
    const bp=h.change_1w_bp, direction=bp>=5?1:bp<=-5?-1:0;
    return {score:direction,kind:o.kind,asof:h.as_of,changeBp:bp,quality:'UFFICIALE',
      description:'Variazione settimanale di strumento '+o.kind+' 6M; non livello OIS cross-country'};
  }
  const r=rates?.[ccy],w=r?.weekly2_validation;
  if(finite(r?.['2Y'])&&finite(w?.change_bp)&&day(r.date)&&
     w.end_date===r.date&&day(w.start_date)&&w.start_date<w.end_date&&
     within(r.date,now,7)){
    const bp=w.change_bp,direction=bp>=5?1:bp<=-5?-1:0;
    return {score:0.5*direction,kind:'GOV_2Y_PROXY',asof:r.date,changeBp:bp,
      quality:'PROXY',description:'Movimento del rendimento governativo 2Y: NON è repricing OIS'};
  }
  return {score:0,kind:'MANCANTE',asof:null,changeBp:null,quality:'ASSENTE',
    description:'Variazione 6M ufficiale e 2Y comparabile non disponibili: contributo omesso'};
 }
 function evaluate({observed,prices,ois,rates,now,rankingFn}){
  if(!day(now)||!sourceOK(observed,prices,now))return fails('Fotografia economica o fixing non aggiornati, incoerenti o non verificabili.');
  const rank=typeof rankingFn==='function'?rankingFn(prices,now,FX):null;
  if(!rank||rank.asof!==prices.last_as_of||rank.items?.length!==8)
   return fails('Mancano venti fixing BCE comuni per la componente prezzo.');
  const ordered=[...rank.items];
  const map=new Map(ordered.map((r,n)=>[r.ccy,{...r,rank:n+1,score:(7-2*n)/7}]));
  const currencies=[];
  for(const ccy of FX){
   const raw=inputCountry(observed.countries[ccy],now);
   if(!raw)return fails('Osservazioni macro non verificabili per '+ccy+'.');
   const rate=repricing(ccy,ois,rates,now),price=map.get(ccy);
   if(!price||!finite(price.percent))return fails('Prezzo BCE non valido per '+ccy+'.');
   const score=clamp(0.5*raw.econ+0.3*rate.score+0.2*price.score);
   currencies.push({ccy,score,rank:0,macroScore:raw.econ,policyScore:rate.score,
     priceScore:price.score,pricePercent:price.percent,priceRank:price.rank,
     growthTrend:raw.gTrend,labourDirection:raw.labour,inflationDirection:raw.inflationDirection,
     gdpPeriod:raw.gdp,labourPeriod:raw.unemploymentPeriod,
     inflationPeriod:raw.inflationPeriod,rate,macro:raw,
     coverage:(raw.gTrend!==null?1:0)+1+(rate.quality==='UFFICIALE'?1:0)+1,
     partial:raw.gTrend===null||rate.quality!=='UFFICIALE',
     notes:raw.missing.concat(rate.quality!=='UFFICIALE'?[rate.description]:[])});
  }
  currencies.sort((a,b)=>b.score-a.score||a.ccy.localeCompare(b.ccy));
  currencies.forEach((x,i)=>{x.rank=i+1;x.label=scoreBand(x.score)});
  const by=Object.fromEntries(currencies.map(x=>[x.ccy,x]));
  const row=prices.rows.find(x=>x.Date===rank.asof);
  const first=prices.rows.find(x=>x.Date===rank.from);
  if(!row||!first)return fails('Punti di prezzo necessari al confronto assenti.');
  const pairs=[];
  for(let i=0;i<FX.length;i++)for(let j=i+1;j<FX.length;j++){
   const a=FX[i],b=FX[j],base=by[a],quote=by[b];
   const key=a+b,delta=base.score-quote.score;
   const favored=Math.abs(delta)>=0.22?(delta>0?a:b):null;
   const baseMove=100*((row[b]/row[a])/(first[b]/first[a])-1);
   if(!finite(baseMove))return fails('Confronto FX non finito '+key);
   const priceSide=Math.abs(baseMove)>=0.15?(baseMove>0?a:b):null;
   const aligned=Boolean(favored&&priceSide===favored);
   const opposite=Boolean(favored&&priceSide&&priceSide!==favored);
   const core=base.macroScore-quote.macroScore;
   const rateGap=base.policyScore-quote.policyScore;
   const tier=!favored?4:opposite?3:aligned?1:2;
   const stage=!favored?'Vantaggio stimato non distinto':opposite?'Prezzo contrario alla stima':
    aligned?'Allineamento da verificare':'Prezzo non conferma ancora';
   const story=!favored?
    'Momentum economico, contributo tassi e prezzo non separano abbastanza '+a+' da '+b+'.':
    'La stima relativa favorisce '+favored+'; '+(core>0?'macro più favorevole per '+a:
      core<0?'macro più favorevole per '+b:'macro non discriminante')+
    ', '+(rateGap===0?'pricing senza divergenza netta verificabile':'pricing da leggere per strumenti e date')+
    '. '+(opposite?'Il prezzo si è mosso in senso opposto.':aligned?
      'Il prezzo ha seguito la direzione stimata, senza provarne la causa.':'Manca conferma di prezzo.');
   pairs.push({key,name:a+'/'+b,base:a,quote:b,favored,bias:favored?(favored===a?'LONG':'SHORT'):'NESSUNO',
     tier,stage,story,missing:'Verificare sorprese macro relative, pricing comparabile e reazione del prezzo prima di valutare un ingresso.',
     priceText:'20 fixing BCE · '+(baseMove>0?'+':'')+baseMove.toFixed(2)+'% '+a+'/'+b,
     pricePercent:baseMove,priceSide,aligned,opposite,scoreGap:delta,macroGap:core,
     policyGap:rateGap,quality:'STIMA '+(base.partial||quote.partial?'PARZIALE':'COMPLETA'),
     risk:base.partial||quote.partial,valid:false,source:'STIMA_ESPLICITA_V1'});
  }
  pairs.sort((a,b)=>a.tier-b.tier||Math.abs(b.scoreGap)-Math.abs(a.scoreGap)||a.key.localeCompare(b.key));
  return {status:'STIMA_OPERATIVA_NON_VALIDATA',schema:'GMFQ_MACRO_STRENGTH_ESTIMATED_V1',
   asof:observed.generated_europe_rome_day,priceAsOf:rank.asof,priceFrom:rank.from,
   legacyMacroAsOf:observed.canonical_D_macro_baseline_as_of,
   currencies,pairs,by,ranking:rank,coverage:{currencies:8,pairs:28,
    withGDPAcceleration:currencies.filter(x=>x.growthTrend!==null).length,
    official6M:currencies.filter(x=>x.rate.quality==='UFFICIALE').length},
   method:{economic:0.5,policy:0.3,price:0.2,gdpAcceleration:0.45,gdpLevel:0.2,labour:0.35,
    fixedHeuristic:true,validatedOutOfSample:false,entrySignals:false},
   warning:'Stima interpretativa, non backtest né vantaggio statistico. Serie macro riviste, crescita non comparabile per livelli, strumenti OIS/Futures/2Y non omogenei. Ranking e bias stimati non sono segnali di ingresso.'};
 }
 const api={evaluate,sourceOK,inputCountry,repricing};
 root.FXQuantMacroEstimated=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
