/* Control Room v10 — optional, additive Home card navigation and DXY lookup.
   UI-only. Never fabricates a quote or alters verified-data status. */
(() => {
  'use strict';
  const frame = document.getElementById('gmfq-page');
  if (!frame) return;

  const DXY_CHART = 'https://www.tradingview.com/symbols/TVC-DXY/';
  const destinations = [
    ['.gridtop > .panel:nth-child(2)', '#/tassi?focus=ois', 'Apri Tassi e OIS'],
    ['.gridtop > .panel:nth-child(3)', '#/tassi?focus=curve', 'Apri curve 2Y e 10Y'],
    ['.mid > .panel:nth-child(1)', '#/valute', 'Apri la forza relativa G8'],
    ['.mid > .panel:nth-child(2)', '#/tassi?focus=2y', 'Apri rendimenti a 2 anni'],
    ['.mid > .panel:nth-child(3)', '#/tassi?focus=spread', 'Apri spread 2Y'],
    ['.bottom > .panel:nth-child(1)', '#/screener', 'Apri lo Screener delle 28 coppie'],
    ['.bottom > .panel:nth-child(2)', '#/macro', 'Apri il quadro Macro']
  ];
  const bankCodes = {Fed:'USD',ECB:'EUR',BoE:'GBP',BoJ:'JPY',RBA:'AUD',BoC:'CAD',RBNZ:'NZD',SNB:'CHF'};
  const validCcy = new Set(['USD','EUR','GBP','JPY','CAD','AUD','NZD','CHF']);

  function isHome() {
    const route = (location.hash || '#/home').replace(/^#\/?/,'').split('?')[0];
    return route === 'home' || route === 'index.html';
  }
  function go(route) {
    if (route.startsWith('https://')) {
      window.open(route, '_blank', 'noopener,noreferrer');
      return;
    }
    if (location.hash !== route) location.hash = route;
  }
  function decorate(doc) {
    if (!doc.head || doc.getElementById('gmfq-card-navigation-v10-style')) return;
    const style = doc.createElement('style');
    style.id = 'gmfq-card-navigation-v10-style';
    style.textContent = `
      [data-gmfq-destination] { cursor:pointer; }
      [data-gmfq-destination]:focus-visible { outline:2px solid #efca69;outline-offset:-3px; }
      .gmfq-open-detail { float:right; margin-left:8px; font:600 11px/1.5 Arial,sans-serif;
        letter-spacing:0.015em; color:#efca69; text-decoration:none; white-space:nowrap; }
      .gmfq-open-detail:hover, .gmfq-open-detail:focus-visible { text-decoration:underline; }
      .cc[data-gmfq-destination] .tickerhead::after {content:'↗';color:#d7bc7b;font-size:12px;margin-left:auto;}
      .cc .gmfq-dxy-link {display:inline-block;color:#efca69;font:600 11px/1.25 Arial,sans-serif;
        text-decoration:underline;text-underline-offset:2px;margin-top:4px;}
      .cc .gmfq-dxy-provenance {font:10px/1.3 Arial,sans-serif;color:#91aabe;margin-top:3px;}
      .oisrow[data-gmfq-destination]:hover > span:first-child {color:#efca69;}
    `;
    doc.head.appendChild(style);
  }
  function labelLink(doc, card, route, label) {
    const title = card && card.querySelector('.heading');
    if (!title || title.querySelector('.gmfq-open-detail')) return;
    const anchor = doc.createElement('a');
    anchor.className = 'gmfq-open-detail';
    anchor.href = route;
    anchor.textContent = 'Approfondisci ↗';
    anchor.title = label;
    anchor.setAttribute('aria-label', label);
    title.appendChild(anchor);
    card.dataset.gmfqDestination = route;
    card.tabIndex = 0;
    card.setAttribute('role','link');
    card.setAttribute('aria-label',label);
  }
  function cardTarget(doc, node) {
    const currency = node.closest('#valute .cc');
    if (currency) {
      const ccy = (currency.getAttribute('data-filter') || '').toUpperCase();
      if (ccy === 'DXY') return DXY_CHART;
      if (validCcy.has(ccy)) return '#/valute?ccy=' + ccy;
    }
    const ois = node.closest('#ois .oisrow');
    if (ois) {
      const bank = Object.keys(bankCodes).find(b => ois.textContent.includes(b));
      if (bank) return '#/banche?ccy=' + bankCodes[bank];
    }
    const pair = node.closest('#pairs tr[data-filter]');
    if (pair) {
      const code = (pair.getAttribute('data-filter') || '').replace(/[^A-Z]/g,'');
      if (/^[A-Z]{6}$/.test(code)) return '#/screener?pair=' + code;
    }
    const panel = node.closest('[data-gmfq-destination]');
    return panel?.dataset.gmfqDestination || null;
  }
  function enhanceDxy(doc) {
    if (doc.documentElement.dataset.marketMode !== 'live') return;
    const dxy = [...doc.querySelectorAll('#valute .cc')].find(x => x.getAttribute('data-filter') === 'DXY');
    if (!dxy || dxy.querySelector('.gmfq-dxy-link')) return;
    // The ECB G8 feed cannot construct the ICE benchmark without SEK.
    // Retain the data engine's blank number and display an honestly labelled chart link.
    const move = dxy.querySelector('.move');
    if (!move) return;
    const link = doc.createElement('a');
    link.href = DXY_CHART; link.target = '_blank'; link.rel = 'noopener noreferrer';
    link.className = 'gmfq-dxy-link'; link.textContent = 'Grafico DXY ↗';
    link.title = 'TVC:DXY · TradingView CFD indicativo; non è un fixing ICE';
    const provenance = doc.createElement('div');
    provenance.className = 'gmfq-dxy-provenance';
    provenance.textContent = 'TVC:DXY · CFD indicativo';
    move.replaceWith(link,provenance);
  }
  function applyFocus(doc) {
    const query = (location.hash.split('?')[1] || '');
    const ccy = new URLSearchParams(query).get('ccy');
    if (!ccy || !validCcy.has(ccy) || isHome()) return;
    let done = false;
    function focus() {
      if (done) return true;
      const b = doc.querySelector('button[data-ccy="' + ccy + '"]');
      if (!b) return false;
      done = true;
      b.click(); // existing page controller remains authoritative
      return true;
    }
    if (focus()) return;
    const observer = new MutationObserver(() => { if (focus()) observer.disconnect(); });
    observer.observe(doc.body, {childList:true,subtree:true});
    // One-shot observer; disconnected when any subsequent section is loaded.
    frame.addEventListener('load', () => observer.disconnect(), {once:true});
  }
  function onLoad() {
    let doc;
    try { doc = frame.contentDocument; } catch (_) { return; }
    if (!doc || !doc.body) return;
    if (!isHome()) { applyFocus(doc); return; }
    decorate(doc);
    for (const [selector,route,label] of destinations) {
      labelLink(doc,doc.querySelector(selector),route,label);
    }
    doc.body.addEventListener('click', event => {
      const direct = event.target.closest('a.gmfq-open-detail');
      if (direct) { event.preventDefault(); go(direct.getAttribute('href')); return; }
      if (event.defaultPrevented || event.target.closest('a,button,input,select,textarea')) return;
      const route = cardTarget(doc,event.target);
      if (route) {event.preventDefault();go(route);}
    },false);
    doc.body.addEventListener('keydown', event => {
      if (!['Enter',' '].includes(event.key)) return;
      const element = event.target.closest('[data-gmfq-destination]');
      if (!element || event.target !== element) return;
      event.preventDefault();go(element.dataset.gmfqDestination);
    });
    const currencyList = doc.getElementById('valute');
    if (currencyList) {
      const check = () => {
        currencyList.querySelectorAll('.cc').forEach(el => {
          el.dataset.gmfqDestination = cardTarget(doc,el) || '';
          el.tabIndex = 0;
          el.setAttribute('role','link');
          el.setAttribute('aria-label','Apri approfondimento ' + (el.dataset.filter || 'DXY'));
        });
        enhanceDxy(doc);
      };
      check();
      const observer = new MutationObserver(check);
      observer.observe(currencyList,{childList:true}); 
      frame.addEventListener('load',()=>observer.disconnect(),{once:true});
    }
    const oisList = doc.getElementById('ois');
    if (oisList) {
      const tag = () => {
        oisList.querySelectorAll('.oisrow').forEach(el => {
          const url = cardTarget(doc,el);
          if (url) {el.dataset.gmfqDestination=url;el.tabIndex=0;el.setAttribute('role','link');}
        });
      };
      tag();
      new MutationObserver(tag).observe(oisList,{childList:true});
    }
    const pairsList=doc.getElementById('pairs');
    if(pairsList){
      const mark=()=>pairsList.querySelectorAll('tr[data-filter]').forEach(tr=>{
        const url=cardTarget(doc,tr);if(url){tr.dataset.gmfqDestination=url;tr.tabIndex=0;tr.setAttribute('role','link')}
      });
      mark();new MutationObserver(mark).observe(pairsList,{childList:true});
    }
  }
  frame.addEventListener('load', onLoad);
})();
