'use strict';
/* FX Quant NEXT - Independent user-experience prototype.
 * The operational FX engine, pricing and source files remain read-only.
 * No invented live quotes, synthetic rankings, or automatic trade signals.
 */
(function(){
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',AUD:'🇦🇺',NZD:'🇳🇿',CAD:'🇨🇦'};
const NAMES={USD:'Stati Uniti',EUR:'Area euro',GBP:'Regno Unito',JPY:'Giappone',CHF:'Svizzera',AUD:'Australia',NZD:'Nuova Zelanda',CAD:'Canada'};
const ROUTES={overview:'Panoramica',currencies:'Valute G8',pairs:'Coppie FX',macro:'Macro Lab',rates:'Tassi & OIS',cot:'Positioning',risk:'Risk Radar',news:'News Pulse'};
const SOURCES={
 rates:'../../../live_data/sections/NATIVE_RATES_DATA.json',
 dxy:'../../../live_data/sections/DXY_SYNTHETIC_ECB.json',
 pairs:'../../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json',
 macro:'../../../live_data/sections/MACRO_THERMOMETER_DATA.json',
 cb:'../../../live_data/sections/NATIVE_CB_DATA.json',
 cot:'../../../live_data/sections/V247_COT_STORIES.json',
 risk:'../cross-asset-live-data.json',
 ois:'../ois-pricing-snapshot.json',
 news:'../../../live_data/sections/NEWS_PULSE_OPERATIONAL.json',
 themes:'../../../live_data/sections/TOP_THEMES.json'
};
const state={data:{},errors:{},route:'overview',ccy:'USD',against:'EUR',pair:'EURUSD',pairFilter:'all',pairSearch:'',watch:new Set(),window:20,rateMode:'both',riskStream:'VIX',riskWindow:20,macroMetric:'inflation',newsMode:'pulse',chartIndex:0,charts:{}};
try{const w=JSON.parse(localStorage.getItem('fxquant-next-watch')||'[]');if(Array.isArray(w))state.watch=new Set(w.filter(s=>typeof s==='string'))}catch(e){}
const $=id=>document.getElementById(id);
const esc=x=>String(x===undefined||x===null?'':x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const fmt=(v,n=2)=>finite(v)?v.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const sign=(v,n=1,suffix='')=>finite(v)?(v>0?'+':v<0?'−':'')+fmt(Math.abs(v),n)+suffix:'—';
const date=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)?d.slice(8,10)+'/'+d.slice(5,7)+'/'+d.slice(0,4):esc(d||'n.d.');
const validDay=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d);
const dayNow=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const fresh=(d,days=5)=>validDay(d)&&d<=dayNow()&&(Date.parse(dayNow()+'T12:00:00Z')-Date.parse(d+'T12:00:00Z'))/864e5<=days;
const qBadge=(quality)=>{const q=String(quality||'NON CLASSIFICATO');let c='neutral';if(/CON RISCHI|ESTREMO|EXTREME|NON VALUTABILE|STALE/i.test(q))c=/NON VALUTABILE|STALE/i.test(q)?'warning':'danger';else if(/CONFERMARE|STIMA|INDICATIV|DA VERIFICARE/i.test(q))c='warning';else if(/PULITO|UFFICIALE|VALIDAT/i.test(q))c='good';return '<span class="badge '+c+'">'+esc(q)+'</span>'};
const arrow=(n)=>finite(n)?n>0?'↑':n<0?'↓':'→':'—';
function routeLink(route,label,cls='ghost-btn small'){return '<a class="'+cls+'" href="#'+route+'">'+esc(label)+'</a>'}
const get=k=>state.data[k]||null;
const choose=(id,options,selected,attr='data-select')=>options.map(v=>'<button type="button" class="pill '+(String(v.value)===String(selected)?'active':'')+'" '+attr+'="'+esc(v.value)+'" aria-pressed="'+String(String(v.value)===String(selected))+'">'+esc(v.label)+'</button>').join('');
const timeWindows=[{label:'5 sedute',value:5},{label:'20 sedute',value:20},{label:'60 sedute',value:60},{label:'Tutto',value:9999}];
const eurPairs=()=>get('pairs')?.pairs||{};
const currencyInfo=ccy=>({rate:get('rates')?.[ccy],cb:get('cb')?.[ccy],macro:get('macro')?.currencies?.[ccy],ois:get('ois')?.currencies?.[ccy],cot:get('cot')?.[ccy]});
function sectionTitle(title,sub='',link='',label='Approfondisci'){return '<div class="sectionline"><h2>'+esc(title)+'</h2><div>'+ (sub?'<p>'+esc(sub)+'</p>':'')+(link?routeLink(link,label,'aside-link'):'')+'</div></div>'}
function pageHero(kicker,title,lead,right=''){return '<div class="page-hero"><div><div class="eyebrow">'+esc(kicker)+'</div><h1>'+title+'</h1><p class="lead">'+lead+'</p></div>'+(right?'<div class="page-hero-right">'+right+'</div>':'')+'</div>'}
function panel(head,sub,body,extra=''){return '<section class="panel '+extra+'"><div class="panel-head"><div><span class="mini-overline">'+esc(sub||'RESEARCH VIEW')+'</span><h2>'+head+'</h2></div></div>'+body+'</section>'}
function stat(label,value,meta,delta='',deltaTone='neutral',onRoute=''){
 return '<'+(onRoute?'a href="#'+onRoute+'"':'div')+' class="kpi '+(onRoute?'clickable':'')+'"><div class="kpi-top"><span class="kpi-label">'+esc(label)+'</span><span class="kpi-icon">✳</span></div><strong class="kpi-value">'+esc(value)+'</strong><div class="kpi-meta"><span>'+esc(meta)+'</span>'+(delta?'<span class="delta '+deltaTone+'">'+esc(delta)+'</span>':'')+'</div></'+(onRoute?'a':'div')+'>';
}
function pQuality(s){if(!s)return 'NON VALUTABILE';return s.quality||'NON VALUTABILE'}
function assetStatus(s){return /PULITO/.test(s)?'good':/CON RISCHI/.test(s)?'danger':/DA CONFERMARE/.test(s)?'warning':'neutral'}
function labelItem(a,b,extra=''){return '<div class="lens '+extra+'"><label>'+esc(a)+'</label><strong>'+esc(b||'n.d.')+'</strong></div>'}
function concise(s,max=190){const x=String(s||'Dato da verificare');return x.length>max?x.slice(0,max-1).trim()+'…':x}
function labelR(ccy){const r=get('rates')?.[ccy];return r&&finite(r['2Y'])?fmt(r['2Y'])+'%':'—'}
function getPairName(k){return k.slice(0,3)+'/'+k.slice(3)}
function filterDays(points,n,withDate=true){const a=points.filter(x=>finite(x.value)&&(!withDate||validDay(x.label)&&x.label<=dayNow())).sort((a,b)=>String(a.label).localeCompare(String(b.label)));return a.slice(-Number(n||20))}
function historyRates(c){
 const r=get('rates')?.[c];
 if(!r?.history2?.dates||!r?.history10?.dates)return [];
 const b=new Map((r.history10.dates||[]).map((d,i)=>[d,r.history10.values?.[i]]));
 return r.history2.dates.map((d,i)=>({label:d,v2:r.history2.values?.[i],v10:b.get(d)})).filter(x=>validDay(x.label)&&x.label<=dayNow()&&x.label<=r.date&&finite(x.v2)&&finite(x.v10));
}
function priceHistory(name){
 const s=get('risk')?.streams?.[name];
 if(!Array.isArray(s?.history))return [];
 return s.history.filter(x=>Array.isArray(x)&&validDay(x[0])&&x[0]<=dayNow()&&finite(x[1])).map(x=>({label:x[0],value:x[1]}));
}
function dxyHistory(){
 const d=get('dxy');return Array.isArray(d?.history)?d.history.filter(x=>validDay(x.date)&&finite(x.value)&&x.date<=dayNow()).map(x=>({label:x.date,value:x.value})):[];
}
function plot(opts){
 const id='plot-'+(++state.chartIndex);
 const all=opts.lines||[];
 const normalized=all.map(line=>({name:line.name,color:line.color||'#96cbe6',values:(line.values||[]).filter(x=>x&&finite(x.value)).slice(-Number(opts.window||9999))}));
 const count=Math.max(0,...normalized.map(x=>x.values.length));
 if(count<2||!normalized.some(x=>x.values.length>1))return '<div class="empty"><strong>Storico non disponibile</strong><p>Non disegniamo curve se mancano osservazioni validate e confrontabili.</p></div>';
 const values=normalized.flatMap(l=>l.values.map(p=>p.value));
 let min=Math.min(...values),max=Math.max(...values),pad=(max-min)*.16;
 if(pad===0)pad=Math.max(.01,Math.abs(max)*.004);min-=pad;max+=pad;
 const W=700,H=240,L=53,R=18,T=21,B=31;
 const X=i=>L+i*(W-L-R)/Math.max(1,count-1);
 const Y=v=>T+(max-v)/(max-min)*(H-T-B);
 let body='';
 for(let t=0;t<5;t++){const y=T+t*(H-T-B)/4;const val=max-(max-min)*t/4;body+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y+'" y2="'+y+'" stroke="#2d465b" stroke-dasharray="3 6"/><text x="'+(L-10)+'" y="'+(y+3)+'" font-size="10" text-anchor="end" fill="#7997ac">'+fmt(val,opts.precision??2)+'</text>';}
 normalized.forEach(line=>{
  if(line.values.length<2)return;
  const coords=line.values.map((p,i)=>[X(i),Y(p.value)]);
  body+='<polyline points="'+coords.map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ')+'" fill="none" stroke="'+line.color+'" stroke-width="2.7" stroke-linejoin="round" stroke-linecap="round"/>';
  const last=coords[coords.length-1];body+='<circle cx="'+last[0]+'" cy="'+last[1]+'" r="3.8" fill="'+line.color+'" stroke="#0a1827" stroke-width="2"/>';
 });
 const base=normalized.find(x=>x.values.length===count)||normalized[0],left=base.values[0]?.label,right=base.values.at(-1)?.label;
 body+='<text x="'+L+'" y="'+(H-6)+'" font-size="10" fill="#7899ad">'+esc(opts.axisDates===false?'Inizio finestra':validDay(left)?date(left):left||'')+'</text><text x="'+(W-R)+'" y="'+(H-6)+'" text-anchor="end" font-size="10" fill="#7899ad">'+esc(opts.axisDates===false?'Ultima osservazione':validDay(right)?date(right):right||'')+'</text>';
 body+='<line data-crosshair x1="0" y1="'+T+'" x2="0" y2="'+(H-B)+'" stroke="#bfdded" stroke-dasharray="4 5" opacity="0" />';
 state.charts[id]={lines:normalized,count,L,R,W,unit:opts.unit||'',precision:opts.precision??2};
 return '<div class="chart" data-chart="'+id+'"><svg viewBox="0 0 700 240" preserveAspectRatio="none" role="img" aria-label="'+esc(opts.label||'Grafico storico')+'">'+body+'</svg><div class="chart-tooltip"></div></div><div class="chart-legend">'+normalized.map(l=>'<span><b style="background:'+l.color+'"></b>'+esc(l.name)+'</span>').join('')+'</div>';
}
function chartEvents(e){
 const chart=e.target.closest('.chart[data-chart]');if(!chart)return;
 const meta=state.charts[chart.dataset.chart];if(!meta)return;
 const rect=chart.getBoundingClientRect();
 const u=Math.max(0,Math.min(1,(e.clientX-rect.left)/Math.max(1,rect.width)));
 const index=Math.round(u*(meta.count-1)),x=meta.L+(index/(meta.count-1))*(meta.W-meta.L-meta.R);
 const line=chart.querySelector('[data-crosshair]'),tooltip=chart.querySelector('.chart-tooltip');
 if(line){line.setAttribute('x1',x);line.setAttribute('x2',x);line.setAttribute('opacity','1');}
 const src=meta.lines.find(l=>l.values[index])?.values[index];
 if(!src)return;
 const rows=meta.lines.map(l=>{const p=l.values[index];return p?'<div><span style="color:'+l.color+'">●</span> '+esc(l.name)+': <b>'+fmt(p.value,meta.precision)+esc(meta.unit)+'</b></div>':''}).join('');
 tooltip.innerHTML='<div style="color:#91aec1;margin-bottom:4px">'+esc(validDay(src.label)?date(src.label):src.label)+'</div>'+rows;
 tooltip.style.display='block';tooltip.style.top='7px';tooltip.style.left=Math.max(2,Math.min(rect.width-138,(x/meta.W)*rect.width+12))+'px';
}
function chartHide(e){const a=e.target.closest('.chart[data-chart]');if(!a)return;const ch=a.querySelector('[data-crosshair]'),tip=a.querySelector('.chart-tooltip');if(ch)ch.setAttribute('opacity','0');if(tip)tip.style.display='none';}
function controlsWindows(){return '<div class="pill-controls" id="window-buttons">'+choose('',timeWindows,state.window,'data-window')+'</div>'}
function ratesPlot(ccy='USD',window=state.window,mode=state.rateMode){
 const rows=historyRates(ccy).slice(-Number(window)),ls=[];
 if(mode==='both'||mode==='2y')ls.push({name:'2Y',color:'#9dd4ed',values:rows.map(x=>({label:x.label,value:x.v2}))});
 if(mode==='both'||mode==='10y')ls.push({name:'10Y',color:'#ee6475',values:rows.map(x=>({label:x.label,value:x.v10}))});
 return plot({lines:ls,unit:'%',label:'Andamento dei rendimenti governativi '+ccy});
}
function oisDetail(ccy){
 const a=get('ois')?.currencies?.[ccy];if(!a?.horizons)return '<div class="empty"><strong>Pricing non disponibile</strong><p>Manca un feed datato utilizzabile per questa valuta.</p></div>';
 const keys=['3m','6m','12m'];
 const points=keys.map(k=>a.horizons[k]).filter(x=>x&&finite(x.rate));
 const dateSet=new Set(points.map(x=>x.as_of));
 const mixedDates=dateSet.size>1;
 return '<div class="panel-head"><div><span class="mini-overline">Percorso atteso · 3M / 6M / 12M</span><h2>'+FLAGS[ccy]+' '+ccy+' · Market pricing</h2><p>'+esc(a.kind)+' · '+esc(a.quality)+'</p></div>'+qBadge(a.quality)+'</div>'
 +'<div class="metric-split">'+keys.map(k=>{const x=a.horizons[k];return '<div class="stat"><small>'+k.toUpperCase()+' · '+esc(date(x?.as_of))+'</small><strong>'+ (finite(x?.rate)?fmt(x.rate,3)+'%':'—')+'</strong><em>'+esc(x?.contract||a.kind||'n.d.')+'</em></div>'}).join('')+'</div>'
 +'<div class="chart-summary" style="margin-top:14px">'+(mixedDates?'Le scadenze hanno date diverse: la linea non rappresenta una curva simultanea. ':'Le scadenze riportano la stessa data. ')+
 'Valori '+esc(a.kind)+' ('+esc(a.quality)+'). Non equivalgono automaticamente al tasso ufficiale della banca centrale.</div>'
 +'<p class="source-caption">Fonte: '+esc(a.source)+' · Ultimo aggiornamento indicato: '+date(a.as_of)+'.</p>';
}
function pairFilterOptions(){return [{label:'Tutte',value:'all'},{label:'Con rischi',value:'CON RISCHI'},{label:'Da confermare',value:'DA CONFERMARE'},{label:'Pulite',value:'PULITO'},{label:'Non valutabili',value:'NON VALUTABILE'},{label:'★ Salvate',value:'watch'}];}
function pairListKeys(){
 const rows=eurPairs(),q=state.pairSearch.trim().toUpperCase().replace(/[^A-Z]/g,'');
 return Object.keys(rows).sort().filter(k=>{const qual=pQuality(rows[k].setup);return (!q||k.includes(q))&&(state.pairFilter==='all'||state.pairFilter==='watch'&&state.watch.has(k)||qual===state.pairFilter)});
}
function pairRow(k,compact=false){
 const p=eurPairs()[k],s=p?.setup||{},q=pQuality(s);
 return '<button type="button" class="pair-row '+(state.pair===k?'active':'')+'" data-pair="'+k+'"><span><strong>'+esc(getPairName(k))+'</strong><span class="subtitle">'+esc(s.structuralFav?'Contesto: '+s.structuralFav:'Valutazione da approfondire')+' · '+esc(s.price?.text||'Prezzo non classificato')+'</span></span><span class="right">'+qBadge(q)+'<span class="arrow">›</span></span>'+(compact?'':'')+'</button>';
}
function riskAligned(){
 const a=get('risk')?.streams||{},n=a.NASDAQCOM,v=a.VIX,h=a.HY_OAS;
 const same=validDay(n?.date)&&n.date===v?.date&&n.date===h?.date;
 return {same,n,v,h,assessment:same&&finite(n?.change_1d_pct)&&finite(v?.value)&&finite(h?.previous)&&finite(h?.value)?(n.change_1d_pct<-1&&v.value>25&&h.value>h.previous?'Stress multi-asset concordante':'Nessuna conferma completa di stress intenso'):'Confronto simultaneo non validato'};
}
function currentStory(){
 const u=get('rates')?.USD,risk=riskAligned(),d=get('dxy');
 const ok=u&&finite(u.chg2_bp)&&validDay(u.date);
 if(!ok)return {headline:'Prima i dati.<br> Poi le conclusioni.',lead:'La piattaforma distingue ciò che è osservato da ciò che resta da verificare. I feed non ancora disponibili non diventano segnali di mercato.',date:'Date delle fonti da validare'};
 const verb=u.chg2_bp< -1?'rallenta':u.chg2_bp>1?'sale':'si stabilizza';
 const text=u.chg2_bp< -1?'Il rendimento Treasury USA a 2 anni scende':u.chg2_bp>1?'Il rendimento Treasury USA a 2 anni sale':'Il Treasury 2Y USA varia poco';
 return {headline:'Il front-end USA<br><em>'+verb+'.</em> E il resto del mercato?',lead:text+' di '+sign(u.chg2_bp,1,' pb')+' al '+date(u.date)+'. '+(risk.same?'Nasdaq, VIX e credito HY permettono anche una lettura cross-asset sincronizzata.':'VIX, azionario e credito HY hanno date non tutte coincidenti: una diagnosi simultanea di risk-off sarebbe prematura.'),date:'UST 2Y '+date(u.date)+' · DXY '+date(d?.as_of)};
}
function overview(){
 const r=get('rates')?.USD,d=get('dxy'),ri=get('risk')?.streams||{},story=currentStory(),f=get('pairs'),ph=ri.HY_OAS;
 const kpis=[
 stat('Treasury USA · 2Y',r?fmt(r['2Y'])+'%':'—',r?'Al '+date(r.date):'Nessun dato',finite(r?.chg2_bp)?sign(r.chg2_bp,1,' pb'):'',r?.chg2_bp>0?'up':'down','rates'),
 stat('USD · Proxy BCE',d?fmt(d.value):'—',d?'Al '+date(d.as_of):'Nessun dato',finite(d?.value)&&finite(d?.previous_value)?sign((d.value/d.previous_value-1)*100,2,'%'):'','neutral','currencies'),
 stat('VIX · Volatilità',ri.VIX?fmt(ri.VIX.value):'—',ri.VIX?'Al '+date(ri.VIX.date):'Nessun dato',finite(ri.VIX?.change_1d_pct)?sign(ri.VIX.change_1d_pct,1,'%'):'',ri.VIX?.change_1d_pct>0?'down':'up','risk'),
 stat('Credito HY · OAS',ph?fmt(ph.value)+'%':'—',ph?'Al '+date(ph.date):'Nessun dato',finite(ph?.previous)?sign((ph.value-ph.previous)*100,0,' pb'):'',ph?.value>ph?.previous?'down':'up','risk')].join('');
 const ar=historyRates('USD').slice(-Number(state.window)),ls=[{name:'Treasury 2Y',color:'#9dcfec',values:ar.map(x=>({label:x.label,value:x.v2}))},{name:'Treasury 10Y',color:'#ee6475',values:ar.map(x=>({label:x.label,value:x.v10}))}];
 const snapshot=f?.pairs||{};const ideas=Object.keys(snapshot).filter(k=>snapshot[k]?.setup?.quality!=='NON VALUTABILE').sort().slice(0,5);
 const n=get('news'); const news=(n?.items||[]).slice(0,2);
 const aligned=riskAligned();
 return pageHero('IL TUO BRIEFING VISIVO','Benvenuto nel tuo <em>Market Desk.</em>','Una piattaforma da esplorare, non una parete di numeri. Prima la storia, poi i prezzi che la confermano o la smentiscono.',routeLink('pairs','Esplora 28 coppie ⇄','solid-btn'))
 +'<div class="overview-stage"><section class="stage-story"><div><span class="pretitle">◉ IL TEMA DA INDAGARE</span><h2>'+story.headline+'</h2><p>'+esc(story.lead)+'</p></div><div class="stage-bottom">'+routeLink('rates','Esplora tassi & pricing →','solid-btn')+'<span class="hero-fact">'+esc(story.date)+'</span></div></section>'
 +'<section class="panel stage-right polished"><div class="panel-head"><div><span class="mini-overline">DATI CHE PARLANO</span><h2>Il mercato dei tassi USA</h2><p>Due scadenze, una storia da interpretare</p></div><span class="badge">UST 2Y / 10Y</span></div>'
 +plot({lines:ls,unit:'%',label:'Storico Treasury USA 2Y e 10Y',window:state.window})
 +'<div class="chart-summary">Le due linee sono rendimenti governativi, non tassi OIS. Un movimento del 10Y può riflettere crescita, inflazione, real yields e term premium.</div></section></div>'
 +sectionTitle('La fotografia dei mercati','Dati con date proprie')+'<div class="kpi-grid grid cols-4">'+kpis+'</div>'
 +sectionTitle('Capire prima di decidere','Tre passaggi, sempre nello stesso ordine')
 +'<div class="story-steps"><div class="step"><span class="step-kicker"><span class="step-number">1</span> OSSERVAZIONE</span><h3>Cosa è successo?</h3><p>'+esc(r?'Treasury USA 2Y '+sign(r.chg2_bp,1,' pb')+' nella seduta del '+date(r.date)+'.':'Serve un dato Treasury datato.')+'</p></div>'
 +'<div class="step"><span class="step-kicker"><span class="step-number">2</span> INTERPRETAZIONE</span><h3>Cosa potrebbe significare?</h3><p>Il front-end è sensibile alle attese sui tassi ufficiali, ma per attribuire il movimento alla banca centrale occorre leggere anche OIS e shock macro.</p></div>'
 +'<div class="step"><span class="step-kicker"><span class="step-number">3</span> VERIFICA</span><h3>Il mercato conferma?</h3><p>'+esc(aligned.same?aligned.assessment:'Nasdaq, VIX e credito HY non sono su date identiche. Confronto da completare, senza dedurre causalità.')+'</p></div></div>'
 +sectionTitle('Research playground','Scegli cosa approfondire','pairs','Apri il selettore FX')
 +'<div class="grid tilted"><section class="panel"><div class="panel-head"><div><span class="mini-overline">FX / SETUP MONITOR</span><h2>Le coppie da studiare</h2><p>Stati del motore, non un ranking né segnali d’ingresso</p></div>'+qBadge('28 CROSS')+'</div><div class="pair-list">'+(ideas.length?ideas.map(k=>pairRow(k,true)).join(''):'<p class="no-result">Feed delle coppie non disponibile.</p>')+'</div></section>'
 +'<section class="panel glow"><div class="panel-head"><div><span class="mini-overline">NEWS / ULTIMO SNAPSHOT</span><h2>Perché oggi conta</h2><p>Notizie con fonte, data e categoria</p></div></div>'+(news.length?news.map(item=>'<div class="timeline-item" style="margin:0 0 9px"><span class="mini-overline">'+esc(item.ccy||item.category||'G8')+' · '+date(item.as_of)+'</span><h3>'+esc(item.title)+'</h3><p>'+esc(concise(item.detail,155))+'</p></div>').join(''):'<div class="empty"><strong>News non disponibili</strong></div>')+routeLink('news','Vai al News Pulse ↗','ghost-btn small')+'</section></div>'
 +'<div class="data-status"><span class="live-dot"></span><div><strong>Regola FX Quant:</strong> niente segnali ricavati automaticamente da uno shock non verificato. Ogni mercato mantiene la propria data, lo strumento e la qualità della fonte.</div></div>';
}
function currencies(){
 const c=state.ccy,x=currencyInfo(c),rate=x.rate,cb=x.cb,macro=x.macro,ois=x.ois,cot=x.cot;
 const inflation=macro?.inflation,labour=macro?.labour;
 const rateCards=rate?'<div class="metric-split"><div class="stat"><small>Government 2Y</small><strong>'+fmt(rate['2Y'])+'%</strong><em>'+date(rate.date)+'</em></div><div class="stat"><small>Government 10Y</small><strong>'+fmt(rate['10Y'])+'%</strong><em>'+date(rate.date)+'</em></div><div class="stat"><small>10Y − 2Y</small><strong>'+sign(rate.curve_bp,1,' pb')+'</strong><em>'+esc(rate.curve_state||'Pendenza')+'</em></div></div>':'<p class="no-result">Serie rendimenti non disponibile</p>';
 return pageHero('FX G8 / COUNTRY DEEP DIVE','Una valuta. <em>Molti driver.</em>','Seleziona una valuta: cambia l’intero quadro, dai dati macro ai rendimenti, al pricing dei tassi e al positioning. Nessun punteggio di forza inventato.')
 +'<div class="currency-grid">'+FX.map(k=>{const r=get('rates')?.[k];return '<button class="currency-chip" type="button" data-ccy="'+k+'" aria-pressed="'+String(k===c)+'"><span class="flag">'+FLAGS[k]+'</span><strong>'+k+'</strong><span class="meta">Gov 2Y · '+date(r?.date)+'</span><span class="latest">'+labelR(k)+'</span></button>'}).join('')+'</div>'
 +sectionTitle(FLAGS[c]+' '+NAMES[c]+' · '+c,'Lettura multidimensionale')
 +'<div class="grid tilted"><section class="panel glow"><div class="focus-row"><span class="mini-overline">MERCATO DEI TASSI</span>'+qBadge(rate?.quality||'DATO NON VALIDATO')+'</div><h2 class="focus-headline">'+(rate?'Il 2Y '+(rate.chg2_bp<0?'scende':rate.chg2_bp>0?'sale':'è stabile')+'. Cosa prezza il mercato?':'La serie 2Y è da verificare')+'</h2><p class="focus-subtitle">La direzione del governo 2Y non dimostra da sola il percorso della banca centrale. Confrontiamo OIS, timing e macro.</p><div class="divider"></div>'+rateCards+'<div class="chart-summary" style="margin-top:15px">'+(rate?'2Y '+sign(rate.chg2_bp,1,' pb')+' · 10Y '+sign(rate.chg10_bp,1,' pb')+' nell’ultima variazione indicata dalla fonte.':'Nessuna variazione verificata.')+'</div></section>'
 +'<section class="panel"><div class="panel-head"><div><span class="mini-overline">BANCA CENTRALE</span><h2>'+esc(cb?.bank||c)+'</h2><p>Decisione politica e pricing non sono la stessa cosa</p></div></div><div class="metric-split"><div class="stat"><small>Tasso ufficiale</small><strong>'+esc(cb?.rate_text||'—')+'</strong><em>'+date(cb?.last_date)+'</em></div><div class="stat"><small>Prossima riunione</small><strong style="font-size:17px">'+date(cb?.next_meeting)+'</strong></div><div class="stat"><small>Indicazione</small><strong style="font-size:13px">'+esc(concise(cb?.stance||'n.d.',65))+'</strong></div></div><p class="source-caption">'+esc(concise(cb?.official_next||'Nessuna guidance validata.',210))+'</p></section></div>'
 +sectionTitle('Macro + Pricing + Positioning','Leggi gli elementi insieme, senza forzare una tesi')
 +'<div class="grid cols-3">'
 +'<section class="panel"><span class="mini-overline">01 / MACRO</span><h3 class="focus-headline" style="font-size:19px">Inflazione e lavoro</h3><div class="flow-track"><div class="flow-item"><label>Inflazione</label><p><b>'+fmt(inflation?.latest_value,2)+'%</b> · '+esc(inflation?.direction||'n.d.')+' · '+esc(inflation?.acceleration||'n.d.')+'<br>Dato: '+esc(inflation?.as_of||'n.d.')+'</p></div><div class="flow-item"><label>Disoccupazione</label><p><b>'+fmt(labour?.latest_value,2)+'%</b> · '+esc(labour?.direction||'n.d.')+' · '+esc(labour?.acceleration||'n.d.')+'<br>Dato: '+esc(labour?.as_of||'n.d.')+'</p></div></div>'+routeLink('macro','Apri Macro Lab ↗')+'</section>'
 +'<section class="panel"><span class="mini-overline">02 / PRICING</span><h3 class="focus-headline" style="font-size:19px">3M · 6M · 12M</h3><div class="flow-track">'+['3m','6m','12m'].map(k=>'<div class="flow-item"><label>'+k.toUpperCase()+'</label><p><b>'+fmt(ois?.horizons?.[k]?.rate,3)+'%</b> · '+date(ois?.horizons?.[k]?.as_of)+'</p></div>').join('')+'</div><p class="source-caption">'+esc(ois?.kind||'Strumento non disponibile')+' · '+esc(ois?.quality||'Qualità da verificare')+'</p>'+routeLink('rates','Apri OIS & tassi ↗')+'</section>'
 +'<section class="panel"><span class="mini-overline">03 / COT</span><h3 class="focus-headline" style="font-size:19px">Come sono posizionati i fondi?</h3>'+qBadge(cot?.signal||'NON DISPONIBILE')+'<p class="focus-subtitle" style="margin:12px 0">'+esc(concise(cot?.today||'COT non caricato',245))+'</p><p class="source-caption">'+esc(cot?.w1||'')+'</p>'+routeLink('cot','Apri il positioning ↗')+'</section></div>'
 +'<div class="notice" style="margin-top:18px"><strong>Attenzione ai confronti:</strong> government yield, OIS e futures secondari hanno convenzioni diverse. Non usare direttamente lo spread tra strumenti diversi come segnale FX.</div>';
}
function pairs(){
 const all=eurPairs(),keys=pairListKeys(),s=all[state.pair]?.setup,fr=all[state.pair]?.decision_frame||s?.structural||{},price=s?.price,qual=pQuality(s);
 const d=all[state.pair]?.relative_dynamics||{};
 const watchLabel=state.watch.has(state.pair)?'★ Nella watchlist':'☆ Salva per dopo';
 return pageHero('FX / PAIR EXPLORER','28 coppie. <em>Una tesi alla volta.</em>','Qui non cerchiamo soltanto chi è forte. Leggiamo vantaggio macro, pricing, COT, prezzo e soprattutto cosa potrebbe smentire la tesi.')
 +'<div class="grid tilted"><section class="panel"><div class="panel-head"><div><span class="mini-overline">ESPLORA E FILTRA</span><h2>Il tuo universo FX</h2><p>Prezzi ECB: '+date(get('pairs')?.price_asof)+' · '+Object.keys(all).length+' coppie</p></div></div><div class="filters"><input id="pair-search" class="input" type="search" placeholder="Cerca EUR/USD, AUDCAD..." autocomplete="off" value="'+esc(state.pairSearch)+'" aria-label="Cerca coppia FX"><div class="filter-group" id="pair-filters">'+choose('',pairFilterOptions(),state.pairFilter,'data-pfilter')+'</div></div><div class="pair-list" id="pair-results">'+(keys.length?keys.map(k=>pairRow(k)).join(''):'<div class="empty"><strong>Nessuna coppia</strong><p>Prova a cambiare filtro o ricerca.</p></div>')+'</div><p class="source-caption">“Pulito”, “Con rischi”, “Da confermare” e “Non valutabile” sono stati del motore, non raccomandazioni operative.</p></section>'
 +'<div class="grid"><section class="panel glow"><div class="focus-row"><span class="mini-overline">PAIR DEEP DIVE</span>'+qBadge(qual)+'</div><h2 class="focus-headline">'+(s?esc(s.pair||getPairName(state.pair)):'Seleziona una coppia')+'</h2><p class="focus-subtitle">'+esc(s?.structural?.relation||fr?.relation||'Scegli una coppia per leggere la relazione tra macro e prezzi.')+'</p><div style="display:flex;gap:8px;flex-wrap:wrap;margin:17px 0"><button class="watch-btn '+(state.watch.has(state.pair)?'saved':'')+'" type="button" data-watch="'+state.pair+'">'+watchLabel+'</button><span class="badge info">Prezzo '+date(get('pairs')?.price_asof)+'</span></div>'
 +'<div class="lens-grid"><div class="lens"><label>Struttura</label><strong>'+esc(s?.structuralFav?'Vantaggio: '+s.structuralFav:'Non definita')+'</strong><p>'+esc(concise(fr.quality||'Da confermare',130))+'</p></div><div class="lens"><label>Prezzo</label><strong>'+esc(price?.text||'Non classificato')+'</strong><p>'+esc(concise(fr.priceNote||'',120))+'</p></div><div class="lens"><label>Timing</label><strong>'+esc(concise(s?.timing?.text,70))+'</strong></div><div class="lens"><label>COT</label><strong>'+esc(concise(s?.cot?.text,145))+'</strong></div></div></section>'
 +'<section class="panel"><div class="panel-head"><div><span class="mini-overline">DALLA TESI ALLA DECISIONE</span><h2>Cosa deve succedere adesso?</h2></div></div><div class="flow-track"><div class="flow-item"><label>Confermerebbe</label><p>'+esc(fr.priceNote||s?.price?.text||'Prezzo e pricing da verificare')+'</p></div><div class="flow-item"><label>Invalida / frena</label><p>'+esc(fr.missing||'Mancano conferme da macro, tassi e prezzo.')+'</p></div><div class="flow-item"><label>Monitorare</label><p>'+esc(fr.watch||s?.structural?.watch||'Aspettare una conferma osservabile, non dedurre ingressi automatici.')+'</p></div></div></section></div></div>'
 +'<div class="data-status"><span class="live-dot"></span><div>La watchlist è salvata esclusivamente in questo browser. Nessuna coppia rappresenta un ordine, un segnale di ingresso o una stima di rendimento futuro.</div></div>';
}
function macro(){
 const m=get('macro')?.currencies||{},c=state.ccy,row=m[c]||{},metric=state.macroMetric,series=row[metric]||{},other=row[metric==='inflation'?'labour':'inflation']||{};
 const h=Array.isArray(series.history)?series.history.filter(finite):[];
 const nums=h.slice(-60).map((v,i)=>({label:'Obs '+String(Math.max(1,h.length-Math.min(h.length,60)+i+1)),value:v}));
 return pageHero('MACRO / DYNAMIC LAB','Il dato conta. <em>Il cambiamento di più.</em>','Livello → Direzione → Velocità → Accelerazione → Turning point. Scegli paese e variabile: leggi la dinamica, non soltanto l’ultimo numero.')
 +'<div class="macro-grid">'+FX.map(k=>{const x=m[k];return '<button class="macro-tile" type="button" data-ccy="'+k+'" aria-pressed="'+String(k===c)+'"><strong>'+FLAGS[k]+' '+k+'</strong><span class="macro-detail">Inflazione · '+esc(x?.inflation?.as_of||'n.d.')+'</span><span class="mini-number">'+fmt(x?.inflation?.latest_value,1)+'%</span></button>'}).join('')+'</div>'
 +sectionTitle(FLAGS[c]+' '+NAMES[c]+' · Esplora le serie','Selezione interattiva')
 +'<div class="grid tilted"><section class="panel glow"><div class="panel-head"><div><span class="mini-overline">SERIE MACRO / '+esc(c)+'</span><h2>'+esc(series.label||'Seleziona una serie')+'</h2><p>Ultimo dato: '+esc(series.as_of||'n.d.')+' · '+h.length+' osservazioni storiche</p></div><div class="pill-controls">'+choose('',[{label:'Inflazione',value:'inflation'},{label:'Lavoro',value:'labour'}],metric,'data-metric')+'</div></div>'
 +'<div class="metric-split"><div class="stat"><small>Livello</small><strong>'+fmt(series.latest_value,2)+(metric==='inflation'?'%':'%')+'</strong></div><div class="stat"><small>Direzione</small><strong style="font-size:15px">'+esc(series.direction||'—')+'</strong></div><div class="stat"><small>Accelerazione</small><strong style="font-size:15px">'+esc(series.acceleration||'—')+'</strong></div></div>'
 +'<div style="margin-top:18px">'+plot({lines:[{name:series.label||'Serie macro',color:metric==='inflation'?'#eb7585':'#8bbfeb',values:nums}],unit:'%',label:'Serie '+(series.label||'macro')+', osservazioni ordinate',axisDates:false})+'</div>'
 +'<p class="source-caption">Questa serie non include date per ogni punto dello storico nell’overlay corrente: l’asse indica la sequenza, non mesi attribuiti artificialmente. Fonte '+esc(series.source||'da verificare')+'.</p></section>'
 +'<section class="panel"><div class="panel-head"><div><span class="mini-overline">COME LEGGERE I DATI</span><h2>Quando una variazione conta davvero?</h2></div></div><div class="flow-track"><div class="flow-item"><label>Livello</label><p>'+esc(series.label||'La variabile')+' è al '+fmt(series.latest_value,2)+'%. Un livello elevato o basso non equivale da solo a un segnale FX.</p></div><div class="flow-item"><label>Direzione</label><p>'+esc(series.direction||'Non classificata')+'. Conta se la variazione persiste rispetto al passato, non il singolo dato.</p></div><div class="flow-item"><label>Accelerazione</label><p>'+esc(series.acceleration||'Non classificata')+'. Anche un indicatore che sale può iniziare a perdere velocità.</p></div><div class="flow-item"><label>Altra dimensione</label><p>'+esc(other.label||'Altra serie')+': '+fmt(other.latest_value,2)+'% · '+esc(other.direction||'n.d.')+' · '+esc(other.as_of||'n.d.')+'.</p></div></div></section></div>'
 +sectionTitle('Heatmap G8','Un confronto descrittivo, non un ranking tra economie')
 +'<section class="panel"><div class="table-wrap"><table class="data-table"><thead><tr><th>Economia</th><th>Inflazione</th><th>Direzione</th><th>Disoccupazione</th><th>Direzione</th><th>Ultimo CPI</th></tr></thead><tbody>'+FX.map(k=>{const x=m[k];return '<tr class="'+(k===c?'active':'')+'"><td><button type="button" data-ccy="'+k+'">'+FLAGS[k]+' '+k+'</button></td><td>'+fmt(x?.inflation?.latest_value,1)+'%</td><td>'+esc(x?.inflation?.direction||'—')+'</td><td>'+fmt(x?.labour?.latest_value,1)+'%</td><td>'+esc(x?.labour?.direction||'—')+'</td><td>'+esc(x?.inflation?.as_of||'—')+'</td></tr>'}).join('')+'</tbody></table></div></section>';
}
function rates(){
 const c=state.ccy,other=state.against;
 const a=currencyInfo(c),b=currencyInfo(other),r=a.rate,rr=b.rate,common=historyRates(c).slice(-Number(state.window));
 const govDiff=finite(r?.['2Y'])&&finite(rr?.['2Y'])?(r['2Y']-rr['2Y'])*100:null;
 return pageHero('RATES / MARKET PRICING','I tassi non sono <em>una sola storia.</em>','Front-end, long-end, curva e aspettative di banca centrale. Distinguiamo Treasury e governativi da OIS e futures, con scadenze e date esplicite.')
 +'<div class="panel glow"><div class="focus-row"><div><span class="mini-overline">RATE EXPLORER</span><h2 class="focus-headline" style="font-size:23px">'+FLAGS[c]+' '+c+' · Rendimenti & pricing</h2></div><div class="select-controls"><select class="select" id="rate-country" aria-label="Scegli valuta">'+FX.map(k=>'<option value="'+k+'" '+(k===c?'selected':'')+'>'+FLAGS[k]+' '+k+'</option>').join('')+'</select><span class="mini-overline">vs</span><select class="select" id="rate-compare" aria-label="Scegli valuta di confronto">'+FX.filter(k=>k!==c).map(k=>'<option value="'+k+'" '+(k===other?'selected':'')+'>'+FLAGS[k]+' '+k+'</option>').join('')+'</select></div></div><div class="divider"></div>'
 +'<div class="metric-split"><div class="stat"><small>Gov 2Y</small><strong>'+fmt(r?.['2Y'])+'%</strong><em>'+date(r?.date)+'</em></div><div class="stat"><small>Gov 10Y</small><strong>'+fmt(r?.['10Y'])+'%</strong><em>'+date(r?.date)+'</em></div><div class="stat"><small>Spread '+c+' − '+other+' · 2Y</small><strong>'+sign(govDiff,1,' pb')+'</strong><em>'+date(r?.date)+' / '+date(rr?.date)+'</em></div></div>'
 +'<p class="source-caption">2Y differenziale indicativo tra rendimenti sovrani. Date '+(r?.date===rr?.date?'coincidenti':'non coincidenti')+'; curva e tipo di benchmark potrebbero differire. Non equivale a uno spread OIS o a un segnale FX.</p></div>'
 +sectionTitle('Il movimento dei rendimenti','Cambia finestra e scadenza')
 +'<div class="grid tilted"><section class="panel"><div class="panel-head"><div><span class="mini-overline">GOVERNMENT YIELDS</span><h2>'+c+' · Storico 2Y e 10Y</h2><p>'+esc(r?.source||'Fonte non caricata')+'</p></div></div><div class="filters"><div class="pill-controls">'+choose('',timeWindows,state.window,'data-window')+'</div><div class="pill-controls">'+choose('',[{label:'2Y + 10Y',value:'both'},{label:'Solo 2Y',value:'2y'},{label:'Solo 10Y',value:'10y'}],state.rateMode,'data-rate-mode')+'</div></div>'
 +ratesPlot(c)+'<div class="chart-summary" style="margin-top:12px">Ultimo movimento osservato: 2Y '+sign(r?.chg2_bp,1,' pb')+' · 10Y '+sign(r?.chg10_bp,1,' pb')+'. La causa richiede analisi macro e pricing.</div></section>'
 +'<section class="panel">'+oisDetail(c)+'</section></div>'
 +sectionTitle('Il perché dei prezzi','Tre fattori che vanno separati')
 +'<div class="story-steps"><div class="step"><span class="step-kicker"><span class="step-number">1</span> FRONT-END</span><h3>Banca centrale e percorso atteso</h3><p>OIS o futures indicativi aiutano a capire le aspettative. Un 2Y governativo da solo non basta ad attribuire la causa.</p></div><div class="step"><span class="step-kicker"><span class="step-number">2</span> LONG-END</span><h3>Crescita, inflazione e duration</h3><p>Nel 10Y possono pesare rendimenti reali, breakeven, term premium, offerta e domanda di titoli.</p></div><div class="step"><span class="step-kicker"><span class="step-number">3</span> MERCATO FX</span><h3>Contano i differenziali</h3><p>Confronta scadenze, date, qualità e prezzo prima di trasformare un differenziale in una tesi valutaria.</p></div></div>';
}
function cot(){
 const cot=get('cot')||{};
 return pageHero('COT / POSITIONING','Il positioning è <em>una fotografia, non un ordine.</em>','Stock, flussi settimanali e persistenza aiutano a leggere dove il mercato potrebbe essere affollato. Gli estremi richiedono conferme da prezzo e macro.')
 +'<div class="currency-grid">'+FX.map(k=>{const c=cot[k];return '<button class="currency-chip" type="button" data-ccy="'+k+'" aria-pressed="'+String(k===state.ccy)+'"><span class="flag">'+FLAGS[k]+'</span><strong>'+k+'</strong><span class="meta">'+esc(concise(c?.signal||'Non disponibile',40))+'</span><span class="latest" style="font-size:10px">'+esc(concise(c?.w1||'Nessun aggiornamento',65))+'</span></button>'}).join('')+'</div>'
 +sectionTitle(FLAGS[state.ccy]+' '+state.ccy+' · Il posizionamento dei fondi','CFTC con data propria')
 +'<div class="grid tilted"><section class="panel glow"><div class="focus-row"><span class="mini-overline">CFTC / POSITIONING MONITOR</span>'+qBadge(cot[state.ccy]?.signal||'NON VALIDATO')+'</div><h2 class="focus-headline" style="font-size:24px">Com’è cambiata la posizione?</h2><p class="focus-subtitle" style="font-size:13px;margin:14px 0">'+esc(cot[state.ccy]?.today||'Nessun dato COT verificato')+'</p><div class="flow-track"><div class="flow-item"><label>1 settimana</label><p>'+esc(cot[state.ccy]?.w1||'Dato non disponibile')+'</p></div><div class="flow-item"><label>4 settimane</label><p>'+esc(cot[state.ccy]?.w4||'Dato non disponibile')+'</p></div><div class="flow-item"><label>Fondi</label><p>'+esc(cot[state.ccy]?.funds_detail||'Nessun dettaglio')+'</p></div></div></section>'
 +'<section class="panel"><div class="panel-head"><div><span class="mini-overline">LETTURA DELLA QUALITÀ</span><h2>Quando uno stock estremo conta</h2></div></div><p class="focus-subtitle">'+esc(cot[state.ccy]?.why||'Il COT deve essere analizzato con prezzo e dati macro.')+'</p><div class="divider"></div><div class="notice warn"><strong>Prezzo non confermato:</strong> '+esc(cot[state.ccy]?.price_detail||'Il collegamento fra COT e prezzo richiede verifiche specifiche.')+'</div><p class="source-caption">Un valore estremo e un flusso che si muove rapidamente sono due condizioni diverse. La classificazione storica non indica necessariamente un trade da aprire.</p></section></div>';
}
function risk(){
 const streams=get('risk')?.streams||{},a=streams[state.riskStream],x=riskAligned();
 const streamOpts=[['SP500','S&P 500'],['NASDAQCOM','Nasdaq'],['VIX','VIX'],['IG_OAS','Credito IG'],['HY_OAS','Credito HY']];
 const pts=priceHistory(state.riskStream).slice(-Number(state.riskWindow));
 return pageHero('CROSS-ASSET / RISK RADAR','Il rischio non ha <em>un solo termometro.</em>','Unisci azionario, volatilità e credito. Tocca un indicatore per esplorare le serie; le conferme valgono soltanto quando gli orologi sono coerenti.')
 +'<div class="grid cols-4">'+stat('S&P 500',fmt(streams.SP500?.value),date(streams.SP500?.date),sign(streams.SP500?.change_1d_pct,2,'%'),streams.SP500?.change_1d_pct>0?'up':'down')
 +stat('Nasdaq Composite',fmt(streams.NASDAQCOM?.value),date(streams.NASDAQCOM?.date),sign(streams.NASDAQCOM?.change_1d_pct,2,'%'),streams.NASDAQCOM?.change_1d_pct>0?'up':'down')
 +stat('VIX',fmt(streams.VIX?.value),date(streams.VIX?.date),sign(streams.VIX?.change_1d_pct,2,'%'),streams.VIX?.change_1d_pct>0?'down':'up')
 +stat('HY OAS',fmt(streams.HY_OAS?.value)+'%',date(streams.HY_OAS?.date),finite(streams.HY_OAS?.previous)?sign((streams.HY_OAS.value-streams.HY_OAS.previous)*100,0,' pb'):'',streams.HY_OAS?.value>streams.HY_OAS?.previous?'down':'up')+'</div>'
 +sectionTitle('Risk Radar interattivo','Cinque stream, nessun proxy confuso con un altro')
 +'<div class="grid tilted"><section class="panel"><div class="panel-head"><div><span class="mini-overline">CROSS-ASSET / SCELTA LIBERA</span><h2>'+esc(streamOpts.find(v=>v[0]===state.riskStream)?.[1]||state.riskStream)+'</h2><p>'+esc(a?.publisher||'Fonte da verificare')+' · '+date(a?.date)+'</p></div></div><div class="filters"><div class="pill-controls">'+streamOpts.map(v=>'<button class="pill '+(v[0]===state.riskStream?'active':'')+'" data-risk="'+v[0]+'" type="button" aria-pressed="'+String(v[0]===state.riskStream)+'">'+v[1]+'</button>').join('')+'</div><div class="pill-controls">'+choose('',[{label:'5 sedute',value:5},{label:'20 sedute',value:20},{label:'Tutto',value:9999}],state.riskWindow,'data-risk-window')+'</div></div>'
 +plot({lines:[{name:streamOpts.find(v=>v[0]===state.riskStream)?.[1],color:state.riskStream==='VIX'||state.riskStream.includes('OAS')?'#ed6679':'#83cdec',values:pts}],unit:state.riskStream.includes('OAS')?'%':'',label:'Grafico '+state.riskStream})+'<div class="chart-summary" style="margin-top:11px">Ultima rilevazione: '+fmt(a?.value)+' · Variazione giornaliera '+sign(a?.change_1d_pct,2,'%')+'. '+esc(a?.not_intraday?'Dato di chiusura, non intraday.':'Verificare orario di rilevazione.')+'</div></section>'
 +'<section class="panel glow"><span class="mini-overline">REGIME / INTERPRETAZIONE</span><h2 class="focus-headline" style="font-size:22px">'+esc(x.assessment)+'</h2><p class="focus-subtitle">Il rischio si legge meglio quando azioni, credito e volatilità si muovono nello stesso intervallo.</p><div class="divider"></div><div class="flow-track"><div class="flow-item"><label>Nasdaq</label><p>'+date(x.n?.date)+' · '+sign(x.n?.change_1d_pct,2,'%')+'</p></div><div class="flow-item"><label>VIX</label><p>'+date(x.v?.date)+' · '+fmt(x.v?.value)+'</p></div><div class="flow-item"><label>HY OAS</label><p>'+date(x.h?.date)+' · '+fmt(x.h?.value)+'%</p></div></div>'+(x.same?'<div class="notice" style="margin-top:14px">Date allineate: puoi descrivere la co-occorrenza, non attribuire automaticamente la causa.</div>':'<div class="notice warn" style="margin-top:14px">Date differenti: non attribuiamo simultaneità a movimenti che possono appartenere a sedute diverse.</div>')+'</section></div>';
}
function news(){
 const n=get('news'),items=(n?.items||[]),official=n?.official_releases?.headlines||[];
 const list=state.newsMode==='pulse'?items:official;
 return pageHero('NEWS / EVENT MONITOR','Meno rumore. <em>Più contesto.</em>','Le novità servono solo se cambiano la lettura di Macro, tassi o prezzo. Ogni voce riporta data e origine, senza attribuire reazioni causali non misurate.')
 +'<div class="filters"><div class="pill-controls">'+choose('',[{label:'Market Pulse',value:'pulse'},{label:'Comunicazioni ufficiali',value:'official'}],state.newsMode,'data-news-mode')+'</div><span class="data-date">Contenuti market pulse: '+date(n?.content_as_of)+' · '+items.length+' aggiornamenti</span></div>'
 +'<div class="grid tilted"><section class="panel"><div class="panel-head"><div><span class="mini-overline">EVENT FEED / DATATO</span><h2>'+(state.newsMode==='pulse'?'Le notizie che meritano attenzione':'Comunicazioni degli emittenti')+'</h2></div></div><div class="timeline">'+(list.length?list.slice(0,20).map(x=>'<article class="timeline-item"><span class="mini-overline">'+esc(x.ccy||x.source||x.category||'Fonte')+' · '+date(x.as_of||x.published_at||x.date)+'</span><h3>'+esc(x.title||x.headline||'Comunicazione')+'</h3><p>'+esc(x.detail||x.summary||x.description||'Apri la fonte ufficiale per il dettaglio.')+'</p></article>').join(''):'<div class="empty"><strong>Nessuna voce validata</strong></div>')+'</div></section>'
 +'<section class="panel glow"><span class="mini-overline">METODO / NEWS</span><h2 class="focus-headline" style="font-size:22px">Un evento non spiega sempre una candela.</h2><p class="focus-subtitle">Per affermare che il mercato ha reagito a un dato, servono confronti prima/dopo sullo stesso strumento e su un orario coerente.</p><div class="divider"></div><div class="flow-track"><div class="flow-item"><label>Fatto</label><p>Che cosa è stato pubblicato, da chi e quando.</p></div><div class="flow-item"><label>Surprise</label><p>Se disponibile: effettivo meno consenso, distinto da revisione del dato precedente.</p></div><div class="flow-item"><label>Market pricing</label><p>Quale curva o futures hanno reagito. Se non è verificato, la causa rimane un’ipotesi.</p></div></div></section></div>';
}
function render(){
 const route=ROUTES[state.route]?state.route:'overview';
 state.charts={};state.chartIndex=0;
 const views={overview,currencies,pairs,macro,rates,cot,risk,news};
 $('content').innerHTML=views[route]();
 $('crumb-page').textContent=ROUTES[route];
 document.querySelectorAll('#nav [data-route]').forEach(a=>{if(a.dataset.route===route)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
 const ok=Object.keys(state.data).length,missing=Object.keys(SOURCES).length-ok;
 const dates=[get('rates')?.USD?.date,get('dxy')?.as_of,get('pairs')?.price_asof].filter(validDay);
 $('top-asof').textContent='Riferimenti '+(dates.length?dates.map(date).join(' · '):'da verificare');
 $('top-quality').classList.toggle('warn',missing>0);
 $('top-quality').innerHTML='<span class="live-dot"></span>'+(missing===0?'FEED DISPONIBILI':ok+'/'+Object.keys(SOURCES).length+' FEED');
 $('sidebar-feed').textContent=ok+'/'+Object.keys(SOURCES).length+' fonti caricate · dati non intraday';
 document.title='FX Quant Next — '+ROUTES[route];
}
function saveWatch(){try{localStorage.setItem('fxquant-next-watch',JSON.stringify([...state.watch]))}catch(e){}}
function navigate(){
 const route=location.hash.slice(1).split('?')[0]||'overview';
 state.route=ROUTES[route]?route:'overview';render();window.scrollTo({top:0,behavior:'instant'});
 $('app').classList.remove('menu-open');$('menu-toggle').setAttribute('aria-expanded','false');
}
window.addEventListener('hashchange',navigate);
$('menu-toggle').addEventListener('click',()=>{const open=!$('app').classList.contains('menu-open');$('app').classList.toggle('menu-open',open);$('menu-toggle').setAttribute('aria-expanded',String(open))});
$('mobile-overlay').addEventListener('click',()=>{$('app').classList.remove('menu-open');$('menu-toggle').setAttribute('aria-expanded','false')});
document.addEventListener('click',e=>{
 const c=e.target.closest('[data-ccy]');if(c){state.ccy=c.dataset.ccy;if(state.against===state.ccy)state.against=FX.find(k=>k!==state.ccy);render();return}
 const p=e.target.closest('[data-pair]');if(p){state.pair=p.dataset.pair;if(state.route==='overview')location.hash='#pairs';else render();return}
 const f=e.target.closest('[data-pfilter]');if(f){state.pairFilter=f.dataset.pfilter;render();return}
 const w=e.target.closest('[data-watch]');if(w){state.watch.has(w.dataset.watch)?state.watch.delete(w.dataset.watch):state.watch.add(w.dataset.watch);saveWatch();render();return}
 const a=e.target.closest('[data-window]');if(a){state.window=Number(a.dataset.window);render();return}
 const b=e.target.closest('[data-rate-mode]');if(b){state.rateMode=b.dataset.rateMode;render();return}
 const k=e.target.closest('[data-metric]');if(k){state.macroMetric=k.dataset.metric;render();return}
 const rs=e.target.closest('[data-risk]');if(rs){state.riskStream=rs.dataset.risk;render();return}
 const rw=e.target.closest('[data-risk-window]');if(rw){state.riskWindow=Number(rw.dataset.riskWindow);render();return}
 const nn=e.target.closest('[data-news-mode]');if(nn){state.newsMode=nn.dataset.newsMode;render();return}
});
document.addEventListener('input',e=>{if(e.target.id==='pair-search'){state.pairSearch=e.target.value;const list=$('pair-results');if(!list)return;const keys=pairListKeys();list.innerHTML=keys.length?keys.map(k=>pairRow(k)).join(''):'<div class="empty"><strong>Nessuna coppia trovata</strong><p>Prova un nome o un filtro diverso.</p></div>';}})
document.addEventListener('change',e=>{
 if(e.target.id==='rate-country'){state.ccy=e.target.value;if(state.against===state.ccy)state.against=FX.find(k=>k!==state.ccy);render();}
 if(e.target.id==='rate-compare'){state.against=e.target.value;render();}
});
document.addEventListener('pointermove',chartEvents);
document.addEventListener('pointerout',e=>{if(e.target.closest('.chart')&&!e.relatedTarget?.closest?.('.chart'))chartHide(e)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('app').classList.remove('menu-open');$('menu-toggle').setAttribute('aria-expanded','false')}});
async function loadAll(){
 const jobs=Object.entries(SOURCES).map(async([key,path])=>{
  const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),10000);
  try{
   const r=await fetch(path,{cache:'no-store',signal:ctl.signal});
   if(!r.ok)throw Error('HTTP '+r.status);
   const d=await r.json();
   if(d===null||typeof d!=='object')throw Error('JSON non valido');
   if(key==='pairs'&&d.pair_count!==28)throw Error('28 coppie non validate');
   if(key==='risk'&&!d.streams)throw Error('Stream cross-asset mancanti');
   if(key==='ois'&&!d.currencies)throw Error('Pricing assente');
   if(key==='dxy'&&d.not_official_ice!==true)throw Error('DXY non classificato');
   state.data[key]=d;
  }catch(e){state.errors[key]=String(e.message||e);}
  finally{clearTimeout(timer)}
 });
 await Promise.allSettled(jobs);
 render();
}
navigate();
loadAll();
})();
