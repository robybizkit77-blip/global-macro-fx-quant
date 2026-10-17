(()=>{
  'use strict';

  const ROOT='../../live_data/sections/';
  const PATHS={
    changed:ROOT+'WHAT_CHANGED.json',
    calendar:ROOT+'CALENDAR_OPERATIONAL_VIEW.json',
    themes:ROOT+'TOP_THEMES.json',
    rates:ROOT+'NATIVE_RATES_DATA.json',
    cb:ROOT+'NATIVE_CB_DATA.json',
    cot:ROOT+'V250_COT_CHART_DATA.json'
  };
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const MONTHS=['Gen','Feb','Mar','Apr','Mag','Giu','Lug','Ago','Set','Ott','Nov','Dic'];
  const RATES_MAX_AGE_DAYS=4;
  const COT_MAX_AGE_DAYS=10;

  const esc=(v)=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const n=(v)=>Number.isFinite(Number(v))?Number(v):null;
  const sign=(v,d=1)=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}`};
  const pct=(v,d=1)=>{const x=n(v);return x===null?'—':`${x>0?'+':''}${x.toFixed(d)}%`};
  const dateIT=(s)=>{if(!s)return '—';const d=new Date(`${String(s).slice(0,10)}T00:00:00Z`);return Number.isNaN(d.getTime())?String(s):`${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`};
  const monthLabel=(s)=>{if(!s)return '';const d=new Date(`${String(s).slice(0,10)}T00:00:00Z`);return Number.isNaN(d.getTime())?'':`${MONTHS[d.getUTCMonth()]} ${String(d.getUTCFullYear()).slice(2)}`};
  const timeLabel=(s)=>{if(!s)return '—';return String(s).slice(0,5)};
  const trim=(s,max)=>{s=String(s??'');return s.length<=max?s:s.slice(0,max-1).trimEnd()+'…'};
  const asArray=(data,key)=>Array.isArray(data)?data:(Array.isArray(data?.[key])?data[key]:[]);
  const explicitAsOf=(data)=>Array.isArray(data)?null:(data?.as_of||data?.asOf||data?.generated_at||data?.generatedAt||null);
  function ageDays(s){if(!s)return Infinity;const t=Date.parse(`${String(s).slice(0,10)}T00:00:00Z`);if(!Number.isFinite(t))return Infinity;const now=new Date();const today=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());return Math.floor((today-t)/86400000);}
  const fresh=(s,max)=>ageDays(s)>=0&&ageDays(s)<=max;
  const todayISO=()=>{const d=new Date();return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`;};
  const impactScore=(x)=>{const explicit=n(x?.impact_score);if(explicit!==null)return Math.max(1,Math.min(5,Math.round(explicit)));const importance=String(x?.importance||'').toUpperCase();if(importance==='HIGH')return 5;if(importance==='MEDIUM')return 3;return 1;};

  async function load(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json();}

  function latestHistory(series,key='history2'){
    const raw=series?.[key];
    if(Array.isArray(raw)) return raw.map(x=>({date:x?.date,value:n(x?.value)})).filter(x=>x.value!==null).sort((a,b)=>String(a.date).localeCompare(String(b.date)));
    const dates=Array.isArray(raw?.dates)?raw.dates:[], values=Array.isArray(raw?.values)?raw.values:[];
    return dates.map((date,i)=>({date,value:n(values[i])})).filter(x=>x.date&&x.value!==null).sort((a,b)=>String(a.date).localeCompare(String(b.date)));
  }

  function renderWhatChanged(data){
    const host=document.querySelector('.changed .change-list');if(!host)return;
    const asof=explicitAsOf(data);
    if(!asof){host.innerHTML='<div class="change"><i>!</i><div><b>Aggiornamento trattenuto</b><small>Feed senza as-of certificato: non viene presentato come “oggi”.</small></div><span class="tag amber">WITHHELD</span><em>—</em></div>';document.documentElement.setAttribute('data-what-changed-freshness','WITHHELD');return;}
    const items=asArray(data,'items').slice(0,5);if(!items.length)return;
    host.innerHTML=items.map((x,i)=>{const ccy=x.ccy||'G8';const rm=n(x.rate_move);const trailing=rm===null?(n(x.delta_score)!==null?sign(x.delta_score,2):''):`${rm>0?'+':''}${rm.toFixed(0)}bp`;const tagClass=Math.abs(rm||0)>=10?'red':'blue';const title=`${ccy} · ${x.cycle||'Quadro macro'}`;return `<div class="change"><i>${i+1}</i><div><b>${esc(trim(title,58))}</b><small>${esc(trim(x.summary||'',90))}</small></div><span class="tag ${tagClass}">${esc(ccy)}</span><em>${esc(trailing)}</em></div>`;}).join('');document.documentElement.setAttribute('data-what-changed-freshness','DATED');
  }

  function stanceLabel(v){const s=String(v||'').toUpperCase();if(s.includes('HAWK'))return ['Hawkish','hawkish'];if(s.includes('DOV'))return ['Dovish','dovish'];return ['Neutrale','neutral'];}

  function renderCB(data){
    const card=document.querySelector('.cbs');if(!card||!data)return;card.querySelectorAll('.cbrow').forEach(x=>x.remove());const head=card.querySelector('.cb-head');if(!head)return;
    ORDER.forEach(ccy=>{const x=data[ccy];if(!x)return;const [label,cls]=stanceLabel(x.stance||x.official_bias||x.impulse);const row=document.createElement('div');row.className='cbrow';const bank=x.bank||({USD:'Fed',EUR:'ECB',GBP:'BoE',JPY:'BoJ',CHF:'SNB',CAD:'BoC',AUD:'RBA',NZD:'RBNZ'}[ccy]);const rate=x.rate_text||((n(x.rate)!==null)?`${Number(x.rate).toFixed(2)}%`:'—');row.innerHTML=`<b>${FLAGS[ccy]||''} ${esc(bank)}</b><span>${esc(rate)}</span><i class="${cls}">${esc(label)}</i><em>${esc(dateIT(x.next_meeting||x.official_next))}</em>`;card.appendChild(row);});
  }

  function cotAsOf(data){let latest=null;ORDER.forEach(ccy=>{const dates=Array.isArray(data?.[ccy]?.dates)?data[ccy].dates:[];const d=dates.at(-1);if(d&&(!latest||String(d)>String(latest)))latest=d;});return latest;}
  function renderCOT(data){
    const host=document.querySelector('.cot-card .cot-chart');const sub=document.querySelector('.cot-card .subline');if(!host||!data)return;const asof=cotAsOf(data);
    if(!fresh(asof,COT_MAX_AGE_DAYS)){host.innerHTML='<div class="cotrow"><span>WITHHELD</span><i><b style="width:0"></b></i><em class="neg">STALE</em></div>';if(sub)sub.textContent=`COT trattenuto · as of ${dateIT(asof)}`;document.documentElement.setAttribute('data-cot-freshness','WITHHELD');return;}
    const rows=[];ORDER.forEach(ccy=>{const x=data[ccy];const a=Array.isArray(x?.netoi)?x.netoi:[];const v=n(a.at(-1));if(v!==null)rows.push({ccy,v});});if(!rows.length)return;rows.sort((a,b)=>b.v-a.v);const max=Math.max(10,...rows.map(x=>Math.abs(x.v)));host.innerHTML=rows.map(x=>{const cls=x.v>=0?'pos':'neg';const width=Math.min(48,Math.abs(x.v)/max*48);return `<div class="cotrow"><span>${FLAGS[x.ccy]||''} ${x.ccy}</span><i><b class="${cls}" style="width:${width.toFixed(1)}%"></b></i><em class="${cls}">${pct(x.v,1)}</em></div>`;}).join('');const axis=document.querySelector('.cot-card .cot-axis');if(axis){const m=Math.ceil(max/10)*10;axis.innerHTML=`<span>-${m}</span><span>-${m/2}</span><span>0</span><span>${m/2}</span><span>${m}</span>`;}if(sub)sub.textContent=`Net / Open Interest · CFTC Legacy Non-Commercial · as of ${dateIT(asof)}`;document.documentElement.setAttribute('data-cot-freshness','FRESH');
  }

  function renderCalendar(data){
    const host=document.querySelector('.calendar-table');const ev=asArray(data,'events').filter(x=>!x?.date||String(x.date)>=todayISO()).sort((a,b)=>String(a?.date||'').localeCompare(String(b?.date||''))).slice(0,8);if(!host||!ev.length)return;const head='<div class="thead"><span>ORA</span><span>CCY</span><span>EVENTO</span><span>IMPATTO</span><span>CONS</span><span>PREC</span></div>';host.innerHTML=head+ev.map(x=>{const score=impactScore(x);const cls=score>=4?'high':score>=3?'med':'low';const dots='●'.repeat(score)+'○'.repeat(5-score);const title=`${x.date?dateIT(x.date).split(' ').slice(0,2).join(' ')+' · ':''}${x.title||''}`;const time=x.time_utc||x.time_local||null;return `<div><span>${esc(timeLabel(time))}</span><b>${esc(x.ccy||'—')}</b><small>${esc(trim(title,55))}</small><i class="dots ${cls}">${dots}</i><em>${esc(x.consensus??'—')}</em><em>${esc(x.previous??'—')}</em></div>`;}).join('');
  }

  function renderThemes(data){
    const host=document.querySelector('.themes .theme-grid');if(!host)return;const asof=explicitAsOf(data);
    if(!asof){host.innerHTML='<div class="theme t1"><div class="thumb"></div><div><b>Top Themes trattenuti</b><small>Feed senza as-of certificato. Nessun tema viene presentato come corrente.</small><em>WITHHELD</em></div></div>';document.documentElement.setAttribute('data-themes-freshness','WITHHELD');return;}
    const themes=asArray(data,'themes').slice(0,5);if(!themes.length)return;host.innerHTML=themes.map((x,i)=>{const ccy=Array.isArray(x.ccy)?x.ccy[0]:(x.ccy||x.bucket||'MACRO');return `<div class="theme t${i+1}"><div class="thumb"></div><div><b>${esc(trim(x.title||x.id||'Tema',30))}</b><small>${esc(trim(x.body||x.story||x.change||'',72))}</small><em>${esc(String(ccy).toUpperCase())}</em></div></div>`;}).join('');document.documentElement.setAttribute('data-themes-freshness','DATED');
  }

  function renderRates(data){
    const keys=['USD','EUR','GBP','JPY'];if(!data||!keys.every(k=>data[k]))return;const usdHistory=latestHistory(data.USD,'history2');const asof=data.USD?.date||usdHistory.at(-1)?.date||null;const legend=document.querySelector('.rate-legend');const chart=document.querySelector('.ratechart');const tip=document.querySelector('.rate-tip');
    if(!fresh(asof,RATES_MAX_AGE_DAYS)){if(legend)legend.innerHTML=keys.map(k=>`<span class="${k.toLowerCase()}">● ${k} —</span>`).join('');if(chart)chart.querySelectorAll('polyline').forEach(el=>el.setAttribute('points',''));if(tip)tip.innerHTML=`<small>WITHHELD · rates stale · as of ${esc(dateIT(asof))}</small>`;document.documentElement.setAttribute('data-rates-panel-freshness','WITHHELD');return;}
    if(legend)legend.innerHTML=keys.map(k=>`<span class="${k.toLowerCase()}">● ${k} ${(n(data[k]?.current?.y2)??n(data[k]?.['2Y']))?.toFixed(2)??'—'}%</span>`).join('');if(!chart)return;const map={USD:'usd',EUR:'eur',GBP:'gbp',JPY:'jpy'};const histories={};let all=[];keys.forEach(k=>{histories[k]=latestHistory(data[k],'history2').slice(-120);all.push(...histories[k].map(x=>x.value));});const maxY=Math.max(5,...all),minY=Math.min(0,...all);const top=20,bottom=195,left=25,right=350;const y=(v)=>top+(bottom-top)*(1-(v-minY)/((maxY-minY)||1));keys.forEach(k=>{const el=chart.querySelector(`polyline.${map[k]}`),h=histories[k];if(!el||!h.length)return;el.setAttribute('points',h.map((p,i)=>`${(left+(right-left)*(i/Math.max(1,h.length-1))).toFixed(1)},${y(p.value).toFixed(1)}`).join(' '));});const labels=[...chart.querySelectorAll('.axis text')];if(labels.length>=11){for(let i=0;i<6;i++){const v=maxY-(maxY-minY)*(i/5);labels[i].textContent=`${v.toFixed(v%1?1:0)}%`;}const h=histories.USD;[0,.25,.5,.75,1].forEach((q,i)=>{const p=h[Math.min(h.length-1,Math.round((h.length-1)*q))];labels[6+i].textContent=monthLabel(p?.date);});}const latestDate=histories.USD.at(-1)?.date;if(tip)tip.innerHTML=`<small>${esc(dateIT(latestDate))}</small>`+['GBP','USD','EUR','JPY'].map(k=>`<span class="${map[k]}">● ${k}&nbsp; ${(n(data[k]?.current?.y2)??n(data[k]?.['2Y']))?.toFixed(2)??'—'}%</span>`).join('');document.documentElement.setAttribute('data-rates-panel-freshness','FRESH');
  }

  async function main(){
    const entries=await Promise.all(Object.entries(PATHS).map(async([k,p])=>{try{return [k,await load(p)]}catch(e){console.warn('[GMFQ data]',k,e);return [k,null]}}));
    const data=Object.fromEntries(entries);
    renderWhatChanged(data.changed);
    renderCB(data.cb);
    renderCOT(data.cot);
    renderCalendar(data.calendar);
    renderThemes(data.themes);
    renderRates(data.rates);
    document.documentElement.setAttribute('data-website-live-adapter','READY');
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();
