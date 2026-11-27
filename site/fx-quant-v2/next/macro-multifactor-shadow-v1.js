'use strict';
/* Macro score research V1. Transparent uncalibrated within-country breadth.
 * Never imported by FX ranking, pair selection or production data writers.
 * Missing components are not observed neutral values. No PIT/backtest claim.
 */
(function(root){
const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const FAMILY=[['gdp','PIL e crescita',15],['jobs','Mercato del lavoro',20],['demand','Consumi e domanda',15],['industry','Manifattura',10],['services','Servizi',15],['house','Immobiliare',10],['finance','Credito e liquidità',10],['leading','Anticipatori',5]];
const MONEY={USD:'US_M2SL_history_value',EUR:'EA_M3_history_value',GBP:'UK_M4_SA_history_value',JPY:'JP_M3_SA_history_value',CHF:'CH_M3_history_value',CAD:'CA_M2PP_SA_history_value',AUD:'AU_BROAD_MONEY_SA_history_value',NZD:'RBNZ_C50_BROAD_MONEY'};
const finite=Number.isFinite;
const sign=(x,t=0)=>Math.abs(x)<=t+1e-10?0:Math.sign(x);
const mean=a=>a.length?a.reduce((s,v)=>s+v,0)/a.length:null;
const iso=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(Date.parse(d))&&new Date(Date.parse(d)).toISOString().slice(0,10)===d;
const recent=(d,now,n)=>iso(d)&&iso(now)&&d<=now&&(Date.parse(now)-Date.parse(d))/864e5<=n;
const qnum=q=>/^\d{4}Q[1-4]$/.test(q||'')?Number(q.slice(0,4))*4+Number(q.at(-1)):NaN;
const qend=q=>finite(qnum(q))?new Date(Date.UTC(+q.slice(0,4),+q.at(-1)*3,0)).toISOString().slice(0,10):null;
const levelScore=x=>finite(x)?5+5*x:null;
// Fixed dimensions: direction 50%, level 25%, acceleration 15%, persistence 10%.
// Missing dimensions reduce effective coverage, never receive a guessed sign.
function dimensions({direction,level,acceleration,persistence}){
 const parts=[[direction,.5],[level,.25],[acceleration,.15],[persistence,.1]].filter(([v])=>finite(v)&&Math.abs(v)<=1);
 const coverage=parts.reduce((s,[,w])=>s+w,0);
 return {value:coverage?parts.reduce((s,[v,w])=>s+v*w,0)/coverage:null,coverage};
}
function area(row){
 if(!row||row.signal?.tone==='neutral')return null;
 const active=(row.signalSource==='original'?row.items:row.items?.slice(0,1))||[];
 const items=active.filter(x=>x&&!x.stale&&!x.invalid&&[-1,0,1].includes(x.verdict));
 if(!items.length||items.length!==active.length)return null;
 const evidence=items.map(x=>{
  const c=x.cycle||{};
  // Only use a structural level/acceleration when the engine actually measured it.
  // The level is already in the economic direction for the whitelisted real series.
  const direction=c.direction??x.verdict;
  const persistence=finite(c.persistence)&&c.persistence>=2&&[-1,1].includes(c.direction)?c.direction:null;
  const d=dimensions({direction,level:c.level,acceleration:c.acceleration,persistence});
  return {...d,label:x.metric.name,period:x.period,source:x.source,phase:c.phase||null,
   basis:c.basis||'LATEST_CHANGE_ONLY',direction,level:c.level??null,acceleration:c.acceleration??null,persistence,
   reversal:c.reversal||null};
 });
 return {value:mean(evidence.map(x=>x.value)),coverage:mean(evidence.map(x=>x.coverage)),evidence};
}
function observedOK(doc,now){
 return doc?.schema==='GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1'&&
 doc.status==='OBSERVED_ECONOMIC_CONTEXT_NOT_FX_SIGNAL'&&doc.safe_to_recompute_structural_pair_theses===false&&
 doc.safe_to_republish_D===false&&doc.historic_PIT_OOS_not_certified===true&&
 doc.eligible_for_trading_or_forward_backtest===false&&recent(doc.generated_europe_rome_day,now,7);
}
function gdp(doc,ccy,now){
 if(!observedOK(doc,now))return null;
 const g=doc.countries?.[ccy]?.growth,p=g?.prior_documented_quarter;
 if(!g||g.is_growth_strength_score!==false||!recent(g.publisher_release_day,now,175)||
 !recent(qend(g.reference_quarter),now,210)||!finite(g.nonannualized_qoq_descriptive_pct))return null;
 const validPrior=p&&qnum(g.reference_quarter)-qnum(p.reference_quarter)===1&&iso(p.publisher_release_day)&&p.publisher_release_day<=now&&
 finite(p.nonannualized_qoq_descriptive_pct)&&g.later_revisions_not_identical_to_first_release===true;
 const level=sign(g.nonannualized_qoq_descriptive_pct,.2);
 const direction=validPrior?sign(g.nonannualized_qoq_descriptive_pct-p.nonannualized_qoq_descriptive_pct,.1):null;
 const d=dimensions({level,direction,acceleration:null,persistence:null});
 return {...d,evidence:[{label:'PIL reale t/t non annualizzato',period:g.reference_quarter,source:g.publisher_source,level,direction,
 acceleration:null,persistence:null,value:d.value,coverage:d.coverage,basis:'GDP_QOQ',phase:null,reversal:null}]};
}
function money(doc,c,now){
 if(!observedOK(doc,now)||doc.sector_financial_status!=='RESEARCH_ONLY')return null;
 const s=doc.sector_financial_dynamics;
 if(s?.schema!=='GMFQ_G8_SECTOR_FINANCIAL_DYNAMICS_RESEARCH_V1'||s.safe_to_publish_D!==false||s.safe_to_update_pairs!==false||
 s.historical_PIT_certified!==false||s.no_cross_country_aggregation!==true||s.as_of!==doc.generated_europe_rome_day)return null;
 const row=s.countries?.[c]?.find(r=>r.series_id===MONEY[c]&&r.pillar==='liquidity'&&r.measurement==='STOCK'&&r.horizon==='STOCK_3M_ENDPOINT');
 if(!row||!finite(row.momentum_pct)||!/^\d{4}-\d{2}$/.test(row.reference_period||''))return null;
 const end=new Date(Date.UTC(+row.reference_period.slice(0,4),+row.reference_period.slice(5,7),0)).toISOString().slice(0,10);
 if(!recent(end,now,95))return null;
 // Nominal broad-money stock growth is a direction-only liquidity proxy,
 // NOT real credit flows, monetary stance, or a causal risk-on signal.
 const direction=finite(row.velocity_pp)?sign(row.velocity_pp,.15):null;
 const level=sign(row.momentum_pct,.15),acceleration=finite(row.acceleration_pp)?sign(row.acceleration_pp,.15):null;
 const d=dimensions({direction,level,acceleration,persistence:null});
 return {...d,evidence:[{...d,label:row.label+' · proxy nominale',period:row.reference_period,source:row.series_id,level,direction,acceleration,persistence:null,basis:'NOMINAL_MONEY_STOCK_3M',phase:null,reversal:null}]};
}
function finance(credit,liquidity){
 // Fixed equal subweights within the 10% family. Each half has independent
 // coverage; missing half cannot silently be substituted by the other.
 const parts=[credit,liquidity].filter(x=>x&&finite(x.value));
 if(!parts.length)return null;
 const denom=parts.reduce((s,x)=>s+x.coverage,0);
 return {value:denom?parts.reduce((s,x)=>s+x.value*x.coverage,0)/denom:null,
 coverage:denom/2,evidence:parts.flatMap(x=>x.evidence)};
}
function evaluate({country,rows=[],observed,day}={}){
 if(!FX.includes(country)||!iso(day))return null;
 const by=Object.fromEntries(rows.map(r=>[r.key,area(r)]));
 const factors={...by,gdp:gdp(observed,country,day),finance:finance(by.credit,money(observed,country,day))};
 const families=FAMILY.map(([key,label,weight])=>{
  const x=factors[key],available=x&&finite(x.value)&&x.coverage>0;
  return {key,label,weight,score:available?levelScore(x.value):null,coverage:available?x.coverage:0,
   contribution:available?weight*x.coverage*x.value:0,evidence:available?x.evidence:[]};
 });
 const effective=families.reduce((s,x)=>s+x.weight*x.coverage,0);
 const present=families.filter(x=>x.score!==null).length;
 // Unaligned observations are visible in detail; no comparable rank produced.
 const score=present>=6&&effective>=45?levelScore(families.reduce((s,x)=>s+x.contribution,0)/effective):null;
 return {country,day,score,effectiveCoverage:effective,present,families,status:score===null?'WITHHELD':'RESEARCH_ONLY',
  weighting:'FIXED_EXPERIMENTAL_COVERAGE_WEIGHTED',eligibleForTrading:false,affectsFxRanking:false,pointInTimeCertified:false};
}
function render(x,esc=s=>String(s??'')){
 if(!x)return '';
 const n=v=>finite(v)?v.toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:1}):'—';
 const tone=v=>!finite(v)?'neutral':v>=6?'green':v<=4?'red':'amber';
 const sym=v=>v===1?'↑':v===-1?'↓':v===0?'→':'—';
 return '<details class="rd-detail" data-macro-multifactor-shadow-v1><summary><strong>Macro Score multidimensionale · ricerca</strong> · '+esc(x.score===null?'Non valutabile':n(x.score)+'/10')+'</summary>'+
 '<p class="rd-fine">Modello sperimentale, non modifica il ranking FX. Copertura '+x.present+'/8 famiglie; '+esc(n(x.effectiveCoverage))+'% del peso teorico osservabile. Pesi fissi non calibrati. Nessuna classifica comparabile, previsione o backtest validato.</p>'+
 '<div style="overflow-x:auto"><table><thead><tr><th>Famiglia</th><th>Peso</th><th>Score</th><th>Copertura</th><th>Contributo*</th></tr></thead><tbody>'+
 x.families.map(f=>'<tr><td>'+esc(f.label)+'</td><td>'+f.weight+'%</td><td class="'+tone(f.score)+'">'+esc(n(f.score))+'</td><td>'+esc(n(100*f.coverage))+'%</td><td>'+esc(f.score===null?'—':n(f.contribution))+'</td></tr>').join('')+'</tbody></table></div>'+
 '<p class="rd-fine">* Contributo centrato su zero, prima della normalizzazione per copertura. Direzione 50%, livello 25%, accelerazione 15%, persistenza 10%; solo dimensioni misurate. Credito e massa monetaria nominale: 5% ciascuno prima della copertura. Inflazione e salari sono separati come contesto di policy.</p>'+
 '<details><summary>Fonti e dimensioni misurate</summary>'+x.families.map(f=>'<p><strong>'+esc(f.label)+'</strong></p>'+ (f.evidence.length?'<ul>'+f.evidence.map(e=>'<li>'+esc(e.label)+' · '+esc(e.period)+' · '+esc(e.source)+' · livello '+sym(e.level)+' / direzione '+sym(e.direction)+' / accelerazione '+sym(e.acceleration)+' / persistenza '+sym(e.persistence)+(e.reversal?' · '+esc(e.reversal):'')+'</li>').join('')+'</ul>':'<p>Non disponibile</p>')).join('')+'</details></details>';
}
const api={evaluate,render,dimensions,area,gdp,money,finance,FAMILY};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FXQuantMacroMultifactorShadow=api;
})(typeof window==='undefined'?globalThis:window);
