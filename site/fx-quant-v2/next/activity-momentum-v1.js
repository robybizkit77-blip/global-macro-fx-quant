/* Shared research-only diagnostic from the canonical observed Macro V3 feed. */
(function(root){
'use strict';
const G8=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const routes=['overview','macro','currencies','pairs'];
function read(feed,today,route,ccy,pair){
 if(!routes.includes(route))return null;
 const x=feed?.activity_momentum_research;
 const wanted=route==='macro'||route==='currencies'?[ccy]:route==='pairs'&&/^[A-Z]{6}$/.test(pair||'')?[pair.slice(0,3),pair.slice(3)]:G8;
 if(feed?.activity_momentum_status!=='RESEARCH_ONLY'||x?.schema!=='GMFQ_G8_CURRENT_ACTIVITY_MOMENTUM_RESEARCH_V1'||x?.safe_to_publish_D!==false||x?.safe_to_update_pairs!==false||x?.no_cross_country_momentum_aggregation!==true||x?.as_of!==feed.generated_europe_rome_day||!/^\d{4}-\d{2}-\d{2}$/.test(x?.as_of||'')||x.as_of>today||!G8.every(c=>Array.isArray(x.countries?.[c])))return {status:'unavailable',rows:[]};
 const rows=wanted.filter(c=>G8.includes(c)).flatMap(c=>x.countries[c].map(r=>({...r,currency:c})));
 return {status:x.as_of===today?'dated_today':'historical',day:x.as_of,rows};
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
function narrative(rows,esc){
 return rows.map(r=>'<p><strong>'+esc(r.currency+' · '+r.label)+'</strong> — '+esc(reading(r))+' <small>('+esc(r.reference_period)+')</small></p>').join('');
}
function render(x,esc,fmt){
 if(!x)return '';
 const number=(v,unit)=>Number.isFinite(v)?esc((v>0?'+':'')+fmt(v,2)+unit):'—';
 const tone=v=>!Number.isFinite(v)||v===0?'neutral':v>0?'good':'danger';
 const colored=(v,u)=>'<span class="badge '+tone(v)+'">'+number(v,u)+'</span>';
 const turn={DOWN_TO_UP:'Da calo a recupero del momentum',UP_TO_DOWN:'Da recupero a calo del momentum',NONE:'Nessuna inversione'};
 const table='<div style="overflow-x:auto"><table><thead><tr><th>Valuta / indicatore</th><th>Periodo</th><th>Livello</th><th>Momentum</th><th>Velocità</th><th>Accelerazione</th><th>Svolta</th></tr></thead><tbody>'+x.rows.map(r=>'<tr><td>'+esc(r.currency+' · '+r.label)+(r.nominal_not_real?' (nominale)':'')+'</td><td>'+esc(r.reference_period)+'</td><td>'+number(r.level,'')+' '+esc(r.unit||'')+'</td><td>'+colored(r.momentum_pct,'%')+'</td><td>'+colored(r.velocity_pp,' pp')+'</td><td>'+colored(r.acceleration_pp,' pp')+'</td><td>'+esc(turn[r.turning_point]||'Non valutabile')+'</td></tr>').join('')+'</tbody></table></div>';
 return '<details class="panel" data-activity-momentum-v1 open><summary><strong>Momentum dell’attività economica</strong> · ricerca</summary><p>'+(x.status==='unavailable'?'Diagnostica non ancora pubblicata o non validabile.':(x.status==='historical'?'Elaborazione precedente: ':'Elaborazione del giorno: ')+esc(x.day)+'. Il periodo di ogni indicatore resta distinto dalla data di elaborazione.')+'</p>'+(x.status==='unavailable'?'':narrative(x.rows,esc)+'<details><summary>Dettaglio quantitativo</summary>'+table+'</details>'+'<p>Mensili: ultimi tre mesi rispetto ai tre precedenti. Trimestrali: trimestre su trimestre. Velocità = variazione del momentum; accelerazione = variazione della velocità. Svolta del momentum, non del livello economico. Serie riviste, non point-in-time; nessun ranking o segnale Forex. La spesa AUD nominale e il retail NZD trimestrale non sono confrontabili direttamente con le altre serie reali mensili.</p>')+'</details>';
}
const api={read,render,reading};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FXQuantActivityMomentum=api;
})(typeof window==='undefined'?globalThis:window);
