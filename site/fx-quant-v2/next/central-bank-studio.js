'use strict';
/* FX Quant Next — G8 Central Bank Research Studio.
 * WANT = dated official communication; CAN = observed macro constraints;
 * PRICE = dated market instrument. Never conflate the three.
 */
(function(root){
 const valid=x=>/^(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)$/.test(x||'');
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 function classifyAction(bank){
  const x=String(bank?.action||'').toUpperCase();
  if(x.includes('RIALZO')||x.includes('AUMENT'))return {label:'ULTIMA DECISIONE · RIALZO',tone:'hawk'};
  if(x.includes('TAGLIO')||x.includes('RIDUZ'))return {label:'ULTIMA DECISIONE · TAGLIO',tone:'dove'};
  if(x.includes('INVARIATO')||x.includes('INVARIATA'))return {label:'ULTIMA DECISIONE · INVARIATA',tone:'neutral'};
  return {label:'DECISIONE DA VERIFICARE',tone:'unknown'};
 }
 function constraint(macro){
  if(!macro)return {text:'I dati macro osservati non sono disponibili in questo modulo: nessuna capacità di manovra dedotta.',dates:'Non disponibili'};
  const p=macro.inflation,l=macro.labour;
  const inf=finite(p?.latest_value)&&p?.as_of?
   'Inflazione '+p.latest_value.toLocaleString('it-IT',{maximumFractionDigits:2})+(String(p.transformation||'').includes('yoy')?'% a/a':' (metrica della fonte)')+', '+(p.direction||'direzione non classificata').toLowerCase()+', dato '+p.as_of+'.':
   'Inflazione corrente non verificabile.';
  const lab=finite(l?.latest_value)&&l?.as_of?
   'Lavoro: '+(l.label||'indicatore')+' '+l.latest_value.toLocaleString('it-IT',{maximumFractionDigits:2})+
   (/disoccupazione/i.test(l.label||'')?'%':'')+', '+(l.direction||'direzione non classificata').toLowerCase()+', dato '+l.as_of+'.':
   'Indicatore lavoro non verificabile.';
  return {text:inf+' '+lab+' Questi sono vincoli da interpretare, non una previsione automatica del prossimo voto.',
   dates:[p?.as_of,l?.as_of].filter(Boolean).join(' · ')||'Date non disponibili'};
 }
 function constraintReading(macro){
  const inflation=String(macro?.inflation?.direction||'').toUpperCase();
  const unemployment=String(macro?.labour?.direction||'').toUpperCase();
  const unemploymentSeries=/disoccupazione|unemployment/i.test(macro?.labour?.label||'');
  if(!unemploymentSeries)return 'La direzione del lavoro va interpretata secondo l’indicatore: non basta a qualificare una svolta della politica monetaria.';
  if(inflation.includes('SALE')&&unemployment.includes('SALE'))
   return 'Inflazione e disoccupazione in aumento rendono più complesso il compromesso tra stabilità dei prezzi e attività: la banca non ha una scelta automatica.';
  if(inflation.includes('SALE')&&unemployment.includes('SCENDE'))
   return 'Inflazione in aumento e disoccupazione in calo rendono meno evidente l’urgenza di allentare. Occorre però verificare la persistenza e le sorprese.';
  if(inflation.includes('SCENDE')&&unemployment.includes('SALE'))
   return 'Inflazione in calo e disoccupazione in aumento potrebbero aumentare lo spazio per allentare, ma soltanto se la banca condivide questa diagnosi.';
  if(inflation.includes('SCENDE')&&unemployment.includes('SCENDE'))
   return 'Inflazione e disoccupazione in calo danno segnali diversi sulla necessità di allentare: crescita e salari diventano decisivi.';
  return 'I due indicatori non identificano da soli la capacità di intervenire. Servono composizione, sorprese, salari e crescita.';
 }
 function marketMovement(o){
  const h=o?.horizons?.['6m'];
  if(!h||!finite(h.rate)||!day(h.as_of))
   return 'Il pricing a sei mesi non ha livello e data verificabili: nessun nuovo repricing può essere dedotto.';
  const deltas=[['1D',h.change_1d_bp],['1W',h.change_1w_bp]]
   .filter(x=>finite(x[1])).map(([t,v])=>t+' '+(v>0?'+':v<0?'−':'')+Math.abs(v).toLocaleString('it-IT',{maximumFractionDigits:1})+' pb');
  return deltas.length?
   'Sul 6M il feed riporta '+deltas.join(' · ')+' (osservazione '+h.as_of+'). Questa è una variazione dello strumento dichiarato, non la prova del motivo né della reazione FX.':
   'Sul 6M è disponibile un livello al '+h.as_of+', ma non una variazione 1D/1W certificata: non possiamo dire che le aspettative stiano cambiando oggi.';
 }
 function pricing(o,esc,fmt,date){
  const horizons=['3m','6m','12m'].map(k=>{
   const x=o?.horizons?.[k],ok=finite(x?.rate)&&day(x?.as_of);
   return '<div class="drivers-fact"><span>'+k.toUpperCase()+' / RIFERIMENTO DI MERCATO</span><strong>'+
    (ok?esc(fmt(x.rate,3)+'%'):'Nessuna quotazione verificabile')+'</strong><small>'+esc(ok?date(x.as_of):'Fonte o data assente')+'</small></div>';
  }).join('');
  return '<div class="drivers-facts">'+horizons+'</div>';
 }
 const FX_TESTS={
 USD:'Per il dollaro chiediti se il mercato stia alzando o abbassando il 6M Fed rispetto a BCE e BoJ. Se i Treasury si muovono ma i futures non confermano, la causa può essere diversa. Anche un risk-off può sostenere USD e contrastare il differenziale.',
 EUR:'Per EUR conta il divario tra comunicazione BCE e nuovi dati di crescita/inflazione, confrontato con Fed e BoE. Verifica variazioni omogenee del 6M e reazioni EUR/USD o EUR/GBP prima di attribuire forza alla BCE.',
 GBP:'Per GBP il rialzo BoE già deciso non è una sorpresa futura. La questione è se mercato e banca si attendano ulteriori restrizioni rispetto a BCE/Fed, e se EUR/GBP e GBP/USD confermino il nuovo pricing.',
 JPY:'Per JPY il movimento rilevante è il differenziale rispetto a USD e AUD, non soltanto il livello del tasso BoJ. Un cambio delle attese sui tagli/rialzi e una liquidazione del carry possono influenzare USD/JPY in modo diverso.',
 CHF:'Per CHF il percorso SNB va confrontato con quello BCE. EUR/CHF può reagire anche alla domanda di rifugio e a eventuali interventi: il differenziale monetario non identifica da solo il flusso.',
 CAD:'Per CAD confronta percorso BoC e Fed, aspettative di crescita relativa e petrolio. Se il pricing BoC sale ma USD/CAD non segue, cerca un driver alternativo prima di dichiarare una divergenza operativa.',
 AUD:'Per AUD il pricing RBA va confrontato con Fed e BoC, ma anche con crescita cinese e rischio globale. AUD/USD e AUD/CAD servono a distinguere sorpresa monetaria e risk-on.',
 NZD:'Per NZD conta soprattutto il repricing RBNZ relativo alla RBA e alla Fed. Una variazione di proxy bancario non equivale a OIS: confronta le fonti, poi il prezzo NZD/AUD e NZD/USD.'
 };
 function render(api){
  const {get,FX,FLAGS,NAMES,state,pageHero,esc,fmt,date,dayNow}=api;
  const banks=get('cb')||{},ois=get('ois')?.currencies||{},mac=get('macro')?.currencies||{};
  const selected=valid(state.cbCcy)?state.cbCcy:'USD',b=banks[selected],o=ois[selected],m=mac[selected];
  const stance=classifyAction(b),can=constraint(m),reading=constraintReading(m),repricing=marketMovement(o);
  const last=day(b?.last_date)?b.last_date:null;
  const older=last&&dayNow()>=last&&Math.round((Date.parse(dayNow())-Date.parse(last))/864e5)>35;
  const selectedMarketAsOf=o?.as_of||o?.horizons?.['6m']?.as_of||'data non verificata';
  const cards=FX.map(k=>{
   const x=banks[k],action=classifyAction(x);
   return '<button class="drivers-country" type="button" data-bank-country="'+k+'" aria-pressed="'+String(k===selected)+'">'+
    '<span class="drivers-country-head"><b>'+esc(FLAGS[k]||'')+' '+k+'</b><small>'+esc(x?.bank||NAMES[k]||k)+'</small></span>'+
    '<span class="drivers-mini-state" data-tone="'+action.tone+'">'+esc(action.label.replace('ULTIMA DECISIONE · ',''))+'</span>'+
    '<span class="drivers-country-date">'+esc(x?.last_date?date(x.last_date):'Data non verificata')+'</span></button>';
  }).join('');
  const context=b?.context||'Nessuna comunicazione ufficiale classificata nella fonte corrente.';
  const wants=b?.official_bias||b?.stance||'Tono ufficiale non classificato';
  const nextMeeting=b?.next_meeting||null;
  const nextTxt=day(nextMeeting)?
   (nextMeeting>=dayNow()?'Riunione successiva riportata: '+date(nextMeeting)+'.':
    'La data di riunione nello snapshot ('+date(nextMeeting)+') è già trascorsa: verificare la decisione successiva.'):'Prossima riunione non verificabile da questa fonte.';
  const rate=finite(b?.rate)?fmt(b.rate,3)+'%':b?.rate_text||'n.d.';
  return pageHero('CENTRAL BANKS / WANT × CAN','Banche centrali. <em>Cosa vogliono e cosa possono fare?</em>',
   'Le dichiarazioni indicano le intenzioni; crescita, lavoro e inflazione limitano le scelte; futures e OIS mostrano cosa il mercato sta pagando. Il Forex reagisce soprattutto ai cambiamenti relativi e alle sorprese.')+
   '<section class="drivers-panel" id="central-bank-studio"><div class="drivers-head"><div><span class="mini-overline">01 / POLICY MAP G8</span><h2>Otto banche, decisioni con date proprie</h2><p>Seleziona una banca. Un rialzo o un taglio già avvenuto non è automaticamente una sorpresa né un segnale FX.</p></div><span class="drivers-source-mark">DECISIONI E PRICING SEPARATI</span></div>'+
   '<div class="drivers-country-grid">'+cards+'</div></section>'+
   '<section class="drivers-panel drivers-selection" aria-label="Dossier banca centrale '+selected+'">'+
   '<div class="drivers-head"><div><span class="mini-overline">02 / POLICY DOSSIER · '+esc(FLAGS[selected]||'')+' '+selected+'</span>'+
   '<h2>'+esc(b?.full_name||b?.bank||NAMES[selected]||selected)+'</h2></div>'+
   '<span class="drivers-status" data-tone="'+stance.tone+'">'+esc(stance.label)+'</span></div>'+
   '<p class="drivers-lead">Tasso ufficiale riportato '+esc(b?.rate_text||rate)+' · decisione del '+esc(last?date(last):'data da verificare')+
   (older?' · fotografia storica da ricontrollare':'')+'. '+esc(b?.action||'Esito da verificare')+'.</p>'+
   '<div class="drivers-want-can">'+
    '<article class="drivers-analysis"><span>WANT · COSA COMUNICA</span><h3>'+esc(wants)+'</h3><p>'+esc(context)+'</p><small>'+esc(b?.official_next||nextTxt)+'</small></article>'+
    '<article class="drivers-analysis"><span>CAN · QUALI VINCOLI MACRO</span><h3>La libertà di manovra dipende dai prossimi dati</h3><p>'+esc(can.text)+'</p><p class="drivers-can-judgment">'+esc(reading)+'</p><small>Date macro: '+esc(can.dates)+'</small></article>'+
   '</div>'+
   '<div class="drivers-story"><div><span>CHE COSA STA PREZZANDO IL MERCATO</span><p>'+
     esc(o?'Strumento: '+(o.kind||'non classificato')+' · qualità: '+(o.quality||'da verificare')+' · snapshot '+selectedMarketAsOf+'.':'Nessuno strumento di mercato disponibile per questa valuta.')+
     ' '+esc(repricing)+' Il prezzo di un future, di un OIS e il tasso ufficiale non sono intercambiabili.</p></div>'+
     '<div><span>IPOTESI FX · COSA CONFERMARE</span><p>'+esc(FX_TESTS[selected]||'Confronta banca centrale, prezzi monetari relativi e cambio, senza dedurre trade da un voto.')+'</p></div></div>'+
   '<div class="drivers-facts drivers-policy-facts">'+
   '<div class="drivers-fact"><span>TASSO UFFICIALE / DECISIONE</span><strong>'+esc(b?.rate_text||rate)+'</strong><small>'+esc(last?date(last):'Data non verificabile')+'</small></div>'+
   '<div class="drivers-fact"><span>PROSSIMA RIUNIONE / CALENDARIO</span><strong>'+esc(day(nextMeeting)?date(nextMeeting):'Da verificare')+'</strong><small>'+esc(nextTxt)+'</small></div></div>'+
   '<div class="drivers-links"><button type="button" data-bank-open="rates" data-bank-target="'+selected+'">Esamina Tassi & OIS ↗</button>'+
   '<button type="button" data-bank-open="currencies" data-bank-target="'+selected+'">Valuta '+selected+' ↗</button><a href="#macro">Scenario macro ↗</a><a href="#news">Calendario e Notizie ↗</a></div>'+
   '<div class="drivers-source-note">La scheda ufficiale e gli strumenti monetari possono avere date differenti. Fonte banca: '+esc(b?.bank||'non classificata')+
   ', decisione '+esc(last||'non disponibile')+'; mercato '+esc(selectedMarketAsOf)+'. WANT è la comunicazione datata, CAN è un’interpretazione vincolata dalle osservazioni: nessuna probabilità di decisione inventata.</div></section>'+
   '<details class="drivers-panel drivers-fold"><summary>Apri le scadenze 3M / 6M / 12M e verifica le fonti</summary>'+
   pricing(o,esc,fmt,date)+
   '<p class="drivers-source-note">Quote espresse nelle unità della rispettiva fonte. Possono riflettere premi, basis e contratti differenti; non rappresentano una curva OIS uniforme tra le otto valute. Tipo fonte: '+esc(o?.source||'non dichiarata')+'.</p></details>';
 }
 const api={classifyAction,constraint,constraintReading,marketMovement,render};
 root.FXQuantCentralBanks=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
