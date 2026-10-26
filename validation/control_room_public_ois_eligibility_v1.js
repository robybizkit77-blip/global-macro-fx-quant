'use strict';
// QA-only, immutable comparison of public OIS eligibility. Not a trading model.
const CURRENCIES=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const HORIZONS=['3m','6m','12m'];
const numeric=x=>typeof x==='number'&&Number.isFinite(x);
const dateAge=(asof,today)=>{
 if(!/^20\d{2}-\d{2}-\d{2}$/.test(asof||'')||!/^20\d{2}-\d{2}-\d{2}$/.test(today||''))return null;
 const a=Date.parse(asof+'T00:00:00Z'),t=Date.parse(today+'T00:00:00Z');
 if(!Number.isFinite(a)||!Number.isFinite(t)||new Date(a).toISOString().slice(0,10)!==asof||
    new Date(t).toISOString().slice(0,10)!==today)return null;
 return (t-a)/86400000;
};
function expectedOfficialCurrencies(operational,official,today){
 if(operational?.schema!=='GMFQ_OIS_OPERATIONAL_VIEW_V1'||
    !operational.currencies||!official?.currencies||
    CURRENCIES.some(c=>!operational.currencies[c]||!official.currencies[c]))
   throw Error('QA public OIS canonical G8 feed missing');
 const allowed=[];
 for(const c of CURRENCIES){
  const x=operational.currencies[c],source=official.currencies[c];
  const age=dateAge(x.as_of,today);
  const sourceEligible=x.operational_status==='GREEN_OFFICIAL'&&
    x.official_status==='ACTIVE'&&x.quality==='OFFICIAL_CERTIFIED'&&
    x.backtest_eligible_as_official===true&&
    age!==null&&age>=0&&age<=4&&
    HORIZONS.every(h=>numeric(x.horizons?.[h]?.rate)&&
       numeric(x.horizons?.[h]?.policy_delta_bp));
  if(sourceEligible){
   if(source.status!=='ACTIVE'||source.as_of!==x.as_of||
      HORIZONS.some(h=>!numeric(source.horizons?.[h]?.rate)||
       !numeric(source.horizons?.[h]?.policy_delta_bp)||
       Math.abs(source.horizons[h].rate-x.horizons[h].rate)>1e-8||
       Math.abs(source.horizons[h].policy_delta_bp-x.horizons[h].policy_delta_bp)>1e-8))
    throw Error('QA public certified OIS is not backed by canonical official source: '+c);
   allowed.push(c);
  }
 }
 return allowed;
}
module.exports={expectedOfficialCurrencies,dateAge};
