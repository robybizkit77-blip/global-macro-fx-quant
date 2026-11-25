'use strict';
(function(root){
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const labels={AU_CPI_HEADLINE_YOY:'CPI a/a',AU_CPI_TRIMMED_MEAN_YOY:'Trimmed mean a/a',US_REAL_GDP_SAAR:'PIL annualizzato',US_PCE_MOM:'PCE m/m',US_CORE_PCE_MOM:'Core PCE m/m',US_PCE_YOY:'PCE a/a',US_CORE_PCE_YOY:'Core PCE a/a'};
 const fmt=x=>x.toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';
 function rows(s,codes,day){
  if(s?.schema!=='GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1')return [];
  return [...new Set(codes)].flatMap(c=>(s.countries?.[c]?.issuer_releases||[]).filter(r=>r.ccy===c&&r.quality==='OFFICIAL_RECURRING_RELEASE_OBSERVED_NOT_EVENT_REACTION'&&r.as_of<=day&&r.metrics?.length&&r.metrics.every(m=>labels[m.id]&&Number.isFinite(m.value_percent))));
 }
 function meaning(r){
  const m=r.metrics.find(x=>x.id==='AU_CPI_TRIMMED_MEAN_YOY');
  const g=r.metrics.find(x=>x.id==='US_REAL_GDP_SAAR');
  if(m&&Number.isFinite(m.previous_period_percent))return m.value_percent>m.previous_period_percent?'L’inflazione di fondo mensile accelera e rende più difficile allentare la politica monetaria; il pricing va verificato.':m.value_percent<m.previous_period_percent?'L’inflazione di fondo mensile rallenta: possibile sollievo per la RBA, da verificare sul pricing.':'L’inflazione di fondo mensile è stabile.';
  if(g&&Number.isFinite(g.previous_period_percent))return g.value_percent>g.previous_period_percent?'La crescita accelera rispetto al trimestre precedente; conta quanto sia già nei prezzi.':g.value_percent<g.previous_period_percent?'La crescita rallenta rispetto al trimestre precedente.':'La crescita mantiene il ritmo del trimestre precedente.';
  return 'Il PCE conta per la Fed; senza un precedente omogeneo non attribuiamo un’accelerazione o una sorpresa.';
 }
 function render(s,codes,day,cls='source-caption'){
  const data=rows(s,codes,day);if(!data.length)return '';
  return '<div class="'+esc(cls)+'" data-issuer-release-context="'+esc(data.map(r=>r.event_key).join(';'))+'">'+data.map(r=>'<p><strong>'+esc(r.ccy+' · '+r.reference_period+' · '+r.as_of)+'</strong> '+esc(r.metrics.map(m=>labels[m.id]+' '+fmt(m.value_percent)+(Number.isFinite(m.previous_period_percent)?' da '+fmt(m.previous_period_percent):'')).join('; '))+'. '+esc(meaning(r))+' <a href="'+esc(/^https:\/\/(?:www\.)?(?:bea\.gov|abs\.gov\.au)\//.test(r.source_url)?r.source_url:'#news')+'" target="_blank" rel="noopener noreferrer">'+esc(r.source)+'</a></p>').join('')+'</div>';
 }
 root.FXQuantIssuerContext={rows,meaning,render};
 if(typeof module!=='undefined')module.exports=root.FXQuantIssuerContext;
})(typeof window!=='undefined'?window:{});
