const { chromium } = require('playwright');

(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const errs=[];
  page.on('console',m=>{if(m.type()==='error') errs.push(m.text())});
  await page.goto('http://127.0.0.1:8000/',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true,null,{timeout:120000});
  await page.waitForTimeout(1200);
  const result=await page.evaluate(()=>{
    const dateRe=/\b20\d{2}[-\/]\d{2}[-\/]\d{2}\b/g;
    const candidates=[];
    const seen=new Set();
    for(const el of document.querySelectorAll('body *')){
      const cs=getComputedStyle(el), b=el.getBoundingClientRect();
      if(cs.display==='none'||cs.visibility==='hidden'||b.width<=0||b.height<=0) continue;
      const own=[...el.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent||'').join(' ').replace(/\s+/g,' ').trim();
      const dates=[...(own.matchAll(dateRe))].map(m=>m[0]);
      if(!dates.length) continue;
      const key=(el.id||'')+'|'+String(el.className||'')+'|'+own;
      if(seen.has(key)) continue; seen.add(key);
      const view=el.closest('.view,[data-view]');
      candidates.push({
        tag:el.tagName,
        id:el.id||null,
        cls:String(el.className||'').slice(0,180)||null,
        text:own.slice(0,400),
        dates,
        inside_view:view?.id||null,
        x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height),
        parent:{tag:el.parentElement?.tagName||null,id:el.parentElement?.id||null,cls:String(el.parentElement?.className||'').slice(0,160)||null}
      });
    }
    return {
      schema:'GMFQ_GLOBAL_ASOF_MARKER_AUDIT_V1',
      status:'PASS_OBSERVATIONAL',
      price_asof:window.GMFQ_ECB_PRICE_AUDIT?.as_of||document.documentElement.getAttribute('data-price-asof')||null,
      candidates,
      global:candidates.filter(x=>!x.inside_view),
      sep30:candidates.filter(x=>x.dates.some(d=>d==='2026-09-30')),
      errors:[]
    };
  });
  result.errors=errs;
  console.log(JSON.stringify(result,null,2));
  await browser.close();
})().catch(e=>{console.error('::error title=Global as-of marker audit::'+String(e.message||e));process.exit(1)});