(()=>{
  'use strict';
  const CSS = `
  .fxMRGrid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:10px}
  .fxMRCard{background:#071a28;border:1px solid #27495a;border-radius:9px;padding:11px 12px}
  .fxMRCard.pos{border-color:rgba(111,223,168,.38)}
  .fxMRCard.neg{border-color:rgba(211,139,255,.38)}
  .fxMRCard.warn{border-color:rgba(240,201,107,.42)}
  .fxMRCard.neu{border-color:#27495a}
  .fxMRLabel{font-size:8px;font-weight:900;letter-spacing:.07em;color:#7398a8}
  .fxMRTrend{display:block;font-size:12px;font-weight:900;line-height:1.35;margin-top:5px}
  .fxMRCard.pos .fxMRTrend{color:#6fdfa8}.fxMRCard.neg .fxMRTrend{color:#d38bff}
  .fxMRCard.warn .fxMRTrend{color:#f0c96b}.fxMRCard.neu .fxMRTrend{color:#a7bbc4}
  .fxMRText{display:block;font-size:9.5px;line-height:1.45;color:#9bb4bf;margin-top:5px}
  .fxCardLayers{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:7px;padding-top:7px;border-top:1px solid #17394c}
  .fxCardLayer{display:flex;flex-direction:column;gap:2px;min-width:0}
  .fxCardLayer i{font-style:normal;font-size:7px;font-weight:900;letter-spacing:.055em;color:#668a9a}
  .fxCardLayer b{font-size:8.5px!important;line-height:1.25}
  .fxCardLayer b.pos{color:#6fdfa8}.fxCardLayer b.neg{color:#d38bff}.fxCardLayer b.warn{color:#f0c96b}.fxCardLayer b.neu{color:#a7bbc4}
  @media(max-width:760px){.fxMRGrid{grid-template-columns:1fr}}
  `;

  function addCss(){
    if(document.getElementById('fxMacroRatesCss')) return;
    const s=document.createElement('style'); s.id='fxMacroRatesCss'; s.textContent=CSS; document.head.appendChild(s);
  }
  function cls(x){return x?.cls||'neu'}
  function label(x){return (x?.label||'—').replace(/^\s*[↑↓→]\s*/,'')}
  function ensureHeroSplit(){
    const hero=document.querySelector('#currencies .v224CurrencyHero');
    const headline=document.querySelector('#v224Headline');
    if(!hero||!headline) return null;
    let box=document.getElementById('fxMacroRatesSplit');
    if(!box){
      box=document.createElement('div'); box.id='fxMacroRatesSplit'; box.className='fxMRGrid';
      headline.insertAdjacentElement('afterend',box);
    }
    return box;
  }
  function updateHeroSplit(){
    if(typeof window.v219MacroTrend!=='function' || typeof window.v219RatesTrend!=='function') return;
    const c=window.selectedCcy || document.querySelector('#v219CurrencyTitle')?.textContent?.trim().slice(-3) || 'USD';
    const mt=window.v219MacroTrend(c), rt=window.v219RatesTrend(c);
    const ms=typeof window.v224MacroSummary==='function'?window.v224MacroSummary(c):{text:mt.note||'',cls:mt.cls};
    const rs=typeof window.v224RatesSummary==='function'?window.v224RatesSummary(c):{text:rt.note||'',cls:rt.cls};
    const box=ensureHeroSplit(); if(!box)return;
    box.innerHTML=`
      <div class="fxMRCard ${cls(ms)}"><span class="fxMRLabel">MACRO · DIREZIONE</span><b class="fxMRTrend">${label(mt)}</b><span class="fxMRText">${ms.text||mt.note||'—'}</span></div>
      <div class="fxMRCard ${cls(rs)}"><span class="fxMRLabel">RATES · FRONT-END</span><b class="fxMRTrend">${label(rt)}</b><span class="fxMRText">${rs.text||rt.note||'—'}</span></div>`;
    const ratesName=document.querySelector('#v219RatesLayer .v224LayerName');
    if(ratesName) ratesName.textContent='RATES / FRONT-END';
    const sec=document.querySelector('#currencies .v219SectionHead span');
    if(sec) sec.textContent='Macro e Rates sono letti separatamente. Poi controlla COT e Price.';
  }
  function enhanceCards(){
    if(typeof window.v219MacroTrend!=='function' || typeof window.v219RatesTrend!=='function') return;
    document.querySelectorAll('#currencyGrid .ccy').forEach(card=>{
      const c=card.dataset.c; if(!c)return;
      const mt=window.v219MacroTrend(c), rt=window.v219RatesTrend(c);
      let x=card.querySelector('.fxCardLayers');
      if(!x){x=document.createElement('div');x.className='fxCardLayers';card.appendChild(x)}
      x.innerHTML=`<span class="fxCardLayer"><i>MACRO</i><b class="${cls(mt)}">${label(mt)}</b></span><span class="fxCardLayer"><i>RATES</i><b class="${cls(rt)}">${label(rt)}</b></span>`;
    });
  }
  function refresh(){addCss();updateHeroSplit();enhanceCards()}
  function install(){
    addCss();
    if(typeof window.renderCurrency==='function' && !window.renderCurrency.__fxMRWrapped){
      const original=window.renderCurrency;
      const wrapped=function(){const r=original.apply(this,arguments);setTimeout(refresh,0);return r};
      wrapped.__fxMRWrapped=true; window.renderCurrency=wrapped;
    }
    refresh();
    setTimeout(refresh,100);
    setTimeout(refresh,500);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install,{once:true}); else install();
})();

