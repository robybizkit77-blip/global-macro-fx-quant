(()=>{
  'use strict';
  const SCHEMA='GMFQ_LIQUIDITYDESK_OPERATIONAL_UI_V1';
  const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];

  function selected(){
    return document.querySelector('#v243CurrencyCards .v234CurrencyCard.active')?.getAttribute('data-c') ||
      String(document.getElementById('v243CountryName')?.textContent||'').match(/\b(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)\b/)?.[1] || null;
  }
  function markOwner(){
    const root=document.getElementById('liquiditydesk');
    if(!root) throw new Error('LIQUIDITYDESK_VIEW_MISSING');
    const anchor=root.querySelector('#v243CountryName');
    if(!anchor) throw new Error('LIQUIDITYDESK_OWNER_ANCHOR_MISSING');
    anchor.setAttribute('data-gmfq-operational','liquiditydesk');
    anchor.setAttribute('data-owner',SCHEMA);
    return anchor;
  }
  function healthSlices(){
    try{
      const h=typeof window.productionHealthCheck==='function'?window.productionHealthCheck():null;
      return {
        liquidity_freshness:h?.live_freshness_integrity?.live?.LIQUIDITY||null,
        live_freshness_ok:h?.live_freshness_integrity?.ok===true,
        overlay_isolation_ok:h?.overlay_isolation_integrity?.ok===true,
        risk_event_isolation_ok:h?.risk_event_isolation_integrity?.ok===true,
        unrelated_top_status:h?.status||null
      };
    }catch(e){return {error:String(e),live_freshness_ok:false,overlay_isolation_ok:false};}
  }
  function candidate(c){
    try{return typeof window.liquidityStructuralChangeCandidate==='function'?window.liquidityStructuralChangeCandidate(c):null;}
    catch(e){return {error:String(e)};}
  }
  function audit(){
    const root=document.getElementById('liquiditydesk');
    const data=window.__GMFQ_DATA?.NATIVE_LIQ_DATA||null;
    const cards=[...document.querySelectorAll('#v243CurrencyCards .v234CurrencyCard')].map(x=>x.getAttribute('data-c')).filter(Boolean);
    const unique=[...new Set(cards)];
    const ownerCount=root?.querySelectorAll('#v243CountryName[data-gmfq-operational="liquiditydesk"]').length||0;
    const c=selected();
    const country=String(document.getElementById('v243CountryName')?.textContent||'');
    const hs=healthSlices();
    const coverage={};
    const candidates={};
    for(const x of CCYS){
      const row=data?.[x]||null;
      const fresh=hs?.liquidity_freshness?.per_currency?.[x]||null;
      const cand=candidate(x);
      coverage[x]={
        status:row?.status||null,
        liquidity_dir:row?.liquidity_dir||null,
        as_of:row?.as_of||row?.latest_observation||fresh?.latest_observation||null,
        latest_observation:fresh?.latest_observation||null,
        freshness_status:fresh?.status||null
      };
      candidates[x]=cand;
    }
    const issues=[];
    if(ownerCount!==1) issues.push('OWNER_COUNT_'+ownerCount);
    if(cards.length!==8||unique.length!==8||CCYS.some(x=>!unique.includes(x))) issues.push('G8_SELECTOR');
    if(!c||!CCYS.includes(c)||!country.includes(c)) issues.push('SELECTION_SYNC');
    if(!data||CCYS.some(x=>!data[x])) issues.push('NATIVE_LIQ_DATA_COVERAGE');
    for(const x of CCYS){
      const row=coverage[x];
      if(row.status!=='COMPLETO') issues.push('DATA_STATUS_'+x);
      if(!row.liquidity_dir||/NON DISPONIBILE|WITHHELD/i.test(String(row.liquidity_dir))) issues.push('LIQ_DIRECTION_'+x);
      if(!row.latest_observation) issues.push('FRESHNESS_DATE_'+x);
      if(row.freshness_status!=='COMPLETO') issues.push('FRESHNESS_STATUS_'+x);
      const cand=candidates[x];
      if(!cand||cand.status==='WITHHELD'||cand.error) issues.push('STRUCTURAL_CANDIDATE_'+x);
    }
    if(hs.live_freshness_ok!==true) issues.push('LIVE_FRESHNESS_INTEGRITY');
    if(hs.overlay_isolation_ok!==true) issues.push('OVERLAY_ISOLATION_INTEGRITY');
    const visible=String(root?.innerText||'');
    if(!visible||visible.length<100) issues.push('VISIBLE_CONTENT');
    return {
      schema:SCHEMA,status:issues.length?'FAIL':'ACTIVE',core_effect:'NONE',
      owner_type:'HYBRID_CANONICAL_RENDER_ADAPTER',owner_count:ownerCount,
      currencies:unique,coverage_count:unique.length,selected_currency:c,
      canonical_sources:['NATIVE_LIQ_DATA(runtime)','liquidityStructuralChangeCandidate(runtime)','productionHealthCheck.live_freshness_integrity.LIQUIDITY','productionHealthCheck.overlay_isolation_integrity','existing renderNativeLiquidityDesk runtime'],
      freshness_policy:'SOURCE_NATIVE_CADENCE_HOLD_LAST_VALID_COMPONENT',
      coverage,candidates,integrity:{live_freshness_ok:hs.live_freshness_ok,overlay_isolation_ok:hs.overlay_isolation_ok,risk_event_isolation_ok:hs.risk_event_isolation_ok},
      unrelated_health_top_status:hs.unrelated_top_status,issues
    };
  }
  function sync(){
    markOwner();
    const a=audit();
    window.GMFQ_LIQUIDITYDESK_OPERATIONAL=a;
    if(a.status!=='ACTIVE') throw new Error('LIQUIDITYDESK_OPERATIONAL_'+a.issues.join('_'));
    return a;
  }
  function wrap(name){
    const old=window[name];
    if(typeof old!=='function'||old.__gmfqLiquidityOperationalWrapped) return;
    const wrapped=function(){
      const out=old.apply(this,arguments);
      setTimeout(()=>{try{sync();}catch(e){window.GMFQ_LIQUIDITYDESK_OPERATIONAL={schema:SCHEMA,status:'FAIL',core_effect:'NONE',error:String(e?.message||e)};}},0);
      return out;
    };
    wrapped.__gmfqLiquidityOperationalWrapped=true;
    window[name]=wrapped;
  }
  function installClickSync(){
    const box=document.getElementById('v243CurrencyCards');
    if(!box||box.dataset.gmfqLiquidityOperationalBound==='true') return;
    box.dataset.gmfqLiquidityOperationalBound='true';
    box.addEventListener('click',e=>{
      if(!e.target.closest('.v234CurrencyCard[data-c]')) return;
      setTimeout(()=>{try{sync();}catch(err){window.GMFQ_LIQUIDITYDESK_OPERATIONAL={schema:SCHEMA,status:'FAIL',core_effect:'NONE',error:String(err?.message||err)};}},40);
    },true);
  }
  function boot(){
    let tries=0;
    const tick=()=>{
      tries++;
      try{
        if(window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true && window.__GMFQ_DATA?.NATIVE_LIQ_DATA && typeof window.renderNativeLiquidityDesk==='function' && typeof window.liquidityStructuralChangeCandidate==='function' && typeof window.productionHealthCheck==='function'){
          wrap('renderNativeLiquidityDesk');
          installClickSync();
          try{window.renderNativeLiquidityDesk();}catch(e){}
          sync();
          return;
        }
      }catch(e){window.GMFQ_LIQUIDITYDESK_OPERATIONAL={schema:SCHEMA,status:'WAITING',core_effect:'NONE',error:String(e?.message||e)};}
      if(tries<240) setTimeout(tick,250);
      else window.GMFQ_LIQUIDITYDESK_OPERATIONAL={schema:SCHEMA,status:'FAIL',core_effect:'NONE',error:'LIQUIDITYDESK_OPERATIONAL_BOOT_TIMEOUT'};
    };
    tick();
  }
  window.gmfqLiquidityDeskOperationalAudit=audit;
  window.gmfqSyncLiquidityDeskOperational=sync;
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();
