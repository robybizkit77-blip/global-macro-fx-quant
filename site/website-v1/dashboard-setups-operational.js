(()=>{
  'use strict';
  const PATH='../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json';
  const PRIORITY={'PULITO':5,'CON RISCHI':4,'DA CONFERMARE':3,'DA MONITORARE':2,'NON VALUTABILE':1};
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const trim=(v,n)=>{const s=String(v??'');return s.length<=n?s:s.slice(0,n-1).trimEnd()+'…';};
  function reason(s){
    if(s.quality==='NON VALUTABILE')return 'Dati insufficienti';
    if(s.price?.state==='BAD')return 'Prezzo contrario';
    if(s.timing?.state==='ADVERSE')return 'Timing contrario';
    if(s.extension?.state==='ADVANCED')return 'Prezzo esteso';
    if(s.cot?.state==='DIVERGENT')return 'COT non conferma';
    if(s.structural?.quality==='PILASTRI DIVISI')return 'Driver in conflitto';
    if(s.timing?.state==='UNCERTAIN')return 'Timing incerto';
    if(s.timing?.state==='MIXED'||s.timing?.state==='PARTIAL')return 'Serve conferma';
    if(s.price?.state==='NEUTRAL')return 'Prezzo da confermare';
    if(s.quality==='PULITO')return 'Driver coerenti';
    return 'Conferme incomplete';
  }
  function clsQuality(v){const s=String(v||'').toUpperCase();if(s==='PULITO')return'clean';if(s==='CON RISCHI')return'risky';if(s==='DA CONFERMARE')return'confirm';if(s==='DA MONITORARE')return'watch';return'neutral';}
  function clsPrice(v){const s=String(v||'').toUpperCase();if(s==='GOOD')return'good';if(s==='BAD')return'bad';return'neutral';}
  function rows(data){return Object.entries(data?.pairs||{}).map(([code,x])=>{const s=x?.setup||{},st=s.structural||{},p=s.price||{},t=s.timing||{};return{code,pair:x?.canonical_pair||`${code.slice(0,3)}/${code.slice(3,6)}`,fav:s.structuralFav||st.fav||'—',thesis:st.quality||x?.decision_frame?.quality||'—',attract:s.quality||'—',reason:reason(s),priceState:p.state||'NEUTRAL',price:p.text||x?.decision_frame?.priceReading||'—',timing:t.text||x?.decision_frame?.timing||'—',relation:st.relation||x?.decision_frame?.relation||'—'};}).sort((a,b)=>(PRIORITY[String(b.attract).toUpperCase()]||0)-(PRIORITY[String(a.attract).toUpperCase()]||0)||a.pair.localeCompare(b.pair));}
  function render(data){
    const card=document.querySelector('.setups');const host=card?.querySelector('.setup-table');if(!card||!host)return;
    const head=card.querySelector('.card-head h2');if(head)head.innerHTML='<span>▣</span>Setup FX prioritari · Tesi vs Adesso';
    let sub=card.querySelector('.setup-operational-subline');if(!sub){sub=document.createElement('div');sub.className='subline setup-operational-subline';card.querySelector('.card-head')?.after(sub);}sub.textContent='Tesi = struttura Macro + Tassi/CB · Adesso = qualità operativa corrente';
    const r=rows(data).slice(0,5);
    host.classList.add('setup-operational');
    host.innerHTML='<div class="setup-op-head"><span>#</span><span>COPPIA</span><span>FAV</span><span>TESI</span><span>ADESSO</span><span>PREZZO / TIMING</span></div>'+r.map((x,i)=>`<a class="setup-op-row" href="coppia.html?pair=${encodeURIComponent(x.code)}" title="${esc(x.relation)} · ${esc(x.timing)}"><span>${i+1}</span><b>${esc(x.pair)}</b><strong>${esc(x.fav)}</strong><em>${esc(trim(x.thesis,28))}</em><i class="${clsQuality(x.attract)}">${esc(x.reason)}</i><small><u class="${clsPrice(x.priceState)}">${esc(x.price)}</u><span>${esc(trim(x.timing,42))}</span></small></a>`).join('');
    document.documentElement.dataset.dashboardSetups='THESIS_VS_NOW';
  }
  function css(){if(document.getElementById('dashboard-setups-operational-css'))return;const s=document.createElement('style');s.id='dashboard-setups-operational-css';s.textContent=`
    .setup-table.setup-operational{display:block!important;padding:0 10px 10px!important;overflow:hidden!important}
    .setup-table.setup-operational>.setup-op-head,.setup-table.setup-operational>.setup-op-row{display:grid!important;grid-template-columns:28px 96px 54px minmax(0,1.2fr) 148px minmax(0,1.1fr)!important;column-gap:10px!important;align-items:center!important;width:100%!important;box-sizing:border-box!important}
    .setup-op-head>*,.setup-op-row>*{min-width:0!important;box-sizing:border-box!important}
    .setup-op-head{min-height:30px!important;color:#738898!important;font-size:7px!important;letter-spacing:.08em!important;border-bottom:1px solid #183246!important;white-space:nowrap!important}
    .setup-op-head>span{overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important}
    .setup-op-row{min-height:56px!important;text-decoration:none!important;border-bottom:1px solid rgba(31,59,78,.72)!important;color:#c8d6df!important}
    .setup-op-row:hover{background:rgba(22,73,112,.09)!important}
    .setup-op-row>b{color:#edf4f7!important;font-size:11px!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
    .setup-op-row>strong{font-size:9px!important;color:#d8e5ec!important;white-space:nowrap!important}
    .setup-op-row>em{font-style:normal!important;font-size:8px!important;color:#a9bdca!important;line-height:1.25!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important}
    .setup-op-row>i{font-style:normal!important;font-size:7px!important;font-weight:700!important;text-align:center!important;padding:5px 6px!important;border-radius:6px!important;white-space:nowrap!important;width:100%!important;max-width:148px!important;justify-self:center!important}
    .setup-op-row>small{display:flex!important;flex-direction:column!important;justify-content:center!important;gap:3px!important;font-size:8px!important;color:#8fa4b4!important;line-height:1.2!important;overflow:hidden!important}
    .setup-op-row>small>u,.setup-op-row>small>span{display:block!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important}
    .setup-op-row u{text-decoration:none!important;font-weight:700!important}.setup-op-row u.good{color:#48d9a0!important}.setup-op-row u.bad{color:#c97aff!important}.setup-op-row u.neutral{color:#a9bac6!important}
    .setup-op-row>i.clean{background:rgba(72,217,160,.12)!important;color:#64e2af!important}.setup-op-row>i.risky{background:rgba(216,169,92,.12)!important;color:#e7bd73!important}.setup-op-row>i.confirm{background:rgba(88,169,231,.12)!important;color:#7dc0ef!important}.setup-op-row>i.watch{background:rgba(201,122,255,.12)!important;color:#d59aff!important}.setup-op-row>i.neutral{background:rgba(145,164,180,.10)!important;color:#9fb1bd!important}
    .setup-operational-subline{padding:0 12px 7px!important}
    @media(min-width:761px) and (max-width:1500px){
      .setup-table.setup-operational>.setup-op-head,.setup-table.setup-operational>.setup-op-row{grid-template-columns:28px 84px 46px minmax(118px,1.15fr) 130px minmax(145px,1fr)!important;column-gap:6px!important}
      .setup-op-row{min-height:64px!important}
      .setup-op-row>em{white-space:normal!important;overflow:visible!important;text-overflow:clip!important}
      .setup-op-row>small{overflow:visible!important}
      .setup-op-row>small>u,.setup-op-row>small>span{white-space:normal!important;overflow:visible!important;text-overflow:clip!important}
    }
    @media(max-width:760px){
      .setup-table.setup-operational>.setup-op-head{display:none!important}
      .setup-table.setup-operational>.setup-op-row{grid-template-columns:24px minmax(0,1fr) minmax(112px,1fr)!important;column-gap:9px!important;row-gap:6px!important;padding:12px 4px!important;min-height:102px!important}
      .setup-op-row>span:first-child{grid-column:1;grid-row:1/3;font-size:12px!important}
      .setup-op-row>b{grid-column:2;grid-row:1;font-size:13px!important}
      .setup-op-row>strong{grid-column:2;grid-row:2;font-size:11px!important}
      .setup-op-row>strong::before{content:'Favorisce ';color:#8fa4b4;font-weight:400}
      .setup-op-row>em{grid-column:2;grid-row:3;font-size:10px!important;white-space:normal!important;overflow:visible!important}
      .setup-op-row>i{grid-column:3;grid-row:1/3;width:100%!important;max-width:none!important;font-size:10px!important;white-space:normal!important;line-height:1.4!important;padding:8px!important}
      .setup-op-row>small{grid-column:3;grid-row:3;font-size:10px!important;line-height:1.4!important}
      .setup-op-row>small>u,.setup-op-row>small>span{white-space:normal!important;overflow:visible!important}
    }
    @media(max-width:760px){
      .setup-table.setup-operational>.setup-op-head,.setup-table.setup-operational>.setup-op-row{grid-template-columns:24px 78px 42px minmax(0,1fr) 110px minmax(0,1fr)!important;column-gap:6px!important}
      .setup-op-row>em{font-size:7px!important}.setup-op-row>i{font-size:6.5px!important;padding:4px!important}.setup-op-row>small{font-size:7px!important}
    }
  `;document.head.appendChild(s)}
  async function run(){css();try{const r=await fetch(PATH,{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);const j=await r.json();if(j?.status!=='CURRENT_CANONICAL_ENGINE')throw new Error('non-canonical setup view');render(j)}catch(e){console.warn('[GMFQ dashboard setups]',e)}}
  window.GMFQ_DASHBOARD_SETUPS_RUN=run;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();
