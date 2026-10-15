(()=>{
  'use strict';
  const SCHEMA='GMFQ_MACRO_OPERATIONAL_UI_V1';
  const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const CATS=['Crescita','Inflazione','Lavoro'];

  function selectedMacroCurrency(){
    return document.querySelector('#v232CurrencyCards .v232CurrencyCard.active')?.getAttribute('data-c') ||
      String(document.getElementById('v232CountryName')?.textContent||'').match(/\b(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)\b/)?.[1] || null;
  }
  function markOwners(){
    const macro=document.getElementById('macro');
    const heat=document.getElementById('inflationlabour');
    if(!macro||!heat) throw new Error('MACRO_VIEWS_MISSING');
    const macroAnchor=macro.querySelector('#v232CountryName');
    const heatAnchor=heat.querySelector('#il407Grid');
    if(!macroAnchor) throw new Error('MACRO_OWNER_ANCHOR_MISSING');
    if(!heatAnchor) throw new Error('INFLATIONLABOUR_OWNER_ANCHOR_MISSING');
    macroAnchor.setAttribute('data-gmfq-operational','macro');
    macroAnchor.setAttribute('data-owner',SCHEMA);
    heatAnchor.setAttribute('data-gmfq-operational','inflationlabour');
    heatAnchor.setAttribute('data-owner',SCHEMA);
    return {macroAnchor,heatAnchor};
  }
  function coverageAudit(){
    const cov=typeof window.macroBlockCoverage==='function'?window.macroBlockCoverage():null;
    const issues=[];
    if(!cov) return {ok:false,issues:['MACRO_BLOCK_COVERAGE_UNAVAILABLE'],coverage:null};
    for(const c of CCYS){
      for(const cat of CATS){
        const x=cov?.[c]?.[cat];
        if(!x||!(Number(x.count)>0)||!x.latest||!x.source) issues.push(`COVERAGE_${c}_${cat}`);
      }
    }
    return {ok:issues.length===0,issues,coverage:cov};
  }
  function audit(){
    const macro=document.getElementById('macro');
    const heat=document.getElementById('inflationlabour');
    const cards=[...document.querySelectorAll('#v232CurrencyCards .v232CurrencyCard')].map(x=>x.getAttribute('data-c')).filter(Boolean);
    const unique=[...new Set(cards)];
    const macroOwner=macro?.querySelectorAll('#v232CountryName[data-gmfq-operational="macro"]').length||0;
    const heatOwner=heat?.querySelectorAll('#il407Grid[data-gmfq-operational="inflationlabour"]').length||0;
    const selected=selectedMacroCurrency();
    const countryText=String(document.getElementById('v232CountryName')?.textContent||'');
    const integrity=typeof window.macroCategoryIntegrity==='function'?window.macroCategoryIntegrity():null;
    const cov=coverageAudit();
    const heatText=String(heat?.innerText||'');
    const issues=[];
    if(macroOwner!==1) issues.push('MACRO_OWNER_COUNT_'+macroOwner);
    if(heatOwner!==1) issues.push('INFLATIONLABOUR_OWNER_COUNT_'+heatOwner);
    if(cards.length!==8||unique.length!==8||CCYS.some(c=>!unique.includes(c))) issues.push('MACRO_G8_SELECTOR');
    if(!selected||!CCYS.includes(selected)||!countryText.includes(selected)) issues.push('MACRO_SELECTION_SYNC');
    if(integrity?.ok!==true) issues.push('MACRO_CATEGORY_INTEGRITY');
    if(!cov.ok) issues.push(...cov.issues);
    if(CCYS.some(c=>!heatText.includes(c))) issues.push('HEATMAP_G8_COVERAGE');
    return {
      schema:SCHEMA,status:issues.length?'FAIL':'ACTIVE',core_effect:'NONE',
      owner_type:'HYBRID_CANONICAL_RENDER_ADAPTER',macro_owner_count:macroOwner,
      inflationlabour_owner_count:heatOwner,currencies:unique,coverage:unique.length,
      selected_currency:selected,canonical_sources:['macroBlockCoverage(runtime)','macroCategoryIntegrity(runtime)','existing Macro/Heatmap renderers'],
      integrity,macro_block_coverage:cov.coverage,issues
    };
  }
  function sync(){
    markOwners();
    window.GMFQ_MACRO_OPERATIONAL=audit();
    if(window.GMFQ_MACRO_OPERATIONAL.status!=='ACTIVE') throw new Error('MACRO_OPERATIONAL_'+window.GMFQ_MACRO_OPERATIONAL.issues.join('_'));
    return window.GMFQ_MACRO_OPERATIONAL;
  }
  function wrap(name){
    const old=window[name];
    if(typeof old!=='function'||old.__gmfqMacroOperationalWrapped) return;
    const wrapped=function(){
      const out=old.apply(this,arguments);
      setTimeout(()=>{try{sync();}catch(e){window.GMFQ_MACRO_OPERATIONAL={schema:SCHEMA,status:'FAIL',core_effect:'NONE',error:String(e?.message||e)};}},0);
      return out;
    };
    wrapped.__gmfqMacroOperationalWrapped=true;
    window[name]=wrapped;
  }
  function boot(){
    let tries=0;
    const tick=()=>{
      tries++;
      try{
        if(window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true && typeof window.macroBlockCoverage==='function' && typeof window.macroCategoryIntegrity==='function'){
          ['renderMacroLab','renderInflationLabourSection','renderDynamicHeatmap'].forEach(wrap);
          sync();
          return;
        }
      }catch(e){window.GMFQ_MACRO_OPERATIONAL={schema:SCHEMA,status:'WAITING',core_effect:'NONE',error:String(e?.message||e)};}
      if(tries<240) setTimeout(tick,250);
      else window.GMFQ_MACRO_OPERATIONAL={schema:SCHEMA,status:'FAIL',core_effect:'NONE',error:'MACRO_OPERATIONAL_BOOT_TIMEOUT'};
    };
    tick();
  }
  window.gmfqMacroOperationalAudit=audit;
  window.gmfqSyncMacroOperational=sync;
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();
