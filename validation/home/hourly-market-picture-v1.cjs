'use strict';
/*
 * FX Quant Next — independent HOURLY MARKET PICTURE.
 * Reads dated public research inputs, not ChatGPT task deliveries.
 * Narrative is deterministic, conditional and auditable; no model API,
 * fabricated flows, unpublished actuals or claimed intraday FX response.
 */
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const SCHEMA='GMFQ_NEXT_HOURLY_MARKET_PICTURE_V1';
const finite=n=>typeof n==='number'&&Number.isFinite(n);
const day=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&!Number.isNaN(Date.parse(s+'T12:00:00Z'));
const clock=s=>typeof s==='string'&&!Number.isNaN(Date.parse(s));
const age=(a,b)=>(Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/864e5;
const numberFromTitle=s=>{const m=String(s||'').match(/[+-]\d+(?:[.,]\d+)?\s*(?:pb|bp|%|punti)/i);return m?Number(m[0].match(/[+-]\d+(?:[.,]\d+)?/)[0].replace(',','.')):null};
const digest=v=>crypto.createHash('sha256').update(JSON.stringify(v)).digest('hex');
const dmy=s=>day(s)?s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4):'data indicativa';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const dirs=['FUTURES_IMPLIED_REPRICING','OIS_REPRICING','MARKET_GOVERNMENT_RATES',
 'MARKET_FX_ECB_FIXING','MARKET_VOLATILITY_CLOSE','MARKET_EQUITY_CLOSE',
 'MARKET_CREDIT_OAS','MACRO_OFFICIAL_ACTUAL','GEOPOLITICS','GEOPOLITICAL_EVENT'];
