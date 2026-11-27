/* Shared research-only diagnostic from the canonical observed Macro V3 feed. */
(function(root){
'use strict';
const G8=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const routes=['overview','macro','currencies','pairs','banks','rates'];
function read(feed,today,route,ccy,pair,market){
 if(!routes.includes(route))return null;
 const x=feed?.activity_momentum_research;
 const wanted=['macro','currencies','banks','rates'].includes(route)?[ccy]:route==='pairs'&&/^[A-Z]{6}$/.test(pair||'')?[pair.slice(0,3),pair.slice(3)]:G8;
 if(feed?.activity_momentum_status!=='RESEARCH_ONLY'||x?.schema!=='GMFQ_G8_CURRENT_ACTIVITY_MOMENTUM_RESEARCH_V1'||x?.safe_to_publish_D!==false||x?.safe_to_update_pairs!==false||x?.no_cross_country_momentum_aggregation!==true||x?.as_of!==feed.generated_europe_rome_day||!/^\d{4}-\d{2}-\d{2}$/.test(x?.as_of||'')||x.as_of>today||!G8.every(c=>Array.isArray(x.countries?.[c])))return {status:'unavailable',rows:[]};
 const rows=wanted.filter(c=>G8.includes(c)).flatMap(c=>x.countries[c].map(r=>({...r,currency:c})));
 return {status:x.as_of===today?'dated_today':'historical',day:x.as_of,rows,market:market||null,today,route,focusedPair:Boolean(pair),dynamics:readDynamics(feed,today,wanted),sectors:readSectors(feed,today,wanted),wanted};
}
function readSectors(feed,today,wanted){
 const x=feed?.sector_financial_dynamics;
 if(feed?.sector_financial_status!=='RESEARCH_ONLY'||x?.schema!=='GMFQ_G8_SECTOR_FINANCIAL_DYNAMICS_RESEARCH_V1'||x.safe_to_publish_D!==false||x.safe_to_update_pairs!==false||x.historical_PIT_certified!==false||x.no_cross_country_aggregation!==true||x.as_of!==feed.generated_europe_rome_day||!recent(x.as_of,today,7)||!G8.every(c=>Array.isArray(x.countries?.[c])))return null;
 return wanted.filter(c=>G8.includes(c)).flatMap(c=>x.countries[c].map(r=>({...r,currency:c})));
}
function sectorTable(rows,wanted,esc,fmt){
 if(!rows)return '<p>Settori e condizioni finanziarie: diagnostica non disponibile.</p>';
 const labels={manufacturing:'Manifattura · attività reale / indagini',services:'Servizi · attività reale / indagini',housing:'Immobiliare',credit:'Credito',liquidity:'Liquidità',survey:'Indagini generali'};
 const kinds={STOCK:'Stock nominale',QUANTITY:'Quantità',RATE:'Tasso',BALANCE:'Saldo indagine',INDEX:'Indice',WITHHELD:'Fonte sospesa'};
 const horizons={HALF_YEAR:'semestre',STOCK_3M_ENDPOINT:'3 mesi, estremi',STOCK_QOQ_ENDPOINT:'trimestre',EXACT_CALENDAR_DAY:'1 giorno di calendario',EXACT_7_CALENDAR_DAYS:'7 giorni di calendario',ROLLING_3M_OVER_PREVIOUS_3M:'3m/3m',QOQ:'trimestre'};
 const n=(v,u='')=>Number.isFinite(v)?esc(fmt(v,2)+u):'—';
 return Object.entries(labels).map(([p,label])=>{
  const a=rows.filter(r=>r.pillar===p),missing=(wanted||[]).filter(c=>!a.some(r=>r.currency===c&&r.measurement!=='WITHHELD'));
  return '<details><summary><strong>'+esc(label)+'</strong> · '+a.filter(r=>r.measurement!=='WITHHELD').length+'/'+a.length+' serie</summary>'+(missing.length?'<p>Copertura non disponibile qui: '+esc(missing.join(', '))+'.</p>':'')+(a.length?'<div style="overflow-x:auto"><table><thead><tr><th>Indicatore</th><th>Periodo</th><th>Misura</th><th>Livello</th><th>Momentum</th><th>Velocità</th><th>Accelerazione</th></tr></thead><tbody>'+a.map(r=>'<tr><td>'+esc(r.currency+' · '+r.label)+'</td><td>'+esc(r.reference_period||'—')+'</td><td>'+esc(kinds[r.measurement]||'—')+' · '+esc(horizons[r.horizon]||r.frequency)+'</td><td>'+n(r.level,' '+(r.unit||''))+'</td><td>'+n(r.momentum_pct,'%')+(Number.isFinite(r.change_1m_pct)?'<small> · 1M '+n(r.change_1m_pct,'%')+'</small>':'')+'</td><td>'+n(r.velocity_pp)+'</td><td>'+n(r.acceleration_pp)+'</td></tr>').join('')+'</tbody></table></div>':'')+'</details>';
 }).join('')+'<p>Stock: variazioni del saldo, non flussi né crescita reale; possibili riclassificazioni. Indici e saldi: differenze in punti; tassi in punti percentuali. Le frequenze e definizioni non sono uniformi. Nessun segnale FX.</p>';
}
function readDynamics(feed,today,wanted){
 const x=feed?.labour_inflation_dynamics;
 if(feed?.labour_inflation_status!=='RESEARCH_ONLY'||x?.schema!=='GMFQ_G8_LABOUR_INFLATION_DYNAMICS_RESEARCH_V1'||x.safe_to_publish_D!==false||x.safe_to_update_pairs!==false||x.historical_PIT_certified!==false||x.no_cross_country_aggregation!==true||x.as_of!==feed.generated_europe_rome_day||!recent(x.as_of,today,7)||!G8.every(c=>Array.isArray(x.countries?.[c])))return null;
 return wanted.filter(c=>G8.includes(c)).flatMap(c=>x.countries[c].map(r=>({...r,currency:c})));
}
function dynamicsReading(r){
 if(r.measurement==='WITHHELD')return 'Fonte da verificare; nessuna inferenza.';
 if(r.measurement==='COUNT_MOMENTUM')return reading(r);
 if(!Number.isFinite(r.velocity_pp))return 'Variazione non calcolabile su periodi consecutivi.';
 const v=r.velocity_pp,a=r.acceleration_pp;
 let s=r.pillar==='inflation'?(v>0?'Inflazione in aumento':v<0?'Inflazione in diminuzione':'Inflazione invariata'):(v>0?'Indicatore in aumento':v<0?'Indicatore in diminuzione':'Indicatore invariato');
 if(Number.isFinite(a)&&v!==0)s+=a===0?', ritmo invariato':Math.sign(a)===Math.sign(v)?', movimento più rapido':', movimento meno rapido';
 return s+'.'+(r.pillar==='inflation'?' Non implica una variazione del livello dei prezzi nella stessa direzione.':'');
}
function dynamicsTable(rows,esc,fmt){
 if(!rows)return '<p>Lavoro e inflazione: nuova diagnostica non disponibile o da verificare.</p>';
 const n=(v,u)=>Number.isFinite(v)?esc(fmt(v,2)+' '+u):'—';
 return ['labour','inflation'].map(p=>'<details><summary><strong>'+(p==='labour'?'Mercato del lavoro':'Inflazione e prezzi')+'</strong> · '+rows.filter(r=>r.pillar===p&&r.measurement!=='WITHHELD').length+'/'+rows.filter(r=>r.pillar===p).length+' serie</summary><div style="overflow-x:auto"><table><thead><tr><th>Indicatore</th><th>Periodo</th><th>Livello</th><th>Momentum quantità</th><th>Velocità (pp)</th><th>Accelerazione (pp)</th><th>Lettura</th></tr></thead><tbody>'+rows.filter(r=>r.pillar===p).map(r=>'<tr><td>'+esc(r.currency+' · '+r.label)+'</td><td>'+esc(r.reference_period||'—')+' '+esc(r.frequency==='Q'?'(trimestrale)':'(mensile)')+'</td><td>'+n(r.level,r.unit||'')+'</td><td>'+n(r.momentum_pct,'%')+'</td><td>'+n(r.velocity_pp,'')+'</td><td>'+n(r.acceleration_pp,'')+'</td><td>'+esc(dynamicsReading(r))+'</td></tr>').join('')+'</tbody></table></div></details>').join('')+'<p>Per tassi e inflazione YoY, velocità = variazione in punti percentuali del tasso; accelerazione = differenza tra due variazioni consecutive. Per quantità, momentum 3m/3m o QoQ. I periodi e le definizioni non sono necessariamente omogenei. Nessun ranking o segnale FX.</p>';
}
function reading(r){
 const m=r.momentum_pct,v=r.velocity_pp,a=r.acceleration_pp;
 if(!Number.isFinite(m))return 'Momentum non calcolabile: storia insufficiente.';
 const level=m>0?'in aumento':m<0?'in calo':'stabile';
 const object=r.nominal_not_real?'La spesa nominale':'L’indicatore';
 const basis=r.horizon==='QOQ'?'rispetto al trimestre precedente':'negli ultimi tre mesi rispetto ai tre precedenti';
 let line=object+' è '+level+' '+basis+'.';
 if(Number.isFinite(v)){
  if(v>0)line+=m<0?' La contrazione si attenua.':' Il momentum migliora.';
  else if(v<0)line+=m<0?' La contrazione si approfondisce.':' Il momentum perde velocità.';
  else line+=' La velocità del momentum è invariata.';
 }
 if(Number.isFinite(v)&&Number.isFinite(a)){
  if(v<0&&a<0)line+=' La perdita di slancio si intensifica.';
  else if(v<0&&a>0)line+=' La perdita di slancio si attenua.';
  else if(v>0&&a>0)line+=' Il recupero accelera.';
  else if(v>0&&a<0)line+=' Il recupero perde intensità.';
 }
 if(r.turning_point==='DOWN_TO_UP')line+=' Svolta positiva della velocità del momentum, non necessariamente del livello.';
 if(r.turning_point==='UP_TO_DOWN')line+=' Svolta negativa della velocità del momentum, non necessariamente del livello.';
 if(r.nominal_not_real)line+=' Non misura la crescita dei volumi reali.';
 return line;
}
function recent(day,today,max){
 return typeof day==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(day)&&day<=today&&Number.isFinite(Date.parse(day))&&(Date.parse(today)-Date.parse(day))/864e5<=max;
}
function positionReading(c,market,today,fmt){
 const p=market?.cot?.[c],dates=p?.dates;
 if(!Array.isArray(dates)||dates.length<2)return 'COT non disponibile.';
 const i=dates.length-1,d=dates[i],prev=dates[i-1],n=Number.isFinite;
 if(!recent(d,today,14)||!recent(prev,d,7)||Date.parse(d)-Date.parse(prev)!==7*864e5||!['net','long','short','netoi','percentile'].every(k=>Array.isArray(p[k])&&p[k].length===dates.length&&n(p[k][i])&&n(p[k][i-1]))||p.long[i]-p.short[i]!==p.net[i]||p.long[i-1]-p.short[i-1]!==p.net[i-1])return 'COT recente e comparabile non validato.';
 const delta=p.net[i]-p.net[i-1],dl=p.long[i]-p.long[i-1],ds=p.short[i]-p.short[i-1],sign=v=>(v>0?'+':'')+fmt(v,0);
 return 'COT '+d+': netto '+sign(p.net[i])+' contratti; variazione settimanale '+sign(delta)+' (long '+sign(dl)+', short '+sign(ds)+'); Net/OI '+fmt(p.netoi[i],1)+'%, percentile '+fmt(p.percentile[i],0)+'. '+(p.percentile[i]>=80||p.percentile[i]<=20?'Posizionamento estremo: non implica inversione. ':'')+'Il COT non identifica tutti gli operatori e non è intraday.';
}
function priceReading(base,quote,market,today,fmt){
 const p=market?.prices,rs=p?.rows;
 if(!Array.isArray(rs)||rs.length<6||p.base!=='EUR'||!recent(p.last_as_of,today,7))return 'Prezzi recenti non validabili.';
 const last=rs.at(-1),start=rs.at(-6),n=v=>Number.isFinite(v)&&v>0;
 if(last.Date!==p.last_as_of||!recent(start.Date,last.Date,14)||start.Date>=last.Date||![last[base],last[quote],start[base],start[quote]].every(n))return 'Confronto prezzi non validabile.';
 const move=100*((last[quote]/last[base])/(start[quote]/start[base])-1);
 return 'Fixing BCE '+base+'/'+quote+': '+(move>0?'+':'')+fmt(move,2)+'% in cinque osservazioni ('+start.Date+'–'+last.Date+'); variazione del cambio, non flusso osservato.';
}
function marketReading(c,market,today,fmt){
 const cb=market?.cb?.[c],o=market?.ois?.currencies?.[c],r=market?.rates?.[c];
 const n=Number.isFinite, bp=v=>(v>0?'+':'')+fmt(v,1)+' pb';
 const lines=[];
 if(n(cb?.rate)&&recent(cb.last_date,today,120)&&(!cb.next_meeting||cb.next_meeting>today)){
  lines.push('Banca centrale: '+cb.bank+' '+fmt(cb.rate,2)+'% (decisione '+cb.last_date+'); '+String(cb.stance||'orientamento non disponibile')+'.');
 }else lines.push('Decisione monetaria da verificare.');
 const h=o?.horizons?.['6m'];
 if(o?.operational_status==='GREEN_OFFICIAL'&&o?.official_status==='ACTIVE'&&o?.quality==='OFFICIAL_CERTIFIED'&&recent(o.as_of,today,7)&&cb?.last_date<=o.as_of&&n(cb.rate)&&cb.rate===o.policy_rate&&(!cb.next_meeting||cb.next_meeting>today)&&n(h?.rate)&&n(h?.policy_delta_bp)){
  lines.push('OIS 6M: '+fmt(h.rate,2)+'%, '+bp(h.policy_delta_bp)+' rispetto al tasso ufficiale ('+o.as_of+').'+(o.change_1w_available===true&&n(h.change_1w_bp)?' Variazione 1W: '+bp(h.change_1w_bp)+'.':' Variazione settimanale non verificata.'));
 }else if(o?.operational_status==='GREEN_ESTIMATED'&&recent(o.as_of,today,7)&&n(h?.rate)){
  lines.push('Futures 6M indicativi: '+fmt(h.rate,2)+'% ('+o.as_of+'); non equivalgono a un percorso monetario OIS verificato.');
 }else if(o?.operational_status==='WITHHELD'&&c==='NZD'&&recent(o.market_direction_proxy?.as_of,today,7)){
  lines.push('OIS non disponibile; proxy bank-bill NZD separato, non convertibile direttamente in OCR.');
 }else lines.push('Pricing monetario 6M non validabile: nessuna inferenza sul percorso dei tassi.');
 const w2=r?.weekly2_validation,w10=r?.weekly10_validation;
 if(r?.quality==='FULL_CURRENT_OFFICIAL'&&recent(r.date,today,c==='AUD'?14:7)&&w2?.end_date===r.date&&w10?.end_date===r.date&&w2.start_date===w10.start_date&&recent(w2.start_date,r.date,10)&&n(w2.change_bp)&&n(w10.change_bp)){
  lines.push('Governativi 2Y e 10Y: '+bp(w2.change_bp)+' / '+bp(w10.change_bp)+' nel periodo '+w2.start_date+'–'+r.date+'. Il 10Y incorpora anche crescita, inflazione e premio a termine.');
 }else lines.push('Confronto governativo 2Y/10Y recente e omogeneo non validato qui; consultare Tassi per le fonti di ricerca separate.');
 lines.push(positionReading(c,market,today,fmt));
 return lines.join(' ');
}
function narrative(rows,esc,market,today,fmt,route,focusedPair){
 if(!market)return rows.map(r=>'<p><strong>'+esc(r.currency+' · '+r.label)+'</strong> — '+esc(reading(r))+' <small>('+esc(r.reference_period)+')</small></p>').join('');
 const currencies=[...new Set(rows.map(r=>r.currency))];
 return currencies.map(c=>rows.filter(r=>r.currency===c).map(r=>'<p><strong>'+esc(r.currency+' · '+r.label)+'</strong> — '+esc(reading(r))+' <small>('+esc(r.reference_period)+')</small></p>').join('')+'<p><strong>'+esc(c)+' · politica monetaria e mercato</strong> — '+esc(marketReading(c,market,today,fmt))+'</p>').join('')+(route==='pairs'&&focusedPair&&currencies.length===2?'<p><strong>Prezzo relativo</strong> — '+esc(priceReading(currencies[0],currencies[1],market,today,fmt))+'</p>':'');
}
function render(x,esc,fmt){
 if(!x)return '';
 const number=(v,unit)=>Number.isFinite(v)?esc((v>0?'+':'')+fmt(v,2)+unit):'—';
 const tone=v=>!Number.isFinite(v)||v===0?'neutral':v>0?'good':'danger';
 const colored=(v,u)=>'<span class="badge '+tone(v)+'">'+number(v,u)+'</span>';
 const turn={DOWN_TO_UP:'Da calo a recupero del momentum',UP_TO_DOWN:'Da recupero a calo del momentum',NONE:'Nessuna inversione'};
 const table='<div style="overflow-x:auto"><table><thead><tr><th>Valuta / indicatore</th><th>Periodo</th><th>Livello</th><th>Momentum</th><th>Velocità</th><th>Accelerazione</th><th>Svolta</th></tr></thead><tbody>'+x.rows.map(r=>'<tr><td>'+esc(r.currency+' · '+r.label)+(r.nominal_not_real?' (nominale)':'')+'</td><td>'+esc(r.reference_period)+'</td><td>'+number(r.level,'')+' '+esc(r.unit||'')+'</td><td>'+colored(r.momentum_pct,'%')+'</td><td>'+colored(r.velocity_pp,' pp')+'</td><td>'+colored(r.acceleration_pp,' pp')+'</td><td>'+esc(turn[r.turning_point]||'Non valutabile')+'</td></tr>').join('')+'</tbody></table></div>';
 return '<details class="panel" data-activity-momentum-v1'+(x.route!=='overview'&&(x.route!=='pairs'||x.focusedPair)?' open':'')+'> <summary><strong>Momentum dell’attività economica</strong> · ricerca</summary><p>'+(x.status==='unavailable'?'Diagnostica non ancora pubblicata o non validabile.':(x.status==='historical'?'Elaborazione precedente: ':'Elaborazione del giorno: ')+esc(x.day)+'. Il periodo di ogni indicatore resta distinto dalla data di elaborazione.')+'</p>'+(x.status==='unavailable'?'':narrative(x.rows,esc,x.market,x.today,fmt,x.route,x.focusedPair)+dynamicsTable(x.dynamics,esc,fmt)+sectorTable(x.sectors,x.wanted,esc,fmt)+'<details><summary>Dettaglio quantitativo</summary>'+table+'</details>'+'<p>Mensili: ultimi tre mesi rispetto ai tre precedenti. Trimestrali: trimestre su trimestre. Velocità = variazione del momentum; accelerazione = variazione della velocità. Svolta del momentum, non del livello economico. Serie riviste, non point-in-time; nessun ranking o segnale Forex. La spesa AUD nominale e il retail NZD trimestrale non sono confrontabili direttamente con le altre serie reali mensili.</p>')+'</details>';
}
const api={read,render,reading,marketReading,positionReading,priceReading,readDynamics,dynamicsReading,readSectors,sectorTable};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FXQuantActivityMomentum=api;
})(typeof window==='undefined'?globalThis:window);
