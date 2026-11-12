'use strict';
const { chromium } = require('playwright');
const fs = require('fs');

// Final QA covers the current user entrypoint and Next research surface.
// The archived dashboard window globals are intentionally no longer used.
const origin = (process.env.GMFQ_QA_BASE || 'http://127.0.0.1:8000').replace(/\/$/, '');
const routeNames = {
  overview: 'Panoramica',
  currencies: 'Valute G8',
  pairs: 'Coppie FX',
  macro: 'Scenario macro',
  rates: 'Tassi & OIS',
  cot: 'COT',
  risk: 'Rischio',
  news: 'Notizie',
  library: 'Research Library'
};
const currencies = ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];

async function assertG8LayoutMatrix(page,label) {
  const initial=page.viewportSize();
  try {
    // The old screenshot gate used only desktop/mobile and missed intermediate
    // clipping and non-vertical ranked cards; evaluate actual element geometry.
    for(const width of [360,390,768,1024,1280,1440]) {
      await page.setViewportSize({width,height:initial.height});
      const faults=await page.evaluate(() => {
        const issues=[];
        const board=document.querySelector('#orient-strength-board');
        const focus=document.querySelector('#orient-strength-focus');
        if(!board||!focus)return ['G8 sections missing'];
        const bounds=el=>el.getBoundingClientRect();
        const br=bounds(board),fr=bounds(focus);
        if(br.left < -2 || br.right > window.innerWidth+2)
          issues.push('board outside viewport');
        if(fr.left < -2 || fr.right > window.innerWidth+2)
          issues.push('focus outside viewport');
        const rows=[...board.querySelectorAll('.strength-row')];
        if(rows.length!==8)issues.push('expected eight rows');
        const children=['.strength-name','.strength-brief',
          '.strength-market-brief','.strength-price-brief','.strength-reading'];
        let previousBottom=-Infinity;
        for(const [i,row] of rows.entries()) {
          const r=bounds(row);
          if(r.top < previousBottom-1)issues.push('ranking no longer vertical at '+i);
          previousBottom=r.bottom;
          if(r.left < br.left-2 || r.right > br.right+2)
            issues.push('row outside board at '+i);
          const rects=[];
          for(const selector of children) {
            const el=row.querySelector(selector);
            if(!el){issues.push('missing '+selector+' in row '+i);continue;}
            const b=bounds(el);
            if(b.left < r.left-2 || b.right > r.right+2 ||
               b.top < r.top-2 || b.bottom > r.bottom+2)
              issues.push('clipped grid child '+selector+' row '+i);
            if(el.scrollWidth > el.clientWidth+3)
              issues.push('text overflows '+selector+' row '+i);
            rects.push({selector,b});
          }
          for(let a=0;a<rects.length;a++)
            for(let b=a+1;b<rects.length;b++) {
              const x=Math.min(rects[a].b.right,rects[b].b.right)-
                Math.max(rects[a].b.left,rects[b].b.left);
              const y=Math.min(rects[a].b.bottom,rects[b].b.bottom)-
                Math.max(rects[a].b.top,rects[b].b.top);
              if(x>2 && y>2)issues.push('overlapping columns row '+i+
                ': '+rects[a].selector+' / '+rects[b].selector);
            }
        }
        if(document.documentElement.scrollWidth > window.innerWidth+2)
          issues.push('horizontal document overflow');
        return issues;
      });
      if(faults.length)throw Error(label+' G8 layout '+width+'px: '+faults.join('; '));
    }
  } finally {
    await page.setViewportSize(initial);
  }
}

