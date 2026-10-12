(()=>{
  'use strict';
  const CARD_ID='gmfq-bank-research-card';

  function text(tag, value){
    const node=document.createElement(tag);
    node.textContent=String(value);
    return node;
  }

  function isSafe(state){
    return state?.state==='INFORMATIONAL_ONLY' &&
      state?.decision_weight===0 &&
      state?.may_modify_pair_bias===false &&
      state?.may_modify_currency_score===false &&
      state?.may_modify_sizing===false &&
      state?.may_create_direction===false &&
      Array.isArray(state?.records);
  }

  function render(state){
    const host=document.getElementById('themes');
    if(!host || !isSafe(state)) return;
    document.getElementById(CARD_ID)?.remove();

    const card=text('details','');
    card.id=CARD_ID;
    card.style.cssText='margin:0 0 16px;padding:12px 14px;border:1px solid rgba(148,163,184,.18);border-radius:12px;background:rgba(15,23,42,.72);color:inherit;font:inherit;';
    const summary=text('summary','BANCHE CENTRALI · CONTESTO RICERCA — osservazioni e provenance, peso decisionale 0');
    summary.style.cssText='cursor:pointer;font-size:12px;font-weight:700;letter-spacing:.04em;';
    card.append(summary);
    const body=text('div','');
    body.style.cssText='display:grid;gap:7px;padding-top:12px;';
    for(const item of state.records){
      const row=text('div',`${item.currency} · ${item.bank} · ultima decisione ${item.last_decision_date}: ${item.observed_policy_action} · pricing ${item.market_pricing.freshness_status}`);
      row.style.cssText='font-size:11px;opacity:.82;padding-top:7px;border-top:1px solid rgba(148,163,184,.10);';
      body.append(row);
    }
    const guard=text('div','Non crea direzioni e non modifica bias, score o sizing.');
    guard.style.cssText='font-size:10px;opacity:.62;padding-top:2px;';
    body.append(guard);
    card.append(body);
    host.prepend(card);
  }

  window.addEventListener('gmfq:bank-research-state-ready', event=>render(event.detail));
  if(window.__GMFQ_BANK_RESEARCH_STATE) render(window.__GMFQ_BANK_RESEARCH_STATE);
})();
