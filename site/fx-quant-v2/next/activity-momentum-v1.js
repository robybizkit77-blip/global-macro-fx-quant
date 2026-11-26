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
 return {status:x.as_of===today?'dated_today':'historical',day:x.as_of,rows,market:market||null,today,route,focusedPair:Boolean(pair)};
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
 return lines.join(' ');
}
function narrative(rows,esc,market,today,fmt){
 if(!market)return rows.map(r=>'<p><strong>'+esc(r.currency+' · '+r.label)+'</strong> — '+esc(reading(r))+' <small>('+esc(r.reference_period)+')</small></p>').join('');
 return [...new Set(rows.map(r=>r.currency))].map(c=>rows.filter(r=>r.currency===c).map(r=>'<p><strong>'+esc(r.currency+' · '+r.label)+'</strong> — '+esc(reading(r))+' <small>('+esc(r.reference_period)+')</small></p>').join('')+'<p><strong>'+esc(c)+' · politica monetaria e mercato</strong> — '+esc(marketReading(c,market,today,fmt))+'</p>').join('');
}
function render(x,esc,fmt){
 if(!x)return '';
 const number=(v,unit)=>Number.isFinite(v)?esc((v>0?'+':'')+fmt(v,2)+unit):'—';
 const tone=v=>!Number.isFinite(v)||v===0?'neutral':v>0?'good':'danger';
 const colored=(v,u)=>'<span class="badge '+tone(v)+'">'+number(v,u)+'</span>';
 const turn={DOWN_TO_UP:'Da calo a recupero del momentum',UP_TO_DOWN:'Da recupero a calo del momentum',NONE:'Nessuna inversione'};
 const table='<div style="overflow-x:auto"><table><thead><tr><th>Valuta / indicatore</th><th>Periodo</th><th>Livello</th><th>Momentum</th><th>Velocità</th><th>Accelerazione</th><th>Svolta</th></tr></thead><tbody>'+x.rows.map(r=>'<tr><td>'+esc(r.currency+' · '+r.label)+(r.nominal_not_real?' (nominale)':'')+'</td><td>'+esc(r.reference_period)+'</td><td>'+number(r.level,'')+' '+esc(r.unit||'')+'</td><td>'+colored(r.momentum_pct,'%')+'</td><td>'+colored(r.velocity_pp,' pp')+'</td><td>'+colored(r.acceleration_pp,' pp')+'</td><td>'+esc(turn[r.turning_point]||'Non valutabile')+'</td></tr>').join('')+'</tbody></table></div>';
 return '<details class="panel" data-activity-momentum-v1'+(x.route!=='overview'&&(x.route!=='pairs'||x.focusedPair)?' open':'')+'> <summary><strong>Momentum dell’attività economica</strong> · ricerca</summary><p>'+(x.status==='unavailable'?'Diagnostica non ancora pubblicata o non validabile.':(x.status==='historical'?'Elaborazione precedente: ':'Elaborazione del giorno: ')+esc(x.day)+'. Il periodo di ogni indicatore resta distinto dalla data di elaborazione.')+'</p>'+(x.status==='unavailable'?'':narrative(x.rows,esc,x.market,x.today,fmt)+'<details><summary>Dettaglio quantitativo</summary>'+table+'</details>'+'<p>Mensili: ultimi tre mesi rispetto ai tre precedenti. Trimestrali: trimestre su trimestre. Velocità = variazione del momentum; accelerazione = variazione della velocità. Svolta del momentum, non del livello economico. Serie riviste, non point-in-time; nessun ranking o segnale Forex. La spesa AUD nominale e il retail NZD trimestrale non sono confrontabili direttamente con le altre serie reali mensili.</p>')+'</details>';
}
const api={read,render,reading,marketReading};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FXQuantActivityMomentum=api;
})(typeof window==='undefined'?globalThis:window);
