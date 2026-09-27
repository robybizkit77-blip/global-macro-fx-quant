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