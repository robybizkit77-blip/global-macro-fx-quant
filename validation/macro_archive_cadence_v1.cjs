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
// RBNZ M15 uses quarter-END month labels, even when the publisher has
// already released the survey within that quarter. Never generalize this
// exception to arbitrary future dates or claim a first-release timestamp.
function surveyQuarter(row,today){
 const p=row.current_vintage_provenance;
 const match=/^(\d{4})-(03|06|09|12)$/.exec(row.last_date||'');
 const code=/^NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_(CPI_(?:1|2|5|10)Y|Unemp_[12]Y|Wage_[12]Y)$/.exec(row.id||'');
 if(!match||!code||row.source_file!=='NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent.csv'||
    p?.status!=='RBNZ_M15_CURRENT_PUBLISHED_SURVEY_NOT_PIT'||
    p.source_series_id!=='RBNZ_M15_AGGREGATE_WEIGHTED_MEAN_'+code[1]||
    p.source_url!=='https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m15/hm15.xlsx'||
    p.reference_period_semantics!=='survey quarter; observed availability upper bound, not certified release date'||
    p.source_series_first_release_PIT_certified!==false||
    !/^[a-f0-9]{64}$/.test(p.source_payload_sha256||'')||
    !/^\d{4}-\d{2}-\d{2}$/.test(p.available_by_date||'')||
    normalize(p.available_by_date)!==p.available_by_date||
    p.available_by_date>today)return null;
 const start=utc(+match[1],+match[2]-2,1);
 if(start>p.available_by_date||start>today)return null;
 return {period_start:start,available_by:p.available_by_date,frequency:'Q',
   basis:'RBNZ_M15_DOCUMENTED_SURVEY_QUARTER_NOT_PIT'};
}
module.exports={normalize,cadence,surveyQuarter};

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
 const survey={id:'NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_CPI_1Y',source_file:'NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent.csv',last_date:'2026-12',current_vintage_provenance:{status:'RBNZ_M15_CURRENT_PUBLISHED_SURVEY_NOT_PIT',source_series_id:'RBNZ_M15_AGGREGATE_WEIGHTED_MEAN_CPI_1Y',source_url:'https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/m/m15/hm15.xlsx',reference_period_semantics:'survey quarter; observed availability upper bound, not certified release date',source_series_first_release_PIT_certified:false,source_payload_sha256:'a'.repeat(64),available_by_date:'2026-11-26'}};
 assert.equal(surveyQuarter(survey,'2026-11-27').period_start,'2026-10-01');
 assert.equal(surveyQuarter(survey,'2026-11-25'),null);
 assert.equal(surveyQuarter({...survey,last_date:'2027-03'},'2026-11-27'),null);
 assert.equal(surveyQuarter({...survey,id:'OTHER'},'2026-11-27'),null);
 assert.equal(surveyQuarter({...survey,current_vintage_provenance:{...survey.current_vintage_provenance,source_series_first_release_PIT_certified:true}},'2026-11-27'),null);
 assert.equal(surveyQuarter({...survey,current_vintage_provenance:null},'2026-11-27'),null);
 console.log('MACRO_ARCHIVE_CADENCE_SELF_TEST_PASS');
}
