(()=>{
  'use strict';
  const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const FLAG={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const LAYERS=[['macro','Macro'],['rates','Rates'],['central_bank','CB'],['cot','COT'],['price','Price']];

  function layerState(D,ccy,key){
    let win=0,loss=0,mixed=0;
    Object.entries(D.pairStates||{}).forEach(([pair,st])=>{
      if(!pair.split('/').includes(ccy)) return;
      const v=st.layers?.[key];
      if(!v||v==='MISTO'||v==='NON CONFRONTABILE'){mixed++;return;}
      if(v===ccy) win++; else loss++;
    });
    return {win,loss,mixed};
  }

  function state(D,ccy){
    let fav=0,mix=0,opp=0;
    Object.entries(D.pairStates||{}).forEach(([pair,st])=>{
      if(!pair.split('/').includes(ccy)) return;
      if(st.convergence_winner===ccy) fav++;
      else if(st.convergence_winner==='MISTA') mix++;
      else opp++;
    });
    const layer=Object.fromEntries(LAYERS.map(([k])=>[k,layerState(D,ccy,k)]));
    const macro=layer.macro.win,rates=layer.rates.win,cb=layer.central_bank.win,cot=layer.cot.win,price=layer.price.win;
    let label='INTERMEDIA · DIVERGENTE',cls='warn',note='Il quadro è intermedio: nessuna convergenza abbastanza ampia.';
    if(fav>=5){
      if(price>=5){
        label='FORTE CONFERMATA'; cls='strong';
        if(rates<=2) note='Forza relativa ampia e Price coerente; i Rates restano il principale layer in ritardo.';
        else if(cot<=1) note='Macro, Rates e Price sono allineati; il COT resta la divergenza principale.';
        else note='Forza relativa ampia con conferme distribuite tra i layer principali.';
      }else{
        label='FORTE MA DIVERGENTE'; cls='warn';
        note='Forza relativa alta, ma Price/posizionamento non confermano ancora con la stessa ampiezza.';
      }
    }else if(fav<=2){
      if(fav===0&&macro<=1&&rates<=1&&price<=1){
        label='DEBOLE CONFERMATA'; cls='weak';
        note='Debolezza diffusa: Macro, Rates e Price non offrono ancora una conferma di inversione.';
      }else if(price===0&&(macro>=3||cb>=4)){
        label='DEBOLE · EARLY SHIFT'; cls='warn';
        note='Alcuni layer interni migliorano, ma il Price non conferma ancora.';
      }else if(macro>=4&&rates===0){
        label='DEBOLE · MACRO MIGLIORE'; cls='warn';
        note='Macro relativa migliore della forza FX, ma Rates/CB restano un freno.';
      }else{
        label='DEBOLE / DIVERGENTE'; cls='weak';
        note='Forza relativa bassa con segnali non uniformi tra i layer.';
      }
    }else if(price>=5&&cot>=5&&rates===0){
      note='Price e COT sono più forti del blocco Rates/CB: possibile transizione da seguire.';
    }else if(macro===0&&(cb>=4||cot>=4)){
      note='CB/COT sostengono la valuta, ma la Macro relativa non conferma ancora.';
    }
    return {ccy,fav,mix,opp,layer,label,cls,note};
  }

  function cleanLegacyCopies(){
    document.querySelectorAll('#fxG8StateBoard').forEach(el=>el.remove());
    const all=[...document.querySelectorAll('section,div')].filter(el=>{
      if(el.id==='fxG8Standalone'||el.id==='fxG8StateMount') return false;
      const h=[...el.children].find(x=>/^H[1-4]$/.test(x.tagName));
      return h && h.textContent.trim()==='Stato delle 8 valute';
    });
    all.forEach(el=>el.remove());
  }

  function locateDashboardHost(){
    const overview=document.getElementById('overview');
    if(overview) return overview;
    const candidates=[
      document.querySelector('[data-tab="overview"]'),
      document.querySelector('.overview'),
      document.querySelector('main'),
      document.querySelector('#app'),
      document.querySelector('.dashboard')
    ].filter(Boolean);
    return candidates[0]||document.body;
  }

  function ensureMountInsideDashboard(){
    cleanLegacyCopies();
    let mount=document.getElementById('fxG8StateMount');
    if(!mount){
      mount=document.createElement('div');
      mount.id='fxG8StateMount';
    }
    const host=locateDashboardHost();
    if(mount.parentElement!==host){
      if(mount.parentElement) mount.remove();
      const first=host.firstElementChild;
      if(first && first.nextSibling) host.insertBefore(mount,first.nextSibling);
      else host.prepend(mount);
    }
    return mount;
  }

  function render(D){
    const mount=ensureMountInsideDashboard();
    if(Object.keys(D.pairStates||{}).length!==28) throw new Error('pairStates != 28');

    if(!document.getElementById('fxG8StandaloneCss')){
      const st=document.createElement('style');
      st.id='fxG8StandaloneCss';
      st.textContent=`
        #fxG8StateMount{position:relative;z-index:2;background:#06131f;padding:14px 18px 0}
        #fxG8Standalone{max-width:1500px;margin:0 auto 12px}
        .fxg8h{display:flex;justify-content:space-between;gap:12px;align-items:flex-end;margin-bottom:10px}
        .fxg8h h2{margin:0;color:#eef7ff;font:900 16px Arial}
        .fxg8h p{margin:3px 0 0;color:#7f9dab;font:10px/1.4 Arial}
        .fxg8src{color:#5f8596;font:800 8px Arial;letter-spacing:.08em;text-transform:uppercase}
        .fxg8grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
        .fxg8c{background:#0a1f2d;border:1px solid #173b4c;border-radius:12px;padding:10px}
        .fxg8c.strong{border-color:#285d4b}.fxg8c.warn{border-color:#625028}.fxg8c.weak{border-color:#563b69}
        .fxg8top{display:flex;justify-content:space-between;gap:8px;color:#eef7ff;font:900 13px Arial}
        .fxg8breadth{color:#94afbb;font:800 9px Arial}
        .fxg8badge{display:inline-block;margin-top:7px;padding:4px 7px;border-radius:999px;font:900 8px Arial;letter-spacing:.04em}
        .fxg8badge.strong{color:#72dca8;background:rgba(70,185,125,.13)}
        .fxg8badge.warn{color:#efc966;background:rgba(224,181,74,.12)}
        .fxg8badge.weak{color:#d596f1;background:rgba(177,100,220,.13)}
        .fxg8note{margin-top:7px;color:#91aebb;font:9px/1.45 Arial;min-height:38px}
        .fxg8layers{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;margin-top:8px;padding-top:8px;border-top:1px solid #123343}
        .fxg8layers span{text-align:center;color:#628291;font:800 7px Arial;text-transform:uppercase}
        .fxg8layers b{display:block;margin-top:2px;color:#dce9ef;font:900 9px Arial}
        @media(max-width:980px){.fxg8grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
        @media(max-width:620px){#fxG8StateMount{padding:10px 10px 0}.fxg8grid{grid-template-columns:1fr}.fxg8h{align-items:flex-start;flex-direction:column}.fxg8note{min-height:0}}
      `;
      document.head.appendChild(st);
    }

    const rows=CCYS.map(c=>state(D,c)).sort((a,b)=>b.fav-a.fav||a.ccy.localeCompare(b.ccy));
    cleanLegacyCopies();
    mount.innerHTML='<section id="fxG8Standalone"><div class="fxg8h"><div><h2>Stato delle 8 valute</h2><p>Qualità della forza relativa sui 28 cross · nessun nuovo score.</p></div><div class="fxg8src">LIVE · FX G8 STATE v1</div></div><div class="fxg8grid">'+rows.map(r=>
      '<article class="fxg8c '+r.cls+'"><div class="fxg8top"><span>'+(FLAG[r.ccy]||'')+' '+r.ccy+'</span><span class="fxg8breadth">'+r.fav+'/7 favorevoli'+(r.mix?' · '+r.mix+' miste':'')+'</span></div><span class="fxg8badge '+r.cls+'">'+r.label+'</span><div class="fxg8note">'+r.note+'</div><div class="fxg8layers">'+LAYERS.map(([k,l])=>'<span>'+l+'<b>'+r.layer[k].win+'/7</b></span>').join('')+'</div></article>'
    ).join('')+'</div></section>';
    window.FX_G8_STANDALONE_QA={status:'PASS',pairCount:Object.keys(D.pairStates||{}).length,rows,host:(mount.parentElement?.id||mount.parentElement?.className||mount.parentElement?.tagName)};
    setTimeout(cleanLegacyCopies,250);
    setTimeout(()=>{ensureMountInsideDashboard();cleanLegacyCopies()},900);
  }

  async function boot(){
    try{
      const r=await fetch('data/sections/dashboard.json?fxg8='+Date.now(),{cache:'no-store'});
      if(!r.ok) throw new Error('dashboard '+r.status);
      render(await r.json());
    }catch(e){
      const mount=ensureMountInsideDashboard();
      if(mount) mount.innerHTML='<div style="padding:12px;color:#ffb4b4;font:12px Arial">FX G8 State: errore di caricamento · '+String(e)+'</div>';
      window.FX_G8_STANDALONE_QA={status:'FAIL',error:String(e)};
    }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();