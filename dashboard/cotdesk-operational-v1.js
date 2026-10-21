(()=>{
  'use strict';
  const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const CERTIFIED_FIELDS=['date','release_date','net','long','short','net_oi','pct','chg_net_1w','chg_net_4w','chg_long_1w','chg_short_1w','chg_long_4w','chg_short_4w','dates','net_series','long_series','short_series','state_label','flow','comment','posizionamento affollato'];
  const clone=x=>JSON.parse(JSON.stringify(x));
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const threshold=(name,fallback)=>Number((typeof MODEL_RULES!=='undefined'&&MODEL_RULES?.cot?.[name])??fallback);
  const stateLabel=p=>{const r=Math.round(p);return r>=threshold('extremeHigh',80)?'EXTREME LONG':r<=threshold('extremeLow',20)?'EXTREME SHORT':'NEUTRALE'};
  const crowdLabel=n=>Math.abs(n)>=threshold('netOiConcentration',30)?'⚠ Squilibrio ≥30%':'Nessun squilibrio ≥30%';
  const flowLabel=(dNet,dLong,dShort)=>{
    if(dLong>0&&dShort>0) return dShort>dLong?'Nuovi short dominanti':'Nuovi long dominanti';
    if(dLong>0&&dShort<=0) return 'Long in aumento / short in calo';
    if(dLong<=0&&dShort>0) return 'Long in calo / short in aumento';
    if(dNet>0) return 'Net migliora';
    if(dNet<0) return 'Net peggiora';
    return 'Flusso invariato';
  };
  function seriesAuthority(){
    if(typeof V250_COT_CHART_DATA==='undefined'||!V250_COT_CHART_DATA) throw new Error('COT_V250_AUTHORITY_MISSING');
    if(typeof V247_COT_STORIES==='undefined'||!V247_COT_STORIES) throw new Error('COT_V247_AUTHORITY_MISSING');
    return {series:V250_COT_CHART_DATA,stories:V247_COT_STORIES};
  }
  function structuralSnapshot(){
    const currencies={};
    for(const c of CCYS){
      const s=typeof deriveCurrencyState==='function'?deriveCurrencyState(c):null;
      currencies[c]=s?{base:s.base,macro:s.macro,policy:s.policy,policyContext:s.policyContext}:null;
    }
    const pairs={};
    const names=(typeof D!=='undefined'&&Array.isArray(D.pairs)&&D.pairs.length===28)?D.pairs.map(x=>x.pair):null;
    const universe=names||CCYS.flatMap((a,i)=>CCYS.slice(i+1).map(b=>a+'/'+b));
    for(const p of universe){
      const f=typeof derivePairDecisionFrame==='function'?derivePairDecisionFrame(p):null;
      pairs[p]=f?{fav:f.fav,quality:f.quality,structural:clone(f.structural||null)}:null;
    }
    return {currencies,pairs};
  }
  function buildCurrent(c,s,story){
    const n=s?.dates?.length||0;
    if(n!==104) throw new Error('COT_WINDOW_NOT_104:'+c+':'+n);
    for(const k of ['net','long','short','netoi','percentile']) if(!Array.isArray(s[k])||s[k].length!==n) throw new Error('COT_SERIES_INVALID:'+c+':'+k);
    const last=n-1, p1=n-2, p4=n-5;
    const date=String(s.dates[last]);
    const net=Number(s.net[last]), long=Number(s.long[last]), short=Number(s.short[last]);
    const netoi=Number(s.netoi[last]), pct=Number(s.percentile[last]);
    if(!date||![net,long,short,netoi,pct].every(Number.isFinite)) throw new Error('COT_CURRENT_INVALID:'+c);
    const dNet=net-Number(s.net[p1]), dNet4=net-Number(s.net[p4]);
    const dLong=long-Number(s.long[p1]), dLong4=long-Number(s.long[p4]);
    const dShort=short-Number(s.short[p1]), dShort4=short-Number(s.short[p4]);
    return {
      date,release_date:date,net,long,short,net_oi:netoi,pct,
      chg_net_1w:dNet,chg_net_4w:dNet4,chg_long_1w:dLong,chg_short_1w:dShort,chg_long_4w:dLong4,chg_short_4w:dShort4,
      dates:[...s.dates],net_series:[...s.net],long_series:[...s.long],short_series:[...s.short],
      state_label:stateLabel(pct),flow:flowLabel(dNet,dLong,dShort),
      comment:[story?.today,story?.w1,story?.w4].filter(Boolean).join(' '),
      'posizionamento affollato':crowdLabel(netoi)
    };
  }
  function renderConsumers(selected){
    try{if(typeof renderCotMap==='function')renderCotMap();}catch(e){}
    try{if(typeof v245RenderCards==='function')v245RenderCards();}catch(e){}
    try{
      if(typeof v245Select==='function'&&selected) v245Select(selected);
      else if(typeof renderCot==='function') renderCot();
    }catch(e){}
    try{if(typeof renderCurrencyMarketPanel==='function')renderCurrencyMarketPanel();}catch(e){}
    try{if(typeof refreshProductionSnapshotLabels==='function')refreshProductionSnapshotLabels();}catch(e){}
  }
  function sync(){
    if(typeof D==='undefined'||!D?.cot) throw new Error('COT_LEGACY_CONTEXT_MISSING');
    const {series,stories}=seriesAuthority();
    if(new Set(Object.keys(series)).size!==8||CCYS.some(c=>!series[c]||!stories[c])) throw new Error('COT_G8_AUTHORITY_INCOMPLETE');
    const dates=new Set(CCYS.map(c=>String(series[c].dates?.at(-1)||'')));
    if(dates.size!==1||[...dates][0]==='') throw new Error('COT_CROSS_CURRENCY_DATE_MISMATCH');
    const currentAsOf=[...dates][0];
    const beforeStructural=structuralSnapshot();
    const backup=clone(D.cot);
    const previousAsOf=Object.fromEntries(CCYS.map(c=>[c,String(D.cot?.[c]?.release_date||D.cot?.[c]?.date||'') ]));
    try{
      for(const c of CCYS){
        D.cot[c]=D.cot[c]||{};
        const cur=buildCurrent(c,series[c],stories[c]);
        for(const f of CERTIFIED_FIELDS) D.cot[c][f]=clone(cur[f]);
      }
      const afterStructural=structuralSnapshot();
      if(!same(beforeStructural,afterStructural)) throw new Error('COT_OVERLAY_CHANGED_STRUCTURAL_OUTPUT');
      const isolation=typeof overlayIsolationIntegrity==='function'?overlayIsolationIntegrity():null;
      if(isolation&&isolation.ok!==true) throw new Error('COT_OVERLAY_ISOLATION_FAILED:'+JSON.stringify(isolation.issues||[]));
      const selected=(typeof v245CotSelected!=='undefined'&&CCYS.includes(v245CotSelected))?v245CotSelected:'EUR';
      renderConsumers(selected);
      const owner=document.getElementById('v247CountryName');
      if(!owner) throw new Error('COT_OWNER_ANCHOR_MISSING');
      owner.setAttribute('data-gmfq-operational','cot');
      owner.setAttribute('data-gmfq-cot-asof',currentAsOf);
      const coverage={};
      for(const c of CCYS){coverage[c]={as_of:D.cot[c].release_date,net:D.cot[c].net,net_oi:D.cot[c].net_oi,pct:D.cot[c].pct,chg_net_1w:D.cot[c].chg_net_1w,state_label:D.cot[c].state_label,price_confirmation:stories[c].price};}
      window.GMFQ_COTDESK_OPERATIONAL={
        status:'ACTIVE',schema:'GMFQ_COTDESK_OPERATIONAL_UI_V1',core_effect:'NONE',authority:'V250_COT_CHART_DATA + V247_COT_STORIES',
        current_as_of:currentAsOf,previous_as_of:previousAsOf,currency_count:8,window_weeks:104,coverage,
        structural_unchanged:true,overlay_isolation_ok:isolation?isolation.ok:true,
        synchronized_fields:[...CERTIFIED_FIELDS],preserved_legacy_fields:['open_interest','oi_series'],
        price_confirmation_policy:'WITHHELD_UNLESS_SEPARATELY_VALIDATED'
      };
      return window.GMFQ_COTDESK_OPERATIONAL;
    }catch(e){
      Object.keys(D.cot).forEach(k=>delete D.cot[k]); Object.assign(D.cot,backup);
      window.GMFQ_COTDESK_OPERATIONAL={status:'FAIL',schema:'GMFQ_COTDESK_OPERATIONAL_UI_V1',core_effect:'NONE',error:String(e?.message||e)};
      throw e;
    }
  }
  function audit(){
    const s=window.GMFQ_COTDESK_OPERATIONAL||{status:'WAITING',schema:'GMFQ_COTDESK_OPERATIONAL_UI_V1',core_effect:'NONE'};
    const owner=document.querySelectorAll('#cot #v247CountryName[data-gmfq-operational="cot"]');
    return {...s,owner_count:owner.length,selected_currency:String(document.getElementById('v247CountryName')?.textContent||'').trim().slice(0,3)};
  }
  function boot(){
    let n=0;
    const tick=()=>{
      n++;
      try{
        if(window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true&&typeof D!=='undefined'&&D?.cot&&typeof V250_COT_CHART_DATA!=='undefined'&&typeof V247_COT_STORIES!=='undefined'){
          sync();return;
        }
      }catch(e){if(window.GMFQ_COTDESK_OPERATIONAL?.status==='FAIL')return;window.GMFQ_COTDESK_OPERATIONAL={status:'WAITING',schema:'GMFQ_COTDESK_OPERATIONAL_UI_V1',core_effect:'NONE',error:String(e?.message||e)};}
      if(n<240)setTimeout(tick,250);else window.GMFQ_COTDESK_OPERATIONAL={status:'FAIL',schema:'GMFQ_COTDESK_OPERATIONAL_UI_V1',core_effect:'NONE',error:'COT_OPERATIONAL_BOOT_TIMEOUT'};
    };
    tick();
  }
  window.gmfqCotDeskOperationalSync=sync;
  window.gmfqCotDeskOperationalAudit=audit;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
