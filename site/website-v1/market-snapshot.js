(()=>{
  'use strict';

  const ROOT='../../live_data/sections/';
  const RATES_PATH=ROOT+'NATIVE_RATES_DATA.json';
  const FX_PATH='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/ECB_G8_PRICE_HISTORY.json';
  const PAIRS=['EURUSD','GBPUSD','USDJPY','USDCAD','AUDUSD','NZDUSD'];
  const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const ALLOWED=['1D','1W','1M','3M','YTD'];
  const HIERARCHY_ALLOWED=['1D','1W','1M'];
  const FX_MAX_AGE_DAYS=4;
  const RATES_MAX_AGE_DAYS=4;
  const params=new URLSearchParams(location.search);
  let rates=null,fx=null;
  let heroPeriod=ALLOWED.includes(params.get('tf'))?params.get('tf'):'1D';
  let hierarchyPeriod=HIERARCHY_ALLOWED.includes(params.get('h'))?params.get('h'):'1D';
  let rendering=false;

  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const pct=(v,digits=2)=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(digits)}%`;};
  async function load(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}
  async function tryLoad(path){try{return await load(path);}catch(e){console.warn('[GMFQ optional feed]',e);return null;}}
  function ageDays(s){if(!s)return Infinity;const t=Date.parse(`${String(s).slice(0,10)}T00:00:00Z`);if(!Number.isFinite(t))return Infinity;const now=new Date();const today=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());return Math.floor((today-t)/86400000);}
  const fresh=(s,max)=>ageDays(s)>=0&&ageDays(s)<=max;

  function sparkPoints(values,w=90,h=44,pad=2){const a=(values||[]).map(Number).filter(Number.isFinite);if(a.length<2)return `0,${h/2} ${w},${h/2}`;const lo=Math.min(...a),hi=Math.max(...a),span=(hi-lo)||1;return a.map((v,i)=>`${(pad+(w-2*pad)*(i/(a.length-1))).toFixed(1)},${(pad+(h-2*pad)*(1-(v-lo)/span)).toFixed(1)}`).join(' ');}
  function sampled(values,max=34){if(values.length<=max)return values;return Array.from({length:max},(_,i)=>values[Math.round(i*(values.length-1)/(max-1))]);}

  function datedRows(){return (Array.isArray(fx?.rows)?fx.rows:[]).filter(r=>r?.Date).slice().sort((a,b)=>String(a.Date).localeCompare(String(b.Date)));}
  function fxAsOf(){const rows=datedRows(),actual=rows.at(-1)?.Date||null,metadata=fx?.last_as_of||null;return actual&&metadata&&String(actual).slice(0,10)===String(metadata).slice(0,10)?actual:null;}
  function startIndex(rows,period){if(rows.length<2)return 0;if(period==='1D')return Math.max(0,rows.length-2);const last=new Date(`${rows.at(-1).Date}T00:00:00Z`);if(!Number.isFinite(last.getTime()))return Math.max(0,rows.length-2);let target;if(period==='YTD')target=new Date(Date.UTC(last.getUTCFullYear(),0,1));else{target=new Date(last);if(period==='1W')target.setUTCDate(target.getUTCDate()-7);if(period==='1M')target.setUTCMonth(target.getUTCMonth()-1);if(period==='3M')target.setUTCMonth(target.getUTCMonth()-3);}if(!Number.isFinite(target.getTime()))return Math.max(0,rows.length-2);const ts=target.toISOString().slice(0,10);let idx=rows.findIndex(r=>r.Date>=ts);if(idx<0)idx=0;return Math.min(idx,rows.length-2);}
  function pairValue(row,label){const a=label.slice(0,3),b=label.slice(3,6);const av=a==='EUR'?1:n(row?.[a]),bv=b==='EUR'?1:n(row?.[b]);return av&&bv?bv/av:null;}
  function unavailablePairCard(label,reason,asof){return{label,value:'—',change:'—',dir:'flat',values:[0,0],title:`${reason}${asof?` · dati al ${asof}`:''}`};}
  function pairCard(label,period){const rows=datedRows(),asof=fxAsOf();if(!fresh(asof,FX_MAX_AGE_DAYS))return unavailablePairCard(label,'FX non aggiornato',asof);if(rows.length<2)return unavailablePairCard(label,'Storico FX non disponibile',asof);const si=startIndex(rows,period),window=rows.slice(si),vals=window.map(r=>pairValue(r,label)).filter(v=>v!==null);if(vals.length<2)return unavailablePairCard(label,'Storico FX insufficiente',asof);const first=vals[0],last=vals.at(-1),ret=(last/first-1)*100;return{label,value:last>=100?last.toFixed(2):last.toFixed(4),change:pct(ret,2),dir:ret>=0?'up':'down',values:sampled(vals),title:`${period} · ECB fixing · dati al ${asof}`};}

  function rateHistory(series,key){const h=series?.[key];if(Array.isArray(h))return h.map(x=>({date:x?.date,value:n(x?.value)})).filter(x=>x.date&&x.value!==null).sort((a,b)=>String(a.date).localeCompare(String(b.date)));const dates=Array.isArray(h?.dates)?h.dates:[],values=Array.isArray(h?.values)?h.values:[];return dates.map((date,i)=>({date,value:n(values[i])})).filter(x=>x.date&&x.value!==null).sort((a,b)=>String(a.date).localeCompare(String(b.date)));}
  function startRateIndex(h,period){if(h.length<2)return 0;if(period==='1D')return Math.max(0,h.length-2);const last=new Date(`${h.at(-1).date}T00:00:00Z`);if(!Number.isFinite(last.getTime()))return Math.max(0,h.length-2);let target;if(period==='YTD')target=new Date(Date.UTC(last.getUTCFullYear(),0,1));else{target=new Date(last);if(period==='1W')target.setUTCDate(target.getUTCDate()-7);if(period==='1M')target.setUTCMonth(target.getUTCMonth()-1);if(period==='3M')target.setUTCMonth(target.getUTCMonth()-3);}if(!Number.isFinite(target.getTime()))return Math.max(0,h.length-2);const ts=target.toISOString().slice(0,10);let idx=h.findIndex(x=>x.date>=ts);if(idx<0)idx=0;return Math.min(idx,h.length-2);}
  function rateCard(tenor,period){const usd=rates?.USD;if(!usd)return{label:`US ${tenor}Y`,value:'—',change:'—',dir:'flat',values:[0,0],title:'Tassi non disponibili'};const key=tenor===10?'history10':'history2',h=rateHistory(usd,key),asof=usd.date||h.at(-1)?.date||null;if(!fresh(asof,RATES_MAX_AGE_DAYS))return{label:`US ${tenor}Y`,value:'—',change:'—',dir:'flat',values:[0,0],title:`Tassi non aggiornati · dati al ${asof||'—'}`};if(h.length<2)return{label:`US ${tenor}Y`,value:'—',change:'—',dir:'flat',values:[0,0],title:'Storico tassi insufficiente'};const si=startRateIndex(h,period),window=h.slice(si),current=n(usd?.[`${tenor}Y`])??n(usd?.current?.[tenor===10?'y10':'y2'])??window.at(-1)?.value;if(current===null||current===undefined)return{label:`US ${tenor}Y`,value:'—',change:'—',dir:'flat',values:[0,0],title:`Tassi non disponibili · dati al ${asof}`};const first=window[0].value,delta=(current-first)*100;return{label:`US ${tenor}Y`,value:`${current.toFixed(2)}%`,change:`${delta>0?'+':''}${delta.toFixed(1)}bp`,dir:delta>=0?'up':'down',values:sampled(window.map(x=>x.value)),title:`${period} · curva Treasury ufficiale · dati al ${asof}`};}


  function syncHeroTabs(){document.querySelectorAll('.hero-tabs a').forEach(el=>el.classList.toggle('active',el.textContent.trim()===heroPeriod));}
  function syncHierarchyTabs(){document.querySelectorAll('.hierarchy .mini-tabs a').forEach(el=>el.classList.toggle('active',el.textContent.trim()===hierarchyPeriod));}
  function setQuery(key,value,push=true){const u=new URL(location.href);u.searchParams.set(key,value);history[push?'pushState':'replaceState'](null,'',u);}

  // Weekly Market Focus V1: independently select FX crosses by normalized weekly move.
  // Stable rendering contract: exactly eight valid cards or the previous eight-card fallback.
  function weeklyFocusCards(){
    const rows=datedRows(),asof=fxAsOf();
    const fxReady=fresh(asof,FX_MAX_AGE_DAYS)&&rows.length>=35;
    const labels=CCYS.flatMap((a,i)=>CCYS.slice(i+1).map(b=>a+b));
    const ranked=[];
    for(const label of (fxReady?labels:[])){
      const values=rows.map(row=>pairValue(row,label));
      if(values.some(v=>v===null||v<=0))continue;
      const logs=values.map(v=>Math.log(v));
      const d=logs.slice(1).map((v,i)=>v-logs[i]);
      const base=d.slice(-65,-5);
      if(base.length<20)continue;
      const mean=base.reduce((a,b)=>a+b,0)/base.length;
      const stdev=Math.sqrt(base.reduce((a,b)=>a+(b-mean)**2,0)/base.length);
      if(!(stdev>0))continue;
      const move=d.slice(-5).reduce((a,b)=>a+b,0)-5*mean;
      const card=pairCard(label,heroPeriod);
      if(card.value==='—')continue;
      ranked.push({label,score:Math.abs(move)/(stdev*Math.sqrt(5)),card});
    }
    // Include verified G8 sovereign rates. Skip stale and incompatible historical basis.
    for(const ccy of CCYS){
      const country=rates?.[ccy];
      if(!country)continue;
      for(const tenor of [2,10]){
        if(tenor===2&&/NOT_SAME_BASIS|WITHHELD|STALE/i.test(String(country.history2_quality||'')))continue;
        const h=rateHistory(country,tenor===2?'history2':'history10');
        const asof=h.at(-1)?.date;
        // The series itself must be fresh; a newer metadata date cannot revive stale history.
        if(!fresh(asof,RATES_MAX_AGE_DAYS)||!fresh(country.date,RATES_MAX_AGE_DAYS)||h.length<35)continue;
        if(String(country.date).slice(0,10)!==String(asof).slice(0,10))continue;
        const d=h.slice(1).map((row,i)=>row.value-h[i].value);
        const base=d.slice(-65,-5);
        if(base.length<20)continue;
        const mu=base.reduce((a,b)=>a+b,0)/base.length;
        const sigma=Math.sqrt(base.reduce((a,b)=>a+(b-mu)**2,0)/base.length);
        if(!(sigma>0))continue;
        const deviation=d.slice(-5).reduce((a,b)=>a+b,0)-5*mu;
        const window=h.slice(startRateIndex(h,heroPeriod));
        if(window.length<2)continue;
        const latest=h.at(-1).value,delta=(latest-window[0].value)*100;
        ranked.push({label:ccy+tenor,ccys:[ccy],score:Math.abs(deviation)/(sigma*Math.sqrt(5)),
          card:{label:ccy+' '+tenor+'Y',value:latest.toFixed(2)+'%',
            change:(delta>0?'+':'')+delta.toFixed(1)+'bp',dir:delta>=0?'up':'down',
            values:sampled(window.map(x=>x.value)),
            title:'Rendimenti '+ccy+' '+tenor+'Y · dati al '+asof}});
      }
    }
    ranked.sort((a,b)=>b.score-a.score||a.label.localeCompare(b.label));
    const chosen=[],exposure={};
    for(const item of ranked){
      const members=item.ccys||[item.label.slice(0,3),item.label.slice(3,6)];
      if(members.some(c=>(exposure[c]||0)>=3))continue;
      chosen.push(item.card);
      members.forEach(c=>exposure[c]=(exposure[c]||0)+1);
      if(chosen.length===8)break;
    }
    return chosen.length===8?chosen:null;
  }
  function renderHero(){const host=document.querySelector('.ticker-strip');if(!host)return;const cards=weeklyFocusCards()||[...PAIRS.map(p=>pairCard(p,heroPeriod)),rateCard(2,heroPeriod),rateCard(10,heroPeriod)];rendering=true;host.innerHTML=cards.map(c=>`<div class="ticker" title="${esc(c.title)}"><div><small>${esc(c.label)}</small><b>${esc(c.value)}</b><em class="${c.dir}">${esc(c.change)}</em></div><svg viewBox="0 0 90 44"><polyline class="${c.dir}" points="${sparkPoints(c.values)}"/></svg></div>`).join('');rendering=false;syncHeroTabs();document.documentElement.setAttribute('data-market-snapshot',(rates||fx)?'READY':'EMPTY');document.documentElement.setAttribute('data-hero-period',heroPeriod);document.documentElement.setAttribute('data-fx-freshness',fresh(fxAsOf(),FX_MAX_AGE_DAYS)?'FRESH':'WITHHELD');const usdAsOf=rates?.USD?.date||rateHistory(rates?.USD,'history2').at(-1)?.date||null;document.documentElement.setAttribute('data-rates-freshness',fresh(usdAsOf,RATES_MAX_AGE_DAYS)?'FRESH':'WITHHELD');}
  function currencyStrength(period){const asof=fxAsOf(),rows=datedRows();if(!fresh(asof,FX_MAX_AGE_DAYS)||rows.length<2)return[];const si=startIndex(rows,period),a=rows[si],b=rows.at(-1),raw=CCYS.map(ccy=>{const pa=ccy==='EUR'?1:1/n(a[ccy]),pb=ccy==='EUR'?1:1/n(b[ccy]);return{ccy,r:(pb/pa-1)*100};});const mean=raw.reduce((s,x)=>s+x.r,0)/raw.length;return raw.map(x=>({...x,score:x.r-mean})).sort((x,y)=>y.score-x.score);}
  function renderHierarchy(){const rows=[...document.querySelectorAll('.hierarchy .rankrow')],data=currencyStrength(hierarchyPeriod);if(!rows.length)return;if(!data.length){rows.forEach(el=>{const label=el.querySelector(':scope > span'),bar=el.querySelector(':scope > i > b'),val=el.querySelector(':scope > em');if(label)label.textContent='—';if(bar){bar.className='';bar.style.width='0%';}if(val){val.className='';val.textContent='—';}});syncHierarchyTabs();document.documentElement.setAttribute('data-hierarchy-period',hierarchyPeriod);return;}const mx=Math.max(...data.map(x=>Math.abs(x.score)),.01);rows.forEach((el,i)=>{const x=data[i];if(!x)return;const label=el.querySelector(':scope > span'),bar=el.querySelector(':scope > i > b'),val=el.querySelector(':scope > em'),cls=x.score>=0?'pos':'neg';if(label)label.textContent=`${FLAGS[x.ccy]} ${x.ccy}`;if(bar){bar.className=cls;bar.style.width=`${Math.max(8,Math.abs(x.score)/mx*90).toFixed(1)}%`;}if(val){val.className=cls;val.textContent=`${x.score>0?'+':''}${x.score.toFixed(2)}%`;}});const note=document.querySelector('.hierarchy .hierarchy-note');if(note)note.textContent=`Conferma di mercato · fixing ECB al ${fxAsOf()||'—'} · non forza macro`;syncHierarchyTabs();document.documentElement.setAttribute('data-hierarchy-period',hierarchyPeriod);}
  function protectStrip(){const host=document.querySelector('.ticker-strip');if(!host)return;new MutationObserver(()=>{if(!rendering&&host.children.length===0&&(rates||fx))queueMicrotask(renderHero);}).observe(host,{childList:true});}

  function bindInteractions(){
    document.addEventListener('click',e=>{
      const hero=e.target.closest('.hero-tabs a');
      if(hero){const next=hero.textContent.trim();if(ALLOWED.includes(next)){e.preventDefault();if(next!==heroPeriod){heroPeriod=next;setQuery('tf',next,true);renderHero();}return;}}
      const h=e.target.closest('.hierarchy .mini-tabs a');
      if(h){const next=h.textContent.trim();if(HIERARCHY_ALLOWED.includes(next)){e.preventDefault();if(next!==hierarchyPeriod){hierarchyPeriod=next;setQuery('h',next,true);renderHierarchy();}}}
    });
    addEventListener('popstate',()=>{const p=new URLSearchParams(location.search);const nextHero=ALLOWED.includes(p.get('tf'))?p.get('tf'):'1D';const nextHierarchy=HIERARCHY_ALLOWED.includes(p.get('h'))?p.get('h'):'1D';const heroChanged=nextHero!==heroPeriod,hierarchyChanged=nextHierarchy!==hierarchyPeriod;heroPeriod=nextHero;hierarchyPeriod=nextHierarchy;if(heroChanged)renderHero();else syncHeroTabs();if(hierarchyChanged)renderHierarchy();else syncHierarchyTabs();});
    syncHeroTabs();syncHierarchyTabs();
  }

  async function run(){bindInteractions();protectStrip();const [r,f]=await Promise.all([tryLoad(RATES_PATH),tryLoad(FX_PATH)]);rates=r;fx=f;renderHero();renderHierarchy();if(!rates&&!fx)document.documentElement.setAttribute('data-market-snapshot','FAIL');}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();