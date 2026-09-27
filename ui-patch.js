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


/* FX_FULL_RUNTIME_HYDRATION */
(()=>{
  'use strict';

  function replaceObjectContents(target, source){
    if(!target || !source || typeof target!=='object' || typeof source!=='object') return false;
    if(Array.isArray(target) && Array.isArray(source)){
      target.splice(0,target.length,...source);
      return true;
    }
    if(Array.isArray(target) || Array.isArray(source)) return false;
    Object.keys(target).forEach(k=>delete target[k]);
    Object.entries(source).forEach(([k,v])=>target[k]=v);
    return true;
  }

  function hydrateRuntimeData(){
    const p=window.__FX_PAYLOAD__||{};
    const report={status:'PASS',hydrated:[],missing:[]};
    const bind=(name,key,target)=>{
      if(p[key] && target){
        replaceObjectContents(target,p[key]);
        report.hydrated.push(name);
      }else{
        report.missing.push(name);
      }
    };

    try{ bind('NATIVE_RATES_DATA','native_rates',typeof NATIVE_RATES_DATA!=='undefined'?NATIVE_RATES_DATA:null); }catch(e){report.missing.push('NATIVE_RATES_DATA')}
    try{ bind('NATIVE_CB_DATA','native_cb',typeof NATIVE_CB_DATA!=='undefined'?NATIVE_CB_DATA:null); }catch(e){report.missing.push('NATIVE_CB_DATA')}
    try{ bind('NATIVE_LIQ_DATA','native_liq',typeof NATIVE_LIQ_DATA!=='undefined'?NATIVE_LIQ_DATA:null); }catch(e){report.missing.push('NATIVE_LIQ_DATA')}
    try{ bind('CERT53','cert53',typeof CERT53!=='undefined'?CERT53:null); }catch(e){report.missing.push('CERT53')}
    try{ bind('V250_COT_CHART_DATA','cot_charts',typeof V250_COT_CHART_DATA!=='undefined'?V250_COT_CHART_DATA:null); }catch(e){report.missing.push('V250_COT_CHART_DATA')}
    try{ bind('TOP_THEMES','top_themes',typeof TOP_THEMES!=='undefined'?TOP_THEMES:null); }catch(e){report.missing.push('TOP_THEMES')}
    try{ bind('WHAT_CHANGED','what_changed',typeof WHAT_CHANGED!=='undefined'?WHAT_CHANGED:null); }catch(e){report.missing.push('WHAT_CHANGED')}
    try{ bind('V247_COT_STORIES','cot_stories',typeof V247_COT_STORIES!=='undefined'?V247_COT_STORIES:null); }catch(e){report.missing.push('V247_COT_STORIES')}
    try{ bind('V241_PLAIN_MARKET','plain_market',typeof V241_PLAIN_MARKET!=='undefined'?V241_PLAIN_MARKET:null); }catch(e){report.missing.push('V241_PLAIN_MARKET')}

    try{
      if(typeof S!=='undefined'){
        ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'].forEach(ccy=>{
          const k='series_'+ccy;
          if(p[k]){
            S[ccy]=p[k];
            report.hydrated.push('S.'+ccy);
          }else{
            report.missing.push('S.'+ccy);
          }
        });
      }
    }catch(e){
      report.missing.push('S');
    }

    if(report.missing.length) report.status='FALLBACK_PARTIAL';
    window.FX_RUNTIME_HYDRATION_QA=report;

    try{ if(typeof rebuildCanonicalState==='function') rebuildCanonicalState(); }catch(e){}
    try{ if(typeof renderCurrency==='function') renderCurrency(); }catch(e){}
    try{ if(typeof renderPair==='function') renderPair(); }catch(e){}
    try{ if(typeof renderNativeRatesDesk==='function') renderNativeRatesDesk(); }catch(e){}
    try{ if(typeof renderMacroLab==='function') renderMacroLab(); }catch(e){}
    try{ if(typeof renderCot==='function') renderCot(); }catch(e){}

    return report;
  }

  const report=hydrateRuntimeData();
  if(report.status==='PASS') console.info('FX full runtime hydration PASS',report);
  else console.warn('FX full runtime hydration fallback',report);
})();


