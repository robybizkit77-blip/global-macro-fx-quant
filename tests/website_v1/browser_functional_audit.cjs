const {chromium}=require('playwright');
const fs=require('node:fs');
const names=['index','valute','tassi','banche-centrali','posizionamento','coppie','coppia','rischio-eventi','top-themes','library','watchlist','screener','macro-data','strumenti','alert','impostazioni','market-risk'];
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const failures=[],report=[];
 for(const [device,viewport] of Object.entries({desktop:{width:1440,height:900},mobile:{width:390,height:844}})){
  const page=await browser.newPage({viewport});
  for(const name of names){
   const errors=[];page.removeAllListeners('pageerror');page.on('pageerror',e=>errors.push(e.message));
   const response=await page.goto('http://127.0.0.1:8000/site/website-v1/'+name+'.html',{waitUntil:'domcontentloaded',timeout:20000});
   await page.waitForTimeout(1200);
   const state=await page.evaluate(()=>({h1:document.querySelector('h1')?.textContent?.trim()||'',menu:!!document.getElementById('gmfq-mobile-nav'),sidebar:!!document.querySelector('.sidebar'),width:document.documentElement.scrollWidth,viewport:innerWidth}));
   const status=response?.status();
   if(status!==200||errors.length)failures.push({device,name,status,errors});
   if(state.width>state.viewport+16)failures.push({device,name,reason:'horizontal overflow',width:state.width,viewport:state.viewport});
   report.push({device,name,status,errors,state});
  }
  if(device==='desktop'){
    await page.goto('http://127.0.0.1:8000/site/website-v1/index.html',{waitUntil:'domcontentloaded'});
    await page.waitForTimeout(1300);
    const stale=await page.evaluate(()=>{
      const tiles=[...document.querySelectorAll('.ois-tile')];
      return tiles.filter(el=>el.textContent.includes('NZD')).map(el=>({text:el.innerText,svg:!!el.querySelector('svg.ois-mini'),stale:el.classList.contains('stale')}));
    });
    if(!stale.length||stale.some(x=>!x.stale||x.svg||!x.text.includes('WITHHELD')))failures.push({device,reason:'stale NZD OIS visible as current',stale});
    report.push({device,check:'NZD stale OIS fail-closed',stale});
  }
  if(device==='mobile'){
   await page.goto('http://127.0.0.1:8000/site/website-v1/index.html',{waitUntil:'domcontentloaded'});
   await page.waitForTimeout(600);
   const menu=page.locator('#gmfq-mobile-nav');
   if(!(await menu.isVisible()))failures.push({device,reason:'mobile menu not visible'});
   else {await menu.click();const opened=await page.evaluate(()=>document.body.classList.contains('gmfq-sidebar-open'));if(!opened)failures.push({device,reason:'mobile sidebar fails to open'});await page.screenshot({path:'market-qa-mobile-menu.png'});}
  }
  await page.close();
 }
 await browser.close();fs.writeFileSync('market-qa-results.json',JSON.stringify({report,failures},null,2));
 console.log('MARKET_SITE_AUDIT',JSON.stringify({pages:report.length,failures:failures.length,examples:failures.slice(0,15)}));
 if(failures.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
