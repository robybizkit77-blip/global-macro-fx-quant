'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:900}});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto('http://127.0.0.1:8765/site/fx-quant-v2/studio/');
   await page.waitForFunction(()=>!document.getElementById('refresh').disabled,{},{timeout:40000});
   const status=await page.locator('#source-state').innerText();
   assert.match(status,/11\/11 feed letti/,'Actual repository feeds must load: '+status);
   assert.match(status,/motore FX disponibile/,'Existing FX engine must evaluate: '+status);
   assert.equal(await page.locator('#studio-enhanced tbody tr').count(),8);
   assert.equal(await page.locator('#studio-health').count(),1);
   const enhanced=await page.evaluate(()=>researchG8().map(x=>({currency:x.currency,coverage:x.result?.enhanced?.coverage,score:x.result?.enhanced?.score,estimated:x.result?.enhanced?.estimatedWeight,ranking:x.result?.affectsFxRanking})));
   assert.equal(enhanced.length,8);
   assert(enhanced.every(x=>Number.isFinite(x.coverage)&&x.coverage>=0&&x.coverage<=100&&Number.isFinite(x.estimated)&&x.estimated>=0&&x.estimated<=x.coverage&&x.ranking===false&&(x.coverage===100?Number.isFinite(x.score)&&x.score>=0&&x.score<=10:x.score===null)));
   console.log('STUDIO_ENHANCED_G8',JSON.stringify(enhanced));
   assert.match(await page.locator('#studio-health').innerText(),/Affidabilità degli aggiornamenti/);

   for(const route of ['Control Room','Macro','Tassi','Forex','Cross-Asset','Calendario','Report']){
    await page.locator('#nav button').getByText(route,{exact:true}).click();
    assert(await page.locator('#view h1').count(),route+' has no title');
    assert(await page.locator('#view').innerText().then(t=>t.length>100),route+' empty');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),route+' horizontal page overflow at '+width);
    assert.doesNotMatch(await page.locator('#view').innerText(),/\bNaN\b|\bundefined\b/);
   }
   await page.locator('#nav button').getByText('Forex',{exact:true}).click();
   await page.getByRole('button',{name:'28 coppie',exact:true}).click();
   assert.equal(await page.locator('.pairrow').count(),28);
   await page.getByLabel('Valuta base').selectOption('GBP');
   await page.getByLabel('Controvaluta').selectOption('JPY');
   assert.match(await page.locator('#view').innerText(),/GBP\/JPY/);
   assert.equal(await page.locator('#pair-evidence .sector-read').count(),4);
   assert.equal(await page.locator('#pair-gov').count(),1);
   assert.equal(await page.locator('#pair-monetary').count(),1);
   const relativeTests=await page.evaluate(()=>{
     const result=[];
     for(let i=0;i<FX.length;i++)for(let j=i+1;j<FX.length;j++){
       const a=FX[i],b=FX[j],g=studioGovComparison(a,b),m=studioPricingComparison(a,b);
       const rows=g?.rows||[],dateOK=rows.every((x,i)=>!i||x.date>rows[i-1].date);
       const exacts=[m?.oneExact,m?.weekExact].filter(Boolean);
       const matched=exacts.every(x=>x.grade==='MATCHED_EXACT_INTERVAL'&&Number.isFinite(x.fxPct)&&x.from<x.asof);
       result.push({a,b,dateOK,matched,gov:!!g?.ready,monetary:exacts.length});
     }
     return result;
   });
   assert.equal(relativeTests.length,28);
   assert(relativeTests.every(x=>x.dateOK&&x.matched));
   assert(relativeTests.some(x=>x.gov));
   console.log('STUDIO_RELATIVE_RATES',JSON.stringify(relativeTests));

   assert.match(await page.locator('#view').innerText(),/Solidità della tesi.*Attrattività operativa/s);
   const checked=await page.evaluate(()=>{
     const res=[];for(let i=0;i<FX.length;i++)for(let j=i+1;j<FX.length;j++){
       const a=FX[i],b=FX[j],x=pairEvidence(a,b),y=pairEvidence(b,a);
       res.push({a,b,sameFavored:x.x?.favored===y.x?.favored,flow:x.flow===null?y.flow===null:Math.abs(x.flow+y.flow)<1e-9,pricing:x.rp===null?y.rp===null:Math.abs(x.rp.bp+y.rp.bp)<1e-9});
     }return res;
   });
   assert.equal(checked.length,28);assert(checked.every(x=>x.sameFavored&&x.flow&&x.pricing));
   assert.match(await page.locator('#studio-research .plain-reading').innerText(),/Da seguire:/);
   await page.getByRole('button',{name:'Forza G8',exact:true}).click();
   for(const c of ['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD']){
     await page.evaluate(c=>{state.ccy=c;render()},c);
     assert.equal(await page.locator('#currency-dossier .sector-read').count(),4);
     assert.match(await page.locator('#enhanced-country h2').innerText(),new RegExp(c+' · Sintesi quantitativa'));

     assert.match(await page.locator('#currency-dossier h2').innerText(),new RegExp(c+' · Giudizio'));
   }
   // Native components only: no embedded legacy pages or DOM reuse.
   assert.equal(await page.locator('iframe').count(),0);
   await page.getByRole('button',{name:'COT',exact:true}).click();
   await page.locator('.native-cot-table').waitFor({timeout:45000});
   assert.equal(await page.locator('.native-cot-table tbody tr').count(),8);
   const cotChecks=await page.evaluate(()=>{
     const m=FX.map(c=>cotModel(c)).filter(Boolean).map(cotResearch);
     const official=m.filter(x=>Number.isFinite(x.oi));
     return {n:m.length,official:official.length,valid:official.every(x=>Math.abs(x.netoi-100*x.q.net/x.oi)<1e-9),extremes:m.filter(x=>x.q.rounded>=80).length};
   });
   assert.equal(cotChecks.n,8);assert.equal(cotChecks.valid,true);assert(cotChecks.official>0);
   await page.getByRole('button',{name:'Extreme Long',exact:true}).click();
   assert.equal(await page.locator('.native-cot-table tbody tr').count(),cotChecks.extremes);
   await page.getByRole('button',{name:'Tutte',exact:true}).click();
   await page.getByRole('button',{name:'Velocità',exact:true}).click();
   const velocities=await page.evaluate(()=>cotOrdered(FX.map(c=>cotModel(c)).filter(Boolean).map(cotResearch)).map(x=>x.velocity).filter(Number.isFinite));
   assert(velocities.every((v,i)=>i===0||v<=velocities[i-1]));
   await page.getByRole('button',{name:'Percentile storico',exact:true}).click();
   assert.match(await page.locator('#studio-research').innerText(),/Percentili storici pubblicati/);
   await page.getByLabel('Controvaluta COT').selectOption({index:1});
   assert.equal(await page.locator('#cot-peer svg').count(),1);
   console.log('STUDIO_COT_QA',JSON.stringify(cotChecks));

   assert.match(await page.locator('#studio-research .plain-reading').innerText(),/I fondi|Il netto/);
   assert.match(await page.locator('.native-cot-table').innerText(),/P104.*Z104/s);
   assert.equal(await page.locator('.native-cot-table tbody tr td:nth-child(8)').evaluateAll(cells=>cells.filter(c=>/^\d+$/.test(c.textContent.trim())).length),8);
   await page.getByRole('button',{name:'Long / Short',exact:true}).click();
   assert(await page.locator('#studio-research .native-chart svg').count()>=2);
   await page.locator('#nav button').getByText('Tassi',{exact:true}).click();
   assert.equal(await page.locator('[data-studio-bank]').count(),8);
   for(const c of ['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD']){
     await page.locator('[data-studio-bank="'+c+'"]').click();
     assert.equal(await page.locator('#bank-dossier .sector-read').count(),4);
     const t=await page.locator('#bank-dossier').innerText();
     assert.match(t,/Tasso ufficiale.*decisione.*WANT.*CAN.*PRICE.*Forex/s);
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),'Bank dossier overflow '+c+' '+width);
   }
   const absent=await page.evaluate(()=>{const old=loaded.cb;delete loaded.cb;try{return bankEvidence('USD').valid}finally{loaded.cb=old}});
   assert.equal(absent,false);

   await page.locator('.native-curve-card').first().waitFor({timeout:45000});
   assert.equal(await page.locator('.native-curve-card').count(),8);
   assert.equal(await page.locator('.native-curve-card svg').count(),8);
   await page.locator('.native-curve-card').filter({hasText:'GBP'}).click();
   assert.match(await page.locator('#studio-research').innerText(),/GBP · curva e repricing/);
   assert.equal(await page.locator('#studio-research .plain-reading').count(),3);
   assert.match(await page.locator('#studio-research .plain-reading').first().innerText(),/tassi attesi|aspettative|Aspettative/);
   await page.locator('#nav button').getByText('Macro',{exact:true}).click();
   await page.getByLabel('Indicatore macro').waitFor();
   assert(await page.getByLabel('Indicatore macro').locator('option').count()>10);
   assert.equal(await page.locator('#country-sectors .sector-read').count(),9);
   for(const c of ['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD']){
     await page.evaluate(c=>{state.ccy=c;render()},c);
     const judge=await page.locator('#view .judgement').first().innerText();
     assert.match(judge,/PIL.*(CPI|PCE|HICP|inflazione).*Disoccupazione/s);
     assert.match(judge,/6M/);
     assert.equal(await page.locator('#country-sectors .sector-read').count(),9);
   }
   await page.evaluate(()=>{state.ccy='GBP';render()});
   const originalReading=await page.locator('#studio-research .plain-reading').innerText();
   await page.getByLabel('Indicatore macro').selectOption({index:1});
   assert.notEqual(await page.locator('#studio-research .plain-reading').innerText(),originalReading);
   assert(await page.locator('#studio-research svg').count()>0);
   await page.locator('#nav button').getByText('Cross-Asset',{exact:true}).click();
   const riskCheck=await page.evaluate(()=>{
     const q=crossRiskStory().q;
     const dates=['2026-11-19','2026-11-20','2026-11-23','2026-11-24','2026-11-25','2026-11-26'];
     const mock=Object.fromEntries(riskCore.map(k=>[k,{history:dates.map((d,i)=>[d,k==='SP500'||k==='NASDAQCOM'?100-i:k==='VIX'?20+i:k==='HY_OAS'?3+i/10:1+i/100])}]));
     const pressure=commonRisk(mock,'2026-11-27');
     const stale=commonRisk(mock,'2026-12-10');
     mock.VIX.history.pop();
     const missing=commonRisk(mock,'2026-11-27');
     return {actual:q.ok,pressure:pressure.medium?.state,stale:stale.ok,missing:missing.ok};
   });
   assert.equal(riskCheck.actual,true);
   assert.equal(riskCheck.pressure,'pressure');
   assert.equal(riskCheck.stale,false);
   assert.equal(riskCheck.missing,false);
   assert.equal(await page.locator('#risk-common tbody tr').count(),5);
   assert.equal(await page.locator('#risk-financial .sector-read').count(),2);
   const sourceCoverage=await page.evaluate(()=>FX.map(c=>({c,rows:supplementalFinancial(c).length})));
   assert(sourceCoverage.every(x=>x.rows>0),JSON.stringify(sourceCoverage));
   assert.equal(await page.locator('#studio-commodities .sector-read').count(),3);
   assert(await page.locator('#studio-supplemental .sector-read').count()>0);
   const gaps=await page.evaluate(()=>({same:tenorConnect({date:'03M',asof:'2026-11-26'},{date:'06M',asof:'2026-11-26'}),different:tenorConnect({date:'03M',asof:'2026-11-25'},{date:'06M',asof:'2026-11-26'}),missing:tenorConnect({date:'03M'},{date:'06M'}),skip:tenorConnect({date:'03M',asof:'2026-11-26'},{date:'12M',asof:'2026-11-26'})}));
   assert(gaps.same&&!gaps.different&&!gaps.missing&&!gaps.skip);
   console.log('STUDIO_SUPPLEMENTAL_COVERAGE',JSON.stringify(sourceCoverage));


   assert(await page.locator('#studio-research svg').count()>=2);
   await page.getByRole('button',{name:'VIX',exact:true}).click();
   assert.match(await page.locator('#studio-research .plain-reading').innerText(),/Volatilità/);
   await page.locator('#nav button').getByText('Calendario',{exact:true}).click();
   assert.equal(await page.locator('#studio-hourly').count(),1);
   await page.getByRole('button',{name:'Dati macro',exact:true}).click();
   assert(await page.locator('#studio-news-list .sector-read').count()>0);
   await page.getByRole('button',{name:'Comunicazioni ufficiali',exact:true}).click();
   assert(await page.locator('#studio-news-list .sector-read').count()>0);
   const hours=await page.evaluate(()=>{
     const t='2026-11-27T08:00:00Z',digest='a'.repeat(64),now=Date.parse('2026-11-27T10:00:00Z');
     const f={schema:'GMFQ_NEXT_FREE_HOURLY_DESK_V1',status:'ACTIVE',generated_at_utc:t,material_digest:digest,headline:'Test',lead:'Test',news:[]};
     const k={schema:'GMFQ_NEXT_HOURLY_CHECK_V1',status:'VERIFIED',edition_generated_at_utc:t,material_digest:digest,checked_at_utc:'2026-11-27T09:00:00Z'};
     return {valid:hourlyEvidence(f,k,now),wrong:hourlyEvidence(f,{...k,material_digest:'b'.repeat(64)},now),missing:hourlyEvidence(null,k,now)};
   });
   assert(hours.valid.valid&&hours.valid.checked&&hours.valid.age===2&&hours.valid.checkAge===1);
   assert(hours.wrong.valid&&!hours.wrong.checked&&!hours.missing.valid);
   await page.locator('#nav button').getByText('Report',{exact:true}).click();
   assert.equal(await page.locator('#studio-reports a[href*="/reports/"][href$=".html"]').count(),8);
   await page.getByRole('button',{name:'Daily Forex',exact:true}).click();
   assert.equal(await page.locator('#studio-reports .report').count(),1);
   assert.match(await page.locator('#studio-reports').innerText(),/Collegamento (verificato|non disponibile|non verificato)/);
   assert.equal(await page.locator('iframe').count(),0);
   assert.equal(errors.length,0,errors.join('\n'));
   await page.locator('#nav button').getByText('Control Room',{exact:true}).click();
   assert.match(await page.locator('#view').innerText(),/Ultimi dati macro documentati.*Prossimo catalizzatore in agenda/s);
   await page.route('**/ECB_G8_PRICE_HISTORY.json',route=>route.abort());
   await page.locator('#refresh').click();
   await page.waitForFunction(()=>!document.getElementById('refresh').disabled,{},{timeout:40000});
   assert.match(await page.locator('#source-state').innerText(),/10\/11 feed letti.*motore FX non disponibile.*prices/);
   assert.equal(errors.length,0,errors.join('\n'));
   console.log('STUDIO_PREVIEW_REAL_FEEDS_NAVIGATION_FALLBACK_PASS',width);
   await page.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
