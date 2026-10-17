(()=>{
  'use strict';
  const PATH='../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json';
  const PRIORITY={'PULITO':5,'CON RISCHI':4,'DA CONFERMARE':3,'DA MONITORARE':2,'NON VALUTABILE':1};
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const trim=(v,n)=>{const s=String(v??'');return s.length<=n?s:s.slice(0,n-1).trimEnd()+'…';};
  function clsQuality(v){const s=String(v||'').toUpperCase();if(s==='PULITO')return'clean';if(s==='CON RISCHI')return'risky';if(s==='DA CONFERMARE')return'confirm';if(s==='DA MONITORARE')return'watch';return'neutral';}
  function clsPrice(v){const s=String(v||'').toUpperCase();if(s==='GOOD')return'good';if(s==='BAD')return'bad';return'neutral';}
  function rows(data){return Object.entries(data?.pairs||{}).map(([code,x])=>{const s=x?.setup||{},st=s.structural||{},p=s.price||{},t=s.timing||{};return{code,pair:x?.canonical_pair||`${code.slice(0,3)}/${code.slice(3,6)}`,fav:s.structuralFav||st.fav||'—',thesis:st.quality||x?.decision_frame?.quality||'—',attract:s.quality||'—',priceState:p.state||'NEUTRAL',price:p.text||x?.decision_frame?.priceReading||'—',timing:t.text||x?.decision_frame?.timing||'—',relation:st.relation||x?.decision_frame?.relation||'—'};}).sort((a,b)=>(PRIORITY[String(b.attract).toUpperCase()]||0)-(PRIORITY[String(a.attract).toUpperCase()]||0)||a.pair.localeCompare(b.pair));}
  function render(data){
    const card=document.querySelector('.setups');const host=card?.querySelector('.setup-table');if(!card||!host)return;
    const head=card.querySelector('.card-head h2');if(head)head.innerHTML='<span>▣</span>Setup FX prioritari · Tesi vs Adesso';
    let sub=card.querySelector('.setup-operational-subline');if(!sub){sub=document.createElement('div');sub.className='subline setup-operational-subline';card.querySelector('.card-head')?.after(sub);}sub.textContent='Tesi = struttura Macro + Tassi/CB · Adesso = qualità operativa corrente';
    const r=rows(data).slice(0,5);
    host.classList.add('setup-operational');
    host.innerHTML='<div class="setup-op-head"><span>#</span><span>COPPIA</span><span>FAV</span><span>TESI</span><span>ADESSO</span><span>PREZZO / TIMING</span></div>'+r.map((x,i)=>`<a class="setup-op-row" href="coppia.html?pair=${encodeURIComponent(x.code)}" title="${esc(x.relation)} · ${esc(x.timing)}"><span>${i+1}</span><b>${esc(x.pair)}</b><strong>${esc(x.fav)}</strong><em>${esc(trim(x.thesis,28))}</em><i class="${clsQuality(x.attract)}">${esc(x.attract)}</i><small><u class="${clsPrice(x.priceState)}">${esc(x.price)}</u><br>${esc(trim(x.timing,42))}</small></a>`).join('');
    document.documentElement.dataset.dashboardSetups='THESIS_VS_NOW';
  }
  function css(){if(document.getElementById('dashboard-setups-operational-css'))return;const s=document.createElement('style');s.id='dashboard-setups-operational-css';s.textContent=`
    .setup-operational{display:block!important;padding:0 10px 10px!important}
    .setup-op-head,.setup-op-row{display:grid;grid-template-columns:28px 82px 48px minmax(150px,.9fr) 96px minmax(190px,1.35fr);gap:8px;align-items:center}
    .setup-op-head{min-height:28px;color:#738898;font-size:7px;letter-spacing:.08em;border-bottom:1px solid #183246}
    .setup-op-row{min-height:50px;text-decoration:none;border-bottom:1px solid rgba(31,59,78,.72);color:#c8d6df}
    .setup-op-row:hover{background:rgba(22,73,112,.09)}.setup-op-row>b{color:#edf4f7;font-size:11px}.setup-op-row>strong{font-size:9px;color:#d8e5ec}.setup-op-row>em{font-style:normal;font-size:8px;color:#a9bdca;line-height:1.25}.setup-op-row>i{font-style:normal;font-size:7px;font-weight:700;text-align:center;padding:4px 5px;border-radius:5px;white-space:nowrap}.setup-op-row>small{font-size:8px;color:#8fa4b4;line-height:1.3}.setup-op-row u{text-decoration:none;font-weight:700}.setup-op-row u.good{color:#48d9a0}.setup-op-row u.bad{color:#ff6f82}.setup-op-row u.neutral{color:#a9bac6}
    .setup-op-row>i.clean{background:rgba(72,217,160,.12);color:#64e2af}.setup-op-row>i.risky{background:rgba(216,169,92,.12);color:#e7bd73}.setup-op-row>i.confirm{background:rgba(88,169,231,.12);color:#7dc0ef}.setup-op-row>i.watch{background:rgba(201,122,255,.12);color:#d59aff}.setup-op-row>i.neutral{background:rgba(145,164,180,.10);color:#9fb1bd}
    .setup-operational-subline{padding:0 12px 7px!important}
    @media(max-width:760px){.setup-op-head,.setup-op-row{grid-template-columns:24px 72px 42px minmax(110px,.8fr) 84px minmax(140px,1.1fr);gap:5px}.setup-op-row>em{font-size:7px}}
  `;document.head.appendChild(s)}
  async function run(){css();try{const r=await fetch(PATH,{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);const j=await r.json();if(j?.status!=='CURRENT_CANONICAL_ENGINE')throw new Error('non-canonical setup view');render(j)}catch(e){console.warn('[GMFQ dashboard setups]',e)}}
  window.GMFQ_DASHBOARD_SETUPS_RUN=run;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();
