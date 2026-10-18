(()=>{
'use strict';
const target=document.getElementById('mr-rates-data'),label=document.getElementById('mr-rates-asof');
if(!target)return;
const withheld=reason=>{target.textContent='WITHHELD · '+reason;document.documentElement.dataset.marketRiskRates='WITHHELD';};
fetch('../../live_data/sections/NATIVE_RATES_DATA.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(data=>{
  const u=data?.USD,series=u?.history2,series10=u?.history10;
  const last2=Array.isArray(series?.dates)?series.dates.at(-1):null;
  const last10=Array.isArray(series10?.dates)?series10.dates.at(-1):null;
  const date=u?.date;
  const ts=Date.parse(String(date||'')+'T00:00:00Z');
  const now=new Date(),today=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());
  const age=Math.floor((today-ts)/86400000);
  if(!Number.isFinite(age)||age<0||age>5||date!==last2||date!==last10)return withheld('storico Rates non aggiornato o incoerente');
  const y2=Number(u['2Y']),y10=Number(u['10Y']);
  if(!Number.isFinite(y2)||!Number.isFinite(y10))return withheld('rendimenti non validi');
  target.textContent='USA · 2Y '+y2.toFixed(2)+'% · 10Y '+y10.toFixed(2)+'% · spread 10Y−2Y '+((y10-y2)*100).toFixed(0)+' bp';
  if(label)label.textContent='Fonte: U.S. Treasury · dati al '+date+' · contesto Rates, non un segnale autonomo risk-on/risk-off';
  document.documentElement.dataset.marketRiskRates='READY';
}).catch(()=>withheld('feed Rates non disponibile'));
})();