async function checkG8FirstRead(page,label){
  await assertG8LayoutMatrix(page,label);
  const board=page.locator('#orient-strength-board');
  const rows=board.locator('button.strength-row[data-cs-country]');
  if(await rows.count()!==8)throw Error(label+' G8 requires eight macro/rates/expectations/price rows');
  const order=await rows.locator('.strength-name b').allTextContents();
  if(order.length!==8||order[0]!=='#1'||order[7]!=='#8')
    throw Error(label+' estimated G8 ordinal ranking missing');
  if(await board.locator('.strength-brief').count()!==8 ||
     await board.locator('.strength-axis').count()!==0)
    throw Error(label+' dense numeric grid should be replaced by eight editorial summaries');
  if(!(await board.innerText()).includes('Ordine stimato')&&
    !(await board.innerText()).includes('STIMA'))
    throw Error(label+' must visibly label current estimated G8 ranking');
  if(await page.locator('.strength-first-reading > p').count()!==3)
    throw Error(label+' selected currency must lead with three narrative paragraphs');
  const audit=page.locator('details.strength-evidence-fold');
  if(await audit.count()!==1 || await audit.evaluate(el=>el.open))
    throw Error(label+' quantitative evidence must exist, collapsed on first read');
  await audit.locator(':scope > summary').click();
  if(!(await audit.evaluate(el=>el.open)))
    throw Error(label+' detailed source/estimate panel did not expand');
  if(await audit.locator('.strength-card').count()!==4)
    throw Error(label+' four source-qualified dimensions lost inside expanded audit');
  const research=page.locator('details.strength-shadow-fold');
  if(await research.count()!==1)
    throw Error(label+' optional G8 shadow model detail missing');
  await research.locator(':scope > summary').click();
  if(!(await research.evaluate(el=>el.open)))
    throw Error(label+' G8 shadow research explanation did not expand');
  if(!(await research.locator('.strength-shadow-body').innerText()).includes('NON POINT-IN-TIME'))
    throw Error(label+' G8 shadow backtest lacks PIT warning');
  await research.locator(':scope > summary').click();
  await board.locator('[data-cs-country="JPY"]').click();
  await page.waitForFunction(()=>document.querySelector('.strength-row.selected')?.getAttribute('data-cs-country')==='JPY',
    null,{timeout:15000});
  if(!await page.locator('#orient-strength-focus').isVisible())
    throw Error(label+' selected JPY country-first analysis not visible');
  const pair=page.locator('details.strength-pair-fold');
  await pair.locator(':scope > summary').click();
  if(!await pair.evaluate(el=>el.open))
    throw Error(label+' bilateral FX comparison did not expand');
  const pairGrid=await page.locator('.strength-pair-fold > .orient-lead.orient-voice')
    .evaluate(el=>({columns:getComputedStyle(el).gridTemplateColumns,
      width:el.getBoundingClientRect().width,
      children:[...el.children].map(ch=>ch.getBoundingClientRect().width)}));
  if(page.viewportSize().width<=950 && pairGrid.columns.trim().split(/\s+/).length!==1)
    throw Error(label+' bilateral FX desk retained broken two-column layout: '+
      JSON.stringify(pairGrid));
  const thesis=page.locator('details.orient-thesis-details');
  await thesis.locator(':scope > summary').click();
  if(!await thesis.evaluate(el=>el.open))
    throw Error(label+' full macro/rates/COT pair dossier did not expand');
  const methods=page.locator('details.strength-method-fold');
  await methods.locator(':scope > summary').click();
  if(!await methods.evaluate(el=>el.open))
    throw Error(label+' G8 source/research detail did not expand');
  const evidence=methods.locator('.orient-evidence-item');
  if(await evidence.count()!==4||!await evidence.first().isVisible())
    throw Error(label+' four source cards not visible inside expanded research detail');
  // Regression: the inner price ranking lives inside a collapsed-by-default
  // methodology panel. Selecting another G8 currency must NOT close it.
  // Nor may the change collapse the already open pair thesis or Quant audit.
  const insideRank=methods.locator('.orient-rank-row[data-cs-country="GBP"]');
  await insideRank.scrollIntoViewIfNeeded();
  const beforeY=await insideRank.evaluate(el=>el.getBoundingClientRect().top);
  await insideRank.click();
  await page.waitForFunction(() =>
    document.querySelector('.strength-row.selected')?.dataset.csCountry==='GBP' &&
    document.querySelector('#orient-strength-focus h2')?.textContent?.includes('GBP'),
    null,{timeout:15000});
  for(const [name,openPanel] of [
    ['methods',methods],['pair',pair],['pair-thesis',thesis],['numeric-audit',audit]
  ]){
    if(!await openPanel.evaluate(el=>el.open))
      throw Error(label+' G8 selection collapsed already open '+name);
  }
  const afterY=await methods.locator('.orient-rank-row[data-cs-country="GBP"]')
    .evaluate(el=>el.getBoundingClientRect().top);
  if(Math.abs(afterY-beforeY)>85)
    throw Error(label+' switching G8 currency jumped reader position: '+beforeY+' -> '+afterY);
  if(!(await methods.locator('.orient-rank-row[data-cs-country="GBP"]')
    .evaluate(el=>document.activeElement===el)))
    throw Error(label+' changed G8 selection lost keyboard focus');

  // Other controls in the expanded dossier must not close the outer panel.
  await pair.locator('[data-cs-sort="return"]').click();
  if(!await pair.evaluate(el=>el.open)||!await methods.evaluate(el=>el.open))
    throw Error(label+' changing G8 peer sorting collapsed analysis panels');
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2);
  if(overflow)throw Error(label+' G8 first-read caused horizontal overflow');
  await page.locator('#content').screenshot({
    path:'visual-qa-evidence/'+label+'-currencies-first-read.png',timeout:20000
  });
}
async function checkPairChartControls(page,label) {
  const ranking=page.locator('#fx-ranking-desk');
  if(!(await ranking.innerText()).includes('STIMA OPERATIVA V1')||
     !(await ranking.innerText()).includes('vecchio modello del 25 settembre'))
    throw Error(label+' 28-pair ranking still relying on historical core');
  const pulse=page.locator('section.pairs-thesis-pulse');
  if(await pulse.count()!==1)throw Error(label+' 28-pair thesis pulse missing');
  const story=await pulse.innerText();
  if(!story.includes('MONITOR TESI FX') ||
     (!story.includes('Fixing BCE') && !story.includes('non verificabile')))
    throw Error(label+' thesis pulse lacks date status/fail-closed warning');
  const pulseBox=await pulse.boundingBox();
  if(!pulseBox || pulseBox.x < -2 || pulseBox.x+pulseBox.width>page.viewportSize().width+2)
    throw Error(label+' thesis pulse extends outside viewport');
  if(!await page.locator('#fx-ranking-desk').count())
    throw Error(label+' FX ranking removed by thesis pulse');
  const selected=page.locator('#fx-ranking-desk button[data-pair="USDCAD"]').first();
  if (!(await selected.count())) throw Error(label + ' USD/CAD pair not found in ranking');
  await selected.click();
  const detail=page.locator('details.pairs-optional-chart');
  await detail.locator('summary').first().click();
  const deskStory=detail.locator('.decision-desk-story');
  if(await deskStory.count()!==1)
    throw Error(label+' per-pair economic narrative missing');
  const audit=deskStory.locator('details.decision-desk-evidence');
  if(await audit.count()!==1||await audit.evaluate(el=>el.open))
    throw Error(label+' dated evidence not collapsed by default');
  const macroNote=deskStory.locator('.decision-desk-current-macro');
  if(await macroNote.count()){
   const economic=await macroNote.innerText();
   if(!economic.includes('Che cosa cambia nei dati osservati.')||
      !economic.includes('non sorprese rispetto al consenso'))
    throw Error(label+' observation must be grounded and not a surprise claim');
   const r=await macroNote.boundingBox();
   if(!r||r.x< -2||r.x+r.width>page.viewportSize().width+2)
    throw Error(label+' observed macro note clipped');
  }

  if (!(await detail.evaluate(el => el.open))) throw Error(label + ' pair chart did not open');
  for (const days of [20,60,120]) {
    const control=detail.locator('[data-v9-price-window="'+days+'"]');
    await control.click();
    if (!(await detail.evaluate(el => el.open))) throw Error(label + ' chart closed after '+days+' window');
    if ((await detail.locator('[data-v9-price-window="'+days+'"]').getAttribute('aria-pressed')) !== 'true') {
      throw Error(label + ' price chart failed to select '+days+' observations');
    }
  }
  const ref=detail.locator('[data-v12-reference-toggle]');
  if (!(await ref.count())) throw Error(label + ' chart reference control missing');
  const before=await ref.getAttribute('aria-pressed');
  await ref.click();
  if (!(await detail.evaluate(el => el.open))) throw Error(label + ' chart closed when toggling references');
  if ((await detail.locator('[data-v12-reference-toggle]').getAttribute('aria-pressed')) === before) {
    throw Error(label + ' chart references did not toggle');
  }
}

