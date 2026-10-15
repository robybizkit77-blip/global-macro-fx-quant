(()=>{
  'use strict';
  const SCHEMA='GMFQ_PREMIUM_SHELL_V1';
  const STYLE_ID='gmfq-premium-shell-v1-style';
  if(document.getElementById(STYLE_ID)) return;

  const css=`
  :root{
    --gmfq-canvas:#050a12;
    --gmfq-canvas-deep:#030812;
    --gmfq-surface:#0a1320;
    --gmfq-surface-raised:#0d1827;
    --gmfq-surface-soft:#101c2c;
    --gmfq-line:rgba(148,163,184,.14);
    --gmfq-line-strong:rgba(148,163,184,.22);
    --gmfq-text:#eef2f7;
    --gmfq-text-soft:#c8d2df;
    --gmfq-muted:#8795a8;
    --gmfq-blue:#57b8ff;
    --gmfq-blue-deep:#2878f0;
    --gmfq-blue-soft:rgba(56,189,248,.10);
    --gmfq-radius:16px;
    --gmfq-radius-sm:11px;
    --gmfq-shadow:0 20px 50px rgba(0,0,0,.22);
    --bg:var(--gmfq-canvas);
    --panel:var(--gmfq-surface);
    --panel2:var(--gmfq-surface-raised);
    --border:var(--gmfq-line);
    --text:var(--gmfq-text);
    --muted:var(--gmfq-muted);
    --accent:var(--gmfq-blue);
    --accent2:var(--gmfq-blue-deep);
  }

  html,body{
    background:
      radial-gradient(1100px 520px at 72% -10%,rgba(37,99,235,.11),transparent 62%),
      radial-gradient(850px 480px at 18% -18%,rgba(56,189,248,.07),transparent 64%),
      var(--gmfq-canvas-deep) !important;
    color:var(--gmfq-text) !important;
    font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif !important;
    text-rendering:optimizeLegibility;
    -webkit-font-smoothing:antialiased;
  }

  body{letter-spacing:-.006em;}

  .shell{
    min-height:100vh;
    background:transparent !important;
  }

  aside.sidebar,.sidebar{
    background:linear-gradient(180deg,rgba(8,16,27,.98),rgba(5,12,21,.96)) !important;
    border-right:1px solid var(--gmfq-line) !important;
    box-shadow:18px 0 44px rgba(0,0,0,.12);
    backdrop-filter:blur(18px);
  }

  .sidebar .brand,.sidebar [class*="brand"],.sidebar [class*="Brand"]{
    letter-spacing:-.025em;
  }

  .sidebar nav,.sidebar [class*="nav"],.sidebar [class*="Nav"]{
    gap:4px;
  }

  .sidebar button,.sidebar a{
    border-radius:10px !important;
    transition:background-color .16s ease,border-color .16s ease,color .16s ease,transform .16s ease;
  }

  .sidebar button:hover,.sidebar a:hover{
    background:rgba(148,163,184,.075) !important;
    color:var(--gmfq-text) !important;
  }

  .sidebar button.active,.sidebar a.active,.sidebar [aria-current="page"]{
    background:linear-gradient(90deg,rgba(37,99,235,.16),rgba(56,189,248,.075)) !important;
    border-color:rgba(56,189,248,.22) !important;
    color:#f5f9ff !important;
    box-shadow:inset 2px 0 0 rgba(87,184,255,.78);
  }

  main,.main,.content,.main-content{
    background:transparent !important;
  }

  .view{
    max-width:1540px;
    margin-inline:auto;
  }

  .view.active{
    animation:gmfq-premium-view-in .20s ease-out both;
  }

  @keyframes gmfq-premium-view-in{
    from{opacity:.78;transform:translateY(3px)}
    to{opacity:1;transform:none}
  }

  h1,h2,h3,h4,
  [class*="title"],[class*="Title"],
  [class*="headline"],[class*="Headline"]{
    letter-spacing:-.022em;
    text-wrap:balance;
  }

  h1,h2{color:#f4f7fb;}
  h3,h4{color:#e8eef6;}

  .card,
  [class~="panel"],
  [class$="Panel"]{
    border-color:var(--gmfq-line) !important;
  }

  .card{
    border-radius:var(--gmfq-radius) !important;
    background:linear-gradient(180deg,rgba(13,24,39,.94),rgba(9,18,30,.94)) !important;
    box-shadow:0 1px 0 rgba(255,255,255,.018),0 16px 40px rgba(0,0,0,.10);
  }

  table{
    font-variant-numeric:tabular-nums;
  }

  th{
    color:#91a0b3;
    letter-spacing:.035em;
  }

  button,input,select,textarea{font:inherit;}
  ::selection{background:rgba(56,189,248,.24);color:#fff;}
  *{scrollbar-color:rgba(100,116,139,.42) transparent;}

  @media (max-width:900px){
    html,body{background:var(--gmfq-canvas-deep) !important;}
    .shell{min-height:100dvh;}
    aside.sidebar,.sidebar{
      box-shadow:none;
      backdrop-filter:none;
    }
    .view{max-width:none;margin-inline:0;}
    .view.active{animation-duration:.14s;}
    h1,h2,h3,h4,[class*="title"],[class*="Title"]{text-wrap:pretty;}
  }

  @media (prefers-reduced-motion:reduce){
    .view.active{animation:none !important;}
    .sidebar button,.sidebar a{transition:none !important;}
  }
  `;

  const style=document.createElement('style');
  style.id=STYLE_ID;
  style.dataset.gmfqDesign=SCHEMA;
  style.textContent=css;
  document.head.appendChild(style);
  document.documentElement.dataset.gmfqDesign='institutional-editorial-premium';
  document.documentElement.dataset.gmfqDesignVersion='1';

  window.GMFQ_PREMIUM_SHELL={
    schema:SCHEMA,
    status:'ACTIVE',
    scope:'PRESENTATION_ONLY',
    core_effect:'NONE',
    style_id:STYLE_ID,
    direction:'INSTITUTIONAL_EDITORIAL_PREMIUM'
  };
})();
