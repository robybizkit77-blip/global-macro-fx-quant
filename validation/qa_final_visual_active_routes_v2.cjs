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

async function checkPairChartControls(page,label) {
  const selected=page.locator('#fx-ranking-desk button[data-pair="USDCAD"]').first();
  if (!(await selected.count())) throw Error(label + ' USD/CAD pair not found in ranking');
  await selected.click();
  const detail=page.locator('details.pairs-optional-chart');
  await detail.locator('summary').click();
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