function build({pulse,calendar,commodities,previous=null,now}){
 if(!clock(now)||pulse?.schema!== 'GMFQ_NEWS_PULSE_OPERATIONAL_V1'&&
    !String(pulse?.schema||'').startsWith('GMFQ_NEWS_PULSE')||
    !Array.isArray(pulse.items)||!day(pulse.content_as_of)){
  throw Error('Dated operational news-pulse input required');
 }
 const today=now.slice(0,10);
 if(pulse.content_as_of>today)throw Error('Future news snapshot');
 const sorted=pulse.items.filter(x=>dirs.includes(x?.category)&&day(x.as_of)&&
  x.as_of<=today&&age(x.as_of,today)>=0&&age(x.as_of,today)<=7&&
  typeof x.title==='string'&&x.title.length>0&&
  typeof x.quality==='string'&&x.quality.length>0)
  .sort((a,b)=>b.as_of.localeCompare(a.as_of)||
    (a.importance==='HIGH'?-1:1));
 if(sorted.length<4)throw Error('Insufficient cross-asset evidence');
 const pick=(category,test=()=>true)=>sorted.find(x=>x.category===category&&test(x))||null;
 const usd=pick('MARKET_GOVERNMENT_RATES',x=>x.ccy==='USD');
 const eur=pick('MARKET_GOVERNMENT_RATES',x=>x.ccy==='EUR');
 const vix=pick('MARKET_VOLATILITY_CLOSE');
 const sp=pick('MARKET_EQUITY_CLOSE',x=>/S&P/i.test(x.title));
 const nasdaq=pick('MARKET_EQUITY_CLOSE',x=>/Nasdaq/i.test(x.title));
 const hy=pick('MARKET_CREDIT_OAS',x=>/HY/i.test(x.title));
 const ig=pick('MARKET_CREDIT_OAS',x=>/IG/i.test(x.title));
 const eurusd=pick('MARKET_FX_ECB_FIXING',x=>x.pair==='EURUSD');
 const usdjpy=pick('MARKET_FX_ECB_FIXING',x=>x.pair==='USDJPY');
 const audcad=pick('MARKET_FX_ECB_FIXING',x=>x.pair==='AUDCAD');
 const macro=pick('MACRO_OFFICIAL_ACTUAL');
 const ref=(ccy)=>pick('FUTURES_IMPLIED_REPRICING',x=>x.ccy===ccy)||
  pick('OIS_REPRICING',x=>x.ccy===ccy);
 const refs=['USD','EUR','GBP','JPY','CAD','AUD','NZD','CHF'].map(ref).filter(Boolean);
 const nUsd=usd&&numberFromTitle(usd.title),nEur=eur&&numberFromTitle(eur.title);
 const ratesComparable=usd&&eur&&usd.as_of===eur.as_of&&
  finite(nUsd)&&finite(nEur);
 const rateDirection=ratesComparable?
  nUsd-nEur>5?'più a favore del dollaro':
  nUsd-nEur< -5?'meno favorevole al dollaro':'senza un cambiamento netto':null;
 let rates='';
 if(ratesComparable){
  rates='Nell’ultima rilevazione comune i rendimenti governativi USA a due anni '+
   (nUsd>0?'salgono':nUsd<0?'scendono':'restano quasi invariati')+
   ' più '+(Math.abs(nUsd)>Math.abs(nEur)?'rapidamente':'lentamente')+
   ' rispetto all’Eurozona. Il differenziale si muove '+rateDirection+
   ': è un proxy del canale monetario, distinto dalle curve OIS.';
 }else if(usd){
  rates='La variazione del Treasury a due anni indica un aggiustamento del front-end USA; '+
   'per il Forex conta confrontarlo con le altre aree e con la risposta dei cambi.';
 }else{
  rates='Il confronto fra aspettative monetarie resta uno dei driver principali del Forex, '+
   'insieme ai dati macro e alla propensione globale al rischio.';
 }
 if(refs.length){
  const r=refs.slice(0,2).map(x=>x.ccy+': '+x.title.replace(/^[A-Z]{3}:\s*/,'')).join('; ');
  rates+=' Dai riferimenti futures/OIS emerge inoltre '+r+'.';
 }
 const v=numberFromTitle(vix?.title);
 const s=numberFromTitle(sp?.title),n=numberFromTitle(nasdaq?.title);
 const h=numberFromTitle(hy?.title),i=numberFromTitle(ig?.title);
 const equityPositive=finite(s)&&s>0&&finite(n)&&n>0;
 const creditTight=finite(h)&&h<0&&finite(i)&&i<0;
 const volatilityUp=finite(v)&&v>0;
 let risk='La propensione al rischio va letta insieme su azioni, volatilità e credito.';
 if(equityPositive&&creditTight&&volatilityUp){
  risk='Le ultime chiusure azionarie e gli spread creditizi sono costruttivi, '+
   'ma il VIX è risalito in una rilevazione successiva: segnali contrastanti. '+
   'Un rally azionario, da solo, non identifica un ritorno stabile al risk-on.';
 }else if(equityPositive&&creditTight){
  risk='Azionario e credito danno segnali coerenti con una propensione al rischio migliore; '+
   'la tenuta va confrontata con la volatilità e con le valute cicliche.';
 }else if(volatilityUp){
  risk='L’aumento del VIX segnala maggior costo della protezione sulle azioni; '+
   'il comportamento del credito e dei cambi ciclici aiuta a distinguerlo da uno stress più diffuso.';
 }else if(finite(s)&&s<0||finite(n)&&n<0){
  risk='L’azionario mostra cautela. La verifica passa dal credito e dalla volatilità, '+
   'per capire se sia una rotazione o una riduzione più ampia del rischio.';
 }
 const lanes=commodities?.lanes||{};
 const commodity=(k)=>{const x=lanes[k+'.market_proxy'];return x&&
   x.status==='MARKET_PROXY_ACTIVE_SECONDARY'&&day(x.proxy_as_of)&&
   x.proxy_as_of<=today&&age(x.proxy_as_of,today)<=7&&
   finite(x.change_1d_pct)?x:null};
 const gold=commodity('GOLD'),wti=commodity('WTI'),brent=commodity('BRENT');
 let commodityText='';
 if(gold&&(wti||brent)){
  const oil=wti||brent;
  commodityText='Fra le materie prime, oro '+(gold.change_1d_pct>=0?'in rialzo':'in calo')+
   ' e petrolio '+(oil.change_1d_pct>=0?'in rialzo':'in calo')+
   ' nell’ultima rilevazione dei futures (proxy di mercato). '+
   (gold.change_1d_pct>0&&oil.change_1d_pct<0?
    'La divergenza merita attenzione: può riflettere driver diversi fra protezione, dollaro e domanda energetica, non un unico flusso dimostrato.':
    'La loro lettura richiede di distinguere domanda fisica, tassi reali e fattori finanziari.');
 }else if(gold)commodityText='L’oro resta un termometro complementare dei tassi reali e della ricerca di protezione; l’ultima lettura è '+(gold.change_1d_pct>=0?'in rialzo.':'in calo.');
 else if(wti||brent)commodityText='Il petrolio resta rilevante per l’inflazione attesa e per il CAD, ma la relazione con il cambio dipende dai tassi relativi e dal rischio globale.';
 const e=numberFromTitle(eurusd?.title),j=numberFromTitle(usdjpy?.title),a=numberFromTitle(audcad?.title);
 let fx='Il Forex va valutato in termini relativi: tassi e crescita di una valuta contro quelli della sua controparte, poi conferma del prezzo.';
 if(finite(e)&&finite(j)&&e<0&&j>0)fx=
  'Negli ultimi fixing BCE il dollaro guadagna terreno sia contro euro sia contro yen. '+
  (ratesComparable&&nUsd>nEur?'Il rafforzamento contro l’euro è compatibile con il differenziale governativo USA–Eurozona più favorevole. ':
   'Il movimento va confrontato con i tassi relativi. ')+
  'La sua ampiezza nei diversi cross dirà se il sostegno è generale oppure selettivo.';
 else if(finite(e))fx='EUR/USD '+(e>=0?'recupera':'cede')+
  ' negli ultimi fixing BCE. Il driver da discriminare è quanto dipenda da variazioni dei tassi USA, da forza europea o da cambiamenti nella propensione al rischio.';
 if(finite(a)&&Math.abs(a)>=0.2)fx+=' AUD/CAD '+(a<0?'indica una relativa debolezza dell’AUD rispetto al CAD.':
  'indica un recupero relativo dell’AUD rispetto al CAD.');
 // Calendar entries remain scheduled context, not proof of an actual release.
 const scheduled=calendar?.schema==='GMFQ_CALENDAR_OPERATIONAL_VIEW_V3'&&
  Array.isArray(calendar.events)?calendar.events.filter(x=>x?.importance==='HIGH'&&
   x.status==='UPCOMING'&&day(x.date)&&x.date>=today&&
   x.quality?.startsWith('OFFICIAL')&&
   ['INFLATION','GROWTH','LABOUR','CENTRAL_BANK_DECISION'].includes(x.event_type))
   .sort((a,b)=>a.date.localeCompare(b.date)):[],event=scheduled[0];
 let catalyst='Il prossimo passaggio è vedere se le nuove informazioni macro spostano '+
  'le attese sui tassi e se valute e credito reagiscono in modo coerente.';
 if(event){
  const when=event.date===today?'Nel calendario della seduta':'Tra i prossimi eventi';
  catalyst=when+' figura '+event.title+' ('+event.ccy+', '+dmy(event.date)+'). '+
   (event.event_type==='INFLATION'?
    'Una sorpresa sui prezzi può modificare il pricing monetario relativo, ma la composizione conta quanto il numero principale.':
    event.event_type==='LABOUR'?
    'La direzione di occupazione e salari può spostare le aspettative sulla banca centrale, soprattutto se diverge dal trend.':
    event.event_type==='GROWTH'?
    'La novità sarà capire se il ciclo accelera o perde velocità rispetto alle attese.':
    'La differenza tra comunicazione e tassi già incorporati dal mercato guida la reazione FX.')+
   ' È un catalizzatore da interpretare rispetto alle attese, non un esito già osservato.';
 }
 const geopolitical=sorted.filter(x=>/GEOPOLIT/.test(x.category)).slice(0,2);
 const geo=geopolitical.length?' La componente geopolitica include '+geopolitical.map(x=>x.title).join('; ')+'.':'';
 const title=ratesComparable&&nUsd>nEur&&finite(e)&&e<0?
  'Dollaro sostenuto dai tassi relativi, mentre il rischio globale resta disomogeneo':
  equityPositive&&creditTight&&volatilityUp?
  'Azioni e credito recuperano, ma il mercato resta sensibile al rischio':
  'Mercati fra aspettative monetarie, rischio globale e conferme valutarie';
 const lead=ratesComparable&&finite(e)&&e<0?
  'Il filo conduttore è il confronto tra tassi USA ed europei: i rendimenti brevi si muovono in modo favorevole al dollaro e EUR/USD segue. '+
  'Il quadro azionario e la volatilità, invece, non raccontano ancora la stessa storia.':
  'La seduta si legge attraverso tre forze collegate: aspettative sui tassi, qualità della propensione al rischio e risposta relativa delle valute. '+(macro?
  'L’ultimo dato macro pubblicato entra nel contesto, non sostituisce la verifica dei prezzi.':'');
 const sources={news:pulse.content_as_of,calendar:calendar?.last_checked_at_utc?.slice(0,10)||null,
  commodities:gold?.proxy_as_of||wti?.proxy_as_of||brent?.proxy_as_of||null,
  equity:sp?.as_of||nasdaq?.as_of||null,risk:vix?.as_of||null,
  credit:hy?.as_of||null,fx:eurusd?.as_of||null};
 const evidence=sorted.map(x=>({category:x.category,as_of:x.as_of,title:x.title,quality:x.quality,
  source:x.source||null})).concat([gold,wti,brent].filter(Boolean).map(x=>({category:'COMMODITY_PROXY',
  as_of:x.proxy_as_of,title:x.source||'Futures secondary source',quality:x.status})));
 const material=digest({evidence,scheduled:scheduled.slice(0,4),sourceDates:sources});
 const stable=previous?.schema===SCHEMA&&previous.material_digest===material;
 const report={
  schema:SCHEMA,status:stable?'UNCHANGED':'ACTIVE',
  generated_at_utc:now,material_digest:material,
  last_material_change_utc:stable&&clock(previous.last_material_change_utc)?
   previous.last_material_change_utc:now,
  content_as_of:pulse.content_as_of,
  headline:title,lead,
  market_context:rates+' '+risk+(commodityText?' '+commodityText:'')+geo,
  fx_interpretation:fx,
  catalyst,monitor:'Osservare il prossimo confronto macro con le attese, '+
   'il front-end monetario relativo, i cross FX e il rapporto fra volatilità e credito. '+
   'Una divergenza cambia la forza della tesi, non genera automaticamente un trade.',
  source_dates:sources,detail:evidence.slice(0,25),
  coverage:{fx:Boolean(eurusd||usdjpy),rates:Boolean(usd||eur||refs.length),
   equity:Boolean(sp||nasdaq),volatility:Boolean(vix),credit:Boolean(hy||ig),
   commodities:Boolean(gold||wti||brent),macro:Boolean(macro||event),
   geopolitics:geopolitical.length>0},
  governance:{narrative:'RULE_BASED_INTERPRETATION_NOT_HUMAN_REVIEWED',
   chatgpt_alerts_modified:false,intraday_reaction_claimed:false,
   commodities:'SECONDARY_DATED_FUTURES_PROXY',user_facing_trade_signal:false}
 };
 return report;
}
function main(argv=process.argv.slice(2)){
 const arg=k=>{const i=argv.indexOf('--'+k);return i>=0?argv[i+1]:null};
 const root=path.resolve(arg('root')||'.');
 const out=arg('output');if(!out)throw Error('--output required');
 const prior=arg('previous');
 const readOptional=p=>{try{return read(p)}catch(e){if(e.code==='ENOENT')return null;throw e}};
 const n=arg('now')||new Date().toISOString();
 const report=build({
  pulse:read(path.join(root,'live_data/sections/NEWS_PULSE_OPERATIONAL.json')),
  calendar:readOptional(path.join(root,'live_data/sections/CALENDAR_OPERATIONAL_VIEW.json')),
  commodities:readOptional(path.join(root,'live_data/sections/ESTIMATED_RESIDUAL_GAPS.json')),
  previous:prior?readOptional(path.resolve(prior)):null,now:n
 });
 fs.mkdirSync(path.dirname(path.resolve(out)),{recursive:true});
 fs.writeFileSync(path.resolve(out),JSON.stringify(report,null,2)+'\n','utf8');
 console.log('NEXT_HOURLY_MARKET_PICTURE',JSON.stringify({
  status:report.status,asof:report.content_as_of,digest:report.material_digest,
  coverage:report.coverage,chatgpt_alerts_modified:false}));
}
if(require.main===module)main();
module.exports={SCHEMA,build,main,numberFromTitle};
