(()=>{
  'use strict';
  const SCHEMA='GMFQ_PRODUCT_LANGUAGE_V1';
  const SKIP=new Set(['SCRIPT','STYLE','NOSCRIPT','TEXTAREA','INPUT','OPTION']);
  const exact=new Map([
    ['What Changed operativo','Cosa è cambiato'],
    ['Top Themes operativo','Temi principali'],
    ['Calendar operativo','Calendario'],
    ['News Pulse operativo','Ultimi cambiamenti'],
    ['Risk operativo','Rischio globale'],
    ['VALIDATED CHANGE DETECTION','Cambiamenti principali'],
    ['CONTESTO VALIDATO PRECEDENTE','Contesto precedente'],
    ['MACRO → MARKET PRICING · G8','Macro e attese sui tassi'],
    ['MARKET PRICING','Cosa prezza il mercato'],
    ['EVENT RISK · G8','Eventi da seguire'],
    ['CENTRAL BANKS','Banche centrali'],
    ['MACRO RELEASES','Dati macro'],
    ['WHAT CHANGED · VALIDATED LAYERS','Cosa è cambiato'],
    ['CROSS-ASSET RISK MONITOR','Mercati e rischio'],
    ['OFFICIAL RUNTIME','Fonte ufficiale'],
    ['SECONDARY · NON OFFICIAL','Proxy di mercato'],
    ['SCHEDA OPERATIVA','Sintesi'],
    ['LETTURA OPERATIVA','Lettura'],
    ['DRIVER DELLA VALUTA','Cosa guida la valuta'],
    ['DRIVER DOMINANTE','Fattore principale'],
    ['Apri il desk Macro','Apri Macro'],
    ['MACRO COUNTRY DESK','Macro'],
    ['MACRO · SPIEGATA SEMPLICE','Macro'],
    ['MACRO OGGI','Quadro macro'],
    ['MACRO HEATMAP','Mappa macro'],
    ['RATES COUNTRY DESK','Tassi'],
    ['RATES · SPIEGATI SEMPLICE','Tassi'],
    ['IMPULSO RATES','Cosa stanno facendo i tassi'],
    ['OIS / Policy Pricing — G8 Operational','Cosa prezza il mercato'],
    ['ASX BB DIRECTIONAL','Attese tassi NZD · proxy'],
    ['CENTRAL BANK COUNTRY DESK','Banche centrali'],
    ['FOTOGRAFIA POLICY','Quadro attuale'],
    ['TONO OGGI','Tono attuale'],
    ['STANCE ATTUALE','Posizione attuale'],
    ['DIVERGENZA CB / MERCATO','Banca centrale vs mercato'],
    ['LETTURA POLICY · COMPONENTE DI TASSI/CB','Lettura complessiva'],
    ['FOTOGRAFIA LIQUIDITÀ','Quadro liquidità'],
    ['LIQUIDITÀ OGGI','Oggi'],
    ['CREDITO CONFERMA?','Il credito conferma?'],
    ['LENDING CONDITIONS DISPONIBILI','Condizioni di prestito disponibili'],
    ['BILANCIO CB / QE-QT NON DETERMINATO','QE/QT: non determinabile dai dati disponibili'],
    ['OVERLAY LIQUIDITÀ · NON DECIDE LA STRUTTURA','Contesto: non decide da solo la direzione'],
    ['COT · POSIZIONAMENTO SPECULATIVO','Posizionamento COT'],
    ['LETTURA GUIDATA','Lettura'],
    ['POSIZIONAMENTO OGGI','Posizionamento attuale'],
    ['SQUILIBRIO NET/OI','Net/OI'],
    ['SOGLIA MECCANICA','Soglia'],
    ['COSA VEDO OGGI','Situazione attuale'],
    ['METODOLOGIA · PLAYBOOK','Metodo'],
    ['REGOLA MADRE','Regola principale'],
    ['GLOBAL RISK','Rischio globale'],
    ['OUT-OF-SAMPLE · FORWARD VALIDATION','Verifica delle previsioni'],
    ['Forward Test Monitor','Monitor previsioni'],
    ['INTEGRITY PASS','Controlli OK'],
    ['SNAPSHOT','Previsioni registrate'],
    ['RULE BREAKS','Regole modificate'],
    ['Overlay · valore aggiunto','Valore aggiunto dei fattori di contesto'],
    ['Diagnostica OOS, non ottimizzazione','Test su dati successivi, senza ottimizzazione'],
    ['Δ mean vs Core','Differenza vs modello base'],
    ['Rischio OOS & confronto paired','Rischio del test e confronto']
  ]);

  const phrases=[
    [/^CONTENT AS-OF\s+/i,'Aggiornato al '],
    [/^Content as-of\s+/i,'Aggiornato al '],
    [/^GIORNATA DATI\s+/i,'Aggiornato al '],
    [/^Latest source date:\s*/i,'Aggiornato al: '],
    [/^Pricing operativo\s*·\s*ESTIMATED$/i,'Cosa prezza il mercato · Stimato'],
    [/^Pricing operativo\s*·\s*OFFICIAL$/i,'Cosa prezza il mercato · Ufficiale'],
    [/^ESTIMATED$/i,'Stimato'],
    [/^OFFICIAL$/i,'Ufficiale'],
    [/^OFFICIAL CB SCHEDULE$/i,'Data ufficiale'],
    [/^OFFICIAL MACRO RELEASE$/i,'Fonte ufficiale'],
    [/^CONSENSUS SECONDARY$/i,'Consensus di mercato'],
    [/^full current official$/i,'Dati ufficiali aggiornati'],
    [/^Core \/ bias \/ sizing effect:\s*NONE$/i,'Solo contesto: non cambia il segnale'],
    [/^Brent official:\s*WITHHELD\.?$/i,'Dato ufficiale Brent non disponibile'],
    [/^Motore:\s*stato corrente$/i,'Calcolo aggiornato'],
    [/^Baseline congelata:\s*GMFQ OOS V1\.?$/i,'Regole congelate durante il test'],
    [/^Direzione strutturale del Core$/i,'Direzione del modello base'],
    [/^Core$/i,'Modello base']
  ];

  const forbiddenVisible=[
    'What Changed operativo','Top Themes operativo','Calendar operativo','News Pulse operativo','Risk operativo',
    'VALIDATED CHANGE DETECTION','MACRO COUNTRY DESK','RATES COUNTRY DESK','CENTRAL BANK COUNTRY DESK',
    'METODOLOGIA · PLAYBOOK','OUT-OF-SAMPLE · FORWARD VALIDATION','Forward Test Monitor'
  ];

  function normalize(raw){return String(raw||'').replace(/\s+/g,' ').trim();}
  function translate(raw){
    const t=normalize(raw);
    if(!t) return null;
    if(exact.has(t)) return exact.get(t);
    for(const [re,repl] of phrases){if(re.test(t)) return t.replace(re,repl);}
    return null;
  }

  function applyElementLabels(root){
    let changed=0;
    const els=[root,...root.querySelectorAll('*')].filter(el=>el?.nodeType===1&&!SKIP.has(el.tagName)&&!el.matches('script,style,noscript,textarea,input,select,option'));
    els.sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length);
    for(const el of els){
      if(el.dataset?.gmfqLanguageTranslated==='true') continue;
      const text=normalize(el.textContent);
      const out=translate(text);
      if(out==null||out===text) continue;
      // Collapse markup only when the whole element is exactly one known UI label.
      // Analytical cards/paragraphs never match this condition.
      el.textContent=out;
      el.dataset.gmfqLanguageTranslated='true';
      changed++;
    }
    return changed;
  }

  function apply(root=document.body){
    if(!root) return 0;
    let changed=applyElementLabels(root);
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode(node){
      const p=node.parentElement;
      if(!p||SKIP.has(p.tagName)||p.closest('script,style,noscript,textarea,input,select,option')) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }});
    const nodes=[]; let n; while((n=walker.nextNode())) nodes.push(n);
    for(const node of nodes){
      const before=String(node.nodeValue||'');
      const lead=before.match(/^\s*/)?.[0]||'';
      const trail=before.match(/\s*$/)?.[0]||'';
      const core=before.trim();
      const out=translate(core);
      if(out!=null&&out!==normalize(core)){node.nodeValue=lead+out+trail;changed++;}
    }
    return changed;
  }

  let scheduled=false;
  function schedule(){
    if(scheduled) return;
    scheduled=true;
    requestAnimationFrame(()=>{scheduled=false;apply(document.body);window.GMFQ_PRODUCT_LANGUAGE=audit();});
  }

  function audit(){
    const body=String(document.body?.innerText||'');
    const found=forbiddenVisible.filter(x=>body.includes(x));
    return {schema:SCHEMA,status:found.length?'FAIL':'ACTIVE',scope:'PRESENTATION_ONLY',core_effect:'NONE',forbidden_visible:found};
  }

  function boot(){
    apply(document.body);
    const obs=new MutationObserver(schedule);
    obs.observe(document.body,{subtree:true,childList:true,characterData:true});
    window.__GMFQ_PRODUCT_LANGUAGE_OBSERVER=obs;
    document.documentElement.dataset.gmfqLanguage='simple-product';
    window.GMFQ_PRODUCT_LANGUAGE=audit();
    setTimeout(()=>{apply(document.body);window.GMFQ_PRODUCT_LANGUAGE=audit();},600);
  }

  window.gmfqApplyProductLanguage=apply;
  window.gmfqProductLanguageAudit=audit;
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();