/* FX_RATES_SOURCE_SAFETY */
(()=>{
  'use strict';

  function canonicalRateSeries(ccy, tenor){
    try{
      const rows=(typeof S!=='undefined' && S[ccy]) ? S[ccy].filter(x=>x.category==='Rates') : [];
      const patterns = tenor==='2Y'
        ? [/\b2Y\b/i,/2D$/i]
        : [/\b10Y\b/i,/10D$/i];
      for(const re of patterns){
        const hit=rows.find(x=>re.test(x.label||''));
        if(hit && Array.isArray(hit.dates) && Array.isArray(hit.values) && hit.values.length) return hit;
      }
    }catch(e){}
    return null;
  }

  function canonicalLast(ccy,tenor){
    const s=canonicalRateSeries(ccy,tenor);
    if(!s) return null;
    return {date:s.dates.at(-1),value:Number(s.values.at(-1)),series:s};
  }

  function marketCrossCheck(ccy,tenor){
    try{
      const x=NATIVE_RATES_DATA?.[ccy];
      const v=x?.[tenor];
      if(v==null) return null;
      return {date:x.date||'—',value:Number(v),source:x.source||'',quality:x.quality||''};
    }catch(e){return null}
  }

  // Never splice a market-close cross-check into an official historical curve.
  if(typeof v233ChartSeries==='function'){
    v233ChartSeries=function(d,key){
      const c=typeof v233RatesCurrency!=='undefined'?v233RatesCurrency:'USD';
      if(key==='2Y'){
        const s=canonicalRateSeries(c,'2Y');
        return s?[{name:'2Y · serie canonica',series:s}]:[];
      }
      if(key==='10Y'){
        const s=canonicalRateSeries(c,'10Y');
        return s?[{name:'10Y · serie canonica',series:s}]:[];
      }
      if(key==='CURVE'){
        const s2=canonicalRateSeries(c,'2Y'), s10=canonicalRateSeries(c,'10Y');
        if(!s2||!s10) return [];
        const map10=new Map(s10.dates.map((z,i)=>[z,s10.values[i]]));
        const dates=[],values=[];
        s2.dates.forEach((z,i)=>{
          if(map10.has(z)){
            dates.push(z);
            values.push((Number(map10.get(z))-Number(s2.values[i]))*100);
          }
        });
        return dates.length?[{name:'10Y−2Y · serie canonica',series:{dates,values,label:'Curva 10Y−2Y'}}]:[];
      }
      if(key==='REAL') return d?.real?[{name:'Real yield',series:d.real}]:[];
      if(key==='BE') return d?.breakeven?[{name:'Breakeven',series:d.breakeven}]:[];
      return [];
    };
  }

  // Currency Rates detail: canonical official series first, separate market-close cross-check second.
  if(typeof v219RatesDetail==='function'){
    v219RatesDetail=function(c){
      const d=typeof currencyIntelData!=='undefined'?currencyIntelData[c]:null;
      const c2=canonicalLast(c,'2Y'), c10=canonicalLast(c,'10Y');
      const m2=marketCrossCheck(c,'2Y'), m10=marketCrossCheck(c,'10Y');
      const dyn=typeof currencyDynamics==='function'?currencyDynamics(c)?.rates:null;
      const curve=(c2&&c10)?(c10.value-c2.value)*100:null;
      const sourceNote=(m2 && c2 && m2.date!==c2.date)
        ? '<br><b>Cross-check mercato:</b> '+c+' 2Y '+fmt(m2.value,2)+'% al '+m2.date+' · non inserito nella serie storica canonica.'
        : '';
      return '<div class="v219DetailGrid">'+
        '<div class="neu"><span>TASSO 2 ANNI · CANONICO</span><b>'+(c2?fmt(c2.value,2)+'%':'—')+'</b><small>'+(c2?'as of '+c2.date:'serie non disponibile')+'</small></div>'+
        '<div class="neu"><span>TASSO 10 ANNI · CANONICO</span><b>'+(c10?fmt(c10.value,2)+'%':'—')+'</b><small>'+(c10?'as of '+c10.date:'serie non disponibile')+'</small></div>'+
        '<div class="neu"><span>CURVA 2Y-10Y</span><b>'+(curve==null?'—':fmt(curve,0)+' bp')+'</b><small>calcolata sulla stessa famiglia di serie</small></div>'+
        '</div><p class="v219DetailText"><b>Tassi:</b> '+(d?.rates?.[2]||'—')+
        '<br><b>Banca centrale:</b> '+(d?.cb?.[2]||'—')+
        (dyn?.turn?'<br><b>Attenzione:</b> possibile svolta recente nei tassi a breve.':'')+
        sourceNote+
        '</p><button class="v220InlineLink" type="button" onclick="showView(\'rates\')">Apri i grafici Rates</button>';
    };
  }

  window.FX_RATES_SOURCE_QA={status:'PASS',rule:'official historical series never spliced with market-close cross-check'};
})();


