(()=>{
  'use strict';
  const PATH='../../live_data/sections/V250_COT_CHART_DATA.json';
  const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const last=a=>Array.isArray(a)&&a.length?a[a.length-1]:null;
  const prev=a=>Array.isArray(a)&&a.length>1?a[a.length-2]:null;
  const signed=(v,d=1,suffix='')=>v===null?'—':`${v>0?'+':''}${v.toFixed(d)}${suffix}`;
  function ageDays(s){if(!s)return Infinity;const t=Date.parse(`${String(s).slice(0,10)}T00:00:00Z`);if(!Number.isFinite(t))return Infinity;const n=new Date(),today=Date.UTC(n.getUTCFullYear(),n.getUTCMonth(),n.getUTCDate());return Math.floor((today-t)/86400000);}
  function classify(p){if(p===null)return{label:'—',cls:''};const r=Math.round(p);if(r>=80)return{label:'EXTREME LONG',cls:'ext-long'};if(r<=20)return{label:'EXTREME SHORT',cls:'ext-short'};return{label:'NEUTRALE',cls:'normal'};}
  function rows(data){return ORDER.map(ccy=>{const x=data?.[ccy]||{};const n0=num(last(x.netoi)),p=num(last(x.percentile)),net0=num(last(x.net)),net1=num(prev(x.net)),date=last(x.dates);const delta=net0!==null&&net1!==null?net0-net1:null;const pr=p===null?null:Math.round(p);const state=classify(p);return{ccy,netoi:n0,percentile:pr,delta,date,state,crowded:n0!==null&&Math.abs(n0)>=30};});}
  function render(data){
    const card=document.querySelector('.cot-card');const host=card?.querySelector('.cot-chart');const sub=card?.querySelector('.subline');if(!card||!host)return;
    const r=rows(data),asof=r.map(x=>x.date).filter(Boolean).sort().at(-1)||null;
    if(!asof||ageDays(asof)>10){host.innerHTML='<div class="cot-op-empty">Dati COT non correnti</div>';if(sub)sub.textContent=`CFTC Legacy Non-Commercial · dati al ${esc(asof||'—')}`;return;}
    host.classList.add('cot-operational');
    host.innerHTML=r.map(x=>{
      const side=x.netoi===null?'':x.netoi>=0?'pos':'neg';
      const crowd=x.crowded?' crowd':'';
      return `<div class="cot-op-row${crowd}" title="${esc(x.ccy)} · Net/OI ${signed(x.netoi,1,'%')} · percentile ${x.percentile??'—'} · Δ Net 1W ${signed(x.delta,0)}">
        <span class="cot-op-ccy">${FLAGS[x.ccy]} ${x.ccy}</span>
        <span class="cot-op-net ${side}">${signed(x.netoi,1,'%')}</span>
        <span class="cot-op-pct ${x.state.cls}">${x.percentile===null?'—':x.percentile+'°'}<small>${x.state.label}</small></span>
        <span class="cot-op-delta ${x.delta===null?'':x.delta>=0?'pos':'neg'}">${signed(x.delta,0)}</span>
        ${x.crowded?'<b class="cot-op-alert">⚠</b>':''}
      </div>`;
    }).join('');
    if(sub)sub.textContent=`Net/OI · Percentile 104W · Δ Net 1W · CFTC · dati al ${asof}`;
    const axis=card.querySelector('.cot-axis');if(axis)axis.style.display='none';
    document.documentElement.dataset.dashboardCot='OPERATIONAL_104W';
  }
  function css(){if(document.getElementById('dashboard-cot-operational-css'))return;const s=document.createElement('style');s.id='dashboard-cot-operational-css';s.textContent=`
    .cot-operational{display:grid!important;gap:5px!important;padding:6px 10px 10px!important;height:auto!important}
    .cot-op-row{display:grid;grid-template-columns:76px 68px minmax(110px,1fr) 82px 20px;align-items:center;gap:8px;min-height:27px;padding:0 7px;border:1px solid transparent;border-radius:6px;background:rgba(8,27,42,.42)}
    .cot-op-row.crowd{border-color:rgba(201,122,255,.42);background:rgba(201,122,255,.055)}
    .cot-op-ccy{font-size:10px;font-weight:700;color:#dce8ef}.cot-op-net,.cot-op-delta{font-size:10px;font-variant-numeric:tabular-nums;text-align:right}.cot-op-net.pos,.cot-op-delta.pos{color:#48d9a0}.cot-op-net.neg,.cot-op-delta.neg{color:#c97aff}
    .cot-op-pct{display:flex;align-items:center;gap:7px;font-size:10px;font-weight:700;font-variant-numeric:tabular-nums}.cot-op-pct small{font-size:7px;font-weight:700;letter-spacing:.045em}.cot-op-pct.ext-long{color:#48d9a0}.cot-op-pct.ext-short{color:#c97aff}.cot-op-pct.normal{color:#a9bac6}.cot-op-alert{font-size:10px;color:#ffcc66;text-align:center}
    .cot-op-empty{padding:18px;color:#91a5b4;font-size:10px}
    @media(max-width:650px){.cot-op-row{grid-template-columns:64px 58px minmax(94px,1fr) 68px 18px;gap:5px}.cot-op-pct small{display:none}}
  `;document.head.appendChild(s)}
  async function run(){css();try{const q=await fetch(PATH,{cache:'no-store'});if(!q.ok)throw new Error('HTTP '+q.status);const data=await q.json();render(data);setTimeout(()=>render(data),700);setTimeout(()=>render(data),1800)}catch(e){console.warn('[GMFQ dashboard COT]',e)}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();
