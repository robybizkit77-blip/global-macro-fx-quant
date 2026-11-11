'use strict';
/* Pair Thesis Monitor: immutable, dated PRICE-CONTEXT-ONLY snapshots for 28 G8
 * crosses. Never interpret labels as executed flow, edge or trade signals.
 * Usage: node validation/pair_thesis/update_history_v1.cjs
 *   <candidate Pair Setup JSON> <existing history JSON> <output JSON> [git-commit]
 */
const fs=require('node:fs');
const PAIR=/^(?:AUD|CAD|CHF|EUR|GBP|JPY|NZD|USD){2}$/;
const DATE=/^\d{4}-\d{2}-\d{2}$/;
const Q=['PULITO','CON RISCHI','DA CONFERMARE','DA MONITORARE','NON VALUTABILE'];
function clean(s,max=700){return typeof s==='string'?s.slice(0,max):null;}
function finite(n){return typeof n==='number'&&Number.isFinite(n);}
function dateOK(s){return typeof s==='string'&&DATE.test(s)&&!Number.isNaN(Date.parse(s+'T12:00:00Z'));}
function snapPair(p){
 const s=p?.setup||{},f=p?.decision_frame||s.structural||{};
 return {
  fav:clean(s.structuralFav,3),
  quality:clean(s.quality,35),
  price:{state:clean(s.price?.state,35),text:clean(s.price?.text,180)},
  timing:{state:clean(s.timing?.state,35),text:clean(s.timing?.text,220)},
  cot:{state:clean(s.cot?.state,35),text:clean(s.cot?.text,260)},
  liquidity:{state:clean(s.liquidity?.state,35),text:clean(s.liquidity?.text,150)},
  structural:{relation:clean(f.relation,500),missing:clean(f.missing,450),watch:clean(f.watch,600)}
 };
}
function snapshot(doc,sourceCommit=null){
 const date=doc?.price_asof,base=doc?.macro_baseline_asof,ps=doc?.pairs;
 if(!dateOK(date)||!dateOK(base)||base>date||!ps||typeof ps!=='object')
  throw Error('Source dates or Pair Setup missing');
 const keys=Object.keys(ps).sort();
 if(keys.length!==28||new Set(keys).size!==28||keys.some(k=>!PAIR.test(k)||k.slice(0,3)===k.slice(3)))
  throw Error('Snapshot requires exactly 28 unique G8 FX crosses');
 if(!Q.some(x=>keys.some(k=>ps[k]?.setup?.quality===x)))
  throw Error('No recognizable Pair Setup quality labels');
 const pairs={};
 for(const key of keys)pairs[key]=snapPair(ps[key]);
 return {price_asof:date,macro_baseline_asof:base,source_commit:sourceCommit||null,pair_count:keys.length,pairs};
}
function validate(history){
 if(!history||history.schema!=='GMFQ_PAIR_THESIS_HISTORY_V1'||!Array.isArray(history.snapshots))
  throw Error('History schema invalid');
 let prev='';
 for(const shot of history.snapshots){
  if(!dateOK(shot.price_asof)||shot.price_asof<=prev||!dateOK(shot.macro_baseline_asof)||
   Object.keys(shot.pairs||{}).length!==28)throw Error('History must be sorted unique dated 28-pair snapshots');
  prev=shot.price_asof;
 }
 return true;
}
function update(candidate,history,sourceCommit=null){
 validate(history);
 const today=snapshot(candidate,sourceCommit),last=history.snapshots.at(-1);
 if(last&&today.price_asof<last.price_asof)
  throw Error('Candidate price vintage precedes newest history observation');
 if(last&&today.price_asof===last.price_asof)
  return {changed:false,history,reason:'SAME_PRICE_VINTAGE_NO_NEW_DAY'};
 // Macro baseline is intentionally preserved and reported, NOT called updated.
 const all=[...history.snapshots,today].slice(-35);
 const next={schema:'GMFQ_PAIR_THESIS_HISTORY_V1',scope:'SOURCE_DATED_PRICE_ONLY_NO_TRADE_SIGNAL',
  pair_count:28,dates_available:all.map(x=>x.price_asof),snapshots:all};
 validate(next);
 return {changed:true,history:next,reason:'NEW_PRICE_VINTAGE_ARCHIVED'};
}
if(require.main===module){
 const [candidatePath,historyPath,outputPath,commit]=process.argv.slice(2);
 if(!candidatePath||!historyPath||!outputPath)throw Error('Usage: candidate history output [source_commit]');
 const candidate=JSON.parse(fs.readFileSync(candidatePath,'utf8'));
 const current=JSON.parse(fs.readFileSync(historyPath,'utf8'));
 const result=update(candidate,current,commit||null);
 fs.writeFileSync(outputPath,JSON.stringify(result.history,null,2)+'\n');
 console.log(JSON.stringify({status:result.reason,changed:result.changed,
  newest_asof:result.history.snapshots.at(-1)?.price_asof,
  previous_asof:result.history.snapshots.at(-2)?.price_asof,
  pair_count:result.history.pair_count}));
}
module.exports={snapPair,snapshot,validate,update};
