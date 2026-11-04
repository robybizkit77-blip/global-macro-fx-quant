'use strict';
const {chromium}=require('playwright'),fs=require('fs');
const base=(process.env.FXV2_BASE||'http://127.0.0.1:8000/site/fx-quant-v2').replace(/\/+$/,'');
const mode=process.env.FXV2_MODE||'local';
const out='fxv2-browser-evidence';fs.mkdirSync(out,{recursive:true});
const pages=[
 ['home','index.html','#g8Grid'],['valute','valute.html','#currencyGrid'],
 ['coppie','coppie.html','#screener'],['tassi','tassi.html','#countryTabs'],
 ['macro','macro.html','#currencyGrid'],['banche','banche.html','#cbGrid'],
 ['cot','cot.html','#pickGrid'],['cross','cross-asset.html','#assetGrid'],
 ['liquidita','liquidita-credito.html','#countryGrid'],
 ['calendario','calendario-news.html','#eventGrid'],['ricerca','research.html','#archive']];
const viewports=[['desktop',{width:1440,height:900}],['mobile',{width:390,height:844}]];
const markers={
 valute:['#periodContext','fixing BCE dal feed canonico'],
 tassi:['#feedStatus','Feed repository aggiornati'],
 macro:['#dataStatus','Feed canonico MACRO_SERIES collegato'],
 banche:['#dataStatus','Feed banche centrali collegato'],
 cot:['#freshness','Origine:'],cross:['#sourceList','Proxy futures secondari'],
 calendario:['#feedAsOf','Calendario canonico verificato']
};
const actions={valute:'button[data-period="1M"]',macro:'button[data-ccy="NZD"]',
 banche:'button[data-c="NZD"]',cot:'button[data-mode="netoi"]',
 cross:'button[data-view="ENERGY"]',calendario:'button[data-filter="next7"]'};
const result={schema:'GMFQ_FXV2_BROWSER_QA_V1',mode,base,started_utc:new Date().toISOString(),pages:[],findings:[]};
function issue(name,view,kind,detail){result.findings.push({name,view,kind,detail:String(detail).slice(0,450)});}
async function audit(browser,name,file,selector,view,viewport){
 const ctx=await browser.newContext({viewport,reducedMotion:'reduce'}),page=await ctx.newPage();
 const exceptions=[],network=[],rec={name,view,http:null,menu:null,primary:null,overflow:null,feed:null};
 page.on('pageerror',e=>exceptions.push(String(e)));
 page.on('requestfailed',r=>{if(/raw\.githubusercontent\.com/.test(r.url()))network.push(r.url()+' '+r.failure()?.errorText);});
 page.on('response',r=>{if(/raw\.githubusercontent\.com/.test(r.url())&&r.status()>=400)network.push(r.status()+' '+r.url());});
 try{
  const response=await page.goto(base+'/'+file,{waitUntil:'domcontentloaded',timeout:70000});
  rec.http=response?.status();if(rec.http!==200)throw Error('HTTP '+rec.http);
  await page.locator('#fxv2-global-header').waitFor({timeout:20000});
  await page.waitForLoadState('networkidle',{timeout:16000}).catch(()=>{});
  await page.waitForTimeout(550);
  const o=await page.evaluate(selector=>{
   const root=document.querySelector(selector),h=document.querySelector('#fxv2-global-header'),s=document.body.innerText;
   return{menu:h?.querySelectorAll('#fxv2-nav a').length||0,
     current:h?.querySelectorAll('#fxv2-nav a[aria-current="page"]').length||0,
     page:document.body.dataset.fxv2Page||'',
     primary:root?.children.length||0,exists:!!root,
     overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),
     textLen:s.trim().length,bad:['undefined','[object Object]','NaN'].filter(x=>s.includes(x))};
  },selector);
  Object.assign(rec,o);
  if(o.menu!==11||o.current!==1||o.page!==name)issue(name,view,'navigation',JSON.stringify(o));
  if(!o.exists||!o.primary)issue(name,view,'empty_content',selector);
  if(o.textLen<450)issue(name,view,'empty_page',o.textLen);
  if(o.overflow>12)issue(name,view,'overflow_px',o.overflow);
  if(o.bad.length)issue(name,view,'bad_rendered_values',o.bad);
  if(markers[name]){
   const [s,expected]=markers[name];
   rec.feed=((await page.locator(s).first().textContent().catch(()=>''))||'').trim().slice(0,340);
   if(!rec.feed.includes(expected))issue(name,view,'live_feed_not_confirmed',rec.feed||s+' empty');
  }
  if(view==='mobile'){
   const b=page.locator('#fxv2-global-header .fxv2-toggle');
   await b.click({timeout:10000});
   if((await b.getAttribute('aria-expanded'))!=='true')issue(name,view,'mobile_menu','open failed');
   await b.click({timeout:10000});
   if((await b.getAttribute('aria-expanded'))!=='false')issue(name,view,'mobile_menu','close failed');
  }
  if(actions[name]){
   const b=page.locator(actions[name]).first();
   if(!(await b.count()))issue(name,view,'interaction_missing',actions[name]);
   else{
    await b.click({timeout:10000});await page.waitForTimeout(160);
    const ok=await b.evaluate(e=>e.getAttribute('aria-pressed')==='true'||e.classList.contains('active')||e.classList.contains('on'));
    if(!ok)issue(name,view,'interaction_failed',actions[name]);
   }
  }
 }catch(e){rec.error=String(e);issue(name,view,'load_or_interaction_error',e);}
 finally{
  rec.exceptions=exceptions.slice(0,7);rec.network=network.slice(0,7);
  exceptions.forEach(x=>issue(name,view,'uncaught_javascript',x));
  network.forEach(x=>issue(name,view,'feed_network_failure',x));
  if(result.findings.some(x=>x.name===name&&x.view===view))
   try{await page.screenshot({path:out+'/'+view+'-'+name+'.png',fullPage:true,timeout:10000});}catch(_){}
  result.pages.push(rec);
  console.log('FXV2_PAGE '+JSON.stringify({name,view,http:rec.http,nav:rec.menu,primary:rec.primary,overflow:rec.overflow,
     feed:rec.feed?.slice(0,60),exceptions:exceptions.length,failed:network.length,error:rec.error}));
  await ctx.close();
 }
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{for(const [view,viewport] of viewports)for(const [name,file,selector] of pages)
  await audit(browser,name,file,selector,view,viewport);}
 finally{await browser.close();}
 result.completed_utc=new Date().toISOString();
 result.status=result.findings.length?'FAIL':'PASS';
 fs.writeFileSync(out+'/'+mode+'.json',JSON.stringify(result,null,2)+'\n');
 console.log('FXV2_QA_RESULT '+JSON.stringify({status:result.status,pages:result.pages.length,findings:result.findings.length,first:result.findings.slice(0,25)}));
 if(result.findings.length)process.exitCode=1;
})().catch(e=>{console.error('FXV2_QA_FATAL',e);process.exitCode=2;});