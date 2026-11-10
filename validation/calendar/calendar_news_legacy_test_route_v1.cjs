'use strict';
/**
 * Calendar/News operational browser test entrypoint, isolated from the public
 * website. Public index.html MUST keep redirecting to Control Room v10.
 *
 * Older Calendar/News modules belong to the archived payload bootstrap
 * present in index.html. To audit that archived module's source/evidence
 * contracts, intercept ONLY the local test server's root document and
 * suppress ONLY the navigation redirect in memory. Never write a public
 * legacy index, alter deployed site routing, or replace real market data.
 */
const ENTRY='http://127.0.0.1:8765/';
const REDIRECT=/<script data-gmfq-legacy-redirect="v10">[\s\S]*?<\/script>/g;

async function enableCalendarNewsLegacyHarness(page){
  await page.route(ENTRY,async route=>{
    const response=await route.fetch({maxRedirects:0});
    if(!response.ok())throw new Error('Local dashboard test index HTTP '+response.status());
    const original=await response.text();
    const matches=original.match(REDIRECT)||[];
    if(matches.length!==1)
      throw new Error('Cannot isolate exactly one legacy redirect in test root: '+matches.length);
    const legacy=original.replace(REDIRECT,
      '<!-- legacy navigation redirect disabled ONLY in Calendar/News browser test -->');
    await route.fulfill({response,body:legacy,contentType:'text/html'});
  });
}
module.exports={enableCalendarNewsLegacyHarness};
