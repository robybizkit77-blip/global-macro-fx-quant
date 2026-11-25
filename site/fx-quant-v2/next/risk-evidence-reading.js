'use strict';
/* FX Quant Next V23 — matched-session cross-asset risk. Read-only observations.
 * Never confuse a historical synchronized stress with the latest mixed-date
 * snapshots; do not infer put purchases, dealer gamma, policy or forced flows.
 */
(function(root){
 const K=['SP500','NASDAQCOM','VIX','HY_OAS','IG_OAS'];
 const isDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const iso=x=>x||'n.d.';
 const fmt=(x,n=1)=>x.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n});
 const sign=(x,n=1,u='')=>(x>0?'+':x<0?'−':'')+fmt(Math.abs(x),n)+u;
 const direction=x=>x>0?'in rialzo':x<0?'in calo':'stabile';
 const closingDate=new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'long',timeZone:'UTC'});
 const fxReading={
  stress:'Se la pressione prosegue, un calo di AUD/JPY sarebbe coerente con una minore propensione al rischio. Il confronto con i tassi attesi nei due paesi aiuta a capire quanto può dipendere dalle banche centrali.',
  distensione:'Se la distensione continua, il dollaro australiano può riprendersi contro lo yen. La reazione di AUD/JPY e i tassi attesi nei due paesi aiutano a capire se la ripresa coinvolge anche il cambio.',
  'concentrazione tech':'Per le valute più sensibili al rischio conta se la debolezza si estende oltre il Nasdaq. La reazione del credito e di AUD/JPY può aiutare a capire quanto si diffonde.',
  misto:'Per il cambio, la conferma più chiara arriverebbe da azioni, volatilità e credito che cominciano a muoversi insieme. Se restano divisi, controlla quanto del movimento di AUD/JPY coincide con un cambiamento dei tassi attesi.'
 };
 function read(streams,now){
  const latest=K.map(k=>({key:k,date:isDay(streams?.[k]?.date)&&streams[k].date<=now?
    streams[k].date:null}));
  const sourceDates=latest.map(x=>x.key+' '+iso(x.date)).join(' · ');
  const empty={ready:false,asof:null,previousAsOf:null,
   headline:'Il quadro del rischio resta aperto',
   opening:'Serve una finestra comune per capire se azioni, volatilità e credito si stanno muovendo insieme.',
   fx:'Per collegare queste rilevazioni ai cambi, servono movimenti osservati nello stesso intervallo.',
   observation:'Gli indicatori azionari, il VIX e gli spread creditizi non possono essere confrontati su due date comuni certificate.',
   judgement:'Il mercato potrebbe aver attraversato regimi differenti, ma i feed attuali non dimostrano un movimento simultaneo.',
   monitor:'Verificare due date comuni delle cinque serie prima di attribuire ampiezza e persistenza allo shock.',
   sourceDates,quality:'NESSUNA CONFERMA SINCRONIZZATA'};
  if(!isDay(now)||K.some(k=>!latest.find(x=>x.key===k)?.date||
     !Array.isArray(streams?.[k]?.history)))return empty;
  const maps={};
  for(const k of K){
   const source=streams[k],history=source.history;
   const seen=new Set(),m=new Map();
   for(const r of history){
    if(!Array.isArray(r)||r.length<2||!isDay(r[0])||!finite(r[1]))continue;
    if(r[0]>now||r[0]>source.date)continue;
    if(seen.has(r[0]))return empty;
    seen.add(r[0]);m.set(r[0],r[1]);
   }
   maps[k]=m;
  }
  const common=[...maps.SP500.keys()].filter(d=>K.every(k=>maps[k].has(d))).sort();
  if(common.length<2)return empty;
  const [previousAsOf,asof]=common.slice(-2),vals={};
  for(const k of K){
   const a=maps[k].get(previousAsOf),b=maps[k].get(asof);
   if(!finite(a)||!finite(b)||a<=0||b<=0)return empty;
   vals[k]={previous:a,current:b,change:
    k.endsWith('_OAS')?(b-a)*100:k==='VIX'?b-a:(b/a-1)*100};
  }
  const span=(Date.parse(asof+'T12:00:00Z')-Date.parse(previousAsOf+'T12:00:00Z'))/864e5;
  const age=(Date.parse(now+'T12:00:00Z')-Date.parse(asof+'T12:00:00Z'))/864e5;
  const stale=age>3;
  const equityBroad=vals.SP500.change<0&&vals.NASDAQCOM.change<0;
  const stress=equityBroad&&vals.VIX.change>0&&vals.HY_OAS.change>0;
  const relief=vals.SP500.change>0&&vals.NASDAQCOM.change>0&&
    vals.VIX.change<0&&vals.HY_OAS.change<0;
  const tech=vals.NASDAQCOM.change<0&&vals.SP500.change>=0;
  const regime=stress?'stress':relief?'distensione':tech?'concentrazione tech':'misto';
  const intro=stale?'È una fotografia storica, non lo stato attuale del mercato. ':'';
  const headline=stale?'Rischio, l’ultima lettura comune è storica':
   stress?'La pressione si estende dalle azioni al credito':
   relief?'La tensione si allenta anche sul credito':
   tech?'Il Nasdaq soffre più del mercato ampio':
   'Azioni, volatilità e credito danno segnali misti';
  const asOfTime=Date.parse(asof+'T12:00:00Z');
  const period=Number.isFinite(asOfTime)?closingDate.format(asOfTime):asof;
  const equities=direction(vals.SP500.change)===direction(vals.NASDAQCOM.change)?
   'S&P 500 e Nasdaq erano '+(vals.SP500.change===0?'stabili':direction(vals.SP500.change)):
   'l’S&P 500 era '+direction(vals.SP500.change)+' e il Nasdaq '+direction(vals.NASDAQCOM.change);
  const opening='Nel confronto al '+period+', '+equities+'. La volatilità attesa era '+
   direction(vals.VIX.change)+' e il premio richiesto sulle obbligazioni più rischiose era '+direction(vals.HY_OAS.change)+'.';
  const observation='Nel confronto '+previousAsOf+' → '+asof+
   ': S&P 500 '+sign(vals.SP500.change,2,'%')+', Nasdaq '+sign(vals.NASDAQCOM.change,2,'%')+
   ', VIX '+sign(vals.VIX.change,2,' punti')+', credito HY '+sign(vals.HY_OAS.change,1,' pb')+
   ', credito IG '+sign(vals.IG_OAS.change,1,' pb')+'. '+
   (span>4?'Le date comuni sono separate da '+fmt(span,0)+' giorni: non è una variazione 1D. ':
    'Tutti i movimenti usano lo stesso intervallo di date. ')+intro;
  let judgement=stress?
   'La debolezza è presente sia nell’indice ampio sia nel Nasdaq, mentre la volatilità sale e il premio HY si allarga. '+
    (vals.IG_OAS.change>0?'Anche IG si allarga: la pressione raggiunge il credito di qualità più alta.':
    'IG non mostra un allargamento: il deterioramento del credito è meno generalizzato.')+
    ' È un insieme coerente con maggiore avversione al rischio, non una prova di liquidazioni forzate o di acquisti di put.':
   relief?'Azioni in aumento, VIX in calo e HY in restringimento descrivono una distensione. Non dimostrano, da soli, un miglioramento della crescita.':
   tech?'Il Nasdaq scende mentre l’indice ampio non scende: lo shock può essere settoriale. VIX e credito servono per verificarne la diffusione.':
   'I cinque indicatori non convergono su uno shock unico. La divergenza può dipendere da settori, premi di credito o diversa risposta dei mercati.';
  if(stale)judgement+=' Questa lettura vale per l’intervallo storico indicato.';
  const monitor=stress?'Un recupero delle azioni insieme a volatilità e premi sul credito in calo indicherebbe che la pressione si sta attenuando.':
   relief?'Se il premio sul credito torna a salire mentre le azioni recuperano, la distensione potrebbe perdere forza.':
   tech?'Segui l’S&P 500 e il premio sul credito più rischioso. Se peggiorano insieme al Nasdaq, la pressione si sta allargando.':
   'Se scendono le azioni, sale la volatilità attesa e aumenta anche il premio sul credito, la pressione diventa più diffusa.';
  const fx=stale?'Prima di collegare questo movimento ai cambi di oggi, serve un confronto più recente tra azioni, volatilità e credito.':fxReading[regime];
  return {ready:true,asof,previousAsOf,headline,opening,fx,observation,judgement,monitor,
   sourceDates,quality:stale?'STORICO ALLINEATO':'DATE ALLINEATE',regime,stale,changes:vals,spanDays:span};
 }
 // Latest observations are NOT a matched-session regime.
 const titles={SP500:'S&P 500',NASDAQCOM:'Nasdaq Composite',VIX:'VIX',HY_OAS:'Credito HY',IG_OAS:'Credito IG'};
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function latestObservations(streams,now){
  return K.map(key=>{
   const x=streams?.[key],history=Array.isArray(x?.history)?x.history:[],age=isDay(now)&&isDay(x?.date)?(Date.parse(now)-Date.parse(x.date))/864e5:NaN;
   const dates=history.filter(r=>Array.isArray(r)&&isDay(r[0])&&r[0]<=x.date&&finite(r[1])).sort((a,b)=>a[0].localeCompare(b[0]));
   const a=dates.at(-2),b=dates.at(-1);
   const ok=x?.quality==='PUBLISHED_SOURCE_RESEARCH_ONLY'&&x.not_intraday===true&&age>=0&&age<=7&&
    a&&b&&a[0]<b[0]&&b[0]===x.date&&a[1]>0&&b[1]>0&&
    Math.abs(b[1]-x.value)<.00001&&Math.abs(a[1]-x.previous)<.00001;
   const delta=ok?(key.endsWith('_OAS')?(b[1]-a[1])*100:key==='VIX'?b[1]-a[1]:(b[1]/a[1]-1)*100):null;
   const supportive=finite(delta)?delta*(key==='VIX'||key.endsWith('_OAS')?-1:1):null;
   return {key,label:titles[key],ok:Boolean(ok),date:ok?b[0]:null,previousDate:ok?a[0]:null,value:ok?b[1]:null,delta,
    tone:!finite(supportive)?'neutral':Math.abs(supportive)<.000001?'neutral':supportive>0?'up':'down'};
  });
 }
 function editorial(aligned){
  if(!aligned.ready)return {support:'Le singole osservazioni datate restano consultabili.',friction:aligned.judgement,watch:aligned.monitor};
  const m=aligned.changes,positive=[],negative=[];
  for(const k of ['SP500','NASDAQCOM']){
   const v=m[k].change;if(v>0)positive.push(titles[k]+' in rialzo');else if(v<0)negative.push(titles[k]+' in calo');
  }
  for(const k of ['VIX','HY_OAS','IG_OAS']){
   const v=m[k].change;if(v<0)positive.push(titles[k]+(k==='VIX'?' in calo':' in restringimento'));else if(v>0)negative.push(titles[k]+(k==='VIX'?' in rialzo':' in allargamento'));
  }
  const when=aligned.stale?'Nell’ultima finestra storica comune: ':'Nell’ultima finestra comune: ';
  const sentence=(items,empty)=>items.length?when+new Intl.ListFormat('it',{type:'conjunction'}).format(items)+'.':empty;
  return {support:sentence(positive,'Nessun miglioramento direzionale nei cinque indicatori.'),friction:sentence(negative,'Nessun deterioramento direzionale nei cinque indicatori.')+(aligned.stale?' Il confronto è storico: non descrive il rischio di oggi.':''),watch:aligned.monitor};
 }
 function renderFirstRead(streams,now,aligned=read(streams,now)){
  const rows=latestObservations(streams,now),desk=editorial(aligned);
  const unit=k=>k.endsWith('_OAS')?' pb':k==='VIX'?' punti':'%';
  const number=(k,v)=>finite(v)?sign(v,k.endsWith('_OAS')?1:2,unit(k)):'—';
  const names={stress:'Pressione diffusa',distensione:'Distensione','concentrazione tech':'Pressione sul Nasdaq',misto:'Segnali contrastanti'};
  const label=aligned.ready?(aligned.stale?'Ultima finestra comune · storica':'Ultima finestra comune'):'Finestra comune da verificare';
  const common=aligned.ready?K.map(k=>{
   const d=aligned.changes[k].change,positive=d*(k==='VIX'||k.endsWith('_OAS')?-1:1);
   return '<div class="risk-first-common-item '+(positive>0?'up':positive<0?'down':'neutral')+'"><small>'+titles[k]+'</small><strong>'+esc(number(k,d))+'</strong></div>';
  }).join(''):'';
  const latest=rows.map(x=>'<div class="risk-first-latest-item '+x.tone+'"><span><strong>'+esc(x.label)+'</strong><small>'+esc(x.ok?x.previousDate+' → '+x.date:'Confronto da verificare')+'</small></span><span><strong>'+esc(number(x.key,x.delta))+'</strong><small>'+esc(x.ok?fmt(x.value,2)+(x.key.endsWith('_OAS')?'%':''):'—')+'</small></span></div>').join('');
  return '<section class="risk-first-read" aria-label="Rischio di mercato, finestra comune e ultime osservazioni"><div class="risk-first-head"><div><span class="mini-overline">01 / CONFERME TRA MERCATI</span><h2>'+esc(aligned.ready?names[aligned.regime]:'Quadro non risolto')+'</h2></div><small>'+esc(label+(aligned.ready?' · '+aligned.previousAsOf+' → '+aligned.asof:''))+'</small></div>'+
   '<p class="risk-first-judgment">'+esc(aligned.judgement||aligned.opening)+'</p>'+
   '<div class="risk-first-fx"><strong>Cosa va</strong><p>'+esc(desk.support)+'</p><strong>Cosa frena</strong><p>'+esc(desk.friction)+'</p><strong>Cosa guardare</strong><p>'+esc(desk.watch)+'</p></div>'+
   (common?'<div class="risk-first-common">'+common+'</div>':'')+
   '<h3>Le rilevazioni più recenti, separatamente</h3><p class="risk-first-note">Date diverse: non sono una conferma simultanea e non aggiornano automaticamente il regime comune.</p><div class="risk-first-latest">'+latest+'</div>'+
   '<div class="risk-first-fx"><strong>Per il Forex</strong><p>'+esc(aligned.fx)+'</p><a href="#pairs">Verifica le coppie FX ↗</a></div></section>';
 }
 root.FXQuantRiskEvidence={read,latestObservations,renderFirstRead,editorial};
 if(typeof module!=='undefined'&&module.exports)module.exports={read,latestObservations,renderFirstRead,editorial};
})(typeof window!=='undefined'?window:{});
