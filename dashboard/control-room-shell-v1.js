(()=>{
  'use strict';
  const SCHEMA='GMFQ_CONTROL_ROOM_SHELL_V1';
  const STYLE_ID='gmfq-control-room-shell-v1-style';
  const HEADER_ID='gmfq-control-room-header-v1';
  if(document.getElementById(STYLE_ID)) return;

  const shell=document.querySelector('.shell');
  if(!shell){
    window.GMFQ_CONTROL_ROOM_SHELL={schema:SCHEMA,status:'WITHHELD',reason:'SHELL_NOT_FOUND',core_effect:'NONE'};
    return;
  }
  const rail=shell.firstElementChild||null;
  const workspace=[...shell.children].find(el=>el!==rail)||document.querySelector('main,.main,.content,.main-content');
  if(!workspace){
    window.GMFQ_CONTROL_ROOM_SHELL={schema:SCHEMA,status:'WITHHELD',reason:'WORKSPACE_NOT_FOUND',core_effect:'NONE'};
    return;
  }

  document.documentElement.dataset.gmfqControlRoom='v1';
  document.body.classList.add('gmfq-control-room-v1');
  shell.setAttribute('data-gmfq-control-room-shell','true');
  rail?.setAttribute('data-gmfq-control-room-rail','true');
  workspace.setAttribute('data-gmfq-control-room-workspace','true');

  const navLabels=new Map([
    ['Overview','Dashboard'],['Panoramica','Dashboard'],['Currencies','Valute'],['Rates','Tassi'],
    ['Central Banks','Banche centrali'],['Central Bank','Banche centrali'],['Positioning','Posizionamento'],
    ['Pairs','Coppie'],['Risk','Rischio / Eventi'],['Calendar','Rischio / Eventi'],
    ['Top Themes','Top Themes'],['Themes','Top Themes'],['Library','Library']
  ]);
  if(rail){
    rail.querySelectorAll('button,a').forEach(el=>{
      const t=(el.textContent||'').trim();
      if(navLabels.has(t)) el.textContent=navLabels.get(t);
    });
  }

  if(!document.getElementById(HEADER_ID)){
    const header=document.createElement('section');
    header.id=HEADER_ID;
    header.className='gmfq-cr-head';
    header.innerHTML=`
      <div class="gmfq-cr-head__copy">
        <div class="gmfq-cr-kicker">GLOBAL MACRO FX QUANT · CONTROL ROOM</div>
        <h1>Control Room</h1>
        <p>Panoramica operativa di valute, tassi, pricing e rischio.</p>
      </div>
      <div class="gmfq-cr-head__tools" aria-label="Control Room tools">
        <label class="gmfq-cr-search"><span>⌕</span><input type="search" placeholder="Cerca valute, tassi, temi…" aria-label="Cerca nella dashboard"></label>
        <div class="gmfq-cr-status"><span class="gmfq-cr-dot"></span><span>LIVE DATA</span></div>
      </div>`;
    workspace.insertBefore(header,workspace.firstChild);
  }

  const css=`
  :root{
    --cr-bg:#050911;--cr-bg2:#07101b;--cr-rail:#07111c;--cr-panel:#0b1521;--cr-panel2:#0f1b29;
    --cr-line:rgba(154,169,190,.14);--cr-line2:rgba(197,168,98,.20);--cr-text:#f2f5f8;--cr-soft:#b8c3cf;
    --cr-muted:#7f8da0;--cr-gold:#c9aa68;--cr-blue:#5eb8ff;--cr-green:#4fd1a1;--cr-red:#ff7b86;
    --cr-radius:15px;--cr-shadow:0 18px 48px rgba(0,0,0,.22);
  }
  html,body{background:radial-gradient(1000px 500px at 62% -10%,rgba(26,92,148,.12),transparent 60%),var(--cr-bg)!important;color:var(--cr-text)!important;}
  body.gmfq-control-room-v1{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;}
  [data-gmfq-control-room-shell="true"]{min-height:100vh;background:transparent!important;}
  [data-gmfq-control-room-rail="true"]{
    background:linear-gradient(180deg,rgba(8,17,29,.99),rgba(5,11,19,.99))!important;
    border-right:1px solid var(--cr-line)!important;box-shadow:16px 0 40px rgba(0,0,0,.16)!important;
    backdrop-filter:blur(16px);z-index:8;
  }
  [data-gmfq-control-room-rail="true"]:before{
    content:'GLOBAL MACRO FX QUANT';display:block;padding:18px 16px 8px;color:var(--cr-gold);font:700 11px/1.2 Inter,sans-serif;
    letter-spacing:.13em;opacity:.92;
  }
  [data-gmfq-control-room-rail="true"] button,[data-gmfq-control-room-rail="true"] a{
    border-radius:10px!important;border:1px solid transparent!important;color:var(--cr-soft)!important;transition:.16s ease!important;
  }
  [data-gmfq-control-room-rail="true"] button:hover,[data-gmfq-control-room-rail="true"] a:hover{
    background:rgba(255,255,255,.045)!important;color:#fff!important;border-color:var(--cr-line)!important;
  }
  [data-gmfq-control-room-rail="true"] .active,[data-gmfq-control-room-rail="true"] [aria-current="page"]{
    background:linear-gradient(90deg,rgba(201,170,104,.13),rgba(94,184,255,.06))!important;color:#fff!important;
    box-shadow:inset 2px 0 0 var(--cr-gold)!important;border-color:rgba(201,170,104,.15)!important;
  }
  [data-gmfq-control-room-workspace="true"]{background:transparent!important;position:relative;}
  .gmfq-cr-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;padding:24px 28px 16px;margin:0 auto;max-width:1540px;border-bottom:1px solid var(--cr-line);}
  .gmfq-cr-kicker{font-size:10px;font-weight:800;letter-spacing:.16em;color:var(--cr-gold);margin-bottom:7px;}
  .gmfq-cr-head h1{margin:0;color:#fff;font-family:Georgia,"Times New Roman",serif;font-weight:600;font-size:34px;line-height:1;letter-spacing:-.035em;}
  .gmfq-cr-head p{margin:7px 0 0;color:var(--cr-muted);font-size:13px;}
  .gmfq-cr-head__tools{display:flex;align-items:center;gap:10px;}
  .gmfq-cr-search{height:38px;min-width:260px;display:flex;align-items:center;gap:8px;padding:0 11px;border:1px solid var(--cr-line);border-radius:10px;background:rgba(9,18,29,.82);color:var(--cr-muted);}
  .gmfq-cr-search input{width:100%;border:0;outline:0;background:transparent;color:var(--cr-text);font-size:12px;}
  .gmfq-cr-search input::placeholder{color:#6f7d90;}
  .gmfq-cr-status{height:38px;display:flex;align-items:center;gap:7px;padding:0 11px;border-radius:10px;border:1px solid rgba(79,209,161,.16);background:rgba(79,209,161,.055);font-size:10px;font-weight:800;letter-spacing:.08em;color:#9ce7ca;white-space:nowrap;}
  .gmfq-cr-dot{width:7px;height:7px;border-radius:50%;background:var(--cr-green);box-shadow:0 0 12px rgba(79,209,161,.65);}
  .view{max-width:1540px!important;margin-inline:auto!important;padding-inline:28px!important;}
  .card,[class~="panel"],[class$="Panel"]{background:linear-gradient(180deg,rgba(13,25,39,.96),rgba(8,17,28,.96))!important;border:1px solid var(--cr-line)!important;border-radius:var(--cr-radius)!important;box-shadow:0 1px 0 rgba(255,255,255,.015),var(--cr-shadow)!important;}
  h1,h2,h3,h4,[class*="title"],[class*="Title"]{letter-spacing:-.02em!important;}
  table{font-variant-numeric:tabular-nums;}
  th{color:#8290a3!important;letter-spacing:.04em!important;font-size:10px!important;}
  .badge,.chip,[class*="badge"],[class*="chip"]{border-radius:999px!important;}
  @media(max-width:900px){
    [data-gmfq-control-room-rail="true"]:before{display:none;}
    .gmfq-cr-head{align-items:flex-start;flex-direction:column;padding:18px 16px 12px;gap:12px;}
    .gmfq-cr-head h1{font-size:29px}.gmfq-cr-head__tools{width:100%}.gmfq-cr-search{min-width:0;flex:1}.gmfq-cr-status{display:none}
    .view{padding-inline:14px!important;}
  }
  @media(max-width:560px){.gmfq-cr-search{display:none}.gmfq-cr-head{padding-top:15px}.gmfq-cr-head p{font-size:12px}.gmfq-cr-kicker{font-size:9px}}
  @media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
  `;
  const style=document.createElement('style');
  style.id=STYLE_ID;style.dataset.gmfqDesign=SCHEMA;style.textContent=css;document.head.appendChild(style);

  if(!document.getElementById('gmfq-control-room-home-loader-v1')){
    const home=document.createElement('script');
    home.id='gmfq-control-room-home-loader-v1';
    home.src='dashboard/control-room-home-v1.js';
    home.defer=true;
    document.body.appendChild(home);
  }

  window.GMFQ_CONTROL_ROOM_SHELL={schema:SCHEMA,status:'ACTIVE',scope:'PRESENTATION_ONLY',core_effect:'NONE',rail_bound:!!rail,workspace_bound:true,home_loader:true};
})();