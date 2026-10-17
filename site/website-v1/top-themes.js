(()=>{
  'use strict';
  const ROOT='../../live_data/sections/';
  const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const IMP={HIGH:3,MEDIUM:2,LOW:1};
  const esc=s=>String(s??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const fmt=(v,d=1)=>num(v)==null?'—':Number(v).toFixed(d);
  const bp=v=>num(v)==null?'—':`${v>0?'+':''}${Number(v).toFixed(1)} bp`;
  async function load(f){const r=await fetch(ROOT+f,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();}
  function isoDate(x){return /^\d{4}-\d{2}-\d{2}$/.test(String(x||''));}
  function ageDays(x){if(!isoDate(x))return Infinity;return Math.floor((Date.now()-Date.parse(`${x}T23:59:59Z`))/86400000);}
  function macroMetric(x){if(!x||x.status==='WITHHELD')return 'non disponibile';return [x.temperature_label,x.direction,x.acceleration].filter(Boolean).join(' · ')||'disponibile';}
  function macroAsOf(x){return x?.as_of||null;}
  function bestHorizon(p){const hs=['3m','6m','12m'].map(k=>({k,...(p?.horizons?.[k]||{})})).filter(x=>num(x.change_1d_bp)!=null);return hs.sort((a,b)=>Math.abs(num(b.change_1d_bp)||0)-Math.abs(num(a.change_1d_bp)||0))[0]||null;}
  function derive(news,macro,ois){
    const signals=new Map();
    for(const item of (news.items||[])) if(item?.ccy&&CCYS.includes(item.ccy)&&!signals.has(item.ccy))signals.set(item.ccy,item);
    const rows=CCYS.map(ccy=>{
      const sig=signals.get(ccy)||null,m=macro.currencies?.[ccy]||{},p=ois.currencies?.[ccy]||{},h=bestHorizon(p);
      const infl=m.inflation||null,lab=m.labour||null;
      const asOf=[sig?.as_of,p.as_of,macroAsOf(infl),macroAsOf(lab)].filter(Boolean).sort().at(-1)||null;
      const pricingFresh=isoDate(p.as_of)&&ageDays(p.as_of)<=5&&String(p.operational_status||'').startsWith('GREEN');
      const lead=pricingFresh&&h?`${h.k.toUpperCase()} ${fmt(h.rate,3)}% · Δ1D ${bp(h.change_1d_bp)} · vs policy ${bp(h.policy_delta_bp)}`:'Market pricing non certificato/corrente';
      const confirm=pricingFresh&&sig?`Segnale validato ${sig.importance||''} · ${p.operational_status||'GREEN'}`:sig?'Segnale presente, pricing da non usare come conferma':'Nessun nuovo change validato';
      const diverge=pricingFresh&&h&&num(h.change_1w_bp)!=null&&Math.sign(num(h.change_1d_bp)||0)!==0&&Math.sign(num(h.change_1d_bp))!==Math.sign(num(h.change_1w_bp))?`1D ${bp(h.change_1d_bp)} vs 1W ${bp(h.change_1w_bp)}`:'Nessuna divergenza 1D/1W evidenziata';
      const invalidate=pricingFresh?'Un nuovo repricing opposto o perdita dello stato GREEN':'Finché il pricing non torna GREEN, niente lettura operativa';
      return {ccy,signal:sig,asOf,pricingFresh,lead,confirm,diverge,invalidate,inflation:macroMetric(infl),labour:macroMetric(lab),pricing:p};
    });
    rows.sort((a,b)=>{const ad=a.signal?.as_of||'',bd=b.signal?.as_of||'';if(ad!==bd)return bd.localeCompare(ad);const ai=IMP[a.signal?.importance]||0,bi=IMP[b.signal?.importance]||0;if(ai!==bi)return bi-ai;return a.ccy.localeCompare(b.ccy);});
    return rows;
  }
  function card(r){const s=r.signal,title=s?.title||`${r.ccy}: nessun nuovo change validato`,body=s?.detail||`Contesto macro disponibile. Inflazione: ${r.inflation}. Lavoro: ${r.labour}.`;return `<article class="theme-card"><div class="theme-card-top"><span class="theme-ccy">${FLAGS[r.ccy]} ${esc(r.ccy)}</span><span class="theme-state">${esc(s?.category||'CONTESTO')}</span></div><h3>${esc(title)}</h3><p>${esc(body)}</p><div class="theme-driver"><small>Market pricing</small><b>${esc(r.lead)}</b></div><div class="theme-checks"><div class="theme-check confirm"><span>Conferma</span><b>${esc(r.confirm)}</b></div><div class="theme-check diverge"><span>Divergenza</span><b>${esc(r.diverge)}</b></div><div class="theme-check invalidate"><span>Invalida</span><b>${esc(r.invalidate)}</b></div></div></article>`;}
  function withheld(reason='Sorgente operativa non certificata'){const hero=document.getElementById('themes-hero'),grid=document.getElementById('themes-grid'),count=document.getElementById('themes-count');if(hero)hero.innerHTML=`<article class="theme-lead"><div><small>TOP THEMES · WITHHELD</small><h2>${esc(reason)}</h2><p>La pagina non presenta narrative come correnti finché News Pulse, Macro e Market Pricing non espongono un contratto operativo utilizzabile.</p></div></article>`;if(grid)grid.innerHTML='';if(count)count.textContent='WITHHELD';document.documentElement.setAttribute('data-top-themes-page','WITHHELD');}
  function render(rows,news,ois){if(!isoDate(news?.content_as_of)||!Array.isArray(rows)||!rows.length){withheld();return;}const lead=rows[0],s=lead.signal,title=s?.title||`${lead.ccy}: contesto operativo`,body=s?.detail||`Inflazione: ${lead.inflation}. Lavoro: ${lead.labour}.`;document.getElementById('themes-hero').innerHTML=`<article class="theme-lead"><div><small>Tema principale · ${FLAGS[lead.ccy]} ${esc(lead.ccy)} · ${esc(s?.importance||'CONTESTO')}</small><h2>${esc(title)}</h2><p>${esc(body)}</p></div><div class="theme-lead-side"><div class="theme-kpi"><span>Market pricing</span><b>${esc(lead.lead)}</b></div><div class="theme-kpi"><span>Conferma</span><b>${esc(lead.confirm)}</b></div><div class="theme-kpi"><span>Macro</span><b>Inflazione ${esc(lead.inflation)} · Lavoro ${esc(lead.labour)}</b></div><div class="theme-kpi"><span>Invalidazione</span><b>${esc(lead.invalidate)}</b></div></div></article>`;document.getElementById('themes-grid').innerHTML=rows.slice(1).map(card).join('');document.getElementById('themes-count').textContent=`${rows.length} valute G8 · content as of ${news.content_as_of} · OIS ${ois.summary?.operational_green??'—'}/8 GREEN`;document.documentElement.setAttribute('data-top-themes-page','READY');window.GMFQ_TOP_THEMES_PAGE={status:'READY',schema:'GMFQ_TOP_THEMES_SITE_BRIDGE_V1',content_as_of:news.content_as_of,currencies:rows.length,core_effect:'NONE'};}
  function bind(){document.querySelectorAll('a[href="#"]').forEach(a=>a.addEventListener('click',e=>e.preventDefault()));document.querySelector('.pro-card button')?.addEventListener('click',()=>location.href='index.html');}
  function clock(){const d=new Date(),date=document.getElementById('site-date'),time=document.getElementById('site-time');if(date)date.textContent=new Intl.DateTimeFormat('it-IT',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Rome'}).format(d);if(time)time.textContent=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(d);}
  async function main(){bind();clock();setInterval(clock,30000);try{const [news,macro,ois]=await Promise.all([load('NEWS_PULSE_OPERATIONAL.json'),load('MACRO_THERMOMETER_DATA.json'),load('OIS_OPERATIONAL_VIEW.json')]);if(ageDays(news.content_as_of)>5){withheld(`News Pulse non fresco · as of ${news.content_as_of||'—'}`);return;}render(derive(news,macro,ois),news,ois);}catch(e){console.warn('[GMFQ top-themes]',e);withheld('Errore nel bridge operativo');}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',main,{once:true});else main();
})();