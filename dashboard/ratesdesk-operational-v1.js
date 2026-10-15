(()=>{
  'use strict';
  const SCHEMA='GMFQ_RATESDESK_OPERATIONAL_UI_V1';
  const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];

  function selected(){
    return document.querySelector('#v233CurrencyCards .v233CurrencyCard.active')?.getAttribute('data-c') ||
      String(document.getElementById('v233CountryName')?.textContent||'').match(/\b(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)\b/)?.[1] || null;
  }
  function markOwner(){
    const root=document.getElementById('ratesdesk');
    if(!root) throw new Error('RATESDESK_VIEW_MISSING');
    const anchor=root.querySelector('#v233CountryName');
    if(!anchor) throw new Error('RATESDESK_OWNER_ANCHOR_MISSING');
    anchor.setAttribute('data-gmfq-operational','ratesdesk');
    anchor.setAttribute('data-owner',SCHEMA);
    return anchor;
  }
  function audit(){
    const root=document.getElementById('ratesdesk');
    const cards=[...document.querySelectorAll('#v233CurrencyCards .v233CurrencyCard')].map(x=>x.getAttribute('data-c')).filter(Boolean);
    const unique=[...new Set(cards)];
    const ownerCount=root?.querySelectorAll('#v233CountryName[data-gmfq-operational="ratesdesk"]').length||0;
    const timing=typeof window.ratesTimingBindingIntegrity==='function'?window.ratesTimingBindingIntegrity():null;
    const basis=typeof window.ratesCanonicalBasisIntegrity==='function'?window.ratesCanonicalBasisIntegrity():null;
    const visible=typeof window.visibleRatesSnapshotIntegrity==='function'?window.visibleRatesSnapshotIntegrity():null;
    const rates={};
    for(const c of CCYS){
      try{
        const s=window.rate2YSeries?.(c)||null;
        rates[c]={last_date:s?.dates?.at?.(-1)??null,last_value:s?.values?.at?.(-1)??null,mode:s?.same_basis_mode||null};
      }catch(e){rates[c]={error:String(e)};}
    }
    const c=selected();
    const country=String(document.getElementById('v233CountryName')?.textContent||'');
    const oisOwner=root?.querySelectorAll('#v401OisBlock[data-owner="GMFQ_OIS_OPERATIONAL_UI_V1"]').length||0;
    const issues=[];
    if(ownerCount!==1) issues.push('OWNER_COUNT_'+ownerCount);
    if(cards.length!==8||unique.length!==8||CCYS.some(x=>!unique.includes(x))) issues.push('G8_SELECTOR');
    if(!c||!CCYS.includes(c)||!country.includes(c)) issues.push('SELECTION_SYNC');
    if(timing?.ok!==true) issues.push('TIMING_INTEGRITY');
    if(basis?.ok!==true) issues.push('BASIS_INTEGRITY');
    if(visible?.ok!==true) issues.push('VISIBLE_INTEGRITY');
    if(CCYS.some(x=>!rates[x]?.last_date||rates[x]?.last_value==null)) issues.push('RATE2Y_COVERAGE');
    if(oisOwner!==1) issues.push('OIS_OWNER_COUNT_'+oisOwner);
    return {
      schema:SCHEMA,status:issues.length?'FAIL':'ACTIVE',core_effect:'NONE',
      owner_type:'HYBRID_CANONICAL_RENDER_ADAPTER',owner_count:ownerCount,
      ois_owner_count:oisOwner,currencies:unique,coverage:unique.length,selected_currency:c,
      canonical_sources:['rate2YSeries(runtime)','ratesTimingBindingIntegrity(runtime)','ratesCanonicalBasisIntegrity(runtime)','visibleRatesSnapshotIntegrity(runtime)','existing renderNativeRatesDesk runtime','GMFQ_OIS_OPERATIONAL_UI_V1'],
      rates2y:rates,timing_integrity:timing,basis_integrity:basis,visible_integrity:visible,issues
    };
  }
  function sync(){
    markOwner();
    window.GMFQ_RATESDESK_OPERATIONAL=audit();
    if(window.GMFQ_RATESDESK_OPERATIONAL.status!=='ACTIVE') throw new Error('RATESDESK_OPERATIONAL_'+window.GMFQ_RATESDESK_OPERATIONAL.issues.join('_'));
    return window.GMFQ_RATESDESK_OPERATIONAL;
  }
  function wrap(name){
    const old=window[name];
    if(typeof old!=='function'||old.__gmfqRatesOperationalWrapped) return;
    const wrapped=function(){
      const out=old.apply(this,arguments);
      setTimeout(()=>{try{sync();}catch(e){window.GMFQ_RATESDESK_OPERATIONAL={schema:SCHEMA,status:'FAIL',core_effect:'NONE',error:String(e?.message||e)};}},0);
      return out;
    };
    wrapped.__gmfqRatesOperationalWrapped=true;
    window[name]=wrapped;
  }
  function boot(){
    let tries=0;
    const tick=()=>{
      tries++;
      try{
        if(window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true && typeof window.rate2YSeries==='function' && typeof window.ratesTimingBindingIntegrity==='function' && typeof window.ratesCanonicalBasisIntegrity==='function' && typeof window.visibleRatesSnapshotIntegrity==='function' && window.GMFQ_OIS_OPERATIONAL_UI?.status==='READY'){
          ['renderNativeRatesDesk','selectNativeRates','v401RenderRatesLayers'].forEach(wrap);
          sync();
          return;
        }
      }catch(e){window.GMFQ_RATESDESK_OPERATIONAL={schema:SCHEMA,status:'WAITING',core_effect:'NONE',error:String(e?.message||e)};}
      if(tries<240) setTimeout(tick,250);
      else window.GMFQ_RATESDESK_OPERATIONAL={schema:SCHEMA,status:'FAIL',core_effect:'NONE',error:'RATESDESK_OPERATIONAL_BOOT_TIMEOUT'};
    };
    tick();
  }
  window.gmfqRatesDeskOperationalAudit=audit;
  window.gmfqSyncRatesDeskOperational=sync;
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();
