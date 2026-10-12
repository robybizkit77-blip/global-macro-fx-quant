(()=>{
  'use strict';

  const STYLE_ID='gmfq-reading-hierarchy-style';
  const GUIDE_ID='gmfq-reading-path-guide';
  const LABELS=[
    {needle:'QUADRO DI FONDO',kind:'background'},
    {needle:'CAMBIAMENTO RECENTE',kind:'change'},
    {needle:'COSA STA SUCCEDENDO?',kind:'driver'},
    {needle:'COSA SIGNIFICA PER LA VALUTA?',kind:'driver'},
    {needle:'COSA RAFFORZA QUESTA LETTURA?',kind:'confirm'},
    {needle:'COSA LA METTE IN DUBBIO?',kind:'invalidate'}
  ];

  function injectStyle(){
    if(document.getElementById(STYLE_ID)) return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      #currencies{--gmfq-reading-border:rgba(148,163,184,.20);--gmfq-reading-soft:rgba(203,213,225,.78);--gmfq-reading-muted:rgba(203,213,225,.66)}
      #${GUIDE_ID}{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 16px;padding:10px;border:1px solid var(--gmfq-reading-border);border-radius:14px;background:rgba(15,23,42,.50);box-shadow:0 10px 28px rgba(2,6,23,.12)}
      #${GUIDE_ID} .gmfqReadingStep{min-width:0;padding:9px 10px;border-radius:10px;background:rgba(15,23,42,.60);border:1px solid rgba(148,163,184,.13)}
      #${GUIDE_ID} .gmfqReadingStep b{display:block;font-size:10px;letter-spacing:.08em;opacity:.68;margin-bottom:3px}
      #${GUIDE_ID} .gmfqReadingStep span{display:block;font-size:11px;line-height:1.35;font-weight:780;color:inherit}
      #currencies .gmfqReadingLabel{letter-spacing:.065em!important;font-weight:820!important;line-height:1.28!important}
      #currencies .gmfqReadingBlock{position:relative}
      #currencies .gmfqReadingBlock[data-reading-kind="background"]{border-left:2px solid rgba(56,189,248,.48);padding-left:10px}
      #currencies .gmfqReadingBlock[data-reading-kind="change"]{border-left:2px solid rgba(250,204,21,.46);padding-left:10px}
      #currencies .gmfqReadingBlock[data-reading-kind="driver"]{border-left:2px solid rgba(129,140,248,.46);padding-left:10px}
      #currencies .gmfqReadingBlock[data-reading-kind="confirm"]{border-left:2px solid rgba(34,197,94,.48);padding-left:10px}
      #currencies .gmfqReadingBlock[data-reading-kind="invalidate"]{border-left:2px solid rgba(248,113,113,.48);padding-left:10px}
      #currencies .gmfqReadingHint{font-size:9px;font-weight:760;letter-spacing:.045em;opacity:.66;margin-left:5px;white-space:nowrap}
      #currencies .v461CoreHead{margin-bottom:10px}
      #currencies .gmfqPriceLead,#currencies .gmfqCotTutor,#currencies .gmfqPriceTutor{line-height:1.52}
      #currencies .gmfqPriceLead>span,#currencies .gmfqCotTutor .txt{font-size:12.25px!important;line-height:1.55!important;color:var(--gmfq-reading-soft)!important}
      #currencies .gmfqCotTutor .drivers,#currencies .gmfqPriceTutor .drivers{gap:8px}
      #currencies .gmfqCotTutor .driver,#currencies .gmfqPriceTutor .driver{padding-top:3px;padding-bottom:3px}
      #currencies .gmfqCotTutor .driver b,#currencies .gmfqPriceTutor .driver b{font-size:10px!important;letter-spacing:.025em;opacity:.72}
      #currencies .gmfqCotTutor .driver span,#currencies .gmfqPriceTutor .driver span{font-size:11.5px!important;line-height:1.4!important}
      #currencies .watch{gap:10px;margin-top:10px}
      #currencies .watch .good,#currencies .watch .bad{line-height:1.46}
      #currencies .watch small{font-size:9.5px!important;letter-spacing:.045em;opacity:.72}
      #currencies .watch b{font-size:11.5px!important;line-height:1.46!important}
      #currencies .fx{margin-top:10px;line-height:1.5}
      #currencies .fx>b{font-size:9.5px!important;letter-spacing:.045em;opacity:.76}
      #currencies .fx>div{font-size:11.75px!important;line-height:1.5!important;color:var(--gmfq-reading-soft)!important}
      #currencies .gmfqPriceTick .k,#currencies .gmfqCotTick .k{opacity:.70}
      #currencies .gmfqPriceTick .v,#currencies .gmfqCotTick .v{font-weight:800}
      @media (max-width:800px){
        #${GUIDE_ID}{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;padding:8px}
        #${GUIDE_ID} .gmfqReadingStep{padding:8px}
        #currencies .gmfqPriceLead>span,#currencies .gmfqCotTutor .txt{font-size:12px!important}
      }
      @media (max-width:480px){
        #${GUIDE_ID}{grid-template-columns:1fr}
        #${GUIDE_ID} .gmfqReadingStep{display:grid;grid-template-columns:24px 1fr;align-items:center;gap:4px}
        #${GUIDE_ID} .gmfqReadingStep b{margin:0}
        #currencies .watch{grid-template-columns:1fr!important}
      }
    `;
    document.head.appendChild(style);
  }

  function addGuide(){
    const host=document.getElementById('currencies');
    if(!host || document.getElementById(GUIDE_ID)) return;
    const guide=document.createElement('div');
    guide.id=GUIDE_ID;
    guide.setAttribute('aria-label','Percorso di lettura valuta');
    guide.innerHTML=[
      ['01','QUADRO DI FONDO'],
      ['02','COSA STA CAMBIANDO'],
      ['03','DRIVER DELLA VALUTA'],
      ['04','CONFERMA / INVALIDA']
    ].map(([n,t])=>`<div class="gmfqReadingStep"><b>${n}</b><span>${t}</span></div>`).join('');
    host.prepend(guide);
  }

  function closestReadableBlock(el){
    if(!el) return null;
    return el.closest('.good,.bad,.fx,.watch,.gmfqCotTutor,.gmfqPriceTutor,.gmfqPriceLead,.v461CoreHead,section,article,div') || el.parentElement;
  }

  function decorateLabels(){
    const root=document.getElementById('currencies');
    if(!root) return;
    const nodes=root.querySelectorAll('small,.lab,.k,strong,b,h2,h3,h4,div,span');
    for(const el of nodes){
      if(el.dataset?.gmfqReadingDecorated==='1') continue;
      const text=String(el.textContent||'').trim();
      if(!text || text.length>80) continue;
      const match=LABELS.find(x=>text===x.needle || text.startsWith(x.needle));
      if(!match) continue;
      el.dataset.gmfqReadingDecorated='1';
      el.classList.add('gmfqReadingLabel');
      const block=closestReadableBlock(el);
      if(block){
        block.classList.add('gmfqReadingBlock');
        block.dataset.readingKind=match.kind;
      }
      if(match.needle==='CAMBIAMENTO RECENTE' && !el.querySelector('.gmfqReadingHint')){
        const hint=document.createElement('span');
        hint.className='gmfqReadingHint';
        hint.textContent='· COSA STA CAMBIANDO';
        el.appendChild(hint);
      }
    }
  }

  let queued=false;
  function apply(){
    queued=false;
    injectStyle();
    addGuide();
    decorateLabels();
    window.__GMFQ_READING_HIERARCHY_STATE=Object.freeze({
      status:'PASS_PRESENTATION_ONLY',
      changes_engine:false,
      changes_bias:false,
      changes_sizing:false,
      guide_present:!!document.getElementById(GUIDE_ID)
    });
  }
  function queue(){
    if(queued) return;
    queued=true;
    requestAnimationFrame(apply);
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',queue,{once:true});
  else queue();

  const observer=new MutationObserver(queue);
  observer.observe(document.documentElement,{subtree:true,childList:true});
  window.addEventListener('gmfq:research-state-ready',queue);
  window.addEventListener('resize',queue,{passive:true});
})();
