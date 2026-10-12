(()=>{
  'use strict';

  const STYLE_ID='gmfq-pair-reading-hierarchy-style';
  const GUIDE_ID='gmfq-pair-reading-path-guide';
  const LABELS=[
    {needle:'STRUTTURA OGGI',kind:'structure'},
    {needle:'DIREZIONE',kind:'change'},
    {needle:'COSA STA SUCCEDENDO?',kind:'change'},
    {needle:'COSA RAFFORZA QUESTA LETTURA?',kind:'confirm'},
    {needle:'COSA LA METTE IN DUBBIO?',kind:'invalidate'},
    {needle:'CONCLUSIONE',kind:'conclusion'}
  ];

  function injectStyle(){
    if(document.getElementById(STYLE_ID)) return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      #pairs{--gmfq-pair-border:rgba(148,163,184,.17)}
      #${GUIDE_ID}{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 16px;padding:10px;border:1px solid var(--gmfq-pair-border);border-radius:14px;background:rgba(15,23,42,.46)}
      #${GUIDE_ID} .gmfqPairReadingStep{min-width:0;padding:9px 10px;border-radius:10px;background:rgba(15,23,42,.56);border:1px solid rgba(148,163,184,.11)}
      #${GUIDE_ID} .gmfqPairReadingStep b{display:block;font-size:10px;letter-spacing:.08em;opacity:.65;margin-bottom:3px}
      #${GUIDE_ID} .gmfqPairReadingStep span{display:block;font-size:11px;line-height:1.35;font-weight:780;color:inherit}
      #pairs .gmfqPairReadingLabel{letter-spacing:.06em!important;font-weight:800!important;line-height:1.25!important}
      #pairs .gmfqPairReadingBlock{position:relative}
      #pairs .gmfqPairReadingBlock[data-pair-reading-kind="structure"]{border-left:2px solid rgba(56,189,248,.44);padding-left:10px}
      #pairs .gmfqPairReadingBlock[data-pair-reading-kind="change"]{border-left:2px solid rgba(250,204,21,.42);padding-left:10px}
      #pairs .gmfqPairReadingBlock[data-pair-reading-kind="confirm"]{border-left:2px solid rgba(34,197,94,.44);padding-left:10px}
      #pairs .gmfqPairReadingBlock[data-pair-reading-kind="invalidate"]{border-left:2px solid rgba(248,113,113,.44);padding-left:10px}
      #pairs .gmfqPairReadingBlock[data-pair-reading-kind="conclusion"]{border-left:2px solid rgba(129,140,248,.44);padding-left:10px}
      #pairs #gmfqPairTutor{line-height:1.5}
      #pairs #gmfqPairTutor .ttl{font-size:14px!important;line-height:1.35!important;font-weight:800!important}
      #pairs #gmfqPairTutor .txt{font-size:12px!important;line-height:1.55!important;opacity:.9!important}
      #pairs #gmfqPairTutor .drivers{gap:8px!important}
      #pairs #gmfqPairTutor .driver{padding:8px 9px!important}
      #pairs #gmfqPairTutor .driver b{font-size:10px!important;opacity:.72!important}
      #pairs #gmfqPairTutor .driver span{font-size:11.5px!important;line-height:1.42!important}
      #pairs #gmfqPairTutor .watch{gap:10px!important}
      #pairs #gmfqPairTutor .watch .good,#pairs #gmfqPairTutor .watch .bad{line-height:1.46!important}
      #pairs #gmfqPairTutor .watch small{font-size:9.5px!important;opacity:.75!important}
      #pairs #gmfqPairTutor .watch b{font-size:11.5px!important;line-height:1.45!important}
      #pairs #gmfqPairTutor .confirm{margin-top:10px!important;padding:10px 11px!important}
      #pairs #gmfqPairTutor .confirm>b{font-size:10px!important;letter-spacing:.06em!important;opacity:.76!important}
      #pairs #gmfqPairConclusion{font-size:12px!important;line-height:1.5!important;font-weight:720!important}
      @media(max-width:800px){
        #${GUIDE_ID}{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;padding:8px}
        #${GUIDE_ID} .gmfqPairReadingStep{padding:8px}
      }
      @media(max-width:480px){
        #${GUIDE_ID}{grid-template-columns:1fr}
        #${GUIDE_ID} .gmfqPairReadingStep{display:grid;grid-template-columns:24px 1fr;align-items:center;gap:4px}
        #${GUIDE_ID} .gmfqPairReadingStep b{margin:0}
        #pairs #gmfqPairTutor .watch{grid-template-columns:1fr!important}
      }
    `;
    document.head.appendChild(style);
  }

  function addGuide(){
    const host=document.getElementById('pairs');
    if(!host || document.getElementById(GUIDE_ID)) return;
    const guide=document.createElement('div');
    guide.id=GUIDE_ID;
    guide.setAttribute('aria-label','Percorso di lettura coppia');
    guide.innerHTML=[
      ['01','CONTRASTO STRUTTURALE'],
      ['02','COSA STA CAMBIANDO'],
      ['03','CONFERME / DIVERGENZE'],
      ['04','SEGUIRE O ASPETTARE']
    ].map(([n,t])=>`<div class="gmfqPairReadingStep"><b>${n}</b><span>${t}</span></div>`).join('');
    host.prepend(guide);
  }

  function closestBlock(el){
    if(!el) return null;
    return el.closest('.good,.bad,.confirm,.watch,#gmfqPairTutor,.gmfqPairTick,section,article,div') || el.parentElement;
  }

  function decorate(){
    const root=document.getElementById('pairs');
    if(!root) return;
    const nodes=root.querySelectorAll('small,.lab,.k,strong,b,h2,h3,h4,div,span');
    for(const el of nodes){
      if(el.dataset?.gmfqPairReadingDecorated==='1') continue;
      const text=String(el.textContent||'').trim();
      if(!text || text.length>90) continue;
      const match=LABELS.find(x=>text===x.needle || text.startsWith(x.needle));
      if(!match) continue;
      el.dataset.gmfqPairReadingDecorated='1';
      el.classList.add('gmfqPairReadingLabel');
      const block=closestBlock(el);
      if(block){
        block.classList.add('gmfqPairReadingBlock');
        block.dataset.pairReadingKind=match.kind;
      }
    }
  }

  let queued=false;
  function apply(){
    queued=false;
    injectStyle();
    addGuide();
    decorate();
    window.__GMFQ_PAIR_READING_HIERARCHY_STATE=Object.freeze({
      status:'PASS_PRESENTATION_ONLY',
      changes_engine:false,
      changes_pair_logic:false,
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
  window.addEventListener('resize',queue,{passive:true});
})();
