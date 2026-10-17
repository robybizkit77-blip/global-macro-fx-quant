(()=>{
  'use strict';

  const STORAGE_KEY='gmfq.website.watchlist.v1';
  const PATH='../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json';

  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const norm=v=>String(v??'').trim();

  function readSaved(){
    try{
      const x=JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]');
      return Array.isArray(x)?x:[];
    }catch{return[];}
  }

  function thesisLabel(s){
    const q=norm(s?.structural?.quality||s?.structural?.relation);
    if(!q)return '—';
    const u=q.toUpperCase();
    if(u.includes('FORTE'))return 'FORTE';
    if(u.includes('PARZIALE'))return 'PARZIALE';
    if(u.includes('DEBOLE'))return 'DEBOLE';
    return q;
  }

  function nowLabel(s){return norm(s?.quality)||'—';}
  function priceLabel(s){return norm(s?.price?.text)||'—';}
  function timingLabel(s){return norm(s?.timing?.text)||'Da monitorare';}

  function clsForText(v){
    const s=String(v||'').toUpperCase();
    if(s.includes('CONFERMA')||s==='PULITO')return 'watch-good';
    if(s.includes('DIVERGE')||s.includes('NON '))return 'watch-bad';
    if(s.includes('RISCHI')||s.includes('CONTRARIO')||s.includes('MONITOR'))return 'watch-warn';
    return 'watch-neutral';
  }

  function injectStyle(){
    if(document.getElementById('gmfq-watch-operational-style'))return;
    const st=document.createElement('style');
    st.id='gmfq-watch-operational-style';
    st.textContent=`
      .watch .card-head h2{display:flex;align-items:center;gap:8px}
      .watch .watch-subline{font-size:11px;color:#7f97ab;margin:-2px 0 10px}
      .watch-table .thead,.watch-table>div:not(.thead){display:grid!important;grid-template-columns:minmax(86px,.95fr) minmax(74px,.85fr) minmax(98px,1fr) minmax(120px,1.15fr) minmax(130px,1.3fr)!important;gap:12px;align-items:center}
      .watch-table .thead span{font-size:10px;letter-spacing:.08em;color:#7891a6;text-transform:uppercase}
      .watch-table>div:not(.thead){min-height:50px;border-top:1px solid rgba(127,151,171,.14)}
      .watch-table>div>*{min-width:0}
      .watch-table a{color:#f3f7fb;text-decoration:none;font-weight:700}
      .watch-pill{display:inline-flex;align-items:center;justify-content:center;min-height:22px;padding:2px 8px;border-radius:7px;font-size:10px;font-weight:700;letter-spacing:.02em;background:rgba(127,151,171,.12);white-space:nowrap}
      .watch-good{color:#4be0a5}.watch-bad{color:#c97aff}.watch-warn{color:#f4bd61}.watch-neutral{color:#9fb3c4}
      .watch-state{font-size:11px;line-height:1.25}
      .watch-empty-row{grid-template-columns:28px 1fr auto!important;padding:14px 0}
      @media(max-width:760px){
        .watch-table .thead{display:none!important}
        .watch-table>div:not(.thead){grid-template-columns:1fr 1fr!important;gap:6px 12px;padding:10px 0}
        .watch-table>div:not(.thead)>:first-child{grid-column:1/-1}
        .watch-state{grid-column:1/-1}
      }
    `;
    document.head.appendChild(st);
  }

  function render(data){
    const card=document.querySelector('.watch');
    const host=card?.querySelector('.watch-table');
    if(!card||!host)return;
    injectStyle();
    const head=card.querySelector('.card-head h2');
    if(head)head.innerHTML='<span>▮</span>Watchlist · Monitor operativo';
    let sub=card.querySelector('.watch-subline');
    if(!sub){sub=document.createElement('div');sub.className='watch-subline';card.querySelector('.card-head')?.insertAdjacentElement('afterend',sub);}
    sub.textContent='Pair salvate · Tesi vs Adesso · conferma prezzo e timing';

    const header='<div class="thead"><span>PAIR</span><span>TESI</span><span>ADESSO</span><span>PREZZO</span><span>STATO</span></div>';
    const saved=readSaved();
    if(!saved.length){
      host.innerHTML=header+'<div class="watch-empty-row"><span>☆</span><b>Nessuna pair in watchlist</b><small><a href="watchlist.html">Apri Watchlist →</a></small></div>';
      document.documentElement.dataset.dashboardWatch='EMPTY';
      return;
    }
    const pairs=data?.pairs||{};
    const rows=saved.slice(0,6).map(raw=>{
      const code=String(raw).replace(/[^A-Z]/g,'');
      const x=pairs[code]||{};
      const s=x.setup||{};
      const pair=x.canonical_pair||raw;
      const thesis=thesisLabel(s), now=nowLabel(s), price=priceLabel(s), timing=timingLabel(s);
      return `<div>
        <b><a href="coppia.html?pair=${encodeURIComponent(code)}">${esc(pair)}</a></b>
        <span class="watch-pill ${clsForText(thesis)}">${esc(thesis)}</span>
        <span class="watch-pill ${clsForText(now)}">${esc(now)}</span>
        <span class="${clsForText(price)}">${esc(price)}</span>
        <small class="watch-state ${clsForText(timing)}">${esc(timing)}</small>
      </div>`;
    });
    host.innerHTML=header+rows.join('');
    document.documentElement.dataset.dashboardWatch='OPERATIONAL';
  }

  async function run(){
    try{
      const r=await fetch(PATH,{cache:'no-store'});
      if(!r.ok)throw new Error(`HTTP ${r.status}`);
      render(await r.json());
    }catch(e){console.warn('[GMFQ dashboard watchlist]',e);}
  }

  run();
  setTimeout(run,700);
})();
