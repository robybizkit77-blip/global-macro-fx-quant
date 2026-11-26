'use strict';
// Descriptive archive audit only: cadence inferred from observed spacing is not
// proof of publisher frequency or a current release.
const DAY=86400000, months=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
function utc(y,m,d){
 const x=new Date(Date.UTC(y,m-1,d));
 return x.getUTCFullYear()===y&&x.getUTCMonth()===m-1&&x.getUTCDate()===d?x.toISOString().slice(0,10):null;
}
function normalize(raw){
 if(typeof raw!=='string')return null;
 let m;
 if(m=/^(\d{4})-?Q([1-4])$/.exec(raw))return utc(+m[1],(+m[2]-1)*3+1,1);
 if(m=/^(\d{4})-W(\d{2})$/.exec(raw)){
   const y=+m[1],w=+m[2];if(w<1||w>53)return null;
   const a=new Date(Date.UTC(y,0,4)),monday=+a-((a.getUTCDay()+6)%7)*DAY+(w-1)*7*DAY;
   if(new Date(monday+3*DAY).getUTCFullYear()!==y)return null;
   return new Date(monday).toISOString().slice(0,10);
 }
 if(m=/^(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2})(?:$|T.*| .*)|$)/.exec(raw))return utc(+m[1],+m[2],+(m[3]||1));
 if(m=/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(raw))return utc(+m[3],+m[2],+m[1]);
 if(m=/^(\d{1,2})[ -]([A-Za-z]{3})[ -](\d{4})$/.exec(raw))return utc(+m[3],months.indexOf(m[2].toLowerCase())+1,+m[1]);
 if(m=/^([A-Za-z]{3})-(\d{2})$/.exec(raw))return utc(2000+ +m[2],months.indexOf(m[1].toLowerCase())+1,1);
 return null;
}
function cadence(row){
 const raw=row.dates||[],vs=row.values||[];
 const ds=raw.map(normalize);
 if(raw.length!==vs.length||!raw.length||ds.some(x=>!x)||vs.some(x=>typeof x!=='number'||!Number.isFinite(x)))
   return {observed_frequency:null,history_integrity:'INVALID_DATE_OR_VALUE'};
 if(raw.at(-1)!==row.last_date||vs.at(-1)!==row.last_value)return {observed_frequency:null,history_integrity:'TERMINAL_MISMATCH'};
 if(ds.some((d,i)=>i>0&&d<=ds[i-1]))return {observed_frequency:null,history_integrity:'UNORDERED_OR_DUPLICATE_DATES'};
 if(ds.length<5)return {observed_frequency:null,history_integrity:'INSUFFICIENT_HISTORY'};
 const tail=ds.slice(-24),gaps=tail.slice(1).map((d,i)=>(Date.parse(d)-Date.parse(tail[i]))/DAY);
 const month=d=>+d.slice(0,4)*12+ +d.slice(5,7),mg=tail.slice(1).map((d,i)=>month(d)-month(tail[i]));
 const share=(xs,p)=>xs.filter(p).length/xs.length;
 let observed_frequency=null;
 if(share(gaps,x=>x>=1&&x<=4)>=.85&&share(gaps,x=>x===1)>=.5)observed_frequency='D';
 else if(share(gaps,x=>x>=5&&x<=9)>=.9)observed_frequency='W';
 else if(share(mg,x=>x===1)>=.9)observed_frequency='M';
 else if(share(mg,x=>x===3)>=.9)observed_frequency='Q';
 else if(share(mg,x=>x===12)>=.9)observed_frequency='A';
 return {observed_frequency,history_integrity:'ORDERED',cadence_evidence:'OBSERVED_HISTORY_ONLY_NOT_PUBLISHER_CERTIFICATION',observed_sample_size:tail.length};
}
module.exports={normalize,cadence};

if(require.main===module){
 const assert=require('node:assert/strict');
 assert.equal(normalize('2026-W38'),'2026-09-14');
 assert.equal(normalize('2026-Q3'),'2026-07-01');
 assert.equal(normalize('2026Q2'),'2026-04-01');
 assert.equal(normalize('31/07/2026'),'2026-07-31');
 assert.equal(normalize('31-Aug-2026'),'2026-08-31');
 assert.equal(normalize('Jul-26'),'2026-07-01');
 assert.equal(normalize('2026/8/7'),'2026-08-07');
 assert.equal(normalize('2026-02-31'),null);
 function series(ds){return {dates:ds,values:ds.map(()=>1),last_date:ds.at(-1),last_value:1};}
 const monthly=series(['2026-01','2026-02','2026-03','2026-04','2026-05']);
 assert.equal(cadence(monthly).observed_frequency,'M');
 const quarterly=series(['2025-Q1','2025-Q2','2025-Q3','2025-Q4','2026-Q1']);
 assert.equal(cadence(quarterly).observed_frequency,'Q');
 const unordered=series(['2026/8/1','2026/8/31','2026/8/4','2026/8/5','2026/8/7']);
 assert.equal(cadence(unordered).history_integrity,'UNORDERED_OR_DUPLICATE_DATES');
 assert.equal(cadence(unordered).observed_frequency,null);
 console.log('MACRO_ARCHIVE_CADENCE_SELF_TEST_PASS');
}
