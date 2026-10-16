(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const NAMES={USD:'United States',EUR:'Euro Area',GBP:'United Kingdom',JPY:'Japan',CHF:'Switzerland',CAD:'Canada',AUD:'Australia',NZD:'New Zealand'};
  const COLORS=['#e6b448','#2f8ce9','#a05af0','#f34b66','#24d99a','#e98b38','#49c2d0','#c3d067'];
  const OIS_KEYS=['policy','3m','6m','12m'];
  const OIS_LABELS={policy:'Policy','3m':'3M','6m':'6M','12m':'12M'};
  let rates=null,ois=null,days=252;
  const n=v=>Number.isFinite(Number(v))?Number(v):null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const sign=(v,d=0,suffix='')=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}${suffix}`};
  async function load(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}
  function y2(x){return n(x?.['2Y'])??n(x?.current?.y2)??n(x?.history2?.last_value);}
  function y10(x){return n(x?.['10Y'])??n(x?.current?.y10)??n(x?.history10?.last_value);}
  function hist(x,key){
    const h=x?.[key];
    if(Array.isArray(h)) return h.map(p=>({date:p.date,value:n(p.value)})).filter(p=>p.value!==null);
    if(Array.isArray(h?.dates)&&Array.isArray(h?.values)) return h.dates.map((d,i)=>({date:d,value:n(h.values[i])})).filter(p=>p.value!==null);
    return [];
  }
  function card(ccy){
    const x=rates?.[ccy]||{}; const a=y2(x),b=y10(x),curve=n(x.curve_bp)??((a!==null&&b!==null)?(b-a)*100:null);
    return `<article class="rate-card"><div class="rate-card-top"><div class="rate-identity"><span class="flag">${FLAGS[ccy]}</span><div><b>${ccy}</b><small>${esc(NAMES[ccy])}</small></div></div><span class="rate-quality">${esc(String(x.quality||'CURRENT').replaceAll('_',' '))}</span></div><div class="rate-levels"><div><small>2Y</small><b>${a===null?'—':a.toFixed(2)+'%'}</b></div><div><small>10Y</small><b>${b===null?'—':b.toFixed(2)+'%'}</b></div><div><small>2s10s</small><b>${curve===null?'—':sign(curve,0,'bp')}</b></div></div><div class="rate-state"><span>${esc(x.curve_state||'—')}</span><em>${esc(x.date||x.history2?.last_date||'')}</em></div></article>`;
  }
  function renderCards(){const host=document.getElementById('rates-grid');if(host)host.innerHTML=ORDER.map(card).join('');}
  function renderCurveTable(){
    const host=document.getElementById('curve-table'); if(!host)return;
    const rows=ORDER.map(ccy=>{const x=rates?.[ccy]||{},a=y2(x),b=y10(x),curve=n(x.curve_bp)??((a!==null&&b!==null)?(b-a)*100:null);return{ccy,a,b,curve,state:x.curve_state||'—'};}).filter(r=>r.a!==null||r.b!==null);
    host.innerHTML='<div class="curve-row head"><span>CCY</span><span>2Y</span><span>10Y</span><span>2s10s</span><span>Stato</span></div>'+rows.map(r=>`<div class="curve-row"><b>${FLAGS[r.ccy]} ${r.ccy}</b><span>${r.a===null?'—':r.a.toFixed(2)+'%'}</span><span>${r.b===null?'—':r.b.toFixed(2)+'%'}</span><em class="${(r.curve||0)>=0?'pos':'neg'}">${r.curve===null?'—':sign(r.curve,0,'bp')}</em><span class="state-pill">${esc(r.state)}</span></div>`).join('');
  }
  function renderMoves(){
    const host=document.getElementById('move-table');if(!host)return;
    host.innerHTML='<div class="move-row head"><span>CCY</span><span>Δ 2Y</span><span>Δ 10Y</span><span>Lettura</span></div>'+ORDER.map(ccy=>{const x=rates?.[ccy]||{},d2=n(x.chg2_bp),d10=n(x.chg10_bp);return `<div class="move-row"><b>${FLAGS[ccy]} ${ccy}</b><em class="${(d2||0)>=0?'pos':'neg'}">${d2===null?'—':sign(d2,1,'bp')}</em><em class="${(d10||0)>=0?'pos':'neg'}">${d10===null?'—':sign(d10,1,'bp')}</em><span>${esc(x.curve_state||'—')}</span></div>`;}).join('');
  }
  function renderLegend(){const host=document.getElementById('rates-legend');if(host)host.innerHTML=ORDER.map((c,i)=>`<span class="c${i}"><i></i>${c} ${y2(rates?.[c])?.toFixed(2)??'—'}%</span>`).join('');}
  function renderChart(){
    const svg=document.getElementById('rates-chart');if(!svg)return;
    const series=ORDER.map((ccy,i)=>({ccy,color:COLORS[i],data:hist(rates?.[ccy],'history2').slice(-days)})).filter(s=>s.data.length>1);
    if(!series.length){svg.innerHTML='';return;}
    const all=series.flatMap(s=>s.data.map(p=>p.value)); const min=Math.floor((Math.min(...all)-.25)*2)/2, max=Math.ceil((Math.max(...all)+.25)*2)/2;
    const W=900,H=280,L=42,R=12,T=15,B=28,span=(max-min)||1;
    const y=v=>T+(H-T-B)*(1-(v-min)/span);
    let out='<g class="grid">';
    for(let i=0;i<=5;i++){const yy=T+(H-T-B)*i/5;out+=`<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}"/>`;}
    out+='</g><g class="axis">';
    for(let i=0;i<=5;i++){const v=max-(max-min)*i/5,yy=T+(H-T-B)*i/5;out+=`<text x="4" y="${yy+3}">${v.toFixed(1)}%</text>`;}
    const ref=series[0].data;[0,.25,.5,.75,1].forEach(q=>{const p=ref[Math.min(ref.length-1,Math.round((ref.length-1)*q))];if(p){const x=L+(W-L-R)*q;out+=`<text x="${x}" y="${H-7}" text-anchor="middle">${String(p.date).slice(0,7)}</text>`;}});out+='</g>';
    series.forEach(s=>{const pts=s.data.map((p,i)=>`${(L+(W-L-R)*i/(s.data.length-1)).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');out+=`<polyline points="${pts}" style="stroke:${s.color}"/>`;});
    svg.innerHTML=out;
    const asof=document.getElementById('rates-asof');if(asof)asof.textContent=`${days===63?'3M':days===126?'6M':'1Y'} · ${series[0].data.at(-1)?.date||'—'}`;
  }

  function oisRow(ccy){
    const x=ois?.currencies?.[ccy]||{};
    return {
      ccy,
      raw:x,
      asOf:x.as_of||'—',
      quality:x.quality||x.operational_status||'—',
      source:x.source||'—',
      points:{policy:n(x.policy_rate),'3m':n(x.horizons?.['3m']?.rate),'6m':n(x.horizons?.['6m']?.rate),'12m':n(x.horizons?.['12m']?.rate)},
      delta:{'3m':n(x.horizons?.['3m']?.policy_delta_bp),'6m':n(x.horizons?.['6m']?.policy_delta_bp),'12m':n(x.horizons?.['12m']?.policy_delta_bp)}
    };
  }
  function lineSegments(points,xs,ys){
    let out='';
    for(let i=0;i<points.length-1;i++){
      const a=points[i],b=points[i+1];
      if(a===null||b===null)continue;
      out+=`<line class="curve" x1="${xs[i]}" y1="${ys(a)}" x2="${xs[i+1]}" y2="${ys(b)}"/>`;
    }
    return out;
  }
  function miniOis(row){
    const vals=OIS_KEYS.map(k=>row.points[k]);
    const finite=vals.filter(v=>v!==null);
    const lo=finite.length?Math.min(...finite):0,hi=finite.length?Math.max(...finite):1,span=(hi-lo)||1;
    const xs=[8,55,102,150],y=v=>48-36*((v-lo)/span);
    const seg=lineSegments(vals,xs,y);
    const dots=vals.map((v,i)=>v===null?'':`<circle cx="${xs[i]}" cy="${y(v)}" r="3"/>`).join('');
    const levels=OIS_KEYS.map(k=>`<span>${OIS_LABELS[k]}<b>${row.points[k]===null?'—':row.points[k].toFixed(3)+'%'}</b></span>`).join('');
    const published=finite.length;
    return `<article class="ois-card"><div class="ois-card-top"><div class="ois-card-title"><span class="flag">${FLAGS[row.ccy]}</span><div><b>${row.ccy}</b><small>${esc(row.asOf)}</small></div></div><span class="ois-quality">${esc(String(row.quality).replaceAll('_',' '))}</span></div><svg class="ois-mini" viewBox="0 0 158 58" preserveAspectRatio="none"><line class="base" x1="8" y1="50" x2="150" y2="50"/>${seg}${dots}</svg><div class="ois-points">${levels}</div><div class="ois-card-foot"><span>${published}/4 punti</span><em>${esc(row.raw?.direction_vs_policy||'—')}</em></div></article>`;
  }
  function renderOisCards(){
    const host=document.getElementById('ois-grid');if(!host)return;
    const rows=ORDER.map(oisRow);
    host.innerHTML=rows.map(miniOis).join('');
    const dates=rows.map(r=>r.asOf).filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x)).sort();
    const asof=document.getElementById('ois-asof');if(asof)asof.textContent=`Policy → 3M → 6M → 12M · latest ${dates.at(-1)||'—'} · mixed-source quality visible`;
  }
  function renderOisLegend(){
    const host=document.getElementById('ois-legend');if(!host)return;
    host.innerHTML=ORDER.map((c,i)=>`<span class="c${i}"><i></i>${c}</span>`).join('');
  }
  function renderOisCombined(){
    const svg=document.getElementById('ois-chart');if(!svg)return;
    const rows=ORDER.map(oisRow);
    const all=rows.flatMap(r=>OIS_KEYS.map(k=>r.points[k]).filter(v=>v!==null));
    if(!all.length){svg.innerHTML='';return;}
    const min=Math.floor((Math.min(...all)-.25)*2)/2,max=Math.ceil((Math.max(...all)+.25)*2)/2,span=(max-min)||1;
    const W=900,H=300,L=45,R=20,T=20,B=32;
    const xs=OIS_KEYS.map((_,i)=>L+(W-L-R)*i/(OIS_KEYS.length-1));
    const y=v=>T+(H-T-B)*(1-(v-min)/span);
    let out='<g class="grid">';
    for(let i=0;i<=5;i++){const yy=T+(H-T-B)*i/5;out+=`<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}"/>`;}
    xs.forEach(x=>{out+=`<line x1="${x}" y1="${T}" x2="${x}" y2="${H-B}"/>`;});
    out+='</g><g class="axis">';
    for(let i=0;i<=5;i++){const v=max-(max-min)*i/5,yy=T+(H-T-B)*i/5;out+=`<text x="4" y="${yy+3}">${v.toFixed(1)}%</text>`;}
    OIS_KEYS.forEach((k,i)=>{out+=`<text x="${xs[i]}" y="${H-8}" text-anchor="middle">${OIS_LABELS[k]}</text>`;});
    out+='</g>';
    rows.forEach((r,ri)=>{
      const vals=OIS_KEYS.map(k=>r.points[k]);
      for(let i=0;i<vals.length-1;i++){
        const a=vals[i],b=vals[i+1];if(a===null||b===null)continue;
        out+=`<line x1="${xs[i]}" y1="${y(a)}" x2="${xs[i+1]}" y2="${y(b)}" style="stroke:${COLORS[ri]};stroke-width:1.8"/>`;
      }
      vals.forEach((v,i)=>{if(v!==null)out+=`<circle cx="${xs[i]}" cy="${y(v)}" r="3" style="fill:${COLORS[ri]}"/>`;});
    });
    svg.innerHTML=out;
  }
  function renderOisMatrix(){
    const host=document.getElementById('ois-matrix');if(!host)return;
    const rows=ORDER.map(oisRow);
    host.innerHTML='<div class="ois-row head"><span>CCY</span><span>3M</span><span>6M</span><span>12M</span></div>'+rows.map(r=>`<div class="ois-row"><b>${FLAGS[r.ccy]} ${r.ccy}</b>${['3m','6m','12m'].map(k=>{const v=r.delta[k];return `<em class="${v===null?'muted':v>=0?'pos':'neg'}">${v===null?'—':sign(v,1,'bp')}</em>`;}).join('')}</div>`).join('');
  }
  function renderOis(){renderOisCards();renderOisLegend();renderOisCombined();renderOisMatrix();}

  function render(){renderCards();renderCurveTable();renderMoves();renderLegend();renderChart();renderOis();document.documentElement.setAttribute('data-tassi-page','READY');document.documentElement.setAttribute('data-ois-curves','READY');}
  function bind(){
    document.querySelectorAll('#rates-timeframes button').forEach(btn=>btn.addEventListener('click',()=>{days=Number(btn.dataset.days)||252;document.querySelectorAll('#rates-timeframes button').forEach(x=>x.classList.toggle('active',x===btn));renderChart();}));
    document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));
    const control=document.querySelector('.pro-card button');if(control)control.addEventListener('click',()=>location.href='index.html');
  }
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d);}
  async function main(){bind();clock();setInterval(clock,30000);try{[rates,ois]=await Promise.all([load(ROOT+'NATIVE_RATES_DATA.json'),load(ROOT+'OIS_OPERATIONAL_VIEW.json')]);render();}catch(e){console.warn('[GMFQ tassi]',e);document.documentElement.setAttribute('data-tassi-page','FAIL');document.documentElement.setAttribute('data-ois-curves','WITHHELD');}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
