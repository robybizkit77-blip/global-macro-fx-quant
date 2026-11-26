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
function read(data,today){
 const o=data||{},rows=[];
 const add=(name,items,note)=>rows.push({name,items,note});
 add('Forex e coppie',[item('Fixing BCE',o.currencyPrices?.last_as_of,today,4),item('28 coppie',o.pairs?.price_asof,today,4)],'Fixing di riferimento, non intraday.');
 add('Scenario macro',[item('Elaborazione G8',o.macroObserved?.generated_europe_rome_day,today,4)],'Data elaborazione ≠ data ultima pubblicazione di ogni serie.');
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
 add('COT',G8.map(c=>item(c,o.cotHistory?.[c]?.dates?.at(-1),today,14)),'Report settimanale: festività e calendario CFTC da verificare.');
 add('Rischio e Cross-Asset',['SP500','NASDAQCOM','DJIA','SX5E','VIX','IG_OAS','HY_OAS'].map(k=>item(k,o.risk?.streams?.[k]?.date,today,7)),'Chiusure e spread di date diverse, non quotazioni in tempo reale.');
 add('Notizie e calendario',[item('Notizie',o.news?.content_as_of,today,2),item('Calendario',o.calendar?.last_checked_at_utc,today,2)],'Verifica data del contenuto e ultimo controllo, non completezza delle notizie.');
 add('Base strutturale FX',[{...item('Macro baseline',o.pairs?.macro_baseline_asof,today,7),state:o.pairs?.macro_baseline_asof?'frozen':'missing'}],'Baseline congelata, non confonderla con i prezzi correnti o il nuovo motore sperimentale.');
 const counts={};for(const r of rows)for(const x of r.items)counts[x.state]=(counts[x.state]||0)+1;
 return {rows,counts,attention:rows.some(r=>r.items.some(x=>x.state!=='observed'))};
}
const names={observed:'Data entro soglia',review:'Data da verificare',missing:'Assente',future:'Data futura',withheld:'Non disponibile',estimated:'Stima',check_release:'Verifica riunione',frozen:'Congelata'};
function render(health,esc){
 return '<details class="panel" data-data-health-v1><summary><strong>Affidabilità degli aggiornamenti</strong> · '+(health.attention?'Controlli aperti':'Date entro le soglie indicative')+'</summary><p>Data presente non significa fonte aggiornata all’ultimo rilascio. Controllo diagnostico, non certificazione di freschezza. Nessun effetto sui ranking.</p>'+health.rows.map(r=>'<details><summary><strong>'+esc(r.name)+'</strong> · '+r.items.filter(x=>x.state!=='observed').length+'/'+r.items.length+' da verificare</summary><p>'+esc(r.note)+'</p><div style="overflow-x:auto"><table><thead><tr><th>Fonte / indicatore</th><th>Periodo</th><th>Stato</th></tr></thead><tbody>'+r.items.map(x=>'<tr><td>'+esc(x.label)+'</td><td>'+esc(x.day||'—')+'</td><td><span class="badge '+(x.state==='observed'?'neutral':'warning')+'">'+esc(names[x.state])+'</span> '+esc(x.extra)+'</td></tr>').join('')+'</tbody></table></div></details>').join('')+'</details>';
}
const api={read,render,periodEnd};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
else root.FXQuantDataHealth=api;
})(typeof window==='undefined'?globalThis:window);
