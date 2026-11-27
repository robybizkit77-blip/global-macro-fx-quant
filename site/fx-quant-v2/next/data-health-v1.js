/* FX Quant Next: shared date/coverage diagnostic, no score or source writes. */
(function(root){
'use strict';
const G8=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const months=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
function periodEnd(value){
 if(typeof value!=='string')return null;
 let m=value.match(/^(\d{4})-Q([1-4])$/);
 if(m)return Date.UTC(+m[1],+m[2]*3,0);
 m=value.match(/^(\d{4})-(\d{2})(?:-(\d{2})(?:[T ].*)?)?$/);
 if(m)return m[3]?Date.UTC(+m[1],+m[2]-1,+m[3]):Date.UTC(+m[1],+m[2],0);
 m=value.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
 if(m)return Date.UTC(+m[3],+m[2]-1,+m[1]);
 m=value.match(/^(\d{1,2})[ -]([A-Za-z]{3})[ -](\d{4})$/);
 if(m&&months.includes(m[2].toLowerCase()))return Date.UTC(+m[3],months.indexOf(m[2].toLowerCase()),+m[1]);
 return null;
}
function age(day,today){const a=periodEnd(day),b=periodEnd(today);return a===null||b===null?null:(b-a)/86400000}
function item(label,day,today,maxAge,extra=''){
 const n=age(day,today);
 return {label,day:day||null,state:n===null?'missing':n<0?'future':n>maxAge?'review':'observed',age:n,extra};
}
// These are the same supplemental sources consumed by the dedicated studios.
 // Do not overwrite native dates or imply that a proxy is the same instrument.
 function supplemental(o,today,g){
  const r=[];
  function lane(label,row,day,threshold,kind='research'){
   const x=item(label,day,today,threshold,kind==='proxy'?'Proxy: equivalenza non certificata':'Fonte separata; non promossa al Core');
   if(!row)x.state='missing';
   else if(x.state==='observed')x.state=kind;
   r.push(x);
  }
  const us=g.FXQuantUSBanksCreditResearch,gb=g.FXQuantGBPBoEReservesResearch,gc=g.FXQuantGBPBoESecuredCreditResearch;
  const jp=g.FXQuantJPYBankCreditResearch,ca=g.FXQuantCADCreditResearch,au=g.FXQuantAUDBusinessCreditGrowthResearch,ae=g.FXQuantAUDESBalancesResearch;
  const eu=g.FXQuantEURNFCCreditResearch,nz=g.FXQuantNZDRBNZLiquidity,lanes=o.residualResearch?.lanes;
  lane('USD · H.8 credito bancario',us,us?.latest_observation,21);
  lane('USD · M2',us?.money_stock,us?.money_stock?.latest_observation,65);
  lane('EUR · Prestiti imprese NFC',eu,eu?.latest_observation,65);
  lane('EUR · Liquidità in eccesso',eu?.excess_liquidity,eu?.excess_liquidity?.latest_observation,7);
  lane('EUR · BLS',eu?.lending_conditions,eu?.lending_conditions?.latest_observation,150);
  lane('GBP · Riserve BoE settimanali',gb,gb?.source_period,14);
  lane('GBP · Crescita credito garantito',gc,gc?.last_observation,65);
  lane('GBP · Credit Conditions Survey',gc?.lending_conditions,gc?.lending_conditions?.latest_observation,150);
  lane('JPY · Credito bancario MD11',jp,jp?.last_observation,65);
  lane('JPY · Tankan',jp?.tankan,jp?.tankan?.latest_observation,150);
  lane('JPY · Riserve BoJ',lanes?.['JPY.reserve_balances'],lanes?.['JPY.reserve_balances']?.proxy_as_of,65,'proxy');
  lane('CHF · Depositi a vista SNB',lanes?.['CHF.sight_deposits'],lanes?.['CHF.sight_deposits']?.proxy_as_of,65,'proxy');
  lane('CHF · Credito SNB',lanes?.['CHF.credit'],lanes?.['CHF.credit']?.proxy_as_of,65,'proxy');
  lane('CHF · Costo nuovi finanziamenti',lanes?.['CHF.credit']?.lending_rate_proxy,lanes?.['CHF.credit']?.lending_rate_proxy?.latest_observation,90,'proxy');
  lane('CAD · Prestiti alle imprese',ca,ca?.latest_observation,65);
  lane('CAD · Saldi Lynx',ca?.settlement_balances,ca?.settlement_balances?.latest_observation,7);
  lane('CAD · SLOS',ca?.lending_conditions,ca?.lending_conditions?.latest_observation,150);
  lane('AUD · Crescita credito imprese',au,au?.observation_period,65);
  lane('AUD · Saldi ES',ae,ae?.source_period,14);
  lane('NZD · D10/C50 liquidità, moneta, credito',nz,nz?.period,65);
  lane('NZD · C60 condizioni credito',nz?.credit_conditions,nz?.credit_conditions?.latest_observation,210);
  return r;
 }
function cycleCoverage(feed,today){
 const specs=[
  ['Attività', 'activity_momentum_status','activity_momentum_research','GMFQ_G8_CURRENT_ACTIVITY_MOMENTUM_RESEARCH_V1',13],
  ['Lavoro e inflazione','labour_inflation_status','labour_inflation_dynamics','GMFQ_G8_LABOUR_INFLATION_DYNAMICS_RESEARCH_V1',41],
  ['Settori, credito e liquidità','sector_financial_status','sector_financial_dynamics','GMFQ_G8_SECTOR_FINANCIAL_DYNAMICS_RESEARCH_V1',64]
 ];
 return specs.map(([label,status,key,schema,expected])=>{
  const x=feed?.[key];
  const gate=feed?.[status]==='RESEARCH_ONLY'&&x?.schema===schema&&x.safe_to_publish_D===false&&x.safe_to_update_pairs===false&&x.as_of===feed.generated_europe_rome_day&&age(x.as_of,today)>=0&&age(x.as_of,today)<=7&&G8.every(c=>Array.isArray(x.countries?.[c]));
  if(!gate)return {label,day:x?.as_of||null,state:'withheld',extra:'Copertura non validabile; attesi '+expected+' indicatori.'};
  const rows=G8.flatMap(c=>x.countries[c].map(r=>({...r,currency:c})));
  const unique=new Set(rows.map(r=>r.currency+'|'+r.series_id));
  const valid=rows.filter(r=>r.measurement!=='WITHHELD'&&Number.isFinite(r.level)&&typeof r.reference_period==='string');
  const velocity=valid.filter(r=>Number.isFinite(r.velocity_pp)).length, acceleration=valid.filter(r=>Number.isFinite(r.acceleration_pp)).length;
  const complete=rows.length===expected&&unique.size===expected&&valid.length===expected;
  const missing=rows.filter(r=>r.measurement==='WITHHELD').map(r=>r.currency+' '+r.label+': '+(r.reason||'fonte sospesa'));
  return {label,day:x.as_of,state:complete?'research':'review',extra:valid.length+'/'+expected+' livelli validi; velocità '+velocity+'/'+expected+'; accelerazione '+acceleration+'/'+expected+'. '+(rows.length!==expected||unique.size!==expected?'Perimetro incompleto o duplicato. ':'')+missing.join('; ')};
 });
}
function read(data,today,globals=root){
 const o=data||{},rows=[];
 const add=(name,items,note)=>rows.push({name,items,note});
 add('Forex e coppie',[item('Fixing BCE',o.currencyPrices?.last_as_of,today,4),item('28 coppie',o.pairs?.price_asof,today,4)],'Fixing di riferimento, non intraday.');
 add('Scenario macro',[item('Elaborazione G8',o.macroObserved?.generated_europe_rome_day,today,4)],'Data elaborazione ≠ data ultima pubblicazione di ogni serie.');
 add('Copertura motore economico',cycleCoverage(o.macroObserved,today),'Copertura dei livelli e dei calcoli pubblicati: non certifica l’ultimo rilascio delle fonti né la validità predittiva.');
 add('Tassi governativi',G8.map(c=>item(c,o.rates?.[c]?.date,today,7)),'Archivio 2Y/10Y di base. Fonti alternative possono avere date diverse; non equivalgono automaticamente a una curva completa.');
 add('Pricing monetario',G8.map(c=>{
  const r=o.oisOperational?.currencies?.[c],s=item(c,r?.as_of,today,7,r?.operational_status||'stato non disponibile');
  if(r?.operational_status==='WITHHELD')s.state='withheld';
  else if(s.state==='observed'&&r?.operational_status==='GREEN_ESTIMATED')s.state='estimated';
  return s;
 }),'Fonte operativa: OIS e futures distinti; snapshot indicativi e proxy separati.');
 add('Banche centrali',G8.map(c=>({...item(c,o.cb?.[c]?.last_date,today,90),state:o.cb?.[c]?.last_date?'check_release':'missing'})),'Decisioni a calendario: confrontare con l’ultima riunione, non con una scadenza giornaliera.');
 const roles=['liquidity','money','credit','conditions'];
 add('Liquidità e credito',G8.flatMap(c=>roles.filter(k=>o.liquidity?.[c]?.[k]).map(k=>{
  const r=o.liquidity[c][k],d=r.dates?.at(-1)||r.last_date;
  const threshold=k==='conditions'?150:/^\d{4}-\d{2}$/.test(d||'')?65:65;
  return item(c+' · '+(r.label||k),d,today,threshold);
 })).concat(G8.filter(c=>!roles.some(k=>o.liquidity?.[c]?.[k])).map(c=>item(c,null,today,65))),'Date delle singole serie native; soglie di attenzione indicative, non prova di mancato rilascio. Dossier alternativi separati.');
 add('Fonti integrative · liquidità e credito',supplemental(o,today,globals),'Periodi delle fonti integrative già utilizzate nelle sezioni. Non sostituiscono automaticamente le serie native, e non certificano l’ultimo rilascio.');
 add('Fonti integrative · tassi e pricing',[
  item('CHF · SNB 10Y (senza 2Y)',o.chfSpot?.as_of,today,7,'Solo 10Y informativo'),
  item('CHF · storico SNB 2Y/10Y',o.chfResearch?.last_observation_date,today,45,'Ancoraggio statistico mensile di ricerca'),
  item('AUD · RBA F2 2Y/10Y',o.audDailyResearch?.last_observation_date,today,14,'Pubblicazione F2 a cadenza settimanale; ricerca'),
  item('NZD · RBNZ B2 HTML/XLSX',o.nzdReconciled?.last_observation_date,today,7,'Benchmark governativi post-roll riconciliati; ricerca'),
  item('NZD · RBNZ B2 archivio web',o.nzdPostroll?.daily_observations?.at(-1)?.date,today,7,'Archivio storico separato, non fonte preferita'),
  ...G8.map(c=>{const q=o.ois?.currencies?.[c],x=item(c+' · snapshot pricing',q?.as_of,today,7,q?.quality||'');if(x.state==='observed')x.state='research';return x;}),
  {...item('NZD · proxy direzionale',o.nzdDirectionalProxy?.as_of,today,7),state:o.nzdDirectionalProxy?.as_of&&age(o.nzdDirectionalProxy.as_of,today)>=0&&age(o.nzdDirectionalProxy.as_of,today)<=7?'proxy':item('NZD',o.nzdDirectionalProxy?.as_of,today,7).state}
 ],'Le fonti integrative non risolvono automaticamente una lacuna operativa.');
 add('COT',G8.map(c=>item(c,o.cotHistory?.[c]?.dates?.at(-1),today,14)),'Report settimanale: festività e calendario CFTC da verificare.');
 add('Rischio e Cross-Asset',['SP500','NASDAQCOM','DJIA','SX5E','VIX','IG_OAS','HY_OAS'].map(k=>item(k,o.risk?.streams?.[k]?.date,today,7)),'Chiusure e spread di date diverse, non quotazioni in tempo reale.');
 add('Notizie e calendario',[item('Notizie',o.news?.content_as_of,today,2),item('Calendario',o.calendar?.last_checked_at_utc,today,2)],'Verifica data del contenuto e ultimo controllo, non completezza delle notizie.');
 add('Base strutturale FX',[{...item('Macro baseline',o.pairs?.macro_baseline_asof,today,7),state:o.pairs?.macro_baseline_asof?'frozen':'missing'}],'Baseline congelata, non confonderla con i prezzi correnti o il nuovo motore sperimentale.');
 const counts={};for(const r of rows)for(const x of r.items)counts[x.state]=(counts[x.state]||0)+1;
 return {rows,counts,attention:rows.some(r=>r.items.some(x=>x.state!=='observed'))};
}
const names={observed:'Data entro soglia',review:'Data da verificare',missing:'Assente',future:'Data futura',withheld:'Non disponibile',estimated:'Stima',check_release:'Verifica riunione',frozen:'Congelata',research:'Ricerca · entro soglia',proxy:'Proxy · entro soglia'};
function render(health,esc){
 return '<details class="panel" data-data-health-v1><summary><strong>Affidabilità degli aggiornamenti</strong> · '+(health.attention?'Controlli aperti':'Date entro le soglie indicative')+'</summary><p>Data presente non significa fonte aggiornata all’ultimo rilascio. Controllo diagnostico, non certificazione di freschezza. Nessun effetto sui ranking.</p>'+health.rows.map(r=>'<details><summary><strong>'+esc(r.name)+'</strong> · '+r.items.filter(x=>x.state!=='observed').length+'/'+r.items.length+' da verificare</summary><p>'+esc(r.note)+'</p><div style="overflow-x:auto"><table><thead><tr><th>Fonte / indicatore</th><th>Periodo</th><th>Stato</th></tr></thead><tbody>'+r.items.map(x=>'<tr><td>'+esc(x.label)+'</td><td>'+esc(x.day||'—')+'</td><td><span class="badge '+(x.state==='observed'?'neutral':'warning')+'">'+esc(names[x.state])+'</span> '+esc(x.extra)+'</td></tr>').join('')+'</tbody></table></div></details>').join('')+'</details>';
}
const api={read,render,periodEnd,cycleCoverage};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
else root.FXQuantDataHealth=api;
})(typeof window==='undefined'?globalThis:window);
