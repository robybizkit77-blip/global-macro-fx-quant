(()=>{
  'use strict';
  const CARD_ID='gmfq-research-status-card';

  function el(tag, text){
    const node=document.createElement(tag);
    if(text!==undefined) node.textContent=String(text);
    return node;
  }

  function labelFor(item){
    const raw=String(item?.ui_label||item?.status||'RICERCA');
    return raw.replaceAll('_',' ');
  }

  function render(state){
    const host=document.getElementById('themes');
    if(!host || !state) return;

    const previous=document.getElementById(CARD_ID);
    if(previous) previous.remove();

    const card=el('details');
    card.id=CARD_ID;
    card.style.cssText='margin:0 0 16px;padding:12px 14px;border:1px solid rgba(148,163,184,.18);border-radius:12px;background:rgba(15,23,42,.72);color:inherit;font:inherit;';

    const summary=el('summary');
    summary.style.cssText='cursor:pointer;list-style:none;display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;';

    const titleWrap=el('span');
    titleWrap.style.cssText='display:flex;gap:8px;align-items:center;min-width:0;';
    const title=el('strong','RESEARCH / STATO QUANT');
    title.style.cssText='font-size:12px;letter-spacing:.06em;';
    const badge=el('span',String(state.research_signal_state||'WITHHELD'));
    badge.style.cssText='font-size:10px;font-weight:700;padding:3px 7px;border-radius:999px;border:1px solid rgba(245,158,11,.35);background:rgba(245,158,11,.10);white-space:nowrap;';
    titleWrap.append(title,badge);

    const headline=el('span',`Nessun segnale quant autorizzato · ${Number(state.context_only_count||state.context_only?.length||0)} elementi di contesto · peso decisionale 0`);
    headline.style.cssText='font-size:11px;opacity:.72;';
    summary.append(titleWrap,headline);
    card.append(summary);

    const body=el('div');
    body.style.cssText='padding-top:12px;display:grid;gap:8px;';

    for(const item of (Array.isArray(state.context_only)?state.context_only:[])){
      const row=el('div');
      row.style.cssText='display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 0;border-top:1px solid rgba(148,163,184,.10);';
      const name=el('span',String(item.id||'RESEARCH').replaceAll('_',' '));
      name.style.cssText='font-size:11px;opacity:.84;';
      const status=el('span',labelFor(item));
      status.style.cssText='font-size:10px;font-weight:700;opacity:.76;text-align:right;';
      row.append(name,status);
      body.append(row);
    }

    const guard=el('div','Non modifica bias, score o sizing.');
    guard.style.cssText='font-size:10px;opacity:.62;padding-top:2px;';
    body.append(guard);
    card.append(body);

    host.prepend(card);
  }

  window.addEventListener('gmfq:research-state-ready',event=>render(event.detail));
  if(window.__GMFQ_RESEARCH_STATE) render(window.__GMFQ_RESEARCH_STATE);
})();
