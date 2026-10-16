(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const NAMES={USD:'US Dollar',EUR:'Euro',GBP:'British Pound',JPY:'Japanese Yen',CHF:'Swiss Franc',CAD:'Canadian Dollar',AUD:'Australian Dollar',NZD:'New Zealand Dollar'};
  const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const TF_LABEL={ret1w:'1W',ret1m:'1M',ret3m:'3M',ret6m:'6M',ret1y:'1Y'};
  let state={d:null,rates:null,tf:'ret1w'};

  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const fmtPct=(v,d=2)=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}%`;};
  const cls=v=>(n(v)||0)>=0?'pos':'neg';

  async function load(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}

  function pairRow(ccy){
    if(ccy==='USD')return null;
    const pairs=Array.isArray(state.d?.pairs)?state.d.pairs:[];
    return pairs.find(x=>String(x?.pair||'').replace('/','')===`${ccy}USD`)||pairs.find(x=>String(x?.pair||'').replace('/','')===`USD${ccy}`)||null;
  }

  function perfVsUSD(ccy,tf){
    if(ccy==='USD')return 0;
    const row=pairRow(ccy); if(!row)return null;
    const raw=n(row[tf]); if(raw===null)return null;
    const pair=String(row.pair||'').replace('/','');
    if(pair===`${ccy}USD`)return raw;
    const r=raw/100;
    return (1/(1+r)-1)*100;
  }

  function rate2y(ccy){
    const live=n(state.rates?.[ccy]?.current?.y2);
    if(live!==null)return live;
    return n(state.d?.macro?.[ccy]?.rate2y);
  }

  function currencyCard(ccy){
    const m=state.d?.macro?.[ccy]||{};
    const perf=perfVsUSD(ccy,state.tf);
    const cot=n(m.cot_pct);
    const y2=rate2y(ccy);
    return `<div class="currency-top"><div class="currency-name"><span class="flag">${FLAGS[ccy]}</span><div><b>${ccy}</b><small>${esc(NAMES[ccy])}</small></div></div><div class="currency-perf"><b class="${cls(perf)}">${fmtPct(perf,2)}</b><small>vs USD · ${TF_LABEL[state.tf]}</small></div></div><div class="currency-meta"><div class="metric"><small>Cycle</small><b>${esc(m.cycle_it||m.cycle||'—')}</b></div><div class="metric"><small>2Y</small><b>${y2===null?'—':y2.toFixed(2)+'%'}</b></div><div class="metric"><small>COT pct</small><b>${cot===null?'—':cot.toFixed(0)}</b></div></div><div class="currency-note">${esc(m.simple_summary||'')}</div>`;
  }

  function renderCards(){
    document.querySelectorAll('.currency-card[data-ccy]').forEach(el=>{el.innerHTML=currencyCard(el.dataset.ccy);});
  }

  function renderPerformance(){
    const host=document.getElementById('perf-table'); if(!host)return;
    const rows=ORDER.map(ccy=>({ccy,v:perfVsUSD(ccy,state.tf)})).filter(x=>x.v!==null).sort((a,b)=>b.v-a.v);
    const max=Math.max(0.5,...rows.map(x=>Math.abs(x.v||0)));
    host.innerHTML=rows.map(x=>{
      const width=Math.min(48,Math.abs(x.v)/max*48);
      return `<div class="perf-row"><span>${FLAGS[x.ccy]} ${x.ccy}</span><i><b class="${cls(x.v)}" style="width:${width.toFixed(1)}%"></b></i><em class="${cls(x.v)}">${fmtPct(x.v,2)}</em></div>`;
    }).join('');
    const asof=document.getElementById('perf-asof');
    if(asof)asof.textContent=`${TF_LABEL[state.tf]} · FX as of ${state.d?.pairs?.[0]?.price_asof||state.d?.asOf||'—'}`;
  }

  function render(){renderCards();renderPerformance();document.documentElement.setAttribute('data-valute-page','READY');}

  function bind(){
    document.querySelectorAll('#currency-timeframes button').forEach(btn=>btn.addEventListener('click',()=>{
      const tf=btn.dataset.tf;if(!TF_LABEL[tf])return;
      state.tf=tf;
      document.querySelectorAll('#currency-timeframes button').forEach(x=>x.classList.toggle('active',x===btn));
      render();
    }));
    document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));
    const control=document.querySelector('.pro-card button');if(control)control.addEventListener('click',()=>location.href='index.html');
  }

  function clock(){
    const d=new Date();
    const date=document.getElementById('site-date'),time=document.getElementById('site-time');
    if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);
    if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d);
  }

  async function main(){
    bind();clock();setInterval(clock,30000);
    try{
      [state.d,state.rates]=await Promise.all([load(ROOT+'D.json'),load(ROOT+'NATIVE_RATES_DATA.json')]);
      render();
    }catch(e){console.warn('[GMFQ valute]',e);document.documentElement.setAttribute('data-valute-page','FAIL');}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true}); else main();
})();
