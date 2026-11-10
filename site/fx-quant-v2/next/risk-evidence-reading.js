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
 function read(streams,now){
  const latest=K.map(k=>({key:k,date:isDay(streams?.[k]?.date)&&streams[k].date<=now?
    streams[k].date:null}));
  const sourceDates=latest.map(x=>x.key+' '+iso(x.date)).join(' · ');
  const empty={ready:false,asof:null,previousAsOf:null,
   headline:'Non abbiamo un intervallo comune per verificare lo stress.',
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
  const headline=stale?
   (stress?'Stress cross-asset verificato nella seduta storica del '+asof+'.':
    relief?'Distensione cross-asset osservata al '+asof+', non necessariamente ancora attuale.':
    'Le ultime date comuni sono storiche: nessun nuovo regime certificato.'):
   stress?'Lo stress coinvolge azioni, volatilità e credito.':
   relief?'La distensione coinvolge azioni, volatilità e credito.':
   tech?'Il Nasdaq soffre più del mercato ampio.':
   'Segnali cross-asset misti: non forziamo un regime.';
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
  if(stale)judgement+=' Gli ultimi aggiornamenti delle cinque fonti sono su date diverse: non estendiamo questa diagnosi alla seduta di oggi.';
  const monitor=stress?'Confrontare i prossimi fixing simultanei: un recupero azionario con VIX in discesa e HY in restringimento indebolirebbe la tesi di stress persistente. Un ulteriore allargamento HY/IG la rafforzerebbe.':
   relief?'Verificare se calo di VIX e restrizione HY persistono e si diffondono anche all’azionario ampio; un nuovo allargamento del credito indebolirebbe la distensione.':
   'Verificare nuove rilevazioni su una data comune: la conferma o smentita deve coinvolgere azionario, VIX e credito, non un solo indice.';
  return {ready:true,asof,previousAsOf,headline,observation,judgement,monitor,
   sourceDates,quality:stale?'STORICO ALLINEATO':'DATE ALLINEATE',regime,stale,changes:vals,spanDays:span};
 }
 root.FXQuantRiskEvidence={read};
 if(typeof module!=='undefined'&&module.exports)module.exports={read};
})(typeof window!=='undefined'?window:{});
