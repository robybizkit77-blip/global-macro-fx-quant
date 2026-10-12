(()=>{
  'use strict';

  const BOARD_ID='gmfq-pair-focus-board';
  const STYLE_ID='gmfq-pair-focus-board-style';
  const GROUPS=[
    {id:'A',label:'A · CONTRASTO STRUTTURALE FORTE',match:q=>q.includes('CONTRASTO STRUTTURALE FORTE')},
    {id:'B',label:'B · VANTAGGIO RELATIVO PARZIALE',match:q=>q.includes('VANTAGGIO RELATIVO PARZIALE')},
    {id:'CTX',label:'CONTESTO · RATES MATERIALI',match:q=>q.includes('SEPARAZIONE RATES MATERIALE')},
    {id:'WAIT',label:'WAIT · NESSUN CONTRASTO / ALTRO',match:()=>true}
  ];

  function injectStyle(){
    if(document.getElementById(STYLE_ID)) return;
    const s=document.createElement('style');
    s.id=STYLE_ID;
    s.textContent=`
      #${BOARD_ID}{margin:0 0 14px;padding:12px;border:1px solid rgba(148,163,184,.17);border-radius:14px;background:rgba(15,23,42,.52)}
      #${BOARD_ID} .head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
      #${BOARD_ID} .head h3{margin:0;font-size:13px;line-height:1.3}
      #${BOARD_ID} .head p{margin:3px 0 0;font-size:10.5px;line-height:1.45;opacity:.72;max-width:760px}
      #${BOARD_ID} .guard{font-size:9.5px;line-height:1.3;padding:5px 7px;border:1px solid rgba(148,163,184,.16);border-radius:8px;white-space:nowrap;opacity:.82}
      #${BOARD_ID} .grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
      #${BOARD_ID} .group{min-width:0;padding:9px;border:1px solid rgba(148,163,184,.12);border-radius:11px;background:rgba(15,23,42,.42)}
      #${BOARD_ID} .group h4{margin:0 0 7px;font-size:9.5px;letter-spacing:.05em;line-height:1.35;opacity:.78}
      #${BOARD_ID} .pairs{display:flex;flex-wrap:wrap;gap:6px}
      #${BOARD_ID} button{appearance:none;border:1px solid rgba(148,163,184,.18);border-radius:9px;padding:6px 7px;background:rgba(30,41,59,.66);color:inherit;font:inherit;cursor:pointer;text-align:left;min-width:0}
      #${BOARD_ID} button:hover{border-color:rgba(148,163,184,.38)}
      #${BOARD_ID} button b{display:block;font-size:10.5px;line-height:1.2}
      #${BOARD_ID} button span{display:block;margin-top:2px;font-size:9px;line-height:1.25;opacity:.68}
      #${BOARD_ID} .empty{font-size:9.5px;opacity:.52}
      @media(max-width:900px){#${BOARD_ID} .grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:520px){#${BOARD_ID} .head{display:block}#${BOARD_ID} .guard{display:inline-block;margin-top:7px}#${BOARD_ID} .grid{grid-template-columns:1fr}}
    `;
    document.head.appendChild(s);
  }

  function normalizePair(value){
    const p=String(value||'').trim().toUpperCase();
    return /^[A-Z]{3}\/[A-Z]{3}$/.test(p)?p:null;
  }

  function allPairs(){
    const set=new Set();
    document.querySelectorAll('#pairs [data-pair]').forEach(el=>{
      const p=normalizePair(el.getAttribute('data-pair'));
      if(p) set.add(p);
    });
    return [...set].sort();
  }

  function classify(frame){
    const quality=String(frame?.quality||'').toUpperCase();
    for(const g of GROUPS){
      if(g.match(quality)) return {group:g.id,quality};
    }
    return {group:'WAIT',quality};
  }

  function makeItem(pair,frame){
    const btn=document.createElement('button');
    btn.type='button';
    btn.dataset.gmfqFocusPair=pair;
    const fav=String(frame?.fav||'—').toUpperCase();
    const quality=String(frame?.quality||'').trim()||'QUALITÀ NON DISPONIBILE';
    btn.innerHTML=`<b>${pair}</b><span>${fav==='—'?'nessun favorito':`favorisce ${fav}`} · ${quality.toLowerCase()}</span>`;
    return btn;
  }

  function render(){
    injectStyle();
    const host=document.getElementById('pairs');
    if(!host || typeof window.derivePairDecisionFrame!=='function') return;
    const pairs=allPairs();
    if(pairs.length!==28) return;

    const buckets={A:[],B:[],CTX:[],WAIT:[]};
    const signatures={};
    for(const pair of pairs){
      const frame=window.derivePairDecisionFrame(pair)||{};
      const c=classify(frame);
      buckets[c.group].push({pair,frame});
      signatures[pair]={fav:frame.fav??null,quality:frame.quality??null,setup:frame.setup??null,group:c.group};
    }

    const research=window.__GMFQ_RESEARCH_STATE||{};
    const researchSafe=
      research.research_signal_state==='WITHHELD' &&
      research.decision_weight===0 &&
      research.may_modify_pair_bias===false &&
      research.may_modify_currency_score===false &&
      research.may_modify_sizing===false &&
      !research.load_error;
    const fingerprint=JSON.stringify({signatures,researchSafe,researchWeight:research.decision_weight??0});

    let board=document.getElementById(BOARD_ID);
    if(board?.dataset?.gmfqFocusFingerprint===fingerprint) return;
    if(!board){
      board=document.createElement('section');
      board.id=BOARD_ID;
      const guide=document.getElementById('gmfq-pair-reading-path-guide');
      if(guide?.parentNode===host) guide.insertAdjacentElement('afterend',board);
      else host.prepend(board);
    }

    board.innerHTML=`<div class="head"><div><h3>FOCUS BOARD · 28 CROSS</h3><p>Raggruppamento trasparente basato esclusivamente sulla qualità canonica già prodotta dal Pair Engine. Nessun punteggio nascosto e nessun ranking interno: ordine alfabetico dentro ogni fascia.</p></div><div class="guard">Research / Quant: ${researchSafe?'0 PESO':'WITHHELD'}</div></div><div class="grid"></div>`;
    const grid=board.querySelector('.grid');
    for(const g of GROUPS){
      const box=document.createElement('div');
      box.className='group';
      const rows=buckets[g.id];
      box.innerHTML=`<h4>${g.label} · ${rows.length}</h4><div class="pairs"></div>`;
      const wrap=box.querySelector('.pairs');
      if(!rows.length){
        const empty=document.createElement('span');
        empty.className='empty';
        empty.textContent='Nessuna coppia';
        wrap.appendChild(empty);
      }else{
        rows.sort((a,b)=>a.pair.localeCompare(b.pair)).forEach(x=>wrap.appendChild(makeItem(x.pair,x.frame)));
      }
      grid.appendChild(box);
    }
    board.dataset.gmfqFocusFingerprint=fingerprint;

    window.__GMFQ_PAIR_FOCUS_BOARD_STATE=Object.freeze({
      status:'PASS_PRESENTATION_ONLY',
      pair_count:pairs.length,
      counts:Object.freeze({A:buckets.A.length,B:buckets.B.length,CTX:buckets.CTX.length,WAIT:buckets.WAIT.length}),
      no_hidden_score:true,
      within_bucket_order:'ALPHABETICAL',
      classification_source:'derivePairDecisionFrame.quality',
      changes_engine:false,
      changes_pair_logic:false,
      changes_bias:false,
      changes_sizing:false,
      research_decision_weight:research.decision_weight??0,
      research_state_verified:researchSafe,
      research_affects_classification:false,
      idempotent_fingerprint:true,
      signatures:Object.freeze(signatures)
    });
  }

  function openPair(pair){
    const candidates=[...document.querySelectorAll('#pairs [data-pair]')];
    const source=candidates.find(el=>normalizePair(el.getAttribute('data-pair'))===pair);
    if(source){
      source.click();
      source.scrollIntoView?.({block:'nearest',behavior:'smooth'});
    }
  }

  document.addEventListener('click',e=>{
    const btn=e.target?.closest?.(`#${BOARD_ID} [data-gmfq-focus-pair]`);
    const pair=normalizePair(btn?.dataset?.gmfqFocusPair);
    if(pair) openPair(pair);
  });

  let queued=false;
  function queue(){
    if(queued) return;
    queued=true;
    requestAnimationFrame(()=>{queued=false;render();});
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',queue,{once:true});
  else queue();
  window.addEventListener('gmfq:research-state-ready',queue);
  const observer=new MutationObserver(queue);
  observer.observe(document.documentElement,{childList:true,subtree:true});
})();
