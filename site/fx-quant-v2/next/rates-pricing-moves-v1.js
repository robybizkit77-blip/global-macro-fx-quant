'use strict';
/* Read-only Rates: compare each certified OIS/futures tenor with its actual
 * prior observation. Research secondary-contract moves never become OIS,
 * policy signals or inputs into the 28-pair engine. Unknown stays missing. */
(function(root){
 const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'],T=['3m','6m','12m'];
 const num=x=>typeof x==='number'&&Number.isFinite(x);
 const day=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x);
 const age=(today,asof)=>day(today)&&day(asof)?
  Math.round((Date.parse(today+'T12:00:00Z')-Date.parse(asof+'T12:00:00Z'))/864e5):null;
 const same=(a,b,tol=.00001)=>num(a)&&num(b)&&Math.abs(a-b)<tol;
 const sign=(x,n=1)=>num(x)?(x>0?'+':x<0?'−':'')+Math.abs(x).toFixed(n).replace('.',',')+' pb':'—';
 const cap=x=>String(x??'').replace(/[&<>"']/g,y=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[y]));
 const labelDate=s=>day(s)?s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4):'n.d.';
 const labelKind=k=>k==='OIS'?'OIS ufficiali':k==='FUTURES'?'Futures ufficiali':
  k==='PROXY FUTURES'?'Proxy futures NZD':k==='FUTURES SECONDARI'?'Futures secondari · ricerca':'Non validato';
 function verifiedSecondary(c,t,rate,date,research,window){
  if(!['USD','EUR','CHF'].includes(c)||research?.schema!=='GMFQ_FXV2_SAME_CONTRACT_FUTURES_MOVES_V1'||
   research?.snapshot_research_only!==true||research?.eligible_for_fx_engine!==false||
   research?.eligible_for_policy_repricing_signals!==false||research?.official_ois_created!==false||
   research?.eligible_for_backtests_as_official_ois!==false)return null;
  const x=research.currencies?.[c]?.[t],h=x?.[window==='1w'?'one_week':'one_day'];
  if(x?.status!=='VERIFIED_SAME_CONTRACT_PRICE_CHANGE'||
   x?.source_type!=='SECONDARY_LISTED_FUTURES_NOT_OIS'||
   x?.official_ois!==false||!h||h.same_contract!==true||h.same_expiration!==true||
   !day(h.from_date)||!day(h.to_date)||h.from_date>=h.to_date||
   h.to_date!==date||x.as_of!==date||!same(x.rate_pct,rate)||
   !same(h.current_rate_pct,rate)||!num(h.reference_rate_pct))return null;
  const bp=(rate-h.reference_rate_pct)*100, reported=window==='1w'?x.change_1w_bp:x.change_1d_bp;
  if(!num(reported)||Math.abs(bp-reported)>.011||!num(h.change_bp)||
   Math.abs(h.change_bp-reported)>.011)return null;
  if(window==='1w'&&age(h.to_date,h.from_date)!==7)return null;
  if(window==='1d'&&age(h.to_date,h.from_date)>4)return null;
  return {bp,from:h.from_date,until:h.to_date,levelPrev:h.reference_rate_pct,
   method:'CONTRATTO IDENTICO · RICERCA SECONDARIA'};
 }
 function readCurrency(c,snapshot,operational,research,nzd,today){
  const row=snapshot?.currencies?.[c],kind=row?.kind,valid=['OIS','FUTURES','PROXY FUTURES','FUTURES SECONDARI'].includes(kind);
  const op=operational?.currencies?.[c],nzdRow=nzd;
  const official=kind==='OIS'||kind==='FUTURES';
  const officialOK=official&&op?.official_status==='ACTIVE'&&
   op?.operational_status==='GREEN_OFFICIAL'&&op?.backtest_eligible_as_official===true &&
   op?.source===row?.source;
  const nzdOK=kind==='PROXY FUTURES'&&c==='NZD'&&
   nzdRow?.schema==='GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1'&&
   nzdRow?.as_of===row?.as_of&&nzdRow?.currency==='NZD';
  const sourceType=valid?labelKind(kind):'NON DISPONIBILE';
  const rows=T.map(t=>{
   const p=row?.horizons?.[t],d=p?.as_of,stale=age(today,d);
   const ok=valid&&num(p?.rate)&&day(d)&&stale!==null&&stale>=0&&stale<=7;
   let current=ok?p.rate:null,one=null,week=null,contract=p?.contract||null;
   const output={tenor:t,asof:ok?d:null,rate:current,contract,one:null,week:null,
    source:row?.source||null,kind,status:ok?'DATE_SOURCE_OK':'NON DISPONIBILE'};
   if(!ok)return output;
   if(officialOK){
    const o=op.horizons?.[t];
    if(o&&op.as_of===d&&same(o.rate,p.rate)){
     // Deltas are explicitly validated by official operational feed; they
     // are not obtained by comparing unlike 3M and 12M contracts.
     if(num(o.change_1d_bp)&&same(o.change_1d_bp,p.change_1d_bp,.011))
      one={bp:o.change_1d_bp,until:d,from:null,
       levelPrev:p.rate-o.change_1d_bp/100,method:'VARIAZIONE FONTE UFFICIALE'};
     if(num(o.change_1w_bp)&&same(o.change_1w_bp,p.change_1w_bp,.011))
      week={bp:o.change_1w_bp,until:d,from:null,
       levelPrev:p.rate-o.change_1w_bp/100,method:'VARIAZIONE FONTE UFFICIALE'};
    }
   }else if(nzdOK){
    const x=nzdRow.horizons?.[t];
    if(x&&same(x.implied_bank_bill_rate,p.rate)&&
     x.expiry_label===contract){
     if(num(x.change_1d_bp)&&same(x.change_1d_bp,p.change_1d_bp,.011))
      one={bp:x.change_1d_bp,until:d,from:null,
       levelPrev:p.rate-x.change_1d_bp/100,method:'PROXY BANK-BILL · NON OIS'};
     if(num(x.change_1w_bp)&&same(x.change_1w_bp,p.change_1w_bp,.011))
      week={bp:x.change_1w_bp,until:d,from:x.weekly_reference_trade_date||null,
       levelPrev:p.rate-x.change_1w_bp/100,method:'PROXY BANK-BILL · NON OIS'};
    }
   }else if(kind==='FUTURES SECONDARI'){
    if(contract&&contract===research?.currencies?.[c]?.[t]?.contract){
     one=verifiedSecondary(c,t,p.rate,d,research,'1d');
     week=verifiedSecondary(c,t,p.rate,d,research,'1w');
    }
   }
   output.one=one;output.week=week;
   output.status=one||week?'CONFRONTO DISPONIBILE':'CONFRONTO NON VERIFICATO';
   return output;
  });
  return {ccy:c,kind,sourceType,source:row?.source||'',quality:row?.quality||'NON VALIDATO',
   rows,oneAvailable:rows.filter(r=>r.one).length,weekAvailable:rows.filter(r=>r.week).length,
   officialOis:kind==='OIS'&&officialOK};
 }
 function model(inputs){
  const {snapshot,operational,research,nzd,today}=inputs;
  return Object.fromEntries(FX.map(c=>[c,readCurrency(c,snapshot,operational,research,nzd,today)]));
 }
 function render(inputs){
  const {currency,window,plot,esc,fmt,sign:appSign,date,snapshot,operational,research,nzd,today}=inputs;
  const data=model({snapshot,operational,research,nzd,today}),m=data[currency]||data.USD;
  const mode=window==='1w'?'1w':'1d',prop=mode==='1w'?'week':'one';
  const observations=m.rows.map(r=>({...r,move:r[prop]}));
  const known=observations.filter(r=>r.move),ref6=m.rows.find(r=>r.tenor==='6m');
  const this6=ref6?.[prop],reason=m.sourceType==='OIS ufficiali'?'OIS':
   m.kind==='FUTURES SECONDARI'?'futures secondari (ricerca)':m.sourceType.toLowerCase();
  const sixText=this6?this6.bp>0.05?
   'Il 6M è salito di '+sign(this6.bp)+' rispetto al riferimento precedente.':
   this6.bp<-.05?'Il 6M è sceso di '+sign(Math.abs(this6.bp))+' rispetto al riferimento precedente.':
   'Il 6M è rimasto pressoché invariato rispetto al riferimento precedente.':
   'Per il 6M manca un confronto certificabile su questa finestra.';
  const note=this6?'Si tratta di '+reason+'; un livello implicito più alto può essere compatibile con aspettative meno accomodanti, ma non identifica da solo la causa.':
   'Nessun movimento viene ricostruito da livelli di contratti diversi.';
  const time=m.rows.filter(r=>r[prop]&&r.asof).map(r=>r.asof);
  const sameDates=known.length===3&&new Set(time).size===1;
  const priorDates=known.map(r=>r.move.from).filter(Boolean);
  const consistentPrior=!priorDates.length||new Set(priorDates).size===1;
  const curveAllowed=sameDates&&consistentPrior&&known.every(r=>num(r.rate)&&num(r.move.levelPrev));
  const lines=curveAllowed?[
   {name:'Rilevazione '+labelDate(known[0].asof),color:'#8fe8ce',
    values:known.map(r=>({label:r.tenor.toUpperCase(),value:r.rate}))},
   {name:'Riferimento precedente (da Δ'+mode.toUpperCase()+')',color:'#f4c38b',
    values:known.map(r=>({label:r.tenor.toUpperCase(),value:r.move.levelPrev}))}
  ]:null;
  const innerCurve=lines?'<div class="ois-pricing-curve">'+plot({lines,unit:'%',precision:3,
   label:'Confronto dei tre tenori '+m.sourceType+', valori precedenti derivati da variazioni verificate',axisDates:false})+
   '<p class="rates-plot-note">Riferimento precedente <strong>calcolato</strong> da livello attuale e variazione verificata per ciascun tenore. '+esc(m.kind==='OIS'?
    'Questa è una curva OIS ufficiale in tre punti, non un percorso delle singole riunioni.':
    'Tre contratti futures, NON una curva OIS ufficiale né una previsione meeting-by-meeting.')+'</p></div>':
   '<div class="ois-pricing-no-curve">I 3M, 6M e 12M non hanno date di rilevazione omogenee o variazioni sufficienti: non li colleghiamo con una falsa curva unica.</div>';
  const vals=observations.filter(r=>r.move).map(r=>Math.abs(r.move.bp));
  const compVals=FX.map(c=>data[c].rows[1]?.[prop]?.bp).filter(num).map(Math.abs);
  const scale=Math.max(1,...vals,...compVals);
  function bar(bp){
   if(!num(bp))return '<div class="ois-bp-bar no-data" aria-hidden="true"><i></i></div>';
   const size=Math.max(0,Math.min(48,Math.abs(bp)/scale*48));
   const left=bp<0?50-size:50;
   const type=bp>0.05?'up':bp<-.05?'down':'flat';
   return '<div class="ois-bp-bar '+type+'" aria-hidden="true"><i></i><b style="left:'+left.toFixed(1)+'%;width:'+size.toFixed(1)+'%"></b></div>';
  }
  const cards=observations.map(r=>'<div class="ois-bp-row" data-pricing-tenor="'+r.tenor+'">'+
   '<div class="ois-bp-tenor"><b>'+r.tenor.toUpperCase()+'</b><small>'+
    (r.asof?'Rif. '+date(r.asof):'Dato assente')+'</small></div>'+
   bar(r.move?.bp)+'<div class="ois-bp-num '+(r.move?.bp>0?'up':r.move?.bp<0?'down':'')+'">'+
    esc(sign(r.move?.bp))+'</div></div>').join('');
  const global=FX.map(c=>{
   const a=data[c],r=a.rows[1],bp=r?.[prop]?.bp;
   return '<div class="ois-g8-row" data-pricing-ccy="'+c+'">'+
    '<div class="ois-g8-name"><b>'+c+'</b><small>'+esc(a.sourceType)+'</small></div>'+
    bar(bp)+'<strong class="'+(bp>0?'up':bp<0?'down':'')+'">'+esc(sign(bp))+'</strong>'+
    '<small class="ois-g8-date">'+(r?.asof?date(r.asof):'—')+'</small></div>';
  }).join('');
  const extra=known.map(r=>'<div><b>'+r.tenor.toUpperCase()+'</b> · '+
   esc(r.contract||m.sourceType)+' · '+esc(r.move.method)+' · '+date(r.asof)+
   (r.move.from?' (da '+date(r.move.from)+')':' (riferimento precedente certificato)')+
   ' · '+esc(fmt(r.rate,3))+'%</div>').join('');
  return '<section class="rates-pricing-moves" id="rates-pricing-moves" data-pricing-window="'+mode+
   '" data-pricing-kind="'+esc(m.kind||'NON VALIDATO')+'" aria-label="Variazione giornaliera e settimanale dei tassi impliciti">'+
   '<div class="rates-section-head"><div><span class="chapter-kicker">REPRICING · CONFRONTO CON LA SEDUTA PRECEDENTE</span>'+
   '<h2>Come si sono mossi <em>i tassi attesi?</em></h2></div>'+
   '<p>Confronto dei medesimi tenori nel tempo. OIS ufficiali, futures e proxy restano strumenti distinti.</p></div>'+
   '<div class="ois-moves-tools"><div class="ois-moves-source"><b>'+esc(currency)+' · '+esc(m.sourceType)+
   '</b><small>'+esc(m.quality)+'</small></div>'+
   '<div class="pill-controls">'+[['1d','Rispetto a ieri'],['1w','Rispetto a 1 settimana fa']].map(([k,l])=>
    '<button type="button" class="pill '+(mode===k?'active':'')+'" data-rs-pricing-window="'+k+
    '" aria-pressed="'+String(mode===k)+'">'+l+'</button>').join('')+'</div></div>'+
   '<div class="ois-moves-lead"><strong>'+esc(sixText)+'</strong><p>'+esc(note)+'</p></div>'+
   '<div class="ois-moves-detail-grid"><article class="ois-moves-detail">'+
   '<span class="micro-over">'+esc(currency)+' · '+esc(m.sourceType)+' · Δ'+mode.toUpperCase()+' IN PUNTI BASE</span>'+
   '<h3>Tre orizzonti. Una variazione osservata per ciascuno.</h3>'+
   '<div class="ois-bp-bars">'+cards+'</div>'+
   '<p class="rates-plot-note">La linea centrale è lo zero. Positivo = tasso implicito/forward in rialzo, negativo = in calo; <strong>non implica automaticamente forza della valuta</strong>.</p>'+
   '<details class="ois-moves-evidence"><summary>Contratti, data e fonte dei confronti</summary>'+
   '<div>'+ (extra||'<p>Non esistono confronti verificabili per questa valuta e finestra.</p>')+
   '<p>Fonte: '+esc(m.source||'n.d.')+' · '+esc(m.quality)+
   '. Gli strumenti non OIS non vengono promossi a OIS ufficiali.</p></div></details></article>'+
   '<article class="ois-moves-plot"><span class="micro-over">'+esc(curveAllowed?'DUE RILEVAZIONI COMPARABILI':'COMPARABILITÀ NON CERTIFICATA')+'</span>'+
   '<h3>'+esc(curveAllowed?'Livelli attuali contro riferimento precedente':'Nessuna curva artificiale')+'</h3>'+
   innerCurve+'</article></div>'+
   '<div class="ois-g8-moves"><div class="rates-section-head"><div><span class="chapter-kicker">G8 · CONFRONTO 6M</span>'+
   '<h3>Chi ha registrato il maggior movimento del 6M?</h3></div>'+
   '<p>Variazione sullo stesso strumento per ciascuna valuta; sottostanti diversi, non graduatoria della forza FX.</p></div>'+
   '<div class="ois-g8-rows">'+global+'</div></div>'+
   '<p class="ois-moves-footer">Le variazioni 1D/1W non sono probabilità di rialzo/taglio. Le rilevazioni secondarie riguardano <strong>lo stesso contratto quotato</strong> e restano ricerca informativa; non entrano nei segnali, nelle tesi automatiche o nei backtest OIS ufficiali.</p>'+
   '</section>';
 }
 const api={model,readCurrency,verifiedSecondary,render};
 root.FXQuantPricingMoves=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