async function check(browser, label, viewport) {
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  const receipt = { label, viewport, legacy: {}, current: { routes: [] } };
  try {
    const initial = await page.goto(origin + '/', {waitUntil:'domcontentloaded', timeout:45000});
    if (!initial || !initial.ok()) throw Error(label + ' index HTTP failure');
    await page.waitForURL(u => u.pathname === '/site/control-room-preview/', {timeout:15000});
    receipt.legacy.redirect = new URL(page.url()).pathname;
    // The independent Control Room V10 browser job checks the full preview.

    errors.length = 0;
    const current = await page.goto(origin + '/site/fx-quant-v2/next/index.html#overview',
                                    {waitUntil:'domcontentloaded',timeout:45000});
    if (!current || !current.ok()) throw Error(label + ' Next HTTP failure');
    await page.waitForFunction(() => document.querySelector('#content')?.dataset.view === 'overview' &&
      (document.querySelector('#content')?.innerText || '').length > 100,
      null, {timeout:30000});

    // Validate real source data, NOT decorative labels and NOT a freshness claim.
    const data = await page.evaluate(async () => {
      async function read(path) {
        const response = await fetch(path,{cache:'no-store'});
        if(!response.ok) throw Error(path + ' HTTP ' + response.status);
        return response.json();
      }
      const [pairs,rates] = await Promise.all([
        read('../../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'),
        read('../../../live_data/sections/NATIVE_RATES_DATA.json')
      ]);
      const currencies = ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
      return {
        pairCount: pairs.pair_count,
        actualPairs: Object.keys(pairs.pairs || {}).length,
        pairDate: pairs.price_asof,
        rateCount: currencies.filter(c => rates[c]?.date &&
          Number.isFinite(rates[c]?.['2Y']) &&
          Number.isFinite(rates[c]?.['10Y'])).length,
        rateDates: Object.fromEntries(currencies.map(c => [c,rates[c]?.date || null]))
      };
    });
    receipt.current.sources = data;
    if (data.pairCount !== 28 || data.actualPairs !== 28 || data.rateCount !== 8 ||
        !/^\d{4}-\d{2}-\d{2}$/.test(data.pairDate || '')) {
      throw Error(label + ' G8 / 28 pair source coverage: ' + JSON.stringify(data));
    }
    if (await page.locator('#nav a[data-route]').count() !== Object.keys(routeNames).length) {
      throw Error(label + ' navigation routes do not match the current sections');
    }
    if (label === 'mobile') {
      await page.locator('#menu-toggle').click();
      if (await page.locator('#menu-toggle').getAttribute('aria-expanded') !== 'true') {
        throw Error('Mobile menu did not open');
      }
      await page.locator('#nav a[data-route="pairs"]').click();
      await page.waitForFunction(() =>
        location.hash === '#pairs' && document.querySelector('#content')?.dataset.view === 'pairs',
        null,{timeout:15000});
      if (await page.locator('#menu-toggle').getAttribute('aria-expanded') !== 'false') {
        throw Error('Mobile menu did not close');
      }
    }
    for (const [route,title] of Object.entries(routeNames)) {
      await page.evaluate(route => { location.hash = '#' + route; }, route);
      await page.waitForFunction(({route,title}) =>
        document.querySelector('#content')?.dataset.view === route &&
        document.querySelector('#crumb-page')?.textContent?.trim() === title &&
        document.querySelector('#nav a[data-route="' + route + '"]')?.getAttribute('aria-current') === 'page',
        {route,title}, {timeout:20000});
      const inspection = await page.evaluate(() => {
        const el = document.querySelector('#content');
        const text = (el?.innerText || '').replace(/\s+/g,' ').trim();
        const rect = el?.getBoundingClientRect();
        return {
          length:text.length,
          visible:Boolean(rect && rect.width > 0 && rect.height > 0),
          badTokens:/\bundefined\b|\[object Object\]|\bNaN\b/.test(text),
          uniqueChrome:['app','nav','content','crumb-page'].every(
            id => document.querySelectorAll('#'+id).length === 1)
        };
      });
      if (!inspection.visible || inspection.length < 100 ||
          inspection.badTokens || !inspection.uniqueChrome) {
        throw Error(label + ' ' + route + ' visual failure ' + JSON.stringify(inspection));
      }
      receipt.current.routes.push({route,characters:inspection.length});
      await page.locator('#content').screenshot({
        path:'visual-qa-evidence/' + label + '-' + route + '.png',
        timeout:20000
      });
      if (route === 'currencies') await checkG8FirstRead(page,label);
      if (route === 'pairs') await checkPairChartControls(page,label);
    }
    if(errors.length) throw Error(label + ' page errors: ' + errors.slice(0,5).join(' | '));
    return receipt;
  } finally { await page.close(); }
}
(async () => {
  fs.mkdirSync('visual-qa-evidence',{recursive:true});
  const browser = await chromium.launch({headless:true});
  try {
    const desktop = await check(browser,'desktop',{width:1440,height:1100});
    const mobile = await check(browser,'mobile',{width:390,height:844});
    const out = {status:'PASS', audited:'Control Room redirect and nine FX Quant Next sections, including pair chart controls',desktop,mobile};
    fs.writeFileSync('visual-qa-evidence/final-summary.json',JSON.stringify(out,null,2));
    console.log('FINAL_VISUAL_ACTIVE_ROUTES_PASS',JSON.stringify(out));
  } finally { await browser.close(); }
})().catch(e => {
  console.error('::error title=Final active-route visual QA::' + String(e.stack || e));
  process.exit(1);
});
