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
 // These labels translate only the subject explicitly stated in each
 // official headline. They do NOT imply that the linked article was read
 // or that its content/reaction was independently confirmed.
 const officialTitleRules=[
  [/^Hydropower generation in the Southwest fell to record lows this summer/i,
   "USA, Sud-Ovest: produzione idroelettrica ai minimi storici nell’estate"],
  [/Project Meridian FX APAC/i,
   "Project Meridian FX APAC: collaborazione tra le autorità monetarie di Regno Unito, Singapore e Thailandia"],
  [/^Isabel Schnabel: Made in Europe/i,
   "Isabel Schnabel: «Made in Europe»"],
  [/^Federal Reserve Board announces pricing, effective January 1, 2027, for payment services/i,
   "Fed: nuove tariffe dei servizi di pagamento dal 1° gennaio 2027"],
  [/^Federal Reserve announces revised tentative schedule of Federal Open Market Committee meetings in 2027/i,
   "Fed: calendario provvisorio aggiornato delle riunioni FOMC del 2027"],
  [/^EIA forecasts Alaskan crude oil production to grow 13% in 2027/i,
   "EIA: produzione di greggio in Alaska prevista in aumento del 13% nel 2027"],
  [/^Japanese Government Bonds Held by the Bank of Japan/i,
   "BoJ: titoli di Stato giapponesi detenuti dalla banca centrale"],
  [/^Basic Figures on Fails \(Oct\./i,
   "BoJ: dati di ottobre sui mancati regolamenti dei titoli"],
  [/^RBNZ Reverse Stress Test demonstrates resilience of insurers/i,
   "RBNZ: stress test inverso sulla resilienza delle compagnie assicurative"],
  [/^Philip R\. Lane: The science and practice of monetary policy communication/i,
   "Philip R. Lane: la comunicazione di politica monetaria nell’esperienza BCE"],
  [/^Release of the Bank of Canada.s summary of deliberations/i,
   "Banca del Canada: pubblicato il riepilogo delle deliberazioni"],
  [/^Exchange of letters between the Governor and the Chancellor on the Asset Purchase Facility/i,
   "Banca d’Inghilterra: lettere sull’Asset Purchase Facility, novembre 2026"],
  [/^Designation of Prosegur Australia Pty Ltd under the Cash Distribution Framework Act 2026/i,
   "RBA: designazione di Prosegur Australia nel quadro normativo del contante del 2026"],
  [/^Joint Statement of the Government of Canada and the Bank of Canada on the Renewal of the Monetary Policy Framework/i,
   "Canada: dichiarazione congiunta sul rinnovo del quadro di politica monetaria"],
  [/^Reserve Bank files DCS disclosure charge against Westpac New Zealand Limited/i,
   "RBNZ: contestazione a Westpac NZ sugli obblighi informativi DCS"]
 ];
 const displayOfficialTitle=x=>{
  const title=String(x?.title||'').trim();
  for(const [pattern,translated] of officialTitleRules){
   if(pattern.test(title))return translated;
  }
  // Safeguard for new, unsupported headlines: no imaginary translation.
  if(/\b(il|la|gli|della|delle|governo|banca|produzione|prezzi|pubblicazione|mercati|politica monetaria)\b/i.test(title))return title;
  return 'Nuova comunicazione di '+String(x?.source||'fonte istituzionale')+
   ' · titolo originale nei dettagli';
 };
 function parse(feed,now){
  const empty={pulse:[],official:[],pulseAsOf:null,officialAsOf:null,latest:null,
   gap:'Il feed non contiene una finestra pre/post degli strumenti di mercato; non possiamo attribuire reazioni causali.',quality:'NON VALIDATO'};
  if(!day(now)||!feed||typeof feed!=='object')return empty;
  const pulse=(Array.isArray(feed.items)?feed.items:[]).flatMap((x,i)=>{
   if(!day(x?.as_of)||x.as_of>now||!x.title||!x.source)return [];
   const c=x.category||'';
   // Published date is not first-observed date; prevent historical lookahead.
   if(c==='MACRO_OFFICIAL_ACTUAL'&&
      (!romeDate(x.first_runner_observed_at_utc)||
       romeDate(x.first_runner_observed_at_utc).date>now))return [];
   const money=c==='OIS_REPRICING'||c==='OIS_PROXY_REPRICING'||c==='FUTURES_IMPLIED_REPRICING';
   const kinds={
    OIS_REPRICING:'OIS osservato',OIS_PROXY_REPRICING:'OIS stimato',
    FUTURES_IMPLIED_REPRICING:'Futures: pricing implicito',
    MARKET_FX_ECB_FIXING:'Forex · fixing BCE',
    MARKET_EQUITY_CLOSE:'Azionario · chiusura',
    MARKET_VOLATILITY_CLOSE:'Volatilità · VIX',
    MARKET_CREDIT_OAS:'Credito · spread OAS',
    MARKET_GOVERNMENT_RATES:'Titoli governativi · 2Y/10Y',
    MACRO_UPDATE:'Macro · pubblicazione datata',
    MACRO_OFFICIAL_ACTUAL:'Macro · dato ufficiale BLS'
   };
   const type=kinds[c]||'Aggiornamento di mercato';
   const why=c==='MACRO_OFFICIAL_ACTUAL'?
    'I dati CPI possono modificare le aspettative Fed e il differenziale con altre banche centrali; la direzione USD resta da confermare nei prezzi.':
    c==='OIS_REPRICING'?'Può cambiare la lettura delle attese monetarie nella scadenza indicata; non equivale automaticamente a una sorpresa macro o al movimento FX.':
    c==='OIS_PROXY_REPRICING'?'È una stima informativa, da tenere separata dalle curve OIS ufficiali e dalle variazioni effettive del mercato.':
    c==='FUTURES_IMPLIED_REPRICING'?'Futures e curve OIS non sono la stessa misura: il movimento del contratto può essere un indizio sulle aspettative, non una curva OIS certificata.':
    c==='MARKET_FX_ECB_FIXING'?'Il prezzo esprime forza relativa della coppia nella rilevazione BCE, non dimostra se siano cambiati i fondamentali di una valuta o dell’altra.':
    c==='MARKET_EQUITY_CLOSE'?'Un movimento azionario può riflettere utili, valutazioni o tassi. Un singolo indice non prova la diffusione dello shock.':
    c==='MARKET_VOLATILITY_CLOSE'?'Il VIX misura volatilità implicita sull’azionario USA; da solo non prova acquisti di put, hedging o deleveraging.':
    c==='MARKET_CREDIT_OAS'?'Lo spread OAS misura il premio sul credito, diverso dal rendimento governativo. L’allargamento può segnalare maggiore avversione al rischio.':
    c==='MARKET_GOVERNMENT_RATES'?'Il 2Y è sensibile anche al percorso monetario; il 10Y incorpora crescita, inflazione e premio a termine. Non sono curve OIS.':
    'Il dato va letto nel contesto macro e del prezzo, senza inferire causalità da un titolo.';
   const verify=c==='MACRO_OFFICIAL_ACTUAL'?
    'Confrontare attese pre-evento con provenienza nota, Fed OIS/futures su finestre comuni ed EUR/USD e USD/JPY. Le variazioni annuali non pubblicate non sono zero.':
    money?'Verificare tenor, data e qualità di OIS/futures, sorpresa rispetto al consenso e prezzo FX prima/dopo un evento.':
    c==='MARKET_FX_ECB_FIXING'?'Confrontare differenziali di tasso, macro relative e sedute successive; il fixing BCE non è una quotazione intraday.':
    c==='MARKET_EQUITY_CLOSE'||c==='MARKET_VOLATILITY_CLOSE'||c==='MARKET_CREDIT_OAS'?
     'Confrontare i dati della stessa seduta su azioni, VIX e credito; per parlare di diffusione servono date comuni.':
    c==='MARKET_GOVERNMENT_RATES'?'Verificare OIS/futures della stessa seduta, componenti del 10Y e reazione FX: un governativo non isola lo shock monetario.':
    'Verificare fonte, consenso, eventuali revisioni e risposta del mercato con tempi comparabili.';
   return [{id:'pulse-'+i,title:String(x.title),source:String(x.source),ccy:String(x.ccy||''),
    kind:type,asof:x.as_of,time:null,body:String(x.detail||''),why,verify,
    impact:c==='MACRO_OFFICIAL_ACTUAL'?
     'Dato macro ufficiale osservato; reazione FX/OIS intraday NON misurata né attribuita causalmente.':
     money?'Variazione dello strumento monetario indicato; NON reazione provata a un evento.':
     'Variazione osservata nella chiusura/fixing datato; NON reazione provata a un evento.',
    quality:String(x.quality||'non classificata'),url:link(x.source_url),
    macroSurprise:false,reactionProven:false}];
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
    return [{id:'official-'+i,title:String(x.title),displayTitle:displayOfficialTitle(x),source:String(x.source),ccy:String(x.ccy||''),
      kind:ec.topic==='CB_COMMUNICATION'?'Comunicazione banca centrale':
       ec.topic==='ENERGY_FUNDAMENTALS'?'Fondamentali energia':'Comunicazione istituzionale',
      asof:t.date,time:t.time,body:'Pubblicazione ufficiale: titolo e fonte verificati nel feed. Il contenuto integrale va letto prima di attribuirgli un significato operativo.',
      why,verify,impact,quality:String(x.quality||'fonte istituzionale'),
      url:link(x.url),macroSurprise:false,reactionProven:certifiedReaction}];
   }).sort((a,b)=>(b.asof+'T'+(b.time||'')).localeCompare(a.asof+'T'+(a.time||'')));
  const pulseAsOf=day(feed.content_as_of)&&feed.content_as_of<=now?feed.content_as_of:null;
  const latest=[pulse[0]?.asof,official[0]?.asof].filter(Boolean).sort().at(-1)||null;
  const gap='Movimenti di mercato: '+(pulseAsOf||'data assente')+' · Comunicazioni ufficiali: '+
   (official[0]?.asof||'data assente')+'. Le due sezioni hanno orologi diversi: nessuna pubblicazione equivale automaticamente a sorpresa o a reazione del mercato.';
  return {pulse,official,pulseAsOf,officialAsOf:official[0]?.asof||null,latest,gap,
   quality:pulse.length||official.length?'FATTI DATATI; IMPATTO DA VERIFICARE':'NON VALIDATO'};
 }
 root.FXQuantNewsEvidence={parse,romeDate,link};
 if(typeof module!=='undefined'&&module.exports)module.exports={parse,romeDate,link};
})(typeof window!=='undefined'?window:{});
