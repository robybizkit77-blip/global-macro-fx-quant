'use strict';
/* Semaforo economico USA: ricerca descrittiva, non un modello di probabilita' di recessione.
   Legge esclusivamente MACRO_SERIES, non riscrive la fonte, il Core FX o il pricing. */
(function(root){
  const GROUPS=[
    {key:'house',name:'Immobiliare',why:'Nuove costruzioni e permessi anticipano una parte della domanda ciclica.',metrics:[
      {id:'US_PERMIT_history_PERMIT',name:'Permessi edilizi',upGood:true,unit:'mila annualizzati'},
      {id:'US_HOUST_history_HOUST',name:'Nuovi cantieri',upGood:true,unit:'mila annualizzati'}]},
    {key:'jobs',name:'Lavoro',why:'Assunzioni nette e sussidi misurano lati diversi del mercato del lavoro.',metrics:[
      {id:'US_PAYEMS_history_value',name:'Payrolls',upGood:true,unit:'mila occupati'},
      {id:'US_CCSA_history_CCSA',name:'Sussidi continuativi',upGood:false,scale:1000000,unit:'mln persone'}]},
    {key:'industry',name:'Manifattura',why:'Produzione e ordini non sono la stessa cosa: le divergenze contano.',metrics:[
      {id:'US_INDPRO_history_value',name:'Produzione industriale',upGood:true,unit:'indice'},
      {id:'US_NEWORDER_history_NEWORDER',name:'Nuovi ordini core',upGood:true,unit:'unità fonte non specificate'}]},
    {key:'leading',name:'Indicatore anticipatore',why:'Il CFNAI è un indicatore composito della Fed di Chicago, non il LEI del Conference Board.',metrics:[
      {id:'US_CFNAI_LEAD_INDICATOR_history_CFNAI',name:'CFNAI',upGood:true,kind:'points',minimum:0.05,unit:'indice'}]},
    {key:'demand',name:'Consumi e domanda',why:'I volumi reali aiutano a capire se il consumatore continua a sostenere la crescita.',metrics:[
      {id:'US_PCEC96_history_value',name:'Consumi reali',upGood:true,unit:'mld USD reali SAAR'},
      {id:'US_RRSFS_history_value',name:'Vendite reali al dettaglio',upGood:true,unit:'mln USD reali'}]},
    {key:'credit',name:'Credito',why:'Standard sui prestiti e quantità di credito possono muoversi in direzioni diverse.',metrics:[
      {id:'US_SLOOS_CI_LARGE_MIDDLE_history_value',name:'SLOOS: restrizione standard imprese',upGood:false,kind:'points',minimum:1,unit:'saldo percentuale'},
      {id:'US_TOTBKCR_history_value',name:'Credito bancario totale',upGood:true,unit:'mld USD'}]}
  ];
  const isNum=v=>typeof v==='number'&&Number.isFinite(v);
  function canonicalDate(x){
    if(typeof x!=='string')return null;
    const q=x.match(/^(\d{4})-?Q([1-4])$/);
    if(q)return q[1]+'-'+String(Number(q[2])*3).padStart(2,'0')+'-01';
    const d=x.match(/^(\d{4})-(\d{2})(?:-(\d{2}))?/);
    if(!d)return null;
    return d[1]+'-'+d[2]+'-'+(d[3]||'01');
  }
  function latest(series,today){
    if(!series||!Array.isArray(series.dates)||!Array.isArray(series.values)||series.dates.length!==series.values.length)return null;
    const pairs=series.dates.map((d,i)=>({date:canonicalDate(d),period:d,value:series.values[i]}))
      .filter(x=>x.date&&x.date<=today&&isNum(x.value))
      .sort((a,b)=>a.date.localeCompare(b.date));
    if(pairs.length<2)return null;
    return {current:pairs.at(-1),previous:pairs.at(-2)};
  }
  function inspect(metric,series,today){
    const last=latest(series,today);
    if(!last)return null;
    const c=last.current.value,p=last.previous.value;
    const diff=c-p,pct=p!==0?100*diff/Math.abs(p):null;
    const kind=metric.kind||'percent';
    const min=metric.minimum===undefined?.15:metric.minimum;
    const movement=kind==='points'?diff:pct;
    const verdict=!isNum(movement)||Math.abs(movement)<min?0:Math.sign(movement)*(metric.upGood?1:-1);
    const age=Math.round((Date.parse(today+'T12:00:00Z')-Date.parse(last.current.date+'T12:00:00Z'))/86400000);
    const f=String(series.frequency||'M').toUpperCase();
    const stale=age>(f==='W'?42:f==='Q'?180:80);
    const invalid=age>(f==='W'?90:f==='Q'?300:180);
    return {metric,current:c,diff,pct,kind,verdict:invalid?null:verdict,period:last.current.period,
      source:String(series.source_file||'MACRO_SERIES'),stale,invalid,age,frequency:f};
  }
  function classify(items,needed){
    const a=items.filter(Boolean).filter(x=>x.verdict!==null);
    if(a.length<needed)return {tone:'neutral',label:'Non classificabile'};
    if(a.every(x=>x.verdict===1))return {tone:'green',label:'Verde'};
    if(a.every(x=>x.verdict===-1))return {tone:'red',label:'Rosso'};
    return {tone:'amber',label:'Giallo'};
  }
  function model(catalog,today){
    const a=Array.isArray(catalog?.USD)?catalog.USD:[];
    const source=new Map(a.map(s=>[s.id,s]));
    return GROUPS.map(group=>{
      const items=group.metrics.map(m=>inspect(m,source.get(m.id),today));
      return {...group,items,signal:classify(items,group.metrics.length)};
    });
  }
  function render(args){
    const catalog=args?.catalog||{},today=args?.dayNow?.()||'';
    const esc=args?.esc||((x)=>String(x??''));
    if(!/^\d{4}-\d{2}-\d{2}$/.test(today))return '';
    const rows=model(catalog,today);
    const num=(x,n=1)=>isNum(x)?x.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
    const delta=(x,unit)=>!isNum(x)?'—':(x>0?'+':x<0?'−':'')+num(Math.abs(x),unit==='p.p.'?1:2)+(unit==='p.p.'?' p.p.':'%');
    const itemLine=x=>{
      if(!x)return '<span class="sem-missing">Serie non presente nel feed</span>';
      const scaled=x.metric.scale?x.current/x.metric.scale:x.current;
      const n=x.metric.scale?2:(x.metric.kind==='points'?2:Math.abs(scaled)>100?0:1);
      const reading=num(scaled,n)+' '+esc(x.metric.unit);
      const change=x.kind==='points'?delta(x.diff,'p.p.'):delta(x.pct,'%');
      const isPoints=x.kind==='points';
      return '<div class="sem-measure"><div><strong>'+esc(x.metric.name)+'</strong> <span>'+esc(reading)+'</span> <b>'+esc(isPoints?((x.diff>0?'+':x.diff<0?'−':'')+num(Math.abs(x.diff),2)+' punti'):change)+'</b></div>'+
        '<small>Periodo '+esc(x.period)+' · '+esc(x.source)+(x.stale?' · osservazione datata':'')+'</small></div>';
    };
    const dated=rows.some(r=>r.items.some(x=>x&&x.stale));
    const reds=rows.filter(r=>r.signal.tone==='red').map(r=>r.name.toLowerCase());
    const greens=rows.filter(r=>r.signal.tone==='green').map(r=>r.name.toLowerCase());
    const intro=reds.length?'Fra le ultime osservazioni disponibili, il deterioramento più uniforme riguarda '+reds.join(' e ')+'.':
      'Le ultime osservazioni non mostrano due deterioramenti concordi nei gruppi verificabili.';
    const counter=greens.length?' Il quadro è sostenuto, sullo stesso criterio, da '+greens.join(' e ')+'.':'';
    return '<section class="recession-light" aria-labelledby="recession-light-title">'+
      '<header class="sem-head"><div><span class="sem-kicker">GLOBAL MACRO / USA / LETTURA CICLICA</span>'+
      '<h2 id="recession-light-title">Il semaforo economico</h2>'+
      '<p>'+esc(intro+counter)+' Sono segnali descrittivi, non una diagnosi di recessione.</p></div>'+
      '<span class="sem-date">Serie per periodo originale · '+esc(today)+'</span></header>'+
      '<div class="sem-table" role="table" aria-label="Semaforo economico USA">'+
      '<div class="sem-columns" role="row"><span role="columnheader">Area</span><span role="columnheader">Ultima evidenza disponibile</span><span role="columnheader">Segnale</span></div>'+
      rows.map(r=>'<div class="sem-row" role="row"><div class="sem-area" role="cell"><strong>'+esc(r.name)+'</strong><small>'+esc(r.why)+'</small></div>'+
        '<div class="sem-evidence" role="cell">'+r.items.map(itemLine).join('')+'</div>'+
        '<div class="sem-signal" role="cell"><span class="sem-pill '+r.signal.tone+'"><i aria-hidden="true"></i>'+esc(r.signal.label)+'</span>'+
        (r.items.some(x=>x&&x.stale)?'<small>Presenza di dati datati</small>':'')+'</div></div>').join('')+'</div>'+
      '<div class="sem-policy"><div><span>POLITICA MONETARIA · LETTURA SEPARATA</span>'+
      '<p>La Fed e le aspettative sui tassi possono amplificare o mitigare i rischi ciclici, ma non sono un indicatore diretto di recessione.</p></div>'+
      '<a href="#rates">Verifica Fed, Treasury e OIS ↗</a></div>'+
      '<p class="sem-foot">Metodo: verde = tutti i sottoindicatori disponibili migliorano rispetto alla rilevazione precedente; rosso = tutti peggiorano; giallo = quadro misto o sostanzialmente stabile. Soglie anti-rumore descrittive: 0,15% sulle variazioni relative, 0,05 punti CFNAI e 1 punto SLOOS. Dati troppo vecchi o incompleti restano non classificabili. '+(dated?'Sono presenti osservazioni datate: non interpretare il semaforo come fotografia intraday. ':'')+'I periodi mostrati NON equivalgono alle date di pubblicazione. La fonte è il feed storico MACRO_SERIES (revisionabile); nessun modello NBER o probabilità di recessione è implicato.</p>'+
      '</section>';
  }
  root.FXQuantRecessionLight={render,model};
  if(typeof module!=='undefined'&&module.exports)module.exports={render,model};
})(typeof window!=='undefined'?window:globalThis);
