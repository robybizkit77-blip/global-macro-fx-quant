#!/usr/bin/env node
'use strict';
/* Run actual, unchanged Control Room v10 math against OLD and ECB-corrected
   candidate inputs. No page writes, no Core scoring, no live publication. */
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');

const BASE='site/control-room-preview/home-navigation-v10.js';
const RATE='live_data/sections/NATIVE_RATES_DATA.json';
const FX='live_data/sections/ECB_G8_PRICE_HISTORY.json';
const SNAPSHOT_NOW='2026-10-26T12:00:00.000Z';
const PAIRS=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];

function section(s,start,end){
  const begin=s.indexOf(start),finish=s.indexOf(end,begin+start.length);
  if(begin<0||finish<=begin) throw Error('Control Room function source changed; manual re-audit '+start);
  return s.slice(begin,finish);
}
function actualRuntime(){
  const source=fs.readFileSync(BASE,'utf8');
  // Extract EXACT implementation from the active Control Room JS, not an
  // independently translated/assumed model.
  const js=[
    section(source,'const FX=','const BANK='),
    section(source,'function num(','/* Same approved operational pricing'),
    section(source,'function htmlEscape(','function go('),
    section(source,'function dateHistory(','function yieldChart('),
    section(source,'function pairWhatChangedEvidence(','/* Relative Rates -> FX consistency audit'),
    section(source,'function pairMarketReactionAudit(','/* Bridging an official SAME-DATE')
  ].join('\n');
  class FixedDate extends Date {
    constructor(...args){super(...(args.length?args:[SNAPSHOT_NOW]));}
    static now(){return Date.parse(SNAPSHOT_NOW);}
  }
  const context=vm.createContext({Date:FixedDate,Intl,Number,String,Math,Map,Set,
    Array,Object,RegExp,JSON,console});
  vm.runInContext(js,context,{timeout:5000,filename:BASE});
  for(const f of ['ratesAll','pairMarketReactionAudit','pairWhatChangedEvidence']){
    assert.equal(typeof context[f],'function',f+' must be actual active implementation');
  }
  return {context,sha256:crypto.createHash('sha256').update(source).digest('hex')};
}
function deepJson(v){return JSON.parse(JSON.stringify(v));}
function pairSummary(html){
  const status=/data-reaction-status="([^"]+)"/.exec(html)?.[1]||'INVALID';
  const start=/data-window-start="([^"]+)"/.exec(html)?.[1]||null;
  const end=/data-window-end="([^"]+)"/.exec(html)?.[1]||null;
  const spread=/<div class="gmfq-reaction-metrics"><div><span>.*?<\/span><strong>([^<]+) bp<\/strong>/s.exec(html)?.[1]||null;
  const pct=/<span>CAMBIO · .*?<\/span><strong>([^<]+)%<\/strong>/s.exec(html)?.[1]||null;
  return {status,start,end,spread_bp:spread,fx_change_pct:pct};
}
function collect(ctx,rates,fx){
  const raw=deepJson(ctx.ratesAll(rates));
  const chf=raw.CHF;
  const predictions={};
  for(const tenor of ['2Y','10Y']){
    const isTwo=tenor==='2Y',flag=isTwo?'estimate2':'estimate10',value=isTwo?'v2':'v10';
    predictions[tenor]={
      modeled:chf[flag]===true,
      estimate_pct:chf[flag]===true?chf[value]:null,
      beta:chf[flag]===true?chf[isTwo?'beta2':'beta10']:null,
      r2:chf[flag]===true?chf[isTwo?'r2_2':'r2_10']:null,
      anchor:chf[flag]===true?chf[isTwo?'anchor2':'anchor10']:null,
      input_as_of:chf[flag]===true?chf[isTwo?'estimatedAsOf2':'estimatedAsOf10']:null
    };
  }
  const reactions={};
  const changes={};
  const pairs=[];
  for(let i=0;i<PAIRS.length;i++)for(let j=i+1;j<PAIRS.length;j++)pairs.push(PAIRS[i]+PAIRS[j]);
  for(const pair of pairs){
    const html=ctx.pairMarketReactionAudit(pair,rates,fx);
    reactions[pair]=pairSummary(html);
    // No fabricated pair model: compare only the dated 2Y observed layer.
    const change=ctx.pairWhatChangedEvidence(pair,null,rates,'2026-10-23','2026-09-25');
    const observed=[...change.matchAll(/<p class="gmfq-change-measured">([^<]+)<\/p>/g)].map(m=>m[1]);
    changes[pair]={observed_2Y_legs:observed};
  }
  return {CHF:predictions,reactions,pairChange:changes,
    EUR:{date:rates.EUR.date,y2:rates.EUR['2Y'],y10:rates.EUR['10Y'],
      last_h2:rates.EUR.history2.values.at(-1),last_h10:rates.EUR.history10.values.at(-1)}};
}
function compare(oldRates,newRates,fx){
  const runtime=actualRuntime();
  const before=collect(runtime.context,oldRates,fx);
  const after=collect(runtime.context,newRates,fx);
  const differences={};
  for(const tenor of ['2Y','10Y']){
    const a=before.CHF[tenor],b=after.CHF[tenor];
    differences[tenor]={before:a,after:b,
       estimate_delta_bp:a.estimate_pct!==null&&b.estimate_pct!==null?
                        (b.estimate_pct-a.estimate_pct)*100:null,
       estimate_status_changed:a.modeled!==b.modeled,
       beta_delta:a.beta!==null&&b.beta!==null?b.beta-a.beta:null};
  }
  const reactionChanges=[],observedChanges=[];
  for(const pair of Object.keys(before.reactions)){
    const a=before.reactions[pair],b=after.reactions[pair];
    if(JSON.stringify(a)!==JSON.stringify(b))
      reactionChanges.push({pair,before:a,after:b});
    const ac=before.pairChange[pair],bc=after.pairChange[pair];
    if(JSON.stringify(ac)!==JSON.stringify(bc))
      observedChanges.push({pair,before:ac,after:bc});
  }
  return {
    schema:'GMFQ_EUR_ECB_2Y_10Y_V10_ACTIVE_CONSUMER_SENSITIVITY_V1',
    status:'RESEARCH_SHADOW_CONTROLLED_RELEASE_REVIEW',
    fixed_comparison_clock_rome_day:'2026-10-26',
    original_active_js_sha256:runtime.sha256,
    source_code_executed:'site/control-room-preview/home-navigation-v10.js',
    site_source_functions_executed:[
      'ratesAll','dateHistory','estimate','pairMarketReactionAudit',
      'pairWhatChangedEvidence'],
    fx_input_source:FX,
    currencies:PAIRS,
    compared_pairs:Object.keys(before.reactions).length,
    before_current_eur:before.EUR,after_current_eur:after.EUR,
    CHF_reference_beta_impact:differences,
    pair_reaction_changed_count:reactionChanges.length,
    pair_reaction_changed:reactionChanges,
    pair_observed_2y_changed_count:observedChanges.length,
    pair_observed_2y_changed:observedChanges,
    no_canonical_D_json_or_model_score_loaded:true,
    first_release_pit_certified:false,
    live_data_modified:false,
    core_recomputed:false,
    full_browser_render_verified:false,
    automatic_live_promotion_allowed:false
  };
}
function main(){
  const args=process.argv.slice(2);
  if(args.includes('--self-test')){
    const r=actualRuntime();
    assert.equal(typeof r.context.ratesAll,'function');
    assert.equal(typeof r.context.pairMarketReactionAudit,'function');
    const x=JSON.parse(fs.readFileSync(RATE));
    const f=JSON.parse(fs.readFileSync(FX));
    const out=compare(x,x,f);
    assert.equal(out.compared_pairs,28);
    assert.equal(out.pair_reaction_changed_count,0);
    assert.equal(out.pair_observed_2y_changed_count,0);
    assert.equal(out.CHF_reference_beta_impact['2Y'].estimate_delta_bp,0);
    assert.equal(out.CHF_reference_beta_impact['10Y'].estimate_delta_bp,0);
    const altered=deepJson(x);
    altered.EUR.history2.values[altered.EUR.history2.values.length-17]+=.2;
    const proof=compare(x,altered,f);
    assert.notDeepEqual(proof.CHF_reference_beta_impact['2Y'].before,
                        proof.CHF_reference_beta_impact['2Y'].after,
                        'CHF proxy must be empirically sensitive to the actual EUR source history');
    console.log('V10_ACTIVE_FUNCTION_PARITY_AND_CHF_SENSITIVITY_TEST_PASS');
    return;
  }
  const ci=args.indexOf('--candidate'),oi=args.indexOf('--output');
  if(ci<0||oi<0||!args[ci+1]||!args[oi+1])
    throw Error('Provide --candidate /tmp/candidate.json and --output /tmp/audit.json');
  const output=require('node:path').resolve(args[oi+1]);
  if(!output.startsWith('/tmp/')) throw Error('output must stay in /tmp');
  const original=JSON.parse(fs.readFileSync(RATE,'utf8'));
  const replacement=JSON.parse(fs.readFileSync(args[ci+1],'utf8'));
  const fx=JSON.parse(fs.readFileSync(FX,'utf8'));
  const result=compare(original,replacement,fx);
  assert.equal(result.compared_pairs,28);
  assert.deepEqual(result.before_current_eur,result.after_current_eur);
  assert.equal(result.live_data_modified,false);
  assert.equal(result.automatic_live_promotion_allowed,false);
  fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify({
    schema:result.schema,
    pair_reaction_changed_count:result.pair_reaction_changed_count,
    pair_observed_2y_changed_count:result.pair_observed_2y_changed_count,
    chf_delta:result.CHF_reference_beta_impact,
    no_promotion:true
  }));
}
main();
