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
    !within(price?.last_as_of,now,5)||
    !within(doc.fx_price_as_of,price?.last_as_of,3)||
    price?.source!=='ECB euro foreign exchange reference rates'||
    !Array.isArray(price.rows)||!FX.every(c=>doc.countries?.[c]?.FX_strength===null&&
      doc.countries?.[c]?.macro_score===null&&
      doc.countries?.[c]?.not_a_trade_or_policy_signal===true))
    return false;
  // V3 keeps canonical pair ORIENTATION (USD/JPY, not JPY/USD).
  // Validate the complete unordered set but never reverse its trading code.
  const keys=Object.keys(doc.pair_context||{});
  const seen=new Set();
  return keys.length===28&&keys.every(k=>{
    const p=doc.pair_context[k],a=k.slice(0,3),b=k.slice(4);
    const unordered=[a,b].sort().join('/');
    if(!/^[A-Z]{3}\/[A-Z]{3}$/.test(k)||a===b||
       !FX.includes(a)||!FX.includes(b)||seen.has(unordered)||
       p?.base!==a||p?.quote!==b||
       p.recalculated_structural_thesis!==false||p.pair_trade_bias!==null)return false;
    seen.add(unordered);return true;
  })&&seen.size===28;
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
  // Directional NZ rates proxy is an official ASX bank-bill future, not OIS.
  // Its weekly move is for the SAME listed contract; it may guide only the
  // economic-lens direction at a discounted weight, never the policy level.
  if(ccy==='NZD'&&o?.quality==='PROXY DIREZIONALE'&&
     o?.kind==='PROXY FUTURES'&&day(h?.as_of)&&within(h.as_of,now,7)&&
     finite(h.change_1w_bp)){
    const bp=h.change_1w_bp, direction=bp>=5?1:bp<=-5?-1:0;
    return {score:0.35*direction,kind:'BANK_BILL_6M_DIRECTIONAL_PROXY',
     asof:h.as_of,changeBp:bp,quality:'PROXY',
     description:'ASX NZ bank-bill 6M: variazione settimanale di futures, proxy direzionale scontato; non OIS né stima del percorso OCR'};
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
 // An economic thesis is NOT a price trend. Only the daily-timing lens uses price.
 // Categorical research rules are heuristic, not fitted, predictive or tradable.
 function assessThesisTrade({favored,base,quote,macroGap,policyGap,aligned,opposite,move5}){
  const direction=favored===base?.ccy?1:favored===quote?.ccy?-1:0;
  const relativeMacro=macroGap*direction;
  const relativePolicy=policyGap*direction;
  const rateReady=base?.rate?.quality!=='ASSENTE'&&quote?.rate?.quality!=='ASSENTE'&&
    Boolean(base?.rate?.quality&&quote?.rate?.quality);
  const macroState=!direction?'NON DISTINTA':relativeMacro>=0.12?'FAVOREVOLE':
    relativeMacro<=-0.12?'CONTRARIA':'NON DECISIVA';
  const policyState=!direction?'NON DISTINTA':!rateReady?'ASSENTE':
    relativePolicy>=0.10?'FAVOREVOLE':relativePolicy<=-0.10?'CONTRARIA':'NON DECISIVA';
  const bothSupported=macroState==='FAVOREVOLE'&&policyState==='FAVOREVOLE';
  const anyAgainst=macroState==='CONTRARIA'||policyState==='CONTRARIA';
  const anySupport=macroState==='FAVOREVOLE'||policyState==='FAVOREVOLE';
  const complete=bothSupported&&!base.partial&&!quote.partial&&
    base.rate.quality==='UFFICIALE'&&quote.rate.quality==='UFFICIALE';
  const thesisStrength=!direction?'NON DISTINTA':anyAgainst?'CONTRASTATA':
    complete?'COERENTE':anySupport?'PARZIALE':'NON DISTINTA';
  const relative5=move5*direction;
  const fiveState=!direction||!finite(move5)||Math.abs(move5)<0.05?'INDECISO':
    relative5>0?'COERENTE':'CONTRARIO';
  const tradeAttractiveness=!direction||thesisStrength==='NON DISTINTA'?'NON VALUTABILE':
    thesisStrength==='CONTRASTATA'?'NON SUPPORTATA':
    opposite||fiveState==='CONTRARIO'?'BASSA ORA':
    aligned&&fiveState==='COERENTE'?'DA VALIDARE':'IN ATTESA';
  const macroText=macroState==='FAVOREVOLE'?'il momentum economico sostiene la direzione':
    macroState==='CONTRARIA'?'il momentum economico è contrario':
    'il momentum economico non distingue le due valute';
  const rateText=policyState==='ASSENTE'?'il confronto delle variazioni monetarie è incompleto':
    policyState==='FAVOREVOLE'?'le variazioni dei riferimenti monetari sostengono la direzione':
    policyState==='CONTRARIA'?'le variazioni monetarie sono contrarie':
    'le variazioni monetarie non aggiungono una direzione netta';
  const sourceNote=base?.partial||quote?.partial?
    ' Copertura parziale: dati macro mancanti o tassi governativi usati come proxy.':'';
  const thesisReason=direction?macroText+'; '+rateText+'.'+sourceNote:
    'Macro e variazioni monetarie non mostrano un vantaggio fondamentale sufficientemente distinto.';
  const tradeReason=tradeAttractiveness==='NON VALUTABILE'?
    'Non emerge una direzione fondamentale da valutare come possibile trade.':
    tradeAttractiveness==='NON SUPPORTATA'?
    'Una delle componenti fondamentali contraddice la direzione stimata: il prezzo non basta a risolvere il conflitto.':
    tradeAttractiveness==='BASSA ORA'?
    'Il prezzo su 20 oppure sulle ultime 5 sedute BCE è contrario alla tesi: il timing daily è sfavorevole.':
    tradeAttractiveness==='DA VALIDARE'?
    'I movimenti su 5 e 20 fixing BCE sono coerenti, ma mancano trigger, struttura H4 e rischio/rendimento verificati.':
    'La coerenza del prezzo daily non è ancora uniforme: monitorare, senza anticipare un ingresso.';
  return {thesisStrength,tradeAttractiveness,macroState,policyState,fiveState,
    thesisReason,tradeReason,rateReady,entryValidated:false,thesisValidatedOOS:false};
 }

 function evaluate({observed,prices,ois,rates,model,now,rankingFn}){
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
  const common=prices.rows.filter(r=>day(r?.Date)&&r.Date<=now&&
   FX.every(c=>finite(r[c])&&r[c]>0)).sort((a,b)=>a.Date.localeCompare(b.Date));
  const fifth=common.at(-6);
  if(!row||!first||!fifth||common.at(-1)?.Date!==rank.asof)
   return fails('Punti di prezzo a 5/20 fixing necessari al confronto assenti.');
  const keys=Object.keys(model?.pairs||{}).sort();
  if(keys.length!==28||new Set(keys).size!==28||
    !keys.every(k=>/^[A-Z]{6}$/.test(k)&&by[k.slice(0,3)]&&by[k.slice(3)]&&k.slice(0,3)!==k.slice(3)))
   return fails('Catalogo canonico 28 coppie assente; nessun ranking stimato pubblicabile.');
  const pairs=[];
  for(const key of keys){
   const a=key.slice(0,3),b=key.slice(3),base=by[a],quote=by[b];
   const delta=base.score-quote.score; // Mixed currency ranking, includes price; audit only.
   const core=base.macroScore-quote.macroScore;
   const ratesUsable=base.rate.quality!=='ASSENTE'&&quote.rate.quality!=='ASSENTE';
   const rateGap=ratesUsable?base.policyScore-quote.policyScore:0;
   // The pair's favored side is formed without price: economic momentum + 
   // within-instrument weekly rate changes. No 20-day price circularity.
   const thesisGap=0.5*core+0.3*rateGap;
   const favored=Math.abs(thesisGap)>=0.22?(thesisGap>0?a:b):null;
   const baseMove=100*((row[b]/row[a])/(first[b]/first[a])-1);
   const move5=100*((row[b]/row[a])/(fifth[b]/fifth[a])-1);
   if(!finite(baseMove)||!finite(move5))return fails('Confronto FX non finito '+key);
   const priceSide=Math.abs(baseMove)>=0.15?(baseMove>0?a:b):null;
   const aligned=Boolean(favored&&priceSide===favored);
   const opposite=Boolean(favored&&priceSide&&priceSide!==favored);
   const assessment=assessThesisTrade({
    favored,base,quote,macroGap:core,policyGap:rateGap,aligned,opposite,move5
   });
   let tier=!favored?4:opposite?3:aligned?1:2;
   let stage=!favored?'Vantaggio fondamentale non distinto':opposite?'Prezzo contrario alla tesi':
    aligned?'Allineamento da verificare':'Prezzo non conferma ancora';
   if(assessment.thesisStrength==='NON DISTINTA'){tier=4;stage='Tesi fondamentale non distinta';}
   else if(assessment.thesisStrength==='CONTRASTATA'){tier=Math.max(tier,3);stage='Tesi fondamentale contrastata';}
   else if(assessment.tradeAttractiveness==='BASSA ORA'){
    tier=Math.max(tier,3);stage='Timing daily sfavorevole';
   }
   const story=!favored?
    'Momentum economico, contributo tassi e prezzo non separano abbastanza '+a+' da '+b+'.':
    'La stima relativa favorisce '+favored+'; '+(core>0?'macro più favorevole per '+a:
      core<0?'macro più favorevole per '+b:'macro non discriminante')+
    ', '+(rateGap===0?'pricing senza divergenza netta verificabile':'pricing da leggere per strumenti e date')+
    '. '+(opposite?'Il prezzo si è mosso in senso opposto.':aligned?
      'Il prezzo ha seguito la direzione stimata, senza provarne la causa.':'Il prezzo è in fase di assestamento rispetto alla tesi.');
   pairs.push({key,name:a+'/'+b,base:a,quote:b,favored,bias:favored?(favored===a?'LONG':'SHORT'):'NESSUNO',
     tier,stage,story,missing:'Verificare sorprese macro relative, pricing comparabile e reazione del prezzo prima di valutare un ingresso.',
     priceText:'20 fixing BCE · '+(baseMove>0?'+':'')+baseMove.toFixed(2)+'% '+a+'/'+b,
     pricePercent:baseMove,move5Percent:move5,priceSide,aligned,opposite,scoreGap:delta,
     thesisGap,macroGap:core,policyGap:rateGap,...assessment,
     quality:'STIMA '+(base.partial||quote.partial?'PARZIALE':'COMPLETA'),
     risk:base.partial||quote.partial,valid:false,source:'STIMA_ESPLICITA_V1'});
  }
  pairs.sort((a,b)=>a.tier-b.tier||Math.abs(b.thesisGap)-Math.abs(a.thesisGap)||a.key.localeCompare(b.key));
  return {status:'STIMA_OPERATIVA_NON_VALIDATA',schema:'GMFQ_MACRO_STRENGTH_ESTIMATED_V1',
   asof:observed.generated_europe_rome_day,priceAsOf:rank.asof,priceFrom:rank.from,
   legacyMacroAsOf:observed.canonical_D_macro_baseline_as_of,
   currencies,pairs,by,ranking:rank,coverage:{currencies:8,pairs:28,
    withGDPAcceleration:currencies.filter(x=>x.growthTrend!==null).length,
    official6M:currencies.filter(x=>x.rate.quality==='UFFICIALE').length},
   method:{economic:0.5,policy:0.3,price:0.2,gdpAcceleration:0.45,gdpLevel:0.2,labour:0.35,
    fixedHeuristic:true,validatedOutOfSample:false,entrySignals:false},
   warning:'Stima interpretativa, non backtest né vantaggio statistico. La direzione della tesi FX usa macro e variazioni monetarie, non il prezzo. Il fixing BCE a 5/20 sedute riguarda solo il timing osservato. Serie macro riviste e tassi OIS/Futures/2Y non omogenei. Nessun trade è validato senza trigger, livelli e rischio/rendimento.'};
 }
 const api={evaluate,sourceOK,inputCountry,repricing,assessThesisTrade};
 root.FXQuantMacroEstimated=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
