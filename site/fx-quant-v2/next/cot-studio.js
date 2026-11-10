'use strict';
/**
 * FX Quant NEXT / CFTC COT Research Studio
 *
 * Source: CFTC Legacy non-commercial futures positioning, weekly Tuesdays.
 * Price comparator: historical ECB FX fixing, aligned to COT dates.
 *
 * Never infer a trade signal from net exposure or percentile alone.
 * The dataset is a latest-available snapshot, not today's intraday data.
 * All calculations and statements derive from JSON loaded by the main app.
 */
(function(root){
  const PCTS={lower:20,upper:80};
  const columns=[
    ['net','Net contratti'],['delta1','Δ 1 settimana'],['delta4','Δ 4 settimane'],
    ['netoi','Net/OI (%)'],['percentile','Percentile 104W']
  ];
  function make(api){
    const {get,FX,FLAGS,state,plot,pageHero,esc,fmt,sign,date,finite,validDay,dayNow,qBadge}=api;
    function verifiedRows(ccy){
      const a=get('cotHistory')?.[ccy];
      if(!a||!Array.isArray(a.dates)||a.dates.length<5)return [];
      const keys=['net','long','short','netoi','percentile'];
      if(keys.some(k=>!Array.isArray(a[k])||a[k].length!==a.dates.length))return [];
      const rows=a.dates.map((d,i)=>({date:d,net:a.net[i],long:a.long[i],short:a.short[i],netoi:a.netoi[i],percentile:a.percentile[i]}));
      if(!rows.every(x=>validDay(x.date)&&x.date<=dayNow()&&keys.every(k=>finite(x[k]))
        && Math.abs((x.long-x.short)-x.net)<1.1
        && x.percentile>=0&&x.percentile<=100))return [];
      rows.sort((a,b)=>a.date.localeCompare(b.date));
      if(new Set(rows.map(x=>x.date)).size!==rows.length)return [];
      return rows;
    }
    function report(ccy){
      const hist=verifiedRows(ccy);
      if(hist.length<9)return null;
      const last=hist.at(-1),prev=hist.at(-2),four=hist.at(-5);
      const fx=root.FXQuantCOTEvidence?.priceEvidence?.(ccy,hist,get('currencyPrices'),dayNow())||null;
      const prices=fx?.prices||[],priceRow=fx?.priceRow||null,price1=fx?.price1??null;
      const out={ccy,hist,last,prev,four,delta1:last.net-prev.net,delta4:last.net-four.net,
        longFlow:last.long-prev.long,shortFlow:last.short-prev.short,prices,priceRow,price1,
        priceState:fx?.priceState||'non conclusivo',level:'non validato'};
      const q=root.FXQuantCOTDeskV26?.statistics?.(out,get('cotPriorReference'))||null;
      out.deskStats=q;
      // Only the latest exclusive-current 104W percentile is report-comparable.
      // Historical stored percentiles use an older inclusive method and retain
      // an explicit marker; never silently relabel them as exact.
      out.last={...last,percentile:q?.p??null};
      out.hist=[...hist.slice(0,-1),out.last];
      out.level=q?.level==='EXTREME LONG'?'alto':
        q?.level==='EXTREME SHORT'?'basso':
        q?.level==='NEUTRALE'?'intermedio':'non validato';
      return out;
    }
        function stat(a,b,note,cls=''){
      return '<div class="cot-stat"><span>'+esc(a)+'</span><strong class="'+cls+'">'+esc(b)+'</strong><small>'+esc(note)+'</small></div>';
    }
    function classify(a){
      const q=a?.deskStats;
      if(!q||q.rounded===null)return '<span class="badge warning">P104 DA VERIFICARE</span>';
      return '<span class="badge '+(q.rounded>=80?'good':q.rounded<=20?'danger':'info')+
        '">P'+fmt(q.rounded,0)+' · '+esc(q.level)+'</span>';
    }
        function levelText(a){
      const r=a.last,q=a.deskStats;
      const position=r.net>0?'net long':r.net<0?'net short':'neutri';
      const rank=q?.rounded===null||!q?'non disponibile':
        'P'+fmt(q.rounded,0)+' e Z-score '+sign(q.z,2);
      return 'I fondi risultano '+position+' ('+sign(r.net,0,' contratti')+
        '). Posizione relativa: '+rank+'. '+
        (r.net<0&&q?.rounded>=80?
          'La fascia EXTREME LONG è relativa allo storico: gli operatori restano net short. ':'')+
        'Un estremo storico non prova né l’inversione né l’attrattività di un trade.';
    }
        function flowText(a){
      return root.FXQuantCOTEvidence?.flowReading?.(a)?.detail||
        'Flussi long e short da verificare sulle ultime quattro rilevazioni; nessun trade deducibile dal netto.';
    }
    function priceText(a){
      if(!a.prices.length||!finite(a.price1))return 'Serie prezzo BCE non validata sullo stesso storico CFTC. Non attribuiamo conferme al prezzo.';
      const pair=a.priceRow?.priceLabel||a.ccy+'/USD';
      return 'Dal martedì precedente al '+date(a.last.date)+' il riferimento '+pair+
        ' varia di '+sign(a.price1,2,'%')+' e il net positioning di '+sign(a.delta1,0,' contratti')+
        '. I segni sono '+a.priceState+'. È un confronto fra due osservazioni settimanali, non un test causale né il rendimento successivo alla pubblicazione COT.';
    }
    function interpretation(a){
      const q=a.deskStats,r=root.FXQuantCOTDeskV26?.reading?.(q);
      const fact=r?.fact||'Flussi netti e lordi non validati su base storica omogenea.';
      const view=r?.judgment||'Per un giudizio coerente col report servono 104 osservazioni precedenti certificate.';
      const verify=r?.verify||'Verificare la qualità dello storico precedente e attendere la prossima pubblicazione CFTC.';
      const price=r?.price||priceText(a);
      return '<section class="cot-analysis cot-judgment">'
       +'<div class="cot-analysis-head"><div><span class="chapter-kicker">04 / COSA VEDO DAVVERO · '+FLAGS[a.ccy]+' '+a.ccy+'</span>'
       +'<h2>Il giudizio del desk. <em>Senza copiare le tabelle.</em></h2></div>'
       +'<p>Stock → composizione dei flussi → accelerazione → prezzo → verifica. Le tesi e il timing FX restano distinti.</p></div>'
       +'<div class="cot-analysis-grid">'
       +'<article><span class="cot-number">01</span><span class="micro-over">IL CAMBIAMENTO</span><h3>Che cosa stanno facendo i fondi?</h3><p>'+esc(fact)+'</p></article>'
       +'<article><span class="cot-number">02</span><span class="micro-over">LA CONFERMA DI PREZZO</span><h3>Il prezzo sostiene questa lettura?</h3><p>'+esc(price)+'</p></article>'
       +'<article><span class="cot-number">03</span><span class="micro-over">IL MIO GIUDIZIO</span><h3>Quanto è credibile la tesi?</h3><p>'+esc(view)+'</p></article>'
       +'<article><span class="cot-number">04</span><span class="micro-over">CONFERMA / INVALIDAZIONE</span><h3>Cosa controllare nel prossimo COT?</h3><p>'+esc(verify)+'</p></article>'
       +'</div></section>';
    }
        function countrySelector(){
      return '<div class="cot-country-selector" role="group" aria-label="Valute G8 COT">'
       +FX.map(k=>{
         const a=report(k),q=a?.deskStats,r=a?.last;
         return '<button type="button" data-ccy="'+k+'" aria-pressed="'+String(k===state.ccy)+'" class="cot-country-button '+(k===state.ccy?'active':'')+'">'
         +'<span class="cot-country-symbol">'+FLAGS[k]+' '+k+'</span>'
         +'<strong>'+(q?.rounded!==null&&q?.rounded!==undefined?'P'+fmt(q.rounded,0):'P—')+'</strong>'
         +'<small>'+esc(r?.net>0?'Net long':r?.net<0?'Net short':'Net non validato')+
          ' · '+esc(a?sign(a.delta1,0,' 1W'):'—')+'</small></button>';
       }).join('')+'</div>';
    }
        function graphFor(a){
      const mode=state.cotMode||'net',w=Number(state.cotWindow||26),rows=a.hist.slice(-w);
      let lines,unit='',label,precision=1,note;
      if(mode==='net'){
        label='Posizione netta · contratti';
        lines=[{name:'Long − Short',color:'#7fdabc',values:rows.map(r=>({label:r.date,value:r.net}))}];
        precision=0;
        note='Sopra zero: net long. Sotto zero: net short. Confronta il flusso, non soltanto lo stock.';
      }else if(mode==='gross'){
        label='Long e short · contratti';
        lines=[{name:'Long',color:'#74dcb7',values:rows.map(r=>({label:r.date,value:r.long}))},
               {name:'Short',color:'#f36f83',values:rows.map(r=>({label:r.date,value:r.short}))}];
        precision=0;
        note='Il netto migliora anche quando vengono chiusi short: non equivale sempre a nuovi acquisti long.';
      }else if(mode==='netoi'){
        label='Net / Open Interest (%)';
        lines=[{name:'Net/OI',color:'#9ccde9',values:rows.map(r=>({label:r.date,value:r.netoi}))}];unit='%';
        note='Normalizzazione sulla base di open interest del relativo mercato, non un rendimento.';
      }else if(mode==='percentile'){
        label='Percentile storico · fonte archiviata';
        lines=[{name:'Percentile',color:'#edbf7c',values:rows.map(r=>({label:r.date,value:r.percentile}))}];
        note='Ultimo punto: P104 esatto contro 104 settimane precedenti. I punti storici sono percentili della fonte originale inclusiva: non direttamente confrontabili con il nuovo calcolo. P80/P20 non sono timing.';
      }else{
        label='Variazione netta settimanale';
        lines=[{name:'Δ netto 1W',color:'#abafd7',values:rows.slice(1).map((r,i)=>({label:r.date,value:r.net-rows[i].net}))}];precision=0;
        note='Velocità del cambiamento. Una settimana positiva può anche rappresentare copertura di posizioni short.';
      }
      const modes=[['net','Posizione netta'],['gross','Long e short'],['flow','Flusso 1W'],['netoi','Net/OI'],['percentile','Percentile']];
      const wins=[13,26,52,104];
      const choice=(tag,x,on)=>'<button type="button" data-'+tag+'="'+esc(x)+'" aria-pressed="'+String(on)+'" class="pill '+(on?'active':'')+'">'+esc(x)+'</button>';
      return '<div class="cot-figure-title"><div><span class="micro-over">GRAFICO CFTC / '+a.ccy+'</span><h3>'+esc(label)+'</h3></div><span class="data-date">'+rows.length+' settimane · '+date(rows[0]?.date)+'—'+date(rows.at(-1)?.date)+'</span></div>'
       +'<div class="cot-graph-controls"><div class="pill-controls">'+modes.map(x=>choice('cot-mode',x[0],mode===x[0]).replace('>'+esc(x[0])+'</button>','>'+esc(x[1])+'</button>')).join('')+'</div>'
       +'<div class="pill-controls">'+wins.map(n=>choice('cot-window',n,Number(n)===w).replace('>'+n+'</button>','>'+n+'W</button>')).join('')+'</div></div>'
       +plot({lines,unit,precision,label})
       +'<p class="cot-footnote">'+esc(note)+'</p>';
    }
    function priceGraph(a){
      if(!a.prices.length){
        return '<div class="empty"><strong>Prezzo allineato non validato</strong><p>Non disegniamo una curva di prezzo su date diverse dal COT.</p></div>';
      }
      const pts=a.prices.slice(-Number(state.cotWindow||26));
      return '<div class="cot-figure-title"><div><span class="micro-over">BCE FIXING · STESSE DATE CFTC</span><h3>'+esc(a.priceRow?.priceLabel||a.ccy+'/USD')+' · comparatore prezzo</h3></div>'
        +'<span class="data-date">Al '+date(a.last.date)+'</span></div>'
        +plot({lines:[{name:a.priceRow?.priceLabel||'FX',color:'#a9d6ec',values:pts}],precision:4,label:'Prezzo FX su date COT'})
        +'<p class="cot-footnote">Fixing BCE verificati direttamente sulle date dei martedì COT ('+a.prices.length+' osservazioni abbinate), senza interpolazione; non rappresentano la reazione al report pubblicato più tardi. Quota '+esc(a.priceRow?.priceLabel||'FX')+
        ': quando il prezzo sale si apprezza la valuta al numeratore.</p>';
    }
    function last12(a){
      return '<section class="cot-detailed-table"><div class="cot-analysis-head"><div><span class="chapter-kicker">06 / AUDIT STORICO</span>'
       +'<h2>Le ultime 12 settimane. <em>Long, short e saldo.</em></h2></div>'
       +'<p>Le variazioni delle due gambe spiegano il netto. P104 più recente: metodo esclusivo; i ranghi delle settimane vecchie hanno una definizione differente.</p></div>'
       +'<div class="table-wrap"><table class="data-table cot-table"><thead><tr><th>Martedì CFTC</th><th>Long</th><th>Short</th><th>Net</th><th>Δ Net 1W</th><th>Net/OI</th><th>Rango P*</th></tr></thead><tbody>'
       +a.hist.slice(-12).reverse().map(r=>{
         const i=a.hist.findIndex(x=>x.date===r.date),prev=a.hist[i-1];
         const current=r.date===a.last.date,rank=current?a.deskStats?.rounded:r.percentile;
         return '<tr><td>'+date(r.date)+'</td><td>'+fmt(r.long,0)+'</td><td>'+fmt(r.short,0)+'</td>'
          +'<td>'+sign(r.net,0)+'</td><td>'+sign(prev?r.net-prev.net:null,0)+'</td>'
          +'<td>'+sign(r.netoi,2,'%')+'</td><td>'+(rank===null||rank===undefined?'—':
             (current?'P'+fmt(rank,0):'≈'+fmt(rank,1)))+'</td></tr>';
       }).join('')+'</tbody></table></div>'
       +'<p class="source-caption">* Ultima riga: percentile P104 rispetto alle 104 osservazioni precedenti, verificato contro archivio CFTC. Righe più vecchie: percentili archiviati della serie inclusiva; il simbolo ≈ indica metodo diverso, non precisione inferiore del Net. Long, short, Net e Net/OI provengono dal CFTC.</p></section>';
    }
        function universe(){
      const all=FX.map(report).filter(Boolean),filter=state.cotFilter||'all',sort=state.cotSort||'percentile',asc=state.cotSortAsc===true;
      const rows=all.filter(a=>filter==='all'||filter==='extreme'&&a.level!=='intermedio'&&a.level!=='non validato'
        ||filter==='rising'&&a.delta1>0||filter==='falling'&&a.delta1<0);
      const v=(a,k)=>{
       const q=a.deskStats;
       return k==='percentile'?q?.rounded:k==='z'?q?.z:k==='net'?a.last.net:
        k==='netoi'?a.last.netoi:k==='delta1'?a.delta1:k==='delta4'?a.delta4:q?.delta8;
      };
      rows.sort((a,b)=>{
       const x=v(a,sort),y=v(b,sort);
       if(!finite(x)&&!finite(y))return a.ccy.localeCompare(b.ccy);
       if(!finite(x))return 1;if(!finite(y))return -1;
       return (x-y)*(asc?1:-1)||a.ccy.localeCompare(b.ccy);
      });
      const filters=[['all','Tutte'],['extreme','P20 / P80'],['rising','Net in aumento'],['falling','Net in calo']];
      const heads=[['percentile','P104'],['z','Z104'],['net','Net'],['delta1','Δ 1W'],['delta4','Δ 4W'],['delta8','Δ 8W'],['netoi','Net/OI']];
      return '<section class="cot-universe"><div class="cot-analysis-head"><div><span class="chapter-kicker">02 / CLASSIFICA G8</span>'
       +'<h2>La mappa dei fondi. <em>Dal percentile alto al basso.</em></h2></div>'
       +'<p>Stock, velocità, persistenza e affollamento. I contratti dei diversi futures non misurano la forza relativa delle valute.</p></div>'
       +'<div class="cot-table-filters"><div class="pill-controls">'+filters.map(([k,l])=>
        '<button class="pill '+(k===filter?'active':'')+'" data-cot-filter="'+k+'" aria-pressed="'+String(k===filter)+'" type="button">'+l+'</button>').join('')+
         '</div><small>Clicca sulle intestazioni per ordinare</small></div>'
       +'<div class="table-wrap"><table class="data-table cot-table cot-rank-table"><thead><tr><th>Valuta / fascia</th>'
       +heads.map(([k,l])=>'<th><button type="button" data-cot-sort="'+k+'">'+l+(sort===k?(asc?' ↑':' ↓'):' ↕')+'</button></th>').join('')+
        '<th>As of</th></tr></thead><tbody>'
       +rows.map(a=>{
        const q=a.deskStats,p=q?.rounded,netoi=a.last.netoi;
        return '<tr class="'+(a.ccy===state.ccy?'active':'')+'"><td><button type="button" data-ccy="'+a.ccy+'">'+FLAGS[a.ccy]+' '+a.ccy+
         '</button><small class="cot-row-state '+(p>=80?'cot-long':p<=20?'cot-short':'')+'">'+esc(q?.level||'DA VERIFICARE')+'</small></td>'
         +'<td>'+(p===null||p===undefined?'—':fmt(p,0)+'°')+'</td>'
         +'<td>'+(finite(q?.z)?sign(q.z,2):'—')+'</td><td>'+sign(a.last.net,0)+'</td>'
         +'<td class="'+(a.delta1>0?'tone-up':a.delta1<0?'tone-down':'')+'">'+sign(a.delta1,0)+'</td>'
         +'<td>'+sign(a.delta4,0)+'</td><td>'+sign(q?.delta8,0)+'</td>'
         +'<td class="'+(q?.crowd?'tone-down':'')+'">'+(q?.crowd?'⚠ ':'')+sign(netoi,1,'%')+'</td>'
         +'<td>'+date(a.last.date)+'</td></tr>';
       }).join('')+'</tbody></table></div>'
       +'<p class="source-caption">P104: 104 Net precedenti escludendo il martedì attuale, arrotondamento intero prima delle soglie 80/20. Z104: deviazioni standard campionarie (ddof=1). ⚠ Net/OI ≥ ±30,0% dopo arrotondamento a un decimale. Estremo NON significa inversione imminente.</p></section>';
    }
        function glossary(){
      const terms=[
        ['Long','Contratti futures detenuti in posizione rialzista dai non-commercial; non equivalgono a un ordine di acquisto nel mercato spot FX.'],
        ['Short','Contratti futures detenuti in posizione ribassista dai non-commercial.'],
        ['Net = Long − Short','Differenza fra long e short. Net positivo = prevalenza long; negativo = prevalenza short.'],
        ['Δ Net 1W / 4W','Variazione del netto rispetto a una o quattro rilevazioni prima. Misura il flusso, non il rendimento della valuta.'],
        ['Net/Open Interest','Net rapportato all’open interest complessivo del contratto, espresso in %. È un indicatore relativo del grado di concentrazione.'],
        ['Percentile 104W e Z-score','Ultimo martedì: confronto con 104 Net precedenti, settimana corrente esclusa. Percentile arrotondato all’intero prima delle soglie 80/20; Z=(Net−media)/deviazione standard campionaria. L’archivio storico precedente usa un percentile inclusivo, esplicitamente marcato.'],
         ['Velocità e Net/OI','Velocity = Δ Net 1W / Open Interest. Qui l’OI è ricostruito approssimativamente da Net/NetOI arrotondato, quindi è una stima e non l’OI osservato. Alert se |Net/OI| arrotondato a un decimale raggiunge 30%.'],
        ['Prezzo coerente / divergente','Confronto descrittivo tra segno della variazione di prezzo e variazione netta nel medesimo intervallo. Non certifica una relazione causale.'],
        ['Ritardo COT','Il report CFTC fotografa tipicamente il martedì e viene pubblicato successivamente. La situazione reale può cambiare prima che il dato sia accessibile.']
      ];
      return '<section class="cot-glossary"><div class="cot-analysis-head"><div><span class="chapter-kicker">06 / METODO & DEFINIZIONI</span><h2>Ogni numero ha <em>un significato preciso.</em></h2></div><p>Le definizioni non sono nascoste: sono parte del processo di ricerca.</p></div>'
        +'<div class="cot-definitions">'+terms.map(([title,body])=>'<details><summary>'+esc(title)+'<span>＋</span></summary><p>'+esc(body)+'</p></details>').join('')+'</div></section>';
    }
    function render(){
      const ccy=state.ccy,a=report(ccy),all=FX.map(report).filter(Boolean);
      const sourceDate=a?.last.date;
      const common=all.length===8&&all.every(x=>x.last.date===all[0].last.date);
      const header=pageHero('CFTC / POSITIONING INTELLIGENCE','Leggi lo stock.<br><em>Segui il flusso.</em> Verifica il prezzo.','Un vero laboratorio settimanale: posizione netta, long/short, flussi, Net/OI, percentile, prezzo allineato e tabella completa delle otto valute.');
      let body=header+
        '<div class="cot-source-band"><span><span class="live-dot"></span> CFTC NON-COMMERCIAL · ULTIMO DATO '+date(sourceDate)+'</span>'
         +'<span>'+((a?.hist.length||0))+' SETTIMANE · '+(common?'G8 ALLINEATE':'DATE G8 DA VERIFICARE')+'</span></div>'
        +countrySelector();
      if(!a)return body+'<div class="empty"><strong>Storico COT non validato per '+esc(ccy)+'</strong><p>Il dataset non supera il controllo su date, long, short e net. Non mostriamo segnali sostitutivi.</p></div>';
      const last=a.last,p=a.last.percentile,netDesc=last.net>0?'I long prevalgono':last.net<0?'Gli short prevalgono':'Long e short si equivalgono';
      const summary=root.FXQuantCOTEvidence?.flowReading?.(a)?.headline||
        (a.delta1>0?'Il netto migliora.':a.delta1<0?'Il netto peggiora.':'Il netto non cambia.');
      body+='<section class="cot-hero"><div class="cot-hero-narrative"><span class="chapter-kicker">01 / '+FLAGS[ccy]+' '+ccy+' · LETTURA EVIDENCE-FIRST</span>'
       +'<h2>'+esc(summary)+'<br><em>'+esc(netDesc)+'.</em></h2><p>'+esc(levelText(a))+'</p>'
       +'<div class="cot-status-line">'+classify(a)+'<span>Ultima rilevazione '+date(last.date)+'</span></div></div>'
       +'<div class="cot-hero-visual"><div class="cot-ring" style="--pct:'+Math.min(100,Math.max(0,p))+'"><div><span>PERCENTILE</span><strong>'+fmt(p,1)+'</strong><small>su 104 settimane</small></div></div>'
       +'<span class="cot-risk-label">P20 e P80: fasce storiche, non timing</span></div></section>'
       +'<div class="cot-statstrip">'
       +stat('NET POSITION',sign(last.net,0),'contratti · long − short')
       +stat('Δ NET 1W',sign(a.delta1,0),'variazione settimanale',a.delta1>0?'tone-up':a.delta1<0?'tone-down':'')
       +stat('Δ NET 4W',sign(a.delta4,0),'variazione su quattro settimane',a.delta4>0?'tone-up':a.delta4<0?'tone-down':'')
       +stat('NET / OPEN INTEREST',sign(last.netoi,2,'%'),'normalizzazione percentuale')
       +'</div>'
       +'<section class="cot-graph-theatre"><div class="cot-analysis-head"><div><span class="chapter-kicker">02 / CHART STUDIO</span>'
       +'<h2>Il positioning, <em>senza perdere la profondità.</em></h2></div>'
       +'<p>Seleziona metrica e intervallo. Il prezzo è su un secondo grafico per evitare scale incompatibili e confronti ingannevoli.</p></div>'
       +'<div class="cot-graph-grid"><div class="cot-plot-card">'+graphFor(a)+'</div><div class="cot-plot-card cot-price-card">'
       +priceGraph(a)+'</div></div></section>'
       +interpretation(a)+last12(a)+universe()+glossary()
       +'<section class="cot-after"><div><span class="chapter-kicker">DALLA RICERCA AL MERCATO</span><h2>Il COT racconta il posizionamento.<br><em>La tesi FX richiede molto di più.</em></h2>'
       +'<p>Confronta questa valuta con macro, tassi, pricing e prezzo prima di valutare una coppia. Una concentrazione estrema può persistere a lungo.</p></div>'
       +'<a href="#pairs" class="action-primary">Apri l’esploratore FX <span>↗</span></a></section>'
       +'<p class="source-caption">Fonti: CFTC Legacy Non-Commercial (V250_COT_CHART_DATA), comparatore BCE fixing (Design Studio COT V1). Tutte le osservazioni sono fotografie settimanali, non quote intraday. Lo storico del percentile è di 104 settimane. Ultimo martedì nel dataset: '+date(last.date)+'.</p>';
      return body;
    }
    return render();
  }
  root.FXQuantCOT={render:make};
})(window);