/* FX_RELATIVE_G8_CONTEXT */
(()=>{
  'use strict';

  function runtimeRelativeG8(c){
    if(typeof D==='undefined' || !D.pairStates) return null;
    const rows=Object.entries(D.pairStates).filter(([p])=>p.split('/').includes(c));
    if(rows.length!==7) return null;
    let wins=0, losses=0, mixed=0;
    const layer={macro:{win:0,loss:0,mixed:0},rates:{win:0,loss:0,mixed:0},central_bank:{win:0,loss:0,mixed:0},cot:{win:0,loss:0,mixed:0},price:{win:0,loss:0,mixed:0}};
    rows.forEach(([pair,st])=>{
      const w=st.convergence_winner;
      if(w===c) wins++;
      else if(w==='MISTA') mixed++;
      else losses++;
      Object.keys(layer).forEach(k=>{
        const v=st.layers?.[k];
        if(v===c) layer[k].win++;
        else if(v==='MISTO' || v==='NON CONFRONTABILE' || !v) layer[k].mixed++;
        else layer[k].loss++;
      });
    });
    return {c,wins,losses,mixed,total:rows.length,layer};
  }

  window.FX_RELATIVE_G8=runtimeRelativeG8;

  if(typeof currencyRelativeContext==='function'){
    currencyRelativeContext=function(c){
      const r=runtimeRelativeG8(c);
      if(!r) return 'Relazione G8 non determinata';
      if(r.wins===7) return 'Forza relativa G8 molto ampia · favorita in 7/7 coppie';
      if(r.wins>=5) return 'Forza relativa G8 elevata · favorita in '+r.wins+'/7 coppie';
      if(r.wins>=3) return 'Forza relativa G8 intermedia · favorita in '+r.wins+'/7 coppie'+(r.mixed?' · '+r.mixed+' miste':'');
      if(r.wins===0) return 'Forza relativa G8 debole · nessuna delle 7 coppie la favorisce';
      return 'Forza relativa G8 debole/intermedia · favorita in '+r.wins+'/7 coppie'+(r.mixed?' · '+r.mixed+' miste':'');
    };
  }

  function addRelativeCard(){
    const box=document.getElementById('fxMacroRatesSplit');
    if(!box) return;
    const c=window.selectedCcy || document.querySelector('#v219CurrencyTitle')?.textContent?.trim().slice(-3) || 'USD';
    const r=runtimeRelativeG8(c);
    if(!r) return;
    let card=document.getElementById('fxRelativeG8Card');
    if(!card){
      card=document.createElement('div');
      card.id='fxRelativeG8Card';
      card.className='fxMRCard neu';
      card.style.gridColumn='1 / -1';
      box.appendChild(card);
    }
    const macro=r.layer.macro, rates=r.layer.rates;
    const cls=r.wins>=5?'pos':r.wins===0?'neg':r.wins>=3?'warn':'neu';
    card.className='fxMRCard '+cls;
    card.innerHTML='<span class="fxMRLabel">FORZA RELATIVA G8 · PAIR ENGINE LIVE</span>'+
      '<b class="fxMRTrend">'+r.wins+'/7 coppie favorevoli'+(r.mixed?' · '+r.mixed+' miste':'')+'</b>'+
      '<span class="fxMRText">Macro relativo: '+macro.win+'/7 favorevoli · Rates relativo: '+rates.win+'/7 favorevoli. Questo blocco è separato dal momentum della singola valuta.</span>';
  }

  const oldRefresh=typeof refresh==='function'?refresh:null;
  setTimeout(addRelativeCard,50);
  setTimeout(addRelativeCard,300);
  if(typeof renderCurrency==='function' && !renderCurrency.__fxRelWrapped){
    const original=renderCurrency;
    const wrapped=function(){const r=original.apply(this,arguments);setTimeout(addRelativeCard,0);return r};
    wrapped.__fxRelWrapped=true;
    renderCurrency=wrapped;
  }
})();


