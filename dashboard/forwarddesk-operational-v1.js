(()=>{
  'use strict';
  function audit(){
    const root=document.getElementById('forwarddesk');
    const summary=typeof window.forwardValidationSummary==='function'?window.forwardValidationSummary():null;
    const integrity=typeof window.forwardLedgerIntegrity==='function'?window.forwardLedgerIntegrity():null;
    const helpers={
      pathRisk:typeof window.gmfqForwardPathRiskStats,
      snapshotBasket:typeof window.gmfqForwardSnapshotBasketSeries,
      pairedOverlay:typeof window.gmfqForwardPairedOverlayStats
    };
    const text=String(root?.innerText||'').replace(/\s+/g,' ').trim();
    const runtimeError=/\b[A-Za-z_$][\w$]*\s+is\s+not\s+defined\b|ReferenceError/i.test(text);
    const active=!!root&&text.length>=100&&helpers.pathRisk==='function'&&helpers.snapshotBasket==='function'&&helpers.pairedOverlay==='function'&&(!integrity||integrity.ok===true)&&!runtimeError;
    return {
      status:active?'ACTIVE':'WAITING',schema:'GMFQ_FORWARDDESK_OPERATIONAL_UI_V1',core_effect:'NONE',
      owner_count:document.querySelectorAll('#forwarddesk[data-gmfq-operational="forwarddesk"]').length,
      text_length:text.length,summary,integrity,helpers,runtime_error:runtimeError,
      scope:'OBSERVATIONAL_FORWARD_VALIDATION_ONLY'
    };
  }
  function certify(){
    const root=document.getElementById('forwarddesk');
    if(!root) throw new Error('FORWARDDESK_VIEW_MISSING');
    const a=audit();
    if(a.text_length<100) throw new Error('FORWARDDESK_NOT_RENDERED');
    if(a.helpers.pathRisk!=='function'||a.helpers.snapshotBasket!=='function'||a.helpers.pairedOverlay!=='function') throw new Error('FORWARDDESK_HELPER_CHAIN_INCOMPLETE');
    if(a.integrity&&a.integrity.ok!==true) throw new Error('FORWARDDESK_LEDGER_INTEGRITY_FAILED');
    if(a.runtime_error) throw new Error('FORWARDDESK_VISIBLE_RUNTIME_ERROR');
    root.setAttribute('data-gmfq-operational','forwarddesk');
    window.GMFQ_FORWARDDESK_OPERATIONAL={...audit(),status:'ACTIVE',owner_count:1};
    return window.GMFQ_FORWARDDESK_OPERATIONAL;
  }
  function boot(){
    let n=0;
    const tick=()=>{
      n++;
      try{
        if(window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true&&typeof window.forwardLedgerIntegrity==='function'&&typeof window.forwardValidationSummary==='function'){
          certify();return;
        }
      }catch(e){window.GMFQ_FORWARDDESK_OPERATIONAL={status:'WAITING',schema:'GMFQ_FORWARDDESK_OPERATIONAL_UI_V1',core_effect:'NONE',error:String(e?.message||e)};}
      if(n<240)setTimeout(tick,250);else window.GMFQ_FORWARDDESK_OPERATIONAL={status:'FAIL',schema:'GMFQ_FORWARDDESK_OPERATIONAL_UI_V1',core_effect:'NONE',error:'FORWARDDESK_OPERATIONAL_BOOT_TIMEOUT'};
    };
    tick();
  }
  window.gmfqForwardDeskOperationalAudit=audit;
  window.gmfqForwardDeskOperationalCertify=certify;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