(()=>{
  'use strict';

  const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const LABEL_TO_KEY={
    'Macro':'macro',
    'Rates':'rates',
    'Banca centrale':'central_bank',
    'COT':'cot',
    'Prezzo':'price'
  };

  function reversePairLocal(pair){
    const x=String(pair||'').split('/');
    return x.length===2 ? x[1]+'/'+x[0] : pair;
  }

  function getRuntimePair(pair){
    if(typeof D==='undefined' || !D.pairStates) return null;
    if(D.pairStates[pair]) return {pair,state:D.pairStates[pair],reversed:false};
    const rev=reversePairLocal(pair);
    if(D.pairStates[rev]) return {pair,state:D.pairStates[rev],reversed:true,sourcePair:rev};
    return null;
  }

  function sideForCurrency(pair,value){
    const [a,b]=String(pair||'').split('/');
    if(value===a) return 'A';
    if(value===b) return 'B';
    if(value==='MISTO') return 'MIXED';
    if(value==='NON CONFRONTABILE') return 'WITHHELD';
    return value||'MIXED';
  }

  function runtimeLeadKey(label){
    return LABEL_TO_KEY[label] || (
      label==='Rates / aspettative CB' ? 'rates' :
      label==='Banca centrale / aspettative policy' ? 'central_bank' :
      null
    );
  }

  function runtimeCertifiedAdapter(pair){
    const hit=getRuntimePair(pair);
    if(!hit) return null;

    const st=hit.state;
    const [a,b]=String(pair||'').split('/');
    const layerDirs={};
    for(const [k,v] of Object.entries(st.layers||{})){
      layerDirs[k]=sideForCurrency(pair,v);
    }

    const leadLabel=(st.lead||[])[0]||null;
    const leadKey=runtimeLeadKey(leadLabel);
    const leadCurrency=leadKey ? st.layers?.[leadKey] : null;
    const leadSide=sideForCurrency(pair,leadCurrency);
    const priceSide=sideForCurrency(pair,st.layers?.price);

    const driver =
      leadLabel==='Rates' ? 'RATES' :
      leadLabel==='Banca centrale' ? 'CENTRAL_BANK' :
      leadLabel==='Macro' ? 'MACRO' :
      leadLabel==='COT' ? 'COT' :
      'UNCLEAR';

    let priceConfirmation='PRICE_UNCLEAR';
    if((leadSide==='A'||leadSide==='B') && (priceSide==='A'||priceSide==='B')){
      priceConfirmation=leadSide===priceSide?'PRICE_CONFIRMED':'PRICE_DIVERGES';
    }

    return {
      pair,
      source:'RUNTIME_D_PAIR_STATES',
      source_pair:hit.sourcePair||pair,
      state:st.state,
      state_label:st.state_label,
      lead:(st.lead||[]).map(x=>String(x).toLowerCase()),
      confirms:(st.confirms||[]).map(x=>String(x).toLowerCase().replace('banca centrale','central_bank')),
      diverges:(st.diverges||[]).map(x=>String(x).toLowerCase().replace('banca centrale','central_bank')),
      lags:(st.lags||[]).map(x=>String(x).toLowerCase().replace('banca centrale','central_bank')),
      layer_directions:layerDirs,
      cot_concentration_alert:st.cot_alert||'NONE',
      market_pricing_relative:st.pricing_raw||'WITHHELD',
      dominant_driver_current:{
        driver,
        direction:(leadSide==='A'||leadSide==='B')?leadSide:'MIXED',
        label_it:leadLabel||'Non determinato',
        price_confirmation:priceConfirmation
      },
      runtime_state:st
    };
  }

  function runtimePairDriverStructure(pair){
    const hit=getRuntimePair(pair);
    if(!hit){
      return {driver:'Non determinato',codriver:null,lead:'Non determinato',reason:'pair runtime non disponibile',side:null,source:'runtime'};
    }
    const st=hit.state;
    const lead=(st.lead||[])[0]||'Non determinato';
    const key=runtimeLeadKey(lead);
    const leadCcy=key ? st.layers?.[key] : null;
    const driver =
      lead==='Rates' ? 'Rates / aspettative CB' :
      lead==='Banca centrale' ? 'Banca centrale / aspettative policy' :
      lead==='Macro' ? 'Macro' :
      lead==='COT' ? 'COT / posizionamento' :
      'Non determinato';

    const coreConfirms=(st.confirms||[]).filter(x=>['Macro','Rates','Banca centrale'].includes(x) && x!==lead);
    const codriver=coreConfirms.length ? (
      coreConfirms[0]==='Rates'?'Rates / aspettative CB':
      coreConfirms[0]==='Banca centrale'?'Banca centrale / aspettative policy':
      coreConfirms[0]
    ) : null;

    return {
      driver,
      codriver,
      lead,
      reason:'Fonte corrente: D.pairStates runtime. Snapshot certificati storici esclusi dal percorso decisionale live.',
      side:leadCcy,
      certifiedDriver:lead,
      source:'RUNTIME_D_PAIR_STATES'
    };
  }

  function runtimeOverviewSync(){
    if(typeof D==='undefined' || !D.pairStates) return;
    const counts={rates:0,central_bank:0,macro:0,cot:0,unclear:0};
    Object.values(D.pairStates).forEach(st=>{
      const lead=(st.lead||[])[0]||'';
      if(lead==='Rates') counts.rates++;
      else if(lead==='Banca centrale') counts.central_bank++;
      else if(lead==='Macro') counts.macro++;
      else if(lead==='COT') counts.cot++;
      else counts.unclear++;
    });
    const policyFamily=counts.rates+counts.central_bank;
    const total=Math.max(1,policyFamily+counts.macro+counts.cot+counts.unclear);
    const set=(id,val)=>{const e=document.getElementById(id);if(e)e.textContent=val};
    const bar=(id,val)=>{const e=document.getElementById(id);if(e)e.style.width=(val/total*100).toFixed(1)+'%'};
    set('ovDriverRates',policyFamily);
    set('ovDriverCb','inclusa nei Rates/CB');
    set('ovDriverMacro',counts.macro);
    bar('ovDriverRatesBar',policyFamily);
    bar('ovDriverCbBar',0);
    bar('ovDriverMacroBar',counts.macro);
  }

  function runRuntimeTruthQa(){
    const result={
      status:'PASS',
      source:'RUNTIME_D_PAIR_STATES',
      asOf:(typeof D!=='undefined'?D.asOf:null),
      pairCount:0,
      pairCountExpected:28,
      leadConfirmDivergeIssues:[],
      cotBindingIssues:[],
      staticSnapshotExcluded:true
    };
    if(typeof D==='undefined' || !D.pairStates){
      result.status='FAIL';
      result.reason='D.pairStates non disponibile';
      return result;
    }

    const pairs=Object.entries(D.pairStates);
    result.pairCount=pairs.length;
    if(pairs.length!==28) result.status='FAIL';

    for(const [pair,st] of pairs){
      const leadName=(st.lead||[])[0];
      const leadKey=LABEL_TO_KEY[leadName];
      const leadDir=leadKey?st.layers?.[leadKey]:null;
      if(leadDir && leadDir!=='MISTO' && leadDir!=='NON CONFRONTABILE'){
        for(const c of st.confirms||[]){
          const k=LABEL_TO_KEY[c];
          if(k && st.layers?.[k]!==leadDir){
            result.leadConfirmDivergeIssues.push({pair,type:'confirm',layer:c,lead:leadName,leadDir,value:st.layers?.[k]});
          }
        }
        for(const d of st.diverges||[]){
          const k=LABEL_TO_KEY[d];
          if(k && st.layers?.[k]===leadDir){
            result.leadConfirmDivergeIssues.push({pair,type:'diverge',layer:d,lead:leadName,leadDir,value:st.layers?.[k]});
          }
        }
      }

      const [a,b]=pair.split('/');
      const crowded=[a,b].filter(c=>{
        const x=D.cot?.[c];
        return x && Math.abs(Number(x.net_oi||0))>=30;
      });
      const alert=String(st.cot_alert||'');
      const hasAlert=alert.includes('NET_OI_') && !alert.startsWith('NONE');
      if(crowded.length && !hasAlert) result.cotBindingIssues.push({pair,type:'missing',crowded,alert});
      if(!crowded.length && hasAlert) result.cotBindingIssues.push({pair,type:'unexpected',crowded,alert});
    }

    if(result.leadConfirmDivergeIssues.length || result.cotBindingIssues.length) result.status='FAIL';
    return result;
  }

  function installRuntimeTruthBridge(){
    try{
      if(typeof certifiedPairForMarket==='function') certifiedPairForMarket=runtimeCertifiedAdapter;
      if(typeof derivePairDriverStructure==='function') derivePairDriverStructure=runtimePairDriverStructure;
      if(typeof syncOverviewFromV46==='function') syncOverviewFromV46=runtimeOverviewSync;

      if(typeof rebuildCanonicalState==='function'){
        const old=rebuildCanonicalState;
        rebuildCanonicalState=function(){
          const r=old.apply(this,arguments);
          try{
            if(typeof MODEL_STATE!=='undefined' && D?.pairStates){
              MODEL_STATE.pairs={};
              Object.keys(D.pairStates).forEach(p=>MODEL_STATE.pairs[p]=buildCanonicalPairState(p));
              MODEL_STATE.updatedAt=new Date().toISOString();
            }
          }catch(e){}
          return r;
        };
      }

      window.FX_RUNTIME_TRUTH_QA=runRuntimeTruthQa();
      document.documentElement.dataset.fxTruthSource='runtime';
      if(window.FX_RUNTIME_TRUTH_QA.status!=='PASS'){
        console.error('FX runtime truth QA failed',window.FX_RUNTIME_TRUTH_QA);
      }else{
        console.info('FX runtime truth QA PASS',window.FX_RUNTIME_TRUTH_QA);
      }

      try{ if(typeof rebuildCanonicalState==='function') rebuildCanonicalState(); }catch(e){}
      try{ runtimeOverviewSync(); }catch(e){}
      try{ if(typeof renderPair==='function') renderPair(); }catch(e){}
    }catch(e){
      console.error('Runtime truth bridge install failed',e);
    }
  }

  setTimeout(installRuntimeTruthBridge,0);
  setTimeout(()=>{
    window.FX_RUNTIME_TRUTH_QA=runRuntimeTruthQa();
  },250);
})();
