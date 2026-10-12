(function(){
'use strict';

const MAX_BUSINESS_LAG=1;
const clone=x=>{try{return JSON.parse(JSON.stringify(x))}catch{return null}};

function businessLag(from,to){
  if(!from||!to) return null;
  const a=new Date(String(from).slice(0,10)+'T12:00:00Z');
  const b=new Date(String(to).slice(0,10)+'T12:00:00Z');
  if(!Number.isFinite(a.getTime())||!Number.isFinite(b.getTime())) return null;
  if(!(a<b)) return 0;
  let d=new Date(a),n=0;
  while(d<b){
    d.setUTCDate(d.getUTCDate()+1);
    const wd=d.getUTCDay();
    if(wd!==0&&wd!==6)n++;
  }
  return n;
}

function install(){
  const state={status:'WITHHELD_NO_APPLY',max_business_lag:MAX_BUSINESS_LAG,changes_engine:false,changes_bias:false,changes_sizing:false,changes_pair_structure:false};
  try{
    if(typeof window.deriveGlobalRiskState!=='function'){
      state.reason='deriveGlobalRiskState unavailable';
      window.__GMFQ_RISK_FRESHNESS_GATE_STATE=Object.freeze(state);
      return;
    }
    const original=window.deriveGlobalRiskState;
    if(original.__gmfqFreshnessGuard===true){
      state.status='NO_APPLY_ALREADY_INSTALLED';
      state.reason='freshness guard already installed';
      window.__GMFQ_RISK_FRESHNESS_GATE_STATE=Object.freeze(state);
      return;
    }

    const guarded=function(){
      const base=original();
      const priceAsOf=window.D?.prices?.at?.(-1)?.Date||null;
      const vixAsOf=window.D?.risk?.VIX?.dates?.at?.(-1)||null;
      const brentAsOf=window.D?.risk?.Brent?.dates?.at?.(-1)||null;
      const vixLag=businessLag(vixAsOf,priceAsOf);
      const brentLag=businessLag(brentAsOf,priceAsOf);
      const stale=!!priceAsOf && ((vixLag!=null&&vixLag>MAX_BUSINESS_LAG)||(brentLag!=null&&brentLag>MAX_BUSINESS_LAG));
      if(!stale) return base;
      return {
        state:'WITHHELD',
        cls:'riskMixedTxt',
        detail:`Snapshot rischio non abbastanza recente rispetto al Price ${priceAsOf}. VIX ${vixAsOf||'—'} · Brent ${brentAsOf||'—'}.`,
        driver:'Freshness gate',
        affected:[],
        vix:base?.vix??null,
        brent1m:base?.brent1m??null,
        china:base?.china??null,
        freshness:{price_asof:priceAsOf,vix_asof:vixAsOf,brent_asof:brentAsOf,vix_business_lag:vixLag,brent_business_lag:brentLag,max_business_lag:MAX_BUSINESS_LAG}
      };
    };
    guarded.__gmfqFreshnessGuard=true;
    guarded.__gmfqOriginal=original;
    window.deriveGlobalRiskState=guarded;
    try{deriveGlobalRiskState=guarded}catch(e){}

    if(typeof window.rebuildCanonicalState==='function') window.rebuildCanonicalState();
    else { try{if(typeof rebuildCanonicalState==='function') rebuildCanonicalState()}catch(e){} }

    const current=clone(window.deriveGlobalRiskState());
    state.status=current?.state==='WITHHELD'?'PASS_WITHHELD_STALE_RISK':'PASS_FRESH_RISK_UNCHANGED';
    state.risk=current;
    state.reason=current?.state==='WITHHELD'?'Daily VIX/Brent exceed the certified freshness lag versus Price; risk overlay suppressed.':'Risk inputs are within the certified freshness lag.';
    window.__GMFQ_RISK_FRESHNESS_GATE_STATE=Object.freeze(state);
    window.dispatchEvent(new CustomEvent('gmfq:risk-freshness-ready',{detail:window.__GMFQ_RISK_FRESHNESS_GATE_STATE}));
  }catch(e){
    state.reason=String(e&&e.message||e);
    window.__GMFQ_RISK_FRESHNESS_GATE_STATE=Object.freeze(state);
    console.error('risk-freshness-gate',e);
  }
}

install();
})();
