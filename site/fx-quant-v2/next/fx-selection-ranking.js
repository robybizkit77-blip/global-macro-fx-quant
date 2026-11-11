'use strict';
/* FX Quant Next: a transparent research ordering, not a trading signal or
   a backtested predictive score. All inputs are the existing dated sources. */
(function(root){
  const isDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
  const numeric=x=>typeof x==='number'&&Number.isFinite(x);
  function render(api){
    const {get,FX,FLAGS,esc,fmt,sign,date,dayNow}=api;
    const model=get('pairs'),prices=get('currencyPrices'),now=dayNow();
    const objects=model?.pairs||{},keys=Object.keys(objects);
    if(keys.length!==28)return '<section class="fxr-unavailable" role="status">Classifica sospesa: il motore non ha restituito le 28 coppie attese. Nessun ranking sintetico.</section>';
    const validModel=isDay(model.price_asof)&&model.price_asof<=now;
    const profileApi=root.FXQuantDecisionJourney?.profile;
    const research=keys.map(key=>{
      const s=objects[key]?.setup||{},fav=s.structuralFav;
      const side=fav===key.slice(0,3)?'LONG':fav===key.slice(3)?'SHORT':null;
      const profile=typeof profileApi==='function'?profileApi(key,model,prices,now):null;
      const usable=validModel&&!!profile?.fresh&&profile?.asof===model.price_asof&&profile?.closes?.length>=22;
      const q=s.quality||'NON VALUTABILE',price=s.price?.state||'UNKNOWN',timing=s.timing?.state||'UNKNOWN';
      const coherent5=usable&&profile.fiveState==='COERENTE';
      const coherent20=usable&&profile.twentyState==='COERENTE';
      let tier=5;
      if(usable&&side&&q!=='NON VALUTABILE'){
        if(q==='PULITO'&&price==='GOOD'&&timing==='ALIGNED'&&coherent5&&coherent20)tier=0;
        else if(price==='GOOD'&&timing==='ALIGNED'&&coherent5&&coherent20)tier=1;
        else if(price==='GOOD'&&coherent5)tier=2;
        else if(price==='GOOD'&&timing!=='ADVERSE')tier=3;
        else tier=4;
      }
      return {key,s,side,profile,q,price,timing,tier,coherent5,coherent20,
        dual:s.structural?.macroSide===fav&&s.structural?.policySide===fav};
    });
    // Ordinal, evidence-based buckets. No hidden numerical return prediction.
    const ordered=research.sort((a,b)=>a.tier-b.tier ||
       Number(b.dual)-Number(a.dual) ||
       Number(b.coherent20)-Number(a.coherent20) ||
       (a.q==='PULITO'?-1:a.q==='DA MONITORARE'?0:1)-
       (b.q==='PULITO'?-1:b.q==='DA MONITORARE'?0:1) ||
       a.key.localeCompare(b.key));
    const labels=['TESI E DAILY COERENTI','CONFERME PARZIALI','DA APPROFONDIRE','TESI DA VERIFICARE','TESI IN CONTRASTO','NON VALUTABILE'];
    const tones=['fxr-positive','fxr-positive','fxr-attention','fxr-attention','fxr-caution','fxr-muted'];
    const selected=ordered.filter(x=>x.tier<5).slice(0,5);
    const readiness=ordered.filter(x=>x.tier===0).length;
    const marketOutdated=!(validModel&&ordered.some(x=>x.profile?.fresh));
    const pairNote=marketOutdated?
      'Lo snapshot delle coppie non è sufficientemente recente: graduatoria operativa sospesa.':
      'Ordinamento per qualità del dossier, coerenza del fixing a 5/20 sedute e timing del modello; non misura il rendimento atteso né la convenienza di ingresso.';
    function pairRow(x,index,featured){
      const name=x.key.slice(0,3)+'/'+x.key.slice(3);
      const phase=labels[x.tier],direction=x.side?'Bias '+x.side:'Senza bias';
      const five=numeric(x.profile?.m5)?sign(x.profile.m5,2,'%'):'—';
      const twenty=numeric(x.profile?.m20)?sign(x.profile.m20,2,'%'):'—';
      return '<button type="button" class="fxr-pair '+(featured?'fxr-featured ':'')+tones[x.tier]+'" data-pair="'+esc(x.key)+'" aria-label="Apri dossier '+esc(name)+'">'+
        '<span class="fxr-place">'+(index+1)+'</span>'+
        '<span class="fxr-pair-identity"><strong>'+esc(name)+'</strong><small>'+esc(direction)+'</small></span>'+
        '<span class="fxr-pair-evidence"><b>'+esc(phase)+'</b><small>'+esc(x.q)+' · prezzo 5D '+esc(five)+' · 20D '+esc(twenty)+'</small></span>'+
        '<span class="fxr-pair-go">Apri <span aria-hidden="true">›</span></span></button>';
    }
    const fullPriceRows=(prices?.source==='ECB euro foreign exchange reference rates'&&Array.isArray(prices.rows)?prices.rows:[])
      .filter(row=>isDay(row?.Date)&&row.Date<=now&&FX.every(c=>c==='EUR'||numeric(row[c])&&row[c]>0))
      .sort((a,b)=>a.Date.localeCompare(b.Date));
    const end=fullPriceRows.at(-1),prev5=fullPriceRows.at(-6);
    const age=end?Math.floor((Date.parse(now+'T12:00:00Z')-Date.parse(end.Date+'T12:00:00Z'))/86400000):Infinity;
    const g8Ready=!!(end&&prev5&&age>=0&&age<=5&&end.Date===prices?.last_as_of);
    let g8='<div class="fxr-empty">Fixing G8 assenti, incompleti o non recenti: nessuna classifica di forza pubblicata.</div>';
    if(g8Ready){
      const orderedFX=FX.map(ccy=>({ccy,value:ccy==='EUR'?0:100*Math.log(prev5[ccy]/end[ccy])}))
        .sort((a,b)=>b.value-a.value||a.ccy.localeCompare(b.ccy));
      const hi=orderedFX[0].value,lo=orderedFX.at(-1).value,span=Math.max(.0001,hi-lo);
      g8='<div class="fxr-fx-list">'+orderedFX.map((x,i)=>{
        const width=Math.max(3,Math.min(100,100*(x.value-lo)/span));
        const tone=i<2?'fxr-positive':i>=6?'fxr-caution':'fxr-middle';
        return '<div class="fxr-fx '+tone+'"><span class="fxr-place">'+(i+1)+'</span>'+
          '<span class="fxr-name">'+esc(FLAGS[x.ccy]||'')+' <strong>'+esc(x.ccy)+'</strong></span>'+
          '<div class="fxr-track" aria-hidden="true"><span style="width:'+width.toFixed(2)+'%"></span></div>'+
          '<strong class="fxr-return">'+esc(sign(x.value,2,'%'))+'</strong></div>';
      }).join('')+'</div>';
    }
    const datesDisagree=g8Ready&&validModel&&end.Date!==model.price_asof;
    const topCards=selected.length&&!marketOutdated?
       selected.map((x,i)=>pairRow(x,i,true)).join(''):
       '<div class="fxr-empty">Nessuna coppia promossa fra le selezioni: mancano dati recenti o un vantaggio relativo verificabile.</div>';
    return '<div class="fxr-shell" id="fx-selection-ranking">'+
      '<div class="fxr-intro"><span class="mini-overline">FX SELECTION DESK / PRIMA LA CLASSIFICA</span>'+
      '<p>Prima individua le valute che si stanno muovendo e le coppie da studiare. Apri il dossier soltanto se la tesi merita un controllo su macro, tassi, posizionamento e prezzo.</p></div>'+
      '<section class="fxr-panel"><div class="fxr-heading"><div><span class="mini-overline">01 · FORZA RELATIVA OSSERVATA</span><h2>Ranking delle 8 valute</h2></div>'+
      '<span class="fxr-date">BCE · 5 fixing · '+esc(g8Ready?date(end.Date):'non disponibile')+'</span></div>'+
      '<p class="fxr-context">Dalla più forte alla più debole nelle ultime 5 sedute, misurate rispetto all’EUR. La barra indica la posizione relativa nel gruppo, <strong>non</strong> un punteggio macro o un segnale di acquisto.</p>'+
       g8+'</section>'+
      '<section class="fxr-panel"><div class="fxr-heading"><div><span class="mini-overline">02 · SELEZIONE DI RICERCA</span><h2>Top 5 coppie da approfondire</h2></div>'+
      '<span class="fxr-date">Motore · '+esc(date(model.price_asof))+'</span></div>'+
      '<p class="fxr-context">'+esc(pairNote)+' '+(readiness===0?'<strong>Nessun setup pienamente confermato:</strong> le prime posizioni sono priorità di ricerca, non trade pronti.':'Le conferme della tesi non sostituiscono ingresso, rischio e rapporto rendimento/rischio.')+'</p>'+
      (datesDisagree?'<p class="fxr-vintage-warning">Attenzione: fixing G8 '+esc(date(end.Date))+' e modello coppie '+esc(date(model.price_asof))+' hanno date diverse. Le due classifiche non sono uno snapshot simultaneo.</p>':'')+
      '<div class="fxr-pair-list">'+topCards+'</div></section>'+
      '<section class="fxr-panel"><div class="fxr-heading"><div><span class="mini-overline">03 · UNIVERSO G8</span><h2>Tutte le 28 coppie ordinate</h2></div>'+
      '<span class="fxr-date">'+ordered.length+' / 28</span></div>'+
      '<p class="fxr-context">La posizione descrive <strong>quale dossier esaminare prima</strong>, non una previsione di performance. I confronti senza prove sufficienti restano in fondo, senza punteggi artificiali.</p>'+
      '<div class="fxr-pair-list fxr-all">'+ordered.map((x,i)=>pairRow(x,i,false)).join('')+'</div></section>'+
      '<p class="fxr-method">Metodo: prezzi BCE daily, snapshot strutturale Macro/Tassi e valutazioni di rischio già presenti nel motore. COT e OIS vengono interpretati nel dossier con la rispettiva data; non sono sommati in uno score inventato. Ogni bias LONG/SHORT è una direzione teorica del modello, mai un ordine. Nessun backtest o edge statistico è implicato.</p></div>';
  }
  root.FXQuantFXSelection={render};
})(typeof window!=='undefined'?window:globalThis);
