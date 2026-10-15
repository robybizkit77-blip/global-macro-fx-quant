(()=>{
  'use strict';
  const SCHEMA='GMFQ_OVERVIEW_ASOF_OPERATIONAL_V1';

  function priceAsOf(){
    return window.GMFQ_ECB_PRICE_AUDIT?.as_of || document.documentElement.getAttribute('data-price-asof') || null;
  }

  function relabelHero(){
    const snap=document.getElementById('ov387Snapshot');
    if(!snap) throw new Error('OVERVIEW_SNAPSHOT_MISSING');
    const d=priceAsOf();
    if(!d) throw new Error('PRICE_ASOF_MISSING');
    snap.textContent=`${d} · altri layer con data propria`;
    const box=snap.parentElement;
    if(box){
      for(const n of [...box.childNodes]){
        if(n.nodeType===Node.TEXT_NODE && /GIORNATA DATI/i.test(n.textContent||'')){
          n.textContent=(n.textContent||'').replace(/GIORNATA DATI/i,'PREZZO FX');
        }
      }
    }
    snap.setAttribute('data-gmfq-operational','overview-asof');
    snap.setAttribute('title','Data dell’ultimo fixing FX ufficiale disponibile. Macro, Rates, COT e altri layer mantengono ciascuno la propria data fonte.');
    return d;
  }

  function explainChfRates(){
    const dates=[...document.querySelectorAll('#overview .ov387RateDate')];
    let n=0;
    for(const el of dates){
      const row=el.closest('.ov387RateRow');
      if(!row || !/^CHF\b/.test((row.innerText||'').trim())) continue;
      if((el.textContent||'').trim()==='2026-09-30'){
        el.textContent='2026-09-30 · ultimo SNB validato';
        el.setAttribute('title','Ultimo snapshot 2Y/10Y SNB validato. Il feed ufficiale successivo è trattenuto perché l’export non restituisce osservazioni complete; nessun mix con fonti secondarie.');
        el.setAttribute('data-gmfq-source-state','SNB_LAST_VALIDATED');
        n++;
      }
    }
    return n;
  }

  function render(){
    const d=relabelHero();
    const chfLabels=explainChfRates();
    window.GMFQ_OVERVIEW_ASOF_OPERATIONAL={
      schema:SCHEMA,status:'ACTIVE',core_effect:'NONE',
      price_as_of:d,hero_authority:'GMFQ_ECB_PRICE_AUDIT.as_of',
      chf_rates_as_of:'2026-09-30',chf_rates_state:'SNB_LAST_VALIDATED_SOURCE_EXPORT_BLOCKED',
      chf_labels:chfLabels
    };
    return window.GMFQ_OVERVIEW_ASOF_OPERATIONAL;
  }

  function boot(){
    let tries=0;
    const tick=()=>{
      tries++;
      try{
        if(window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true && priceAsOf()){
          render(); return;
        }
      }catch(e){
        window.GMFQ_OVERVIEW_ASOF_OPERATIONAL={schema:SCHEMA,status:'WAITING',core_effect:'NONE',error:String(e?.message||e)};
      }
      if(tries<240) setTimeout(tick,250);
      else window.GMFQ_OVERVIEW_ASOF_OPERATIONAL={schema:SCHEMA,status:'FAIL',core_effect:'NONE',error:'OVERVIEW_ASOF_BOOT_TIMEOUT'};
    };
    tick();
  }

  window.gmfqRenderOverviewAsOf=render;
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();