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
      if(hist.length<5)return null;
      const last=hist.at(-1),prev=hist.at(-2),four=hist.at(-5);
      const priceDoc=get('cotPrice'),priceRow=priceDoc?.currencies?.[ccy];
      const matched=priceDoc?.price_alignment===last.date&&priceRow?.as_of===last.date
        &&priceRow?.net===last.net&&Array.isArray(priceRow.priceSeries)
        &&priceRow.priceSeries.length===hist.length
        &&priceRow.priceSeries.every(x=>finite(x)&&x>0);
      const prices=matched?priceRow.priceSeries.map((v,i)=>({label:hist[i].date,value:v})):[];
      const firstPrice=prices.at(-2)?.value,secondPrice=prices.at(-1)?.value;
      const price1=finite(firstPrice)&&finite(secondPrice)&&firstPrice>0?(secondPrice/firstPrice-1)*100:null;
      const delta1=last.net-prev.net,delta4=last.net-four.net;
      const priceState= !finite(price1)||delta1===0||price1===0?'non conclusivo'
        :Math.sign(delta1)===Math.sign(price1)?'coerente':'divergente';
      const level=last.percentile>=PCTS.upper?'alto':last.percentile<=PCTS.lower?'basso':'intermedio';
      return {ccy,hist,last,prev,four,delta1,delta4,longFlow:last.long-prev.long,
        shortFlow:last.short-prev.short,prices,priceRow,price1,priceState,level};
    }
    function stat(a,b,note,cls=''){
      return '<div class="cot-stat"><span>'+esc(a)+'</span><strong class="'+cls+'">'+esc(b)+'</strong><small>'+esc(note)+'</small></div>';
    }
    function classify(a){
      if(!a)return '<span class="badge warning">NON VALIDATO</span>';
      const p=a.last.percentile;
      return '<span class="badge '+(p>=80?'warning':p<=20?'danger':'info')+'">P'+fmt(p,1)
          +' · '+(a.level==='alto'?'FASCIA ALTA':a.level==='basso'?'FASCIA BASSA':'FASCIA INTERMEDIA')+'</span>';
    }
    function levelText(a){
      const r=a.last,position=r.net>0?'net long':r.net<0?'net short':'neutri';
      return 'La posizione complessiva è '+position+' ('+sign(r.net,0,' contratti')+
        '). Il percentile storico è P'+fmt(r.percentile,1)+' sulla finestra disponibile di 104 settimane. '+
        (r.net<0&&r.percentile>=80?'Attenzione: P alto non significa net long; la posizione è ancora net short. ':
         r.net>0&&r.percentile<=20?'Attenzione: P basso non significa net short; la posizione è ancora net long. ':'')+
        'Il percentile indica dove si colloca la posizione rispetto alla propria storia, non misura da solo il rischio di inversione.';
    }
    function flowText(a){
      const n=a.delta1,l=a.longFlow,s=a.shortFlow;
      let drive;
      if(l>0&&s<0)drive='Nuovi long e coperture di short contribuiscono entrambi al miglioramento netto.';
      else if(l<0&&s>0)drive='Riduzione dei long e nuovi short contribuiscono entrambi al peggioramento netto.';
      else if(n>0&&s<0)drive='La chiusura di short contribuisce al miglioramento netto: non attribuirlo automaticamente a nuovi compratori.';
      else if(n>0&&l>0)drive='L’aumento dei long contribuisce al miglioramento netto.';
      else if(n<0&&l<0)drive='La contrazione dei long contribuisce al peggioramento netto.';
      else if(n<0&&s>0)drive='L’aumento degli short contribuisce al peggioramento netto.';
      else drive='I flussi long e short si compensano parzialmente.';
      return 'Nell’ultima settimana il netto '+(n>0?'migliora':n<0?'peggiora':'è invariato')+
        ' di '+sign(n,0,' contratti')+'. Long '+sign(l,0)+'; short '+sign(s,0)+'. '+drive;
    }
    function priceText(a){
      if(!a.prices.length||!finite(a.price1))return 'Serie prezzo BCE non validata sullo stesso storico CFTC. Non attribuiamo conferme al prezzo.';
      const pair=a.priceRow?.priceLabel||a.ccy+'/USD';
      return 'Dal martedì precedente al '+date(a.last.date)+' il riferimento '+pair+
        ' varia di '+sign(a.price1,2,'%')+' e il net positioning di '+sign(a.delta1,0,' contratti')+
        '. I segni sono '+a.priceState+'. È un confronto fra due osservazioni settimanali, non un test causale né il rendimento successivo alla pubblicazione COT.';
    }
    function interpretation(a){
      const s=get('cot')?.[a.ccy];
      return '<section class="cot-analysis">'
      +'<div class="cot-analysis-head"><div><span class="chapter-kicker">02 / LETTURA INVESTIGATIVA</span><h2>Quattro domande, <em>quattro risposte.</em></h2></div>'
      +'<p>Separiamo i fatti e le interpretazioni. Un posizionamento estremo o un’inversione del flusso non basta a formulare un segnale.</p></div>'
      +'<div class="cot-analysis-grid">'
      +'<article><span class="cot-number">01</span><span class="micro-over">STOCK / LIVELLO</span><h3>Dove sono posizionati i fondi?</h3><p>'+esc(levelText(a))+'</p></article>'
      +'<article><span class="cot-number">02</span><span class="micro-over">FLOW / CAMBIAMENTO</span><h3>Come si stanno muovendo?</h3><p>'+esc(flowText(a))+'</p></article>'
      +'<article><span class="cot-number">03</span><span class="micro-over">PRICE / CONFERMA</span><h3>Il prezzo racconta la stessa storia?</h3><p>'+esc(priceText(a))+'</p></article>'
      +'<article><span class="cot-number">04</span><span class="micro-over">RISK / TESI</span><h3>Cosa monitorare adesso?</h3><p>'+esc(s?.why||'Verificare prezzi successivi, OIS, dati macro e persistenza del flusso prima di attribuire un bias operativo.')+
      '</p></article></div></section>';
    }
    function countrySelector(){
      return '<div class="cot-country-selector" role="group" aria-label="Valute G8 COT">'
      +FX.map(k=>{
        const a=report(k),r=a?.last;
        return '<button type="button" data-ccy="'+k+'" aria-pressed="'+String(k===state.ccy)+'" class="cot-country-button '+(k===state.ccy?'active':'')+'">'
        +'<span class="cot-country-symbol">'+FLAGS[k]+' '+k+'</span>'
        +'<strong>'+ (finite(r?.percentile)?'P'+fmt(r.percentile,0):'—')+'</strong>'
        +'<small>'+esc(r?.net>0?'Net long':r?.net<0?'Net short':'Net non validato')+' · '+esc(a?sign(a.delta1,0,' 1W'):'—')+'</small></button>';
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
        label='Percentile storico · 104 settimane';
        lines=[{name:'Percentile',color:'#edbf7c',values:rows.map(r=>({label:r.date,value:r.percentile}))}];
        note='P80 / P20 descrivono code della distribuzione storica: non livelli di ingresso.';
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
        +'<p class="cot-footnote">Grafico riferito ai martedì COT, non al momento di pubblicazione del report. Quota '+esc(a.priceRow?.priceLabel||'FX')+
        ': quando il prezzo sale si apprezza la valuta al numeratore.</p>';
    }
    function last12(a){
      return '<section class="cot-detailed-table"><div class="cot-analysis-head"><div><span class="chapter-kicker">04 / AUDIT STORICO</span><h2>Le ultime 12 settimane. <em>Senza scorciatoie.</em></h2></div>'
       +'<p>Il dato va verificato anche nella sua composizione: long, short, netto, flusso, Net/OI e percentile.</p></div>'
       +'<div class="table-wrap"><table class="data-table cot-table"><thead><tr><th>Martedì CFTC</th><th>Long</th><th>Short</th><th>Net</th><th>Δ Net 1W</th><th>Net/OI</th><th>P104</th></tr></thead><tbody>'
       +a.hist.slice(-12).reverse().map(r=>{
         const i=a.hist.findIndex(x=>x.date===r.date),prev=a.hist[i-1];
         return '<tr><td>'+date(r.date)+'</td><td>'+fmt(r.long,0)+'</td><td>'+fmt(r.short,0)+'</td>'
         +'<td>'+sign(r.net,0)+'</td><td>'+sign(prev?r.net-prev.net:null,0)+'</td>'
         +'<td>'+sign(r.netoi,2,'%')+'</td><td>'+fmt(r.percentile,1)+'</td></tr>';
       }).join('')+'</tbody></table></div></section>';
    }
    function universe(){
      const universe=FX.map(report).filter(Boolean),filter=state.cotFilter||'all',sort=state.cotSort||'percentile';
      const asc=state.cotSortAsc===true;
      const rows=universe.filter(a=>filter==='all'||filter==='extreme'&&a.level!=='intermedio'
        ||filter==='rising'&&a.delta1>0||filter==='falling'&&a.delta1<0);
      const v=(a,k)=>k==='net'?a.last.net:k==='netoi'?a.last.netoi:k==='delta1'?a.delta1:k==='delta4'?a.delta4:a.last.percentile;
      rows.sort((a,b)=>(v(a,sort)-v(b,sort))*(asc?1:-1));
      const filters=[['all','Tutte'],['extreme','P20 / P80'],['rising','Net in aumento'],['falling','Net in calo']];
      const headers=[['net','Net'],['delta1','Δ 1W'],['delta4','Δ 4W'],['netoi','Net/OI'],['percentile','P104']];
      return '<section class="cot-universe"><div class="cot-analysis-head"><div><span class="chapter-kicker">05 / COMPARAZIONE G8</span><h2>La mappa del positioning. <em>Valuta per valuta.</em></h2></div>'
       +'<p>Ordina e filtra. I contratti hanno dimensioni diverse: gli stock assoluti non rappresentano una graduatoria della forza FX.</p></div>'
       +'<div class="cot-table-filters"><div class="pill-controls">'+filters.map(([k,l])=>
         '<button class="pill '+(k===filter?'active':'')+'" data-cot-filter="'+k+'" aria-pressed="'+String(k===filter)+'" type="button">'+l+'</button>').join('')+'</div><small>Clicca le intestazioni per ordinare</small></div>'
       +'<div class="table-wrap"><table class="data-table cot-table"><thead><tr><th>Valuta</th>'
       +headers.map(([k,l])=>'<th><button type="button" data-cot-sort="'+k+'">'+l+(sort===k?(asc?' ↑':' ↓'):' ↕')+'</button></th>').join('')+'<th>Rilevazione</th></tr></thead><tbody>'
       +rows.map(a=>'<tr class="'+(a.ccy===state.ccy?'active':'')+'"><td><button type="button" data-ccy="'+a.ccy+'">'+FLAGS[a.ccy]+' '+a.ccy+'</button></td>'
         +'<td>'+sign(a.last.net,0)+'</td><td class="'+(a.delta1>0?'tone-up':a.delta1<0?'tone-down':'')+'">'+sign(a.delta1,0)+'</td>'
         +'<td>'+sign(a.delta4,0)+'</td><td>'+sign(a.last.netoi,2,'%')+'</td><td>'+fmt(a.last.percentile,1)+'</td>'
         +'<td>'+date(a.last.date)+'</td></tr>').join('')
       +'</tbody></table></div><p class="source-caption">Fonte CFTC Legacy Non-Commercial; rilevazione settimanale martedì. P104 è il percentile storico per la singola valuta. Nessuna interpretazione automatica come segnale di trading.</p></section>';
    }
    function glossary(){
      const terms=[
        ['Long','Contratti futures detenuti in posizione rialzista dai non-commercial; non equivalgono a un ordine di acquisto nel mercato spot FX.'],
        ['Short','Contratti futures detenuti in posizione ribassista dai non-commercial.'],
        ['Net = Long − Short','Differenza fra long e short. Net positivo = prevalenza long; negativo = prevalenza short.'],
        ['Δ Net 1W / 4W','Variazione del netto rispetto a una o quattro rilevazioni prima. Misura il flusso, non il rendimento della valuta.'],
        ['Net/Open Interest','Net rapportato all’open interest complessivo del contratto, espresso in %. È un indicatore relativo del grado di concentrazione.'],
        ['Percentile 104W','Rango relativo del netto dentro le ultime 104 settimane. P90 significa più alto rispetto alla maggior parte della propria storia, non necessariamente net long.'],
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
      const summary=a.delta1>0?'Il netto migliora.':a.delta1<0?'Il netto peggiora.':'Il netto non cambia.';
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
