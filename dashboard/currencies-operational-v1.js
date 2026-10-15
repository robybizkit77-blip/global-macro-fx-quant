(()=>{
  'use strict';
  const SCHEMA='GMFQ_CURRENCIES_OPERATIONAL_UI_V1';
  const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];

  function priceAsOf(){
    return window.GMFQ_ECB_PRICE_AUDIT?.as_of || document.documentElement.getAttribute('data-price-asof') || null;
  }
  function selected(){
    return document.querySelector('#currencyGrid .ccy.active')?.dataset?.c ||
      String(document.getElementById('v219CurrencyTitle')?.textContent||'').match(/\b(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)\b/)?.[1] || null;
  }
  function states(){
    const out={};
    for(const c of CCYS){
      try{out[c]=window.deriveCurrencyState?.(c)||null;}catch(e){out[c]=null;}
    }
    return out;
  }
  function markOwner(){
    const root=document.getElementById('currencies');
    if(!root) throw new Error('CURRENCIES_VIEW_MISSING');
    const hero=root.querySelector('.v224CurrencyHero');
    if(!hero) throw new Error('CURRENCIES_HERO_MISSING');
    hero.setAttribute('data-gmfq-operational','currencies');
    hero.setAttribute('data-owner',SCHEMA);
    return hero;
  }
  function audit(){
    const root=document.getElementById('currencies');
    const st=states();
    const cards=[...document.querySelectorAll('#currencyGrid .ccy')].map(x=>x.dataset?.c).filter(Boolean);
    const unique=[...new Set(cards)];
    const ownerCount=root?.querySelectorAll('.v224CurrencyHero[data-gmfq-operational="currencies"]').length||0;
    const c=selected();
    const title=String(document.getElementById('v219CurrencyTitle')?.textContent||'');
    const integrity=typeof window.currencyUiIntegrity==='function'?window.currencyUiIntegrity():null;
    const issues=[];
    if(ownerCount!==1) issues.push('OWNER_COUNT_'+ownerCount);
    if(cards.length!==8||unique.length!==8||CCYS.some(x=>!unique.includes(x))) issues.push('G8_CARDS');
    if(CCYS.some(x=>!st[x])) issues.push('CANONICAL_STATE_COVERAGE');
    if(!c||!CCYS.includes(c)) issues.push('SELECTED_CURRENCY');
    if(c&&!title.includes(c)) issues.push('SELECTED_TITLE_SYNC');
    if(integrity && integrity.ok!==true) issues.push('CURRENCY_UI_INTEGRITY');
    return {
      schema:SCHEMA,status:issues.length?'FAIL':'ACTIVE',core_effect:'NONE',
      owner_type:'HYBRID_CANONICAL_RENDER_ADAPTER',owner_count:ownerCount,
      currencies:unique,coverage:unique.length,selected_currency:c,
      price_as_of:priceAsOf(),canonical_state_source:'deriveCurrencyState(runtime)',
      renderer_source:'existing canonical renderCurrency runtime',
      legacy_technical_shell:'NON_OWNER_RETIRED',integrity,issues
    };
  }
  function sync(){
    markOwner();
    window.GMFQ_CURRENCIES_OPERATIONAL=audit();
    if(window.GMFQ_CURRENCIES_OPERATIONAL.status!=='ACTIVE') throw new Error('CURRENCIES_OPERATIONAL_'+window.GMFQ_CURRENCIES_OPERATIONAL.issues.join('_'));
    return window.GMFQ_CURRENCIES_OPERATIONAL;
  }
  function installWrapper(){
    const old=window.renderCurrency;
    if(typeof old!=='function'||old.__gmfqCurrenciesOperationalWrapped) return;
    const wrapped=function(){
      const out=old.apply(this,arguments);
      try{sync();}catch(e){window.GMFQ_CURRENCIES_OPERATIONAL={schema:SCHEMA,status:'FAIL',core_effect:'NONE',error:String(e?.message||e)};}
      return out;
    };
    wrapped.__gmfqCurrenciesOperationalWrapped=true;
    window.renderCurrency=wrapped;
  }
  function boot(){
    let tries=0;
    const tick=()=>{
      tries++;
      try{
        if(window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true && typeof window.deriveCurrencyState==='function' && typeof window.renderCurrency==='function'){
          installWrapper();
          try{window.renderCurrency();}catch(e){}
          sync();
          return;
        }
      }catch(e){window.GMFQ_CURRENCIES_OPERATIONAL={schema:SCHEMA,status:'WAITING',core_effect:'NONE',error:String(e?.message||e)};}
      if(tries<240) setTimeout(tick,250);
      else window.GMFQ_CURRENCIES_OPERATIONAL={schema:SCHEMA,status:'FAIL',core_effect:'NONE',error:'CURRENCIES_OPERATIONAL_BOOT_TIMEOUT'};
    };
    tick();
  }
  window.gmfqCurrenciesOperationalAudit=audit;
  window.gmfqSyncCurrenciesOperational=sync;
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();