'use strict';
/* News evidence desk V24: preserve every source release; distinguish dated
 * monetary pricing observations, official publication headlines and verified
 * surprises/reactions. Feed is read-only and NOT a live event-price window.
 */
(function(root){
 const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 const romeDate=iso=>{
  if(typeof iso!=='string'||!/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(iso))return null;
  const d=new Date(iso);
  if(!Number.isFinite(d.getTime()))return null;
  const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Rome',year:'numeric',
   month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(d);
  const values=Object.fromEntries(parts.filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
  const date=values.year+'-'+values.month+'-'+values.day;
  return day(date)?{date,time:values.hour+':'+values.minute,local:'Italia'}:null;
 };
 const link=u=>{
  if(typeof u!=='string'||u.length>2000)return null;
  try{const parsed=new URL(u);
   if(parsed.protocol!=='https:'||!parsed.hostname||parsed.username||parsed.password)return null;
   return parsed.href;
  }catch(e){return null;}
 };
 function sourceAudit(feed,now){
  const checked=romeDate(feed?.last_checked_at_utc);
  const validChecked=checked&&day(now)&&checked.date<=now;
  const official=feed?.official_releases||{},sources=official.sources;
  const validSources=validChecked&&Array.isArray(sources)&&sources.length>0&&
    official.last_attempt_day_rome===checked.date&&
    Number.isInteger(official.source_count)&&official.source_count===sources.length;
  const dateLabel=d=>d.slice(8,10)+'/'+d.slice(5,7)+'/'+d.slice(0,4);
  const checkText=validChecked?'Ultimo controllo: '+dateLabel(checked.date)+' ore '+checked.time+' (Italia)':
    'Ultimo controllo delle fonti non verificabile';
  let rssText='Stato delle fonti RSS non certificabile per questa verifica';
  let failures=null,withoutRecent=null;
  if(validSources){
   failures=sources.filter(x=>x.status==='FETCH_OR_PARSE_FAILED').length;
   withoutRecent=sources.filter(x=>x.status==='NO_VERIFIED_RECENT_ITEMS').length;
   const unknown=sources.some(x=>!['OK_RECENT_ITEMS','NO_VERIFIED_RECENT_ITEMS','FETCH_OR_PARSE_FAILED'].includes(x.status));
   if(!unknown&&failures===official.source_failures){
    rssText='RSS ufficiali: '+sources.length+' fonti controllate, '+failures+' errori; '+
      withoutRecent+' senza articoli recenti verificabili';
   }else{
    rssText='Stato RSS incoerente con i dettagli delle fonti: verifica incompleta';
    failures=null;withoutRecent=null;
   }
  }
  return {checkedAt:validChecked?checked.date:null,checkedTime:validChecked?checked.time:null,
    sourceCount:validSources?sources.length:null,failures,withoutRecent,
    auditLine:checkText+' · '+rssText,
    sourceCoverageValid:validSources&&failures!==null};
 }
 function parse(feed,now){
  const empty={pulse:[],official:[],pulseAsOf:null,officialAsOf:null,latest:null,
   ...sourceAudit(feed,now),
   gap:'Il feed non contiene una finestra pre/post degli strumenti di mercato; non possiamo attribuire reazioni causali.',quality:'NON VALIDATO'};
  if(!day(now)||!feed||typeof feed!=='object')return empty;
  const pulse=(Array.isArray(feed.items)?feed.items:[]).flatMap((x,i)=>{
   if(!day(x?.as_of)||x.as_of>now||!x.title||!x.source)return [];
   const isOIS=x.category==='OIS_REPRICING';
   const isFuture=x.category==='FUTURES_IMPLIED_REPRICING';
   const type=isOIS?'OIS osservato':isFuture?'Futures: pricing implicito':'Aggiornamento di mercato';
   const why=isOIS?'Può cambiare la lettura delle attese monetarie nella scadenza indicata; non equivale automaticamente a una sorpresa macro o al movimento FX.':
    isFuture?'Futures e curve OIS non sono la stessa misura: il movimento del contratto può essere un indizio sulle aspettative, non una curva OIS certificata.':
    'Il dato va letto nel contesto macro e del prezzo, senza inferire causalità da un titolo.';
   return [{id:'pulse-'+i,title:String(x.title),source:String(x.source),ccy:String(x.ccy||''),
    kind:type,asof:x.as_of,time:null,body:String(x.detail||''),why,
    verify:'Confrontare lo strumento e la sua scadenza sulla stessa data, eventuale consenso prima della release e variazione FX in una finestra temporale verificata.',
    impact:'Riprezzamento dello strumento descritto dal feed, NON reazione provata a un evento.',
    quality:String(x.quality||'non classificata'),url:null,macroSurprise:false,reactionProven:false}];
  }).sort((a,b)=>b.asof.localeCompare(a.asof));
  const official=(Array.isArray(feed.official_releases?.headlines)?feed.official_releases.headlines:[])
   .flatMap((x,i)=>{
    const t=romeDate(x?.published_at_utc);
    if(!t||t.date>now||!x.title||!x.source)return [];
    const ec=x.desk_context||{},proof=x.reaction_evidence||{};
    const why=typeof ec.why_watch==='string'&&ec.why_watch.trim()?ec.why_watch:
      'Il titolo conferma una pubblicazione, ma non ne misura l’impatto macroeconomico.';
    const verify=typeof ec.verify_next==='string'&&ec.verify_next.trim()?ec.verify_next:
      'Leggere il comunicato integrale; confrontare eventuali nuove informazioni con il consenso.';
    const certifiedReaction=proof.market_reaction==='MEASURED'&&
      proof.causal_attribution==='ESTABLISHED'&&proof.fx?.status==='CERTIFIED_EVENT_WINDOW';
    const impact=certifiedReaction?'Esiste una prova di finestra FX certificata: consultare i dettagli dell’evento e dello strumento.':
      'Reazione FX/OIS NON verificata su finestra intraday; i rendimenti giornalieri, se presenti, sono solo contesto.';
    return [{id:'official-'+i,title:String(x.title),source:String(x.source),ccy:String(x.ccy||''),
      kind:ec.topic==='CB_COMMUNICATION'?'Comunicazione banca centrale':
       ec.topic==='ENERGY_FUNDAMENTALS'?'Fondamentali energia':'Comunicazione istituzionale',
      asof:t.date,time:t.time,body:'Pubblicazione ufficiale: titolo e fonte verificati nel feed. Il contenuto integrale va letto prima di attribuirgli un significato operativo.',
      why,verify,impact,quality:String(x.quality||'fonte istituzionale'),
      url:link(x.url),macroSurprise:false,reactionProven:certifiedReaction}];
   }).sort((a,b)=>(b.asof+'T'+(b.time||'')).localeCompare(a.asof+'T'+(a.time||'')));
  const pulseAsOf=day(feed.content_as_of)&&feed.content_as_of<=now?feed.content_as_of:null;
  const latest=[pulse[0]?.asof,official[0]?.asof].filter(Boolean).sort().at(-1)||null;
  const gap='Market Pulse: '+(pulseAsOf||'data assente')+' · Comunicazioni ufficiali: '+
   (official[0]?.asof||'data assente')+'. Le due sezioni hanno orologi diversi: nessuna pubblicazione equivale automaticamente a sorpresa o a reazione del mercato.';
  return {pulse,official,pulseAsOf,officialAsOf:official[0]?.asof||null,latest,gap,
   ...sourceAudit(feed,now),
   quality:pulse.length||official.length?'FATTI DATATI; IMPATTO DA VERIFICARE':'NON VALIDATO'};
 }
 root.FXQuantNewsEvidence={parse,romeDate,link,sourceAudit};
 if(typeof module!=='undefined'&&module.exports)module.exports={parse,romeDate,link,sourceAudit};
})(typeof window!=='undefined'?window:{});