/* FX_PAIR_NARRATIVE_CLARITY */
(()=>{
  'use strict';

  const LABEL_KEY={ 'Rates':'rates','Banca centrale':'central_bank','COT':'cot','Macro':'macro','Prezzo':'price' };

  function cleanPairNarrative(pair){
    try{
      const st=D?.pairStates?.[pair];
      if(!st) return null;
      const lead=(st.lead||[])[0]||'Non determinato';
      const lk=LABEL_KEY[lead];
      const leadDir=lk?st.layers?.[lk]:null;
      const winner=st.convergence_winner;
      const conf=(st.confirms||[]);
      const div=(st.diverges||[]);
      const lag=(st.lags||[]);
      let text='';

      if(winner==='MISTA'){
        text='I layer sono divisi: non c’è una direzione relativa prevalente. ';
      } else if(leadDir && leadDir!==winner){
        text='La prevalenza dei layer favorisce '+winner+' ('+(st.convergence_count||'—')+'), ma il lead '+lead+' punta verso '+leadDir+': il quadro è quindi realmente divergente. ';
      } else {
        text='La prevalenza dei layer favorisce '+winner+' ('+(st.convergence_count||'—')+'). ';
        if(leadDir) text+='Il lead '+lead+' punta nella stessa direzione. ';
      }

      if(conf.length) text+='Confermano il lead: '+conf.join(', ')+'. ';
      else text+='Nessun altro layer conferma ancora il lead. ';
      if(div.length) text+='Divergono dal lead: '+div.join(', ')+'. ';
      if(lag.length) text+='Non direzionali / in ritardo: '+lag.join(', ')+'. ';

      return text.trim();
    }catch(e){return null}
  }

  window.FX_PAIR_NARRATIVE=cleanPairNarrative;

  // Keep the approved Pair Desk layout. Only replace ambiguous prose when the
  // selected pair comment node can be identified safely.
  function refreshPairNarrative(){
    try{
      const pair=(window.selectedPair||window.currentPair||'').replace('-', '/');
      if(!pair) return;
      const t=cleanPairNarrative(pair);
      if(!t) return;
      const selectors=['#pairComment','#pairNarrative','#pairDeskComment','#vPairComment','[data-role="pair-comment"]'];
      for(const sel of selectors){
        const el=document.querySelector(sel);
        if(el){ el.textContent=t; el.dataset.fxNarrative='runtime-clear'; break; }
      }
    }catch(e){}
  }

  setTimeout(refreshPairNarrative,100);
  setTimeout(refreshPairNarrative,500);
  if(typeof renderPair==='function' && !renderPair.__fxNarrativeWrapped){
    const original=renderPair;
    const wrapped=function(){const r=original.apply(this,arguments);setTimeout(refreshPairNarrative,0);return r};
    wrapped.__fxNarrativeWrapped=true;
    renderPair=wrapped;
  }
})();


