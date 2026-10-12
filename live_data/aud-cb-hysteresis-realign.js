(function(){
'use strict';

const clone=x=>{try{return JSON.parse(JSON.stringify(x))}catch{return null}};

async function realignAudCbHysteresis(){
  const state={
    status:'WITHHELD_NO_APPLY',
    currency:'AUD',
    changes_policy:false,
    changes_pair_logic:false,
    changes_bias:false,
    changes_sizing:false,
    before:null,
    after:null,
    reason:null
  };
  try{
    if(window.__GMFQ_CANONICAL_OVERLAY_READY) await window.__GMFQ_CANONICAL_OVERLAY_READY;
    if(typeof window.cbStructuralChangeCandidate!=='function' || typeof window.evaluateCbLiquidityHysteresis!=='function'){
      state.reason='native-cb-hysteresis-functions-unavailable';
      window.__GMFQ_AUD_CB_HYSTERESIS_REALIGN_STATE=Object.freeze(state);
      return;
    }
    const container=window.CB_LIQ_HYSTERESIS_STATE;
    const current=container?.AUD?.cb;
    const pure=clone(window.cbStructuralChangeCandidate('AUD'));
    state.before=clone(current);

    const exactStaleDiagnostic=
      current?.current===1 &&
      current?.candidate===0 &&
      current?.streak===0 &&
      current?.status==='PENDING_MARKET_CONFIRMATION' &&
      pure?.status==='CANDIDATE' &&
      pure?.candidate===current.current &&
      pure?.last_date==='2026-09-29';

    if(!exactStaleDiagnostic){
      state.status='NO_APPLY_NOT_NEEDED';
      state.reason='AUD CB diagnostic does not match the certified stale post-RBA state';
      state.after=clone(current);
      window.__GMFQ_AUD_CB_HYSTERESIS_REALIGN_STATE=Object.freeze(state);
      return;
    }

    const recalculated=window.evaluateCbLiquidityHysteresis('AUD');
    const next=clone(recalculated?.cb);
    const safeResult=
      next?.current===current.current &&
      next?.candidate===current.current &&
      next?.streak===0 &&
      next?.status==='NO_CHANGE';

    if(!safeResult){
      state.reason='native-recalculation-did-not-match-certified-no-change-contract';
      state.after=clone(current);
      window.__GMFQ_AUD_CB_HYSTERESIS_REALIGN_STATE=Object.freeze(state);
      return;
    }

    container.AUD.cb=recalculated.cb;
    state.status='PASS_REALIGNED_DIAGNOSTIC_ONLY';
    state.reason='Validated post-RBA pricing now yields the native NO_CHANGE diagnostic; structural Policy remains +1.';
    state.after=clone(container.AUD.cb);
    window.__GMFQ_AUD_CB_HYSTERESIS_REALIGN_STATE=Object.freeze(state);
  }catch(e){
    state.reason=String(e&&e.message||e);
    window.__GMFQ_AUD_CB_HYSTERESIS_REALIGN_STATE=Object.freeze(state);
    console.error('aud-cb-hysteresis-realign',e);
  }
}

realignAudCbHysteresis();
})();
