'use strict';
/*
 * G8 Country Strength Board — evidence map, NOT a synthetic trading score.
 * Uses the existing canonical 20-common-ECB-fixing PRICE ranking.
 * Macro, weekly sovereign 2Y moves and official 6M expectation changes
 * remain separate, with source periods and completeness explicit.
 * Never infer policy repricing from a 2Y level, carry, COT extremes or CPI alone.
 */
(function(root){
 const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
 const num=x=>typeof x==='number'&&Number.isFinite(x);
 const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 const period=x=>typeof x==='string'&&/^\d{4}-\d{2}(?:-\d{2})?$/.test(x);
 const age=(d,now)=>day(d)&&day(now)?(Date.parse(now+'T00:00:00Z')-Date.parse(d+'T00:00:00Z'))/864e5:null;
 const goodAge=(d,now,max)=>{const n=age(d,now);return n!==null&&n>=0&&n<=max;};
 const validPeriod=(d,now)=>{if(!period(d)||!day(now))return false;
  const [y,m]=d.slice(0,7).split('-').map(Number),[ny,nm]=now.slice(0,7).split('-').map(Number);
  const months=(ny-y)*12+(nm-m);return m>=1&&m<=12&&months>=0&&months<=4;};
 const dir=x=>x==='SALE'?'sale':x==='SCENDE'?'scende':x==='STABILE'?'stabile':'non verificata';
 const signed=(x,n=1,unit='')=>!num(x)?'—':(x>0?'+':x<0?'−':'')+Math.abs(x).toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n})+unit;
 function macroAxis(m,now){
  const i=m?.inflation,l=m?.labour;
  const inflOK=num(i?.latest_value)&&validPeriod(i.as_of,now)&&
   ['SALE','SCENDE','STABILE'].includes(i.direction);
  const labourOK=num(l?.latest_value)&&validPeriod(l.as_of,now)&&
   ['SALE','SCENDE','STABILE'].includes(l.direction);
  const text=(labourOK?'Disoccupazione '+dir(l.direction)+' ('+l.as_of+')':'Lavoro non verificato')+
   ' · '+(inflOK?'Inflazione '+dir(i.direction)+' ('+i.as_of+')':'inflazione non verificata');
  // No positive "macro currency score": inflation up may signal demand,
  // supply constraints, weaker real income or hawkish repricing.
  return {ok:inflOK&&labourOK,label:labourOK?'Disocc. '+(l.direction==='SALE'?'↑':l.direction==='SCENDE'?'↓':'→'):'Non verificato',
   text,inflationDirection:inflOK?i.direction:null,labourDirection:labourOK?l.direction:null,
   inflationPeriod:inflOK?i.as_of:null,labourPeriod:labourOK?l.as_of:null};
 }
 function ratesAxis(r,now){
  const w=r?.weekly2_validation;
  const ok=num(r?.['2Y'])&&num(w?.change_bp)&&goodAge(r.date,now,7)&&
   w.end_date===r.date&&day(w.start_date)&&w.start_date<w.end_date&&
   typeof w.source==='string'&&w.source.length>8;
  if(!ok)return {ok:false,label:'Non allineati',text:'Manca una variazione 2Y settimanale recente su base omogenea; un vecchio livello non dimostra sostegno monetario.',asof:null,change:null};
  const bp=w.change_bp;
  return {ok:true,label:signed(bp,1,' pb'),change:bp,asof:r.date,
   text:'Rendimento governativo 2Y '+signed(bp,1,' punti base')+
    ' sul confronto storico '+w.start_date+' → '+w.end_date+
    '. Non è un OIS né una prova di repricing della banca centrale.'};
 }
 function pricingAxis(o,now){
  const six=o?.horizons?.['6m'];
  const ok=o?.quality==='FONTE UFFICIALE'&&['OIS','FUTURES'].includes(o?.kind)&&
   num(six?.rate)&&num(six?.change_1w_bp)&&goodAge(six.as_of,now,7)&&
   six.as_of===o.as_of;
  if(!ok)return {ok:false,label:'Non verificato',change:null,asof:null,
   text:'Variazione 6M settimanale non certificata su fonte utilizzabile. Livello o proxy non bastano per attribuire un cambio nelle aspettative.'};
  const v=six.change_1w_bp;
  return {ok:true,label:signed(v,1,' pb'),change:v,asof:six.as_of,
   text:'Riferimento '+o.kind+' a 6 mesi: variazione settimanale '+
   signed(v,1,' punti base')+' al '+six.as_of+' ('+o.source+
   '). Misura dello strumento indicato, non una probabilità di decisione.'};
 }
 function priceAxis(p){
  if(!p||!num(p.percent))return {ok:false,label:'Non verificato',change:null,position:null,
   text:'Mancano 21 fixing BCE comuni per una classifica relativa confrontabile.'};
  return {ok:true,label:signed(p.percent,2,'%'),change:p.percent,position:p.position,
   text:'Media geometrica del movimento FX contro le altre sette valute su 20 fixing BCE comuni.'};
 }
 function reading(x){
  const p=x.price,pr=x.pricing,ra=x.rates,m=x.macro;
  const macroNote=!m.ok?
   'Il quadro macro è incompleto: non deduciamo una direzione del ciclo.':
   m.labourDirection==='SALE'&&m.inflationDirection==='SALE'?
    'Disoccupazione e inflazione salgono insieme: possibile tensione fra crescita e vincolo sui prezzi, non una valuta automaticamente debole o forte.':
   m.labourDirection==='SCENDE'&&m.inflationDirection==='SALE'?
    'Disoccupazione in calo e inflazione in salita: resilienza e pressione sui prezzi sono entrambe da verificare nella reazione della banca centrale.':
   m.labourDirection==='SALE'?
    'Disoccupazione in aumento: cercare conferma di rallentamento in salari, assunzioni e attività, non dedurlo da una sola serie.':
    'Le due serie macro non identificano da sole la fase del ciclo o una sorpresa per il mercato.';
  const spreadNote=ra.ok&&pr.ok&&Math.abs(ra.change)>=1&&Math.abs(pr.change)>=1?
    Math.sign(ra.change)===Math.sign(pr.change)?
    'Il 2Y governativo e il riferimento 6M hanno un segno simile, ma misurano strumenti e periodi differenti: non basta per attribuire una causa.':
    'Il 2Y governativo e il riferimento 6M si muovono in direzioni diverse: occorre distinguere duration, composizione dei rendimenti e aspettative monetarie.':
    'Sui rendimenti e sul 6M manca un confronto omogeneo sufficientemente informativo.';
  let tone='unknown',label='Da completare',base='Senza prezzi comuni non attribuiamo una posizione di forza.';
  if(p.ok){
   if(!pr.ok){tone='incomplete';label='Conferme incomplete';
    base='Il prezzo '+(p.change>0?'è positivo':p.change<0?'è negativo':'è pressoché fermo')+
    ' nel confronto G8, ma non disponiamo di una variazione 6M verificata.';}
   else{
    const moving=Math.abs(pr.change)>=1&&Math.abs(p.change)>=.1;
    const matched=moving&&Math.sign(pr.change)===Math.sign(p.change);
    const diverged=moving&&Math.sign(pr.change)!==Math.sign(p.change);
    if(diverged){tone='divergent';label='Divergenza da studiare';
     base='Prezzo su 20 fixing e aspettative 6M nell’ultima settimana hanno segno opposto. Finestre diverse: possibile divergenza da approfondire, non un trade.';}
    else if(matched){tone='aligned';label='Direzioni compatibili';
     base='Prezzo su 20 fixing e aspettative 6M nell’ultima settimana hanno lo stesso segno. Finestre diverse: non è una conferma causale né un segnale.';}
    else{tone='mixed';label='Quadro non risolto';
     base='Prezzo e variazione settimanale delle aspettative non danno una direzione univoca o sufficientemente ampia.';}
   }
  }
  return {tone,label,text:base+' '+macroNote+' '+spreadNote};
 }
 function analyze({prices,macro,rates,ois,cot,now,rankingFn,fallback}){
  if(!day(now))return {rows:[],priceRanking:null,asof:null,limitations:['Data della seduta non valida']};
  const rank=typeof rankingFn==='function'?rankingFn(prices,now,FX):null;
  const map=new Map(rank?.items?.map((x,i)=>[x.ccy,{...x,position:i+1}])||[]);
  const rows=FX.map(ccy=>{
   const row={ccy,macro:macroAxis(macro?.[ccy],now),rates:ratesAxis(rates?.[ccy],now),
    pricing:pricingAxis(ois?.[ccy],now),price:priceAxis(map.get(ccy))};
   row.context=fallback?.currencies?.[ccy]||null;
   row.reading=reading(row);
   const c=cot?.[ccy];
   const i=c?.dates?.length-1;
   row.cot=i>=1&&goodAge(c.dates[i],now,14)&&num(c.net?.[i])&&num(c.net?.[i-1])?
    {asof:c.dates[i],net:c.net[i],delta:c.net[i]-c.net[i-1]}:null;
   row.evidenceCount=[row.macro.ok,row.rates.ok,row.pricing.ok,row.price.ok].filter(Boolean).length;
   return row;
  });
  // The ONLY ordinal ranking is price strength. Never sort on missing
  // expectations or mix CPI, sovereign yields and FX returns as raw numbers.
  rows.sort((a,b)=>(a.price.position??99)-(b.price.position??99)||a.ccy.localeCompare(b.ccy));
  return {rows,priceRanking:rank,asof:rank?.asof||null,limitations:[
    'La posizione numerica ordina esclusivamente i prezzi BCE; non è un punteggio macro/monetario.',
    'Lavoro e inflazione sono solo due componenti del quadro macro: servono crescita, salari, PMI, credito e sorprese.',
    'Le variazioni del 2Y e degli strumenti 6M non sono necessariamente sullo stesso intervallo delle 20 sedute FX.',
    'Dati insufficienti o fonti indicative restano non verificati: nessun punteggio viene inventato.',
    'Le quotazioni futures secondarie e gli indicatori storici di crescita sono solo un contesto, mai promossi a OIS o nowcast ufficiali.'
  ]};
 }
 const api={analyze,macroAxis,ratesAxis,pricingAxis,priceAxis,reading};
 root.FXQuantCurrencyStrength=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