/* FX_PAIR_CORE_VS_ENGINE_CLARITY */
(()=>{
  'use strict';

  function clarifyPairDesk(){
    try{
      const pair=window.selectedPair;
      if(!pair || typeof D==='undefined' || !D.pairStates?.[pair] || typeof derivePairDecisionFrame!=='function') return;
      const st=D.pairStates[pair];
      const frame=derivePairDecisionFrame(pair);
      const core=frame?.fav || '—';
      const live=st.convergence_winner || 'MISTA';
      const count=st.convergence_count || '—';
      const lead=(st.lead||[])[0] || 'non determinato';
      const leadKey={'Rates':'rates','Banca centrale':'central_bank','COT':'cot','Macro':'macro','Prezzo':'price'}[lead];
      const leadSide=leadKey?st.layers?.[leadKey]:null;

      const head=document.querySelector('#v227Headline');
      const fav=document.querySelector('#v227Fav');
      const why=document.querySelector('#v227FavWhy');
      const drv=document.querySelector('#v227Driver');
      const drvWhy=document.querySelector('#v227DriverWhy');

      if(head){
        if(live==='MISTA'){
          head.textContent = core==='—'
            ? 'Core Macro+Rates non risolutivo. Pair Engine live diviso: nessuna direzione prevalente.'
            : 'Core Macro+Rates: '+core+'. Pair Engine live diviso ('+count+'): quadro non convergente.';
        }else if(core==='—'){
          head.textContent='Core Macro+Rates non risolutivo. Pair Engine live: prevalenza '+live+' ('+count+').';
        }else if(core!==live){
          head.textContent='Core Macro+Rates: '+core+'. Pair Engine live: prevalenza '+live+' ('+count+'). Divergenza strutturale.';
        }else{
          head.textContent='Core Macro+Rates e Pair Engine live allineati su '+live+' ('+count+').';
        }
      }

      if(fav){
        fav.textContent = core==='—' ? 'Core: nessuno' : 'Core: '+core;
      }
      if(why){
        if(live==='MISTA'){
          why.textContent='Il riquadro sopra mostra il vantaggio del core Macro+Rates; il Pair Engine completo resta diviso tra i layer.';
        }else if(core!==live && core!=='—'){
          why.textContent='Il core Macro+Rates favorisce '+core+', mentre la prevalenza dei layer del Pair Engine favorisce '+live+'. Non vanno letti come la stessa cosa.';
        }else{
          why.textContent='Il vantaggio core Macro+Rates è coerente con la prevalenza dei layer del Pair Engine.';
        }
      }

      if(drv && drvWhy && leadSide){
        drv.textContent='Lead live: '+lead;
        drvWhy.textContent = live!=='MISTA' && leadSide!==live
          ? 'Il lead punta verso '+leadSide+', mentre la prevalenza dei layer favorisce '+live+': divergenza reale da monitorare.'
          : 'Il lead punta verso '+leadSide+' e va letto separatamente dal semplice conteggio dei layer.';
      }
    }catch(e){}
  }

  window.FX_CLARIFY_PAIR_DESK=clarifyPairDesk;
  setTimeout(clarifyPairDesk,120);
  setTimeout(clarifyPairDesk,600);
  if(typeof renderPair==='function' && !renderPair.__fxCoreEngineWrapped){
    const original=renderPair;
    const wrapped=function(){const r=original.apply(this,arguments);setTimeout(clarifyPairDesk,0);return r};
    wrapped.__fxCoreEngineWrapped=true;
    renderPair=wrapped;
  }
})();
