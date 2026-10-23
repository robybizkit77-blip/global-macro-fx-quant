'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const src=fs.readFileSync('site/control-room-preview/home-navigation-v10.js','utf8');
const a=src.indexOf('function crossStudyCoverage(rows){'),b=src.indexOf('function crossRiskCard(',a);
assert(a>=0&&b>a,'Cross-Asset research coverage helper missing');
const num=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
const day=Date.parse('2026-10-23T00:00:00Z');
const age=s=>{
 if(typeof s!=='string'||!/^20\d{2}-\d{2}-\d{2}$/.test(s))return null;
 return Math.round((day-Date.parse(s+'T00:00:00Z'))/86400000);
};
const f=new Function('num','romeCalendarAge',src.slice(a,b)+';return crossStudyCoverage;')(num,age);
const rows={
 GOLD:{state:'SECONDARY_RECENT',value:4039.3,asof:'2026-10-22'},
 VIX:{state:'OFFICIAL_RECENT',value:19.03,asof:'2026-10-22'},
 WTI:{state:'OFFICIAL_RECENT',value:107.89,asof:'2026-10-22'},
 BRENT:{state:'SECONDARY_RECENT',value:112.8,asof:'2026-10-22'}
};
assert.deepEqual(Object.fromEntries(Object.entries(f(rows)).filter(([k])=>k!=='checked')),
 {total:4,covered:4,official:2,secondary:2,historical:0});
const broken=structuredClone(rows);
broken.BRENT.value=null;
assert.equal(f(broken).covered,3,'missing futures quote cannot be invented');
broken.BRENT.value=112.8;broken.BRENT.asof='2026-10-24';
assert.equal(f(broken).covered,3,'future-dated market quote rejected');
broken.BRENT.asof='2026-10-22';broken.GOLD.state='WITHHELD';
assert.equal(f(broken).covered,3,'unverified Gold futures cannot count as study coverage');
const older=structuredClone(rows);older.GOLD.state='SECONDARY_HISTORICAL';older.GOLD.asof='2026-10-13';
assert.equal(f(older).historical,1);
assert.equal(f(older).covered,4,'historical but real observations remain labelled');
assert(src.includes("panel.dataset.studyEffect='NONE'"));
assert(src.includes("coverage.official+' ufficiali (VIX/WTI)"));
console.log('CROSS_ASSET_4_OF_4_STUDY_COVERAGE_GOVERNED_PASS');
