const { chromium } = require('playwright');
const fs = require('fs');

const VIEWS = [
  'overview','currencies','pairs','macro','inflationlabour','ratesdesk',
  'cbdesk','liquiditydesk','cot','method','forwarddesk'
];

const MONTHS = {
  gennaio:1,febbraio:2,marzo:3,aprile:4,maggio:5,giugno:6,
  luglio:7,agosto:8,settembre:9,ottobre:10,novembre:11,dicembre:12
};

function parseVisibleDates(text){
  const out=[];
  const add=(iso,raw,kind)=>{ if(/^20\d{2}-\d{2}-\d{2}$/.test(iso)) out.push({iso,raw,kind}); };
  for(const m of text.matchAll(/\b(20\d{2})-(\d{2})-(\d{2})\b/g)) add(`${m[1]}-${m[2]}-${m[3]}`,m[0],'ISO');
  for(const m of text.matchAll(/\b(\d{1,2})[\/-](\d{1,2})[\/-](20\d{2})\b/g)) add(`${m[3]}-${String(Number(m[2])).padStart(2,'0')}-${String(Number(m[1])).padStart(2,'0')}`,m[0],'DMY');
  const monthNames=Object.keys(MONTHS).join('|');
  const re=new RegExp(`\\b(\\d{1,2})\\s+(${monthNames})\\s+(20\\d{2})\\b`,'gi');
  for(const m of text.matchAll(re)) add(`${m[3]}-${String(MONTHS[m[2].toLowerCase()]).padStart(2,'0')}-${String(Number(m[1])).padStart(2,'0')}`,m[0],'ITALIAN');
  return out.sort((a,b)=>a.iso.localeCompare(b.iso));
}

async function run(viewport,label){
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport});
  const errors=[];
  page.on('console',m=>{ if(m.type()==='error') errors.push(m.text()); });
  page.on('pageerror',e=>errors.push(String(e)));
  const response=await page.goto('http://127.0.0.1:8000/',{waitUntil:'domcontentloaded',timeout:120000});
  if(!response||!response.ok()) throw new Error(`${label}: dashboard load failed`);
  await page.waitForFunction(()=>window.GMFQ_POST_GATE_FINAL_AUDIT?.settled_after_cad_chain===true,null,{timeout:120000});
  await page.waitForFunction(()=>window.GMFQ_EDITORIAL_FRESHNESS?.operational_loaded===true,null,{timeout:30000});
  await page.waitForTimeout(700);

  const rows=[];
  for(const view of VIEWS){
    await page.evaluate(v=>window.showView?.(v),view);
    await page.waitForTimeout(view==='ratesdesk'?500:220);
    const snap=await page.evaluate(view=>{
      const el=document.getElementById(view);
      const text=(el?.innerText||'').replace(/\s+/g,' ').trim();
      const op=[...el?.querySelectorAll?.('[data-gmfq-operational]')||[]].map(x=>x.getAttribute('data-gmfq-operational'));
      return {
        exists:!!el,
        text,
        textLength:text.length,
        operationalOwners:op,
        freshness:el?.dataset?.gmfqEditorialFreshness||null,
        freshnessAuthority:el?.dataset?.gmfqFreshnessAuthority||null,
        htmlLength:el?.innerHTML?.length||0
      };
    },view);
    if(!snap.exists||snap.textLength<20) throw new Error(`${label} ${view}: missing/empty view`);
    const dates=parseVisibleDates(snap.text);
    const latest=dates.length?dates.at(-1).iso:null;
    const earliest=dates.length?dates[0].iso:null;
    const unique=[...new Set(dates.map(x=>x.iso))];
    const legacyHints=[
      /25\s+settembre\s+2026/i,
      /29\s+settembre\s+2026/i,
      /30\s+settembre\s+2026/i,
      /settembre\s+2026/i,
      /payload/i,
      /legacy/i
    ].filter(re=>re.test(snap.text)).map(re=>re.source);
    rows.push({
      view,label,ownerType:snap.operationalOwners.length?'DYNAMIC_OR_HYBRID':'PAYLOAD',
      operationalOwners:snap.operationalOwners,
      textLength:snap.textLength,htmlLength:snap.htmlLength,
      latestVisibleDate:latest,earliestVisibleDate:earliest,visibleDateCount:unique.length,
      visibleDates:unique.slice(-12),freshness:snap.freshness,freshnessAuthority:snap.freshnessAuthority,
      legacyTextHints:legacyHints,
      sample:snap.text.slice(0,360)
    });
  }
  if(errors.length) throw new Error(`${label}: console/page errors: ${errors.join(' | ')}`);
  await browser.close();
  return rows;
}

(async()=>{
  const desktop=await run({width:1440,height:1100},'desktop');
  const mobile=await run({width:390,height:844},'mobile');
  const byView={};
  for(const view of VIEWS){
    const d=desktop.find(x=>x.view===view),m=mobile.find(x=>x.view===view);
    byView[view]={desktop:d,mobile:m,viewportParity:{ownerType:d.ownerType===m.ownerType,latestVisibleDate:d.latestVisibleDate===m.latestVisibleDate,freshness:d.freshness===m.freshness}};
  }
  const report={
    schema:'GMFQ_PAYLOAD_OWNER_CURRENTNESS_AUDIT_V1',
    status:'PASS_OBSERVATIONAL',
    generatedAt:new Date().toISOString(),
    views:byView,
    notes:[
      'Dates are extracted from visible text only and are not themselves a freshness verdict.',
      'Historical dates may be legitimate in macro, liquidity, COT, method and forward views.',
      'Use this audit to identify payload-owned surfaces requiring source-by-source migration before redesign.'
    ]
  };
  fs.mkdirSync('payload-owner-currentness-evidence',{recursive:true});
  fs.writeFileSync('payload-owner-currentness-evidence/report.json',JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error('::error title=Payload owner currentness audit::'+String(e.message||e));process.exit(1)});
