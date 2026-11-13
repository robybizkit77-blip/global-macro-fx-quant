'use strict';
/* A dated FX update may accompany a frozen morning briefing, never rewrite it. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const json=p=>JSON.parse(read(p));
const next='site/fx-quant-v2/next/';
const sandbox={window:{},URL};
vm.runInNewContext(read(next+'morning-desk-v1.js'),sandbox,
 {filename:'morning-desk-v1.js',timeout:5000});
const api=sandbox.window.FXQuantMorningDesk;
assert.equal(typeof api.fxResearchPulse,'function');
const engine=require(path.join(root,next,'macro-strength-estimated-v1.js'));
const rank=require(path.join(root,next,'pair-rankings.js'));
const obs=json('site/control-room-preview/macro-v3-current-evidence.json');
const model=json('live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json');
const prices=json('live_data/sections/ECB_G8_PRICE_HISTORY.json');
const estimated=engine.evaluate({
 observed:obs,model,prices,ois:json('site/fx-quant-v2/ois-pricing-snapshot.json'),
 rates:json('live_data/sections/NATIVE_RATES_DATA.json'),
 now:obs.generated_europe_rome_day,rankingFn:rank.currencyRanking
});
assert.equal(estimated.status,'STIMA_OPERATIVA_NON_VALIDATA',estimated.reason);
const feed=json(next+'morning-desk-current.json');
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({
 '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
})[c]);
const today=obs.generated_europe_rome_day;
const params={esc,date:x=>x,dayNow:()=>today};
const currentResearch={
 estimated,selectResearchPairs:rank.selectResearchPairs,
 watchForPair:x=>rank.pairDecisionWatch(x,null)
};
const pulse=api.fxResearchPulse({...currentResearch,...params});
assert(pulse.includes('data-fx-pulse="current"'));
assert(pulse.includes('AGGIORNAMENTO SEPARATO'));
assert(pulse.includes('Ricerca '+estimated.asof));
assert(pulse.includes('fixing BCE '+estimated.priceAsOf));
assert(pulse.includes('non presente nel briefing')===false);
assert(pulse.includes('distinta dal briefing mattutino congelato'));
const chosen=rank.selectResearchPairs(estimated.pairs,5).slice(0,3);
for(const p of chosen)
 assert(pulse.includes('data-pair="'+p.key+'"'),p.key+' must open that exact pair');
const links=(pulse.match(/data-pair="/g)||[]).length;
assert.equal(links,chosen.length);
assert(links<=3);
assert(!pulse.includes('data-signal=')&&!pulse.includes('Compra adesso'));
assert(pulse.includes('Notizie e calendario'));
const plot=()=>'<div class="chart"><svg></svg></div>';
const before=api.build({feed,plot,...params});
const after=api.build({feed,plot,...params,currentResearch});
assert(after.indexOf('data-fx-pulse="current"')>after.indexOf('class="morning-lead"'),
 'Main market narrative must precede the estimated FX research');
if(today!==feed.edition_date)assert(after.includes('edizione archiviata'),'Historical morning must stay visibly archival');
assert.equal(after.replace(/<details class="morning-secondary-research[\s\S]*?<\/details>/,''),before,
 'The independently dated FX research must NOT rewrite any frozen article content');
const noData=api.fxResearchPulse({...params,estimated:null});
assert.equal(noData,'');
const suspended=api.fxResearchPulse({...currentResearch,...params,
 estimated:{...estimated,status:'STIMA_SOSPESA'}});
assert(suspended.includes('data-fx-pulse="unavailable"'));
assert(!suspended.includes('data-pair="'));
const future=api.fxResearchPulse({...currentResearch,...params,
 estimated:{...estimated,asof:'2099-01-01'}});
assert(future.includes('data-fx-pulse="unavailable"'));
const incomplete=api.fxResearchPulse({...currentResearch,...params,
 estimated:{...estimated,pairs:estimated.pairs.slice(1)}});
assert(incomplete.includes('data-fx-pulse="unavailable"'));
const malicious=structuredClone(estimated);
const target=chosen[0]?.key;
if(target){
 const pair=malicious.pairs.find(x=>x.key===target);
 pair.thesisReason='<img src=x onerror=alert(1)>';
 const safe=api.fxResearchPulse({...params,estimated:malicious,
  selectResearchPairs:rank.selectResearchPairs,
  watchForPair:()=>({improve:'<svg onload=alert(1)>'})});
 assert(safe.includes('&lt;img'));
 assert(safe.includes('&lt;svg'));
 assert(!safe.includes('<img')&&!safe.includes('<svg'));
}
const app=read(next+'app.js'),idx=read(next+'index.html'),css=read(next+'morning-desk-v1.css');
assert(app.includes('currentResearch')&&app.includes('watchForPair:x=>'));
assert(app.includes('feed:morning,plot,esc,date,dayNow,currentResearch'),
 'App must pass current dated research to the morning presentation');
assert(app.includes("e.target.closest('[data-pair]')"),'Pair buttons must navigate to selected dossier');
assert(idx.includes('morning-desk-v1.js?v=6'));
assert(idx.includes('morning-desk-v1.css?v=5'));
assert(idx.includes('app.js?v=18.43-drivers1'));
assert(css.includes('morning-fx-pulse-cases'));
console.log('NEXT_HOME_FX_PULSE_V1_PASS: frozen morning unchanged; current G8 + <=3 diversified FX pair gates; dated, safe and routable');
