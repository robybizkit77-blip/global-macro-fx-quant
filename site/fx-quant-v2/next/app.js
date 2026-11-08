'use strict';
/* FX Quant NEXT - Independent user-experience prototype.
 * The operational FX engine, pricing and source files remain read-only.
 * No invented live quotes, synthetic rankings, or automatic trade signals.
 */
(function(){
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',AUD:'🇦🇺',NZD:'🇳🇿',CAD:'🇨🇦'};
const NAMES={USD:'Stati Uniti',EUR:'Area euro',GBP:'Regno Unito',JPY:'Giappone',CHF:'Svizzera',AUD:'Australia',NZD:'Nuova Zelanda',CAD:'Canada'};
const ROUTES={overview:'La ricerca',currencies:'Valute G8',pairs:'Coppie FX',macro:'Scenario macro',rates:'Tassi & OIS',cot:'COT',risk:'Rischio',news:'Notizie'};
const SOURCES={
 rates:'../../../live_data/sections/NATIVE_RATES_DATA.json',
 dxy:'../../../live_data/sections/DXY_SYNTHETIC_ECB.json',
 currencyPrices:'../../../live_data/sections/ECB_G8_PRICE_HISTORY.json',
 pairs:'../../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json',
 macro:'../../../live_data/sections/MACRO_THERMOMETER_DATA.json',
 macroSeries:'../../../live_data/sections/MACRO_SERIES.json',
 cb:'../../../live_data/sections/NATIVE_CB_DATA.json',
 cot:'../../../live_data/sections/V247_COT_STORIES.json',
 cotHistory:'../../../live_data/sections/V250_COT_CHART_DATA.json',
 cotPrice:'../design-studio-cot-v1-data.json',
 risk:'../cross-asset-live-data.json',
 ois:'../ois-pricing-snapshot.json',
 news:'../../../live_data/sections/NEWS_PULSE_OPERATIONAL.json',
 themes:'../../../live_data/sections/TOP_THEMES.json'
};
const state={data:{},errors:{},route:'overview',ccy:'USD',against:'EUR',pair:'EURUSD',pairFilter:'all',pairSearch:'',watch:new Set(),window:20,rateMode:'both',riskStream:'VIX',riskWindow:20,macroMetric:'inflation',newsMode:'pulse',chartIndex:0,charts:{},atlasLens:'rates',homeChart:null,homeWindow:20,spotPair:'EURUSD',cotWindow:26,cotMode:'net',cotFilter:'all',cotSort:'percentile',cotSortAsc:false,rsWindow:60,rsGovMode:'both',rsDiffMode:'2y',msCategory:'Inflazione',msSeriesId:null,msView:'level',msWindow:24,msHeat:'inflation',msHeatSort:'ccy',msHeatAsc:true,msOther:'EUR',msCompareMetric:'inflation',msAdvanced:false,csOther:'EUR',csPriceWindow:60,csRatesMode:'spread',csRatesWindow:60,csMacroMode:'inflation',csMacroWindow:36,csCotWindow:26,csSort:'currency',csReturnWindow:20};
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

function atlasEvidence(key){
 const u=get('rates')?.USD, d=get('dxy'),m=get('macro')?.currencies?.USD,ri=get('risk')?.streams||{},p=get('ois')?.currencies?.USD;
 const rr=riskAligned(),validR=finite(u?.['2Y'])&&finite(u?.chg2_bp)&&validDay(u?.date),validD=finite(d?.value)&&finite(d?.previous_value)&&d.previous_value!==0;
 const dd=validD?(d.value/d.previous_value-1)*100:null;
 const info={
  macro:{
   eyebrow:'01 / MACRO DYNAMICS',name:'MACRO',metric:finite(m?.inflation?.latest_value)?fmt(m.inflation.latest_value,2)+'%':'—',tag:'CPI USA · '+esc(m?.inflation?.as_of||'n.d.'),
   headline:'L’inflazione accelera o perde slancio?',main:finite(m?.inflation?.latest_value)?'L’ultimo CPI USA nel feed è '+fmt(m.inflation.latest_value,2)+'%, con direzione '+esc(m.inflation.direction||'n.d.').toLowerCase()+' e dinamica '+esc(m.inflation.acceleration||'n.d.').toLowerCase()+'.':'La serie CPI non è validata.',
   secondary:'Un livello elevato e una nuova accelerazione non sono sinonimi. Per capire se la politica monetaria cambia servono sorpresa, composizione e persistenza.',check:'Confrontare dati lavoro e inflazione core con le attese, non soltanto l’headline.',date:m?.inflation?.as_of||'',next:'Apri Macro Lab',route:'macro',kind:'Osservazione macro',tone:'amber'
  },
  rates:{
   eyebrow:'02 / FRONT-END & EXPECTATIONS',name:'RATES',metric:validR?sign(u.chg2_bp,1,' pb'):'—',tag:'Treasury 2Y · '+date(u?.date),
   headline:validR?(u.chg2_bp<0?'Il 2Y scende. È repricing Fed?':'Il 2Y si muove. Qual è la causa?'):'Front-end non verificato',
   main:validR?'Al '+date(u.date)+' il Treasury 2Y è '+fmt(u['2Y'])+'% e varia di '+sign(u.chg2_bp,1,' pb')+'. La variazione è osservata. Il suo motivo non è dimostrato.':'Rendimento e variazione non disponibili in modo validato.',
   secondary:'L’OIS/Fed funds futures è la verifica più utile del percorso atteso. Non mescoliamo tasso governativo e OIS come se fossero lo stesso strumento.',
   check:'Prezzi 3M/6M/12M USA: '+(finite(p?.horizons?.['6m']?.rate)?fmt(p.horizons['6m'].rate,3)+'% sul 6M ('+date(p.horizons['6m'].as_of)+', '+esc(p.quality||'')+').':'Dato 6M non validato.')+' Confrontare a orari e basi coerenti.',
   date:u?.date||'',next:'Esplora tassi & OIS',route:'rates',kind:'Rendimenti osservati',tone:'blue'
  },
  fx:{
   eyebrow:'03 / DOLLAR & CONFIRMATION',name:'FX',metric:validD?sign(dd,2,'%'):'—',tag:'DXY proxy · '+date(d?.as_of),
   headline:'Il dollaro sta confermando la storia?',
   main:validD?'Il proxy DXY ricavato da fixing BCE varia di '+sign(dd,2,'%')+' fino al '+date(d.as_of)+'. È un indicatore giornaliero, non il DXY ICE e non una quotazione intraday.':'Nessuna variazione del proxy DXY con data validata.',
   secondary:'Anche quando 2Y e USD si muovono insieme è una co-occorrenza, non una dimostrazione causale. Contano risk sentiment e prezzi delle singole coppie.',
   check:validR&&validD&&u.date===d.as_of?'Il confronto 2Y/DXY è sulla stessa data: esamina se la direzione è coerente, poi verifica le coppie.':'Le date 2Y e USD non coincidono o i dati sono incompleti: la conferma giornaliera resta sospesa.',
   date:d?.as_of||'',next:'Esplora le valute',route:'currencies',kind:'Prezzo proxy, non indice ICE',tone:'green'
  },
  risk:{
   eyebrow:'04 / CROSS-ASSET',name:'RISK',metric:finite(ri.VIX?.value)?fmt(ri.VIX.value):'—',tag:'VIX · '+date(ri.VIX?.date),
   headline:'Lo stress si sta propagando?',
   main:finite(ri.VIX?.value)?'VIX a '+fmt(ri.VIX.value)+' al '+date(ri.VIX.date)+'. '+(finite(ri.HY_OAS?.value)?'Lo spread HY è '+fmt(ri.HY_OAS.value)+'% al '+date(ri.HY_OAS.date)+'.':'Spread credito non disponibile.'):'Non sono disponibili osservazioni VIX validate.',
   secondary:rr.same?'Nasdaq, VIX e HY hanno la stessa data; questo consente di verificare movimenti congiunti, senza attribuire automaticamente causalità.':'Azionario, volatilità e credito hanno timestamp differenti: evitare una lettura simultanea impropria.',
   check:'Valutare se il prezzo azionario conferma l’aumento di volatilità e se il credito amplifica o assorbe lo shock.',
   date:ri.VIX?.date||'',next:'Apri Risk Radar',route:'risk',kind:'Mercati correlati, non causalità',tone:'red'
  }
 };
 return info[key]||info.rates;
}
function homeScreenChart(){
 let keys=state.homeChart||researchCase().focus,w=Number(state.homeWindow||20),lines=[],label='',unit='',result='',asof='';
 const u=get('rates')?.USD,d=get('dxy'),r=get('risk')?.streams||{};
 if(keys==='nasdaq'){
  const a=r.NASDAQCOM;
  lines=[{name:'Nasdaq Composite',color:'#95d8ef',values:priceHistory('NASDAQCOM').slice(-w)}];
  label='Azionario USA · Nasdaq Composite';unit='';asof=a?.date;
  result='Variazione giornaliera '+sign(a?.change_1d_pct,2,'%')+' al '+date(a?.date)+'. Fonte '+String(a?.publisher||'non disponibile')+'. Chiusura daily, non intraday.';
 }else if(keys==='rates'){
  const a=historyRates('USD').slice(-w);
  lines=[{name:'Treasury 2Y',color:'#95d8ef',values:a.map(x=>({label:x.label,value:x.v2}))},{name:'Treasury 10Y',color:'#ef6479',values:a.map(x=>({label:x.label,value:x.v10}))}];
  label='UST · Front-end e long-end';unit='%';asof=u?.date;
  result='2Y '+sign(u?.chg2_bp,1,' pb')+' · 10Y '+sign(u?.chg10_bp,1,' pb')+'. Sono rendimenti, non OIS.';
 }else if(keys==='dxy'){
  lines=[{name:'DXY proxy BCE',color:'#86dfba',values:dxyHistory().slice(-w)}];label='Dollaro · fixing BCE';asof=d?.as_of;
  result='Proxy sintetico, non indice ICE o prezzo intraday.';
 }else{
  const s=r[keys==='vix'?'VIX':'HY_OAS'];
  lines=[{name:keys==='vix'?'VIX':'HY OAS',color:keys==='vix'?'#ef6578':'#ebba79',values:priceHistory(keys==='vix'?'VIX':'HY_OAS').slice(-w)}];label=keys==='vix'?'Volatilità · VIX':'Credito · High Yield OAS';asof=s?.date;
  unit=keys==='hy'?'%':'';
  result='Fonte '+String(s?.publisher||'non disponibile')+'. Serie daily close, non intraday.';
 }
 return '<div class="analysis-chart-head"><div><span class="micro-over">LAB / DATI DATATI</span><h3>'+esc(label)+'</h3></div><span class="time-label">Ultimo '+date(asof)+'</span></div>'
 +'<div class="analyst-toolbar"><div class="chart-tabset">'+choose('',[{label:'Nasdaq',value:'nasdaq'},{label:'2Y / 10Y',value:'rates'},{label:'USD proxy',value:'dxy'},{label:'VIX',value:'vix'},{label:'HY',value:'hy'}],keys,'data-hchart')+'</div><div class="chart-tabset">'+choose('',[{label:'5',value:5},{label:'20',value:20},{label:'60',value:60}],w,'data-hwindow')+'</div></div>'
 +plot({lines,unit,label:'Storico '+label,window:w})
 +'<div class="chart-footnote"><span class="footnote-dot"></span>'+esc(result)+' <strong>Le date delle serie restano indipendenti.</strong></div>';
}
function homePairPreview(k){
 const p=eurPairs()?.[k],s=p?.setup||{},f=p?.decision_frame||s?.structural||{},q=s?.quality||'NON VALUTABILE';
 return '<div class="pair-highlight-top"><span class="micro-over">DOSSIER FX / '+date(get('pairs')?.price_asof)+'</span>'+qBadge(q)+'</div>'
 +'<h3>'+esc(getPairName(k))+'<span class="pair-fav"> '+(s.structuralFav?'→ vantaggio '+esc(s.structuralFav):'')+'</span></h3>'
 +'<p>'+esc(f.relation||'Dossier in attesa di valutazione relativa.')+'</p>'
 +'<div class="pair-conditions"><span><b>PREZZO</b><strong>'+esc(s?.price?.text||'Non classificato')+'</strong></span><span><b>CONFERMA MANCANTE</b><strong>'+esc(concise(f.missing||'Da verificare',95))+'</strong></span></div>'
 +'<a class="text-link" href="#pairs">Apri la tesi completa <span>↗</span></a>';
}

/* Shared editorial case. Only same-session, sufficiently recent observations can lead
   the story. Monthly Macro and weekly COT are context, never intraday corroboration. */
function researchCase(){
 const r=get('risk')?.streams||{},u=get('rates')?.USD||{},d=get('dxy')||{};
 const pairDate=get('pairs')?.price_asof;
 const max=[r.NASDAQCOM?.date,r.VIX?.date,r.HY_OAS?.date,u.date,d.as_of,pairDate].filter(validDay).sort().pop()||null;
 const near=d=>validDay(d)&&validDay(max)&&d<=max&&
   (Date.parse(max+'T12:00:00Z')-Date.parse(d+'T12:00:00Z'))/864e5<=4;
 const n=r.NASDAQCOM||{},v=r.VIX||{},h=r.HY_OAS||{};
 const aligned=validDay(n.date)&&n.date===v.date&&n.date===h.date&&near(n.date)
   &&finite(n.change_1d_pct)&&finite(v.previous)&&finite(v.value)&&finite(h.previous)&&finite(h.value);
 const usRates=near(u.date)&&finite(u['2Y'])&&finite(u['10Y'])&&finite(u.chg2_bp)&&finite(u.chg10_bp);
 const fxAligned=near(d.as_of)&&d.as_of===u.date&&finite(d.value)&&finite(d.previous_value)&&d.previous_value!==0&&usRates;
 const usdDelta=fxAligned?(d.value/d.previous_value-1)*100:null;
 let kind='mixed';
 if(aligned&&n.change_1d_pct<=-1.5&&v.value>v.previous&&h.value>h.previous)kind='stress';
 else if(aligned&&n.change_1d_pct>=1.5&&v.value<v.previous&&h.value<h.previous)kind='relief';
 else if(usRates&&u.chg2_bp<=-2&&u.chg10_bp<=-2)kind='bond-rally';
 else if(usRates&&u.chg2_bp>=2&&u.chg10_bp>=2)kind='yield-selloff';
 else if(fxAligned&&Math.abs(u.chg2_bp)>=2&&Math.abs(usdDelta)>=.08&&u.chg2_bp*usdDelta<0)kind='fx-divergence';
 const leadDate=kind==='stress'||kind==='relief'?n.date:kind==='mixed'?max:u.date;
 const focus={stress:'nasdaq',relief:'nasdaq','bond-rally':'rates','yield-selloff':'rates','fx-divergence':'dxy',mixed:'rates'}[kind];
 return {kind,leadDate,latest:max,focus,aligned,usRates,fxAligned,n,v,h,u,d,usdDelta};
}
function researchEvidence(ctx){
 const {kind,n,v,h,u,d,leadDate}=ctx;
 const rows=[];
 const add=(title,move,detail,day,source)=>{if(validDay(day)&&day===leadDate&&move!=='—')rows.push({title,move,detail,day,source});};
 if(kind==='stress'||kind==='relief'){
  add('Nasdaq Composite',sign(n.change_1d_pct,2,'%'),'Chiusura rispetto alla seduta precedente',n.date,'Nasdaq / FRED');
  add('Volatilità VIX',sign(v.value-v.previous,2,' pt'),'Da '+fmt(v.previous,2)+' a '+fmt(v.value,2),v.date,'Cboe');
  add('Credito High Yield',sign((h.value-h.previous)*100,0,' pb'),'Variazione dello spread OAS',h.date,'ICE / FRED');
  if(ctx.usRates&&u.date===n.date)add('Treasury USA 2Y',sign(u.chg2_bp,1,' pb'),'Variazione del rendimento',u.date,'U.S. Treasury');
 }else if(ctx.usRates){
  add('Treasury USA 2Y',sign(u.chg2_bp,1,' pb'),'Front-end governativo, non OIS',u.date,'U.S. Treasury');
  add('Treasury USA 10Y',sign(u.chg10_bp,1,' pb'),'Long-end, premio a termine incluso',u.date,'U.S. Treasury');
  if(ctx.fxAligned)add('USD · proxy BCE',sign(ctx.usdDelta,2,'%'),'Indice sintetico, non DXY ICE',d.as_of,'Fixing BCE');
 }else{
  if(finite(n.change_1d_pct)&&validDay(n.date)&&n.date===leadDate)
   add('Nasdaq Composite',sign(n.change_1d_pct,2,'%'),'Ultima seduta disponibile',n.date,'Nasdaq / FRED');
  if(validDay(d.as_of)&&d.as_of===leadDate&&finite(d.value)&&finite(d.previous_value)&&d.previous_value)
   add('USD · proxy BCE',sign((d.value/d.previous_value-1)*100,2,'%'),'Fixing BCE, non ICE',d.as_of,'BCE');
 }
 return '<div class="letter-evidence" data-research-kind="'+esc(kind)+'"><div class="letter-evidence-heading"><span>LE PROVE DELLA TESI</span><strong>'+(leadDate?'Seduta '+date(leadDate):'Data da verificare')+'</strong></div>'
  +(rows.length?'<div class="letter-proof-list">'+rows.map(x=>'<div class="letter-proof-row"><span class="proof-name">'+esc(x.title)+'</span><strong>'+esc(x.move)+'</strong><span class="proof-detail">'+esc(x.detail)+'</span><small>'+esc(x.source)+' · '+date(x.day)+'</small></div>').join('')+'</div>':'<p class="letter-proof-empty">Mancano osservazioni della stessa seduta sufficienti per costruire una prova coerente. Non accostiamo date diverse come se fossero una conferma.</p>')
  +'<p class="letter-proof-note">Variazioni osservate, non prova di causalità. Ogni riga usa la data e la fonte che la sostengono.</p></div>';
}
function researchBridge(route){
 const c=researchCase(),m=get('macro')?.currencies?.USD||{},p=get('pairs')||{},o=get('ois')?.currencies?.USD||{},cot=get('cot')||{};
 const message={
  macro:finite(m.inflation?.latest_value)&&finite(m.labour?.latest_value)
    ?'L’inflazione USA è '+fmt(m.inflation.latest_value,2)+'% ('+esc(m.inflation.as_of)+'); disoccupazione '+fmt(m.labour.latest_value,1)+'% ('+esc(m.labour.as_of)+'). Prima di parlare di svolta, confronta periodi e velocità.'
    :'Il ciclo USA non è validabile con entrambe le serie: il punto da verificare è la persistenza della crescita e dell’inflazione.',
  rates:c.usRates?'Il 2Y USA si è mosso di '+sign(c.u.chg2_bp,1,' pb')+' e il 10Y di '+sign(c.u.chg10_bp,1,' pb')+' al '+date(c.u.date)+'. Distingui questa reazione dalle attese OIS/futures.':'La conferma dei Treasury è da verificare: mantieni separate osservazioni e stime.',
  currencies:c.fxAligned?'Il proxy USD varia '+sign(c.usdDelta,2,'%')+' nella stessa data del 2Y USA ('+date(c.d.as_of)+'). Co-movimento o divergenza non dimostrano causalità.':'Verifica il dollaro contro la data delle curve: fixing e Treasury non risultano sincroni o completi.',
  pairs:validDay(p.price_asof)?'Le 28 coppie riflettono il fixing del '+date(p.price_asof)+'. Usa la struttura relativa e il prezzo per verificare la tesi, non per creare segnali automatici.':'Le date del prezzo FX non permettono ancora di confermare una tesi sulla coppia.',
  cot:cot.EUR?.today?'La lettura EUR è '+esc(cot.EUR.signal||'da validare')+'; il COT si riferisce a una settimana diversa dai fixing FX. Verifica il flusso, non il solo estremo.':'Il positioning non può essere promosso a conferma finché non è datato e verificato.',
  risk:c.aligned?'Nasdaq '+sign(c.n.change_1d_pct,2,'%')+', VIX '+sign(c.v.value-c.v.previous,2,' pt')+', HY '+sign((c.h.value-c.h.previous)*100,0,' pb')+' nella seduta del '+date(c.n.date)+'.':'Le osservazioni azionario, VIX e credito non hanno una conferma simultanea aggiornata.',
  news:'Ogni notizia deve essere collegata al dato pubblicato, alla sorpresa e alla reazione misurabile dei prezzi. Senza questa catena non attribuiamo causalità.'
 };
 const prompts={macro:'È davvero cambiato il ciclo?',rates:'I rendimenti confermano un repricing?',currencies:'Le valute stanno confermando?',pairs:'Quali coppie superano la verifica?',cot:'Il positioning anticipa o insegue?',risk:'Lo stress è diffuso o concentrato?',news:'Quale evento cambia davvero la tesi?'};
 return '<aside class="research-continuity" aria-label="Collegamento alla ricerca principale"><div><span>DALLA RICERCA / '+esc(ROUTES[route]||route).toUpperCase()+'</span><h2>'+esc(prompts[route]||'Approfondisci la tesi')+'</h2><p>'+message[route]+'</p></div><a href="#overview">Rileggi la tesi del desk ↗</a></aside>';
}

function overview(){
 const context=researchCase();
 const u=get('rates')?.USD||{},d=get('dxy')||{},risk=get('risk')?.streams||{};
 const n=risk.NASDAQCOM||{},sp=risk.SP500||{},vx=risk.VIX||{},hy=risk.HY_OAS||{};
 const m=get('macro')?.currencies?.USD||{},oc=get('ois')?.currencies?.USD||{},cb=get('cb')?.USD||{};
 const cot=get('cot')||{},pairData=eurPairs(),pairAsOf=get('pairs')?.price_asof;
 const usd2=finite(u['2Y'])&&finite(u.chg2_bp)&&context.usRates;
 const usd10=finite(u['10Y'])&&finite(u.chg10_bp)&&context.usRates;
 const equity=finite(n.change_1d_pct)&&validDay(n.date)&&context.aligned;
 const vix=finite(vx.value)&&finite(vx.previous)&&validDay(vx.date);
 const credit=finite(hy.value)&&finite(hy.previous)&&validDay(hy.date);
 const oneSession=equity&&vix&&credit&&n.date===vx.date&&n.date===hy.date;
 const stress=context.kind==='stress';
 const relief=context.kind==='relief';
 const yieldsUp=context.kind==='yield-selloff';
 const divergent=context.kind==='fx-divergence';
 const bonds=context.kind==='bond-rally'||(context.kind==='stress'&&context.usRates&&u.chg2_bp<-2&&u.chg10_bp<-2);
 const sharedDate=stress&&bonds&&u.date===n.date;
 const latest=[u.date,d.as_of,n.date,hy.date,pairAsOf].filter(validDay).sort().pop();
 const tooOld=!latest||!fresh(latest,8);
 const dx=finite(d.value)&&finite(d.previous_value)&&d.previous_value!==0&&validDay(d.as_of)?(d.value/d.previous_value-1)*100:null;
 const headlineBase=sharedDate
   ?'Non è soltanto una correzione azionaria. Il mercato sta cambiando idea sulla crescita?'
   :stress?'Il rischio torna al centro. Che cosa ci stanno dicendo i mercati?'
   :relief?'Il rischio si allenta. È cambiato qualcosa di più profondo?'
   :bonds?'I rendimenti scendono. È davvero cambiata la storia macro?'
   :yieldsUp?'I rendimenti risalgono. Il mercato sta rivedendo le aspettative?'
   :divergent?'Treasury e dollaro divergono: quale storia manca?'
   :'Quale storia stanno raccontando, insieme, tassi e mercati?';
 const headline=tooOld?'Archivio di ricerca: che cosa ci ha raccontato il mercato?':headlineBase;
 const opening=stress
   ?'La seduta del '+date(n.date)+' non racconta soltanto un ribasso del Nasdaq. L’indice ha perso '+fmt(Math.abs(n.change_1d_pct),2)+'%'+(finite(sp.change_1d_pct)&&sp.date===n.date?', contro '+fmt(Math.abs(sp.change_1d_pct),2)+'% dell’S&P 500':'')+'. Nello stesso giorno il VIX è passato da '+fmt(vx.previous,2)+' a '+fmt(vx.value,2)+' e lo spread high yield si è allargato di '+sign((hy.value-hy.previous)*100,0,' punti base')+'. Quando anche il credito si muove, la questione non riguarda più soltanto la valutazione delle società tecnologiche: entra in gioco il costo del rischio.'
   :relief?'Nella seduta del '+date(n.date)+' il Nasdaq è avanzato del '+fmt(n.change_1d_pct,2)+'%, mentre il VIX è passato da '+fmt(vx.previous,2)+' a '+fmt(vx.value,2)+' e lo spread HY si è ristretto di '+fmt((hy.previous-hy.value)*100,0)+' punti base. È una distensione del rischio osservata sulla stessa data, non ancora una prova che il ciclo macro abbia invertito la rotta.'
   :bonds?'Il movimento che merita attenzione parte dai Treasury: il 2Y USA è sceso di '+fmt(Math.abs(u.chg2_bp),1)+' punti base e il 10Y di '+fmt(Math.abs(u.chg10_bp),1)+' al '+date(u.date)+'. Potrebbe essere un nuovo percorso atteso della Fed, ma l’ipotesi va verificata sui futures e non dedotta dal solo governativo.'
   :yieldsUp?'I Treasury si muovono nella direzione opposta: il 2Y USA sale di '+fmt(u.chg2_bp,1)+' punti base e il 10Y di '+fmt(u.chg10_bp,1)+' al '+date(u.date)+'. Dobbiamo capire se il movimento riguarda le attese di banca centrale o i premi sul lungo termine.'
   :divergent?'Al '+date(u.date)+' il Treasury 2Y si è mosso di '+sign(u.chg2_bp,1,' punti base')+', mentre il proxy del dollaro è variato di '+sign(context.usdDelta,2,'%')+'. La divergenza è sulla stessa data ma non dimostra che uno dei due mercati sia in errore.'
   :equity?'Nell’ultima seduta disponibile, il Nasdaq ha registrato '+sign(n.change_1d_pct,2,'%')+' al '+date(n.date)+'. '+(finite(vx.value)&&validDay(vx.date)?'Il VIX è a '+fmt(vx.value,2)+' al '+date(vx.date)+'. ':'')+'Il punto non è trovare subito una spiegazione unica, ma distinguere ciò che si è mosso insieme da ciò che richiede ancora conferma.'
   :'Non tutti i feed cross-asset sono disponibili con date confrontabili. In questo caso un’analisi seria comincia da ciò che possiamo documentare e segnala ciò che non possiamo ancora concludere.';
 const follow=sharedDate
   ?'Nella stessa seduta il rendimento Treasury a due anni è diminuito di '+fmt(Math.abs(u.chg2_bp),1)+' punti base e quello a dieci anni di '+fmt(Math.abs(u.chg10_bp),1)+'. I prezzi dei Treasury si muovono in senso opposto ai rendimenti: è un quadro compatibile con domanda di duration. Ma dai prezzi non possiamo sapere chi abbia comprato, né attribuire automaticamente il movimento al timore di recessione.'
   :usd2?'Il Treasury USA a due anni, nell’osservazione del '+date(u.date)+', quota '+fmt(u['2Y'],3)+'% e varia di '+sign(u.chg2_bp,1,' punti base')+'. '+(usd10?'Il dieci anni varia di '+sign(u.chg10_bp,1,' punti base')+'. ':'')+'I due rendimenti descrivono una reazione di mercato; da soli non identificano la notizia che l’ha prodotta.'
   :'Sul Treasury USA a due anni manca una variazione datata utilizzabile. La diagnosi sul mercato obbligazionario resta quindi aperta.';
 const shape=bonds?'Se il front-end scende più del long-end, la curva può irripidirsi anche mentre tutti i rendimenti calano; se accade il contrario, può appiattirsi. In entrambi i casi serve misurare l’ampiezza del movimento prima di parlare di cambio di regime.':'Il 2Y reagisce più direttamente alle attese di politica monetaria; il 10Y può riflettere anche rendimenti reali, inflazione attesa e premio a termine. Non sono due voti identici sulla stessa notizia.';
 const macroInf=m.inflation,macroLab=m.labour;
 const macroReading=finite(macroInf?.latest_value)&&finite(macroLab?.latest_value)
   ?'Il quadro macro complica la lettura. L’ultimo dato di inflazione headline USA presente nel nostro archivio è '+fmt(macroInf.latest_value,2)+'% ('+(macroInf.as_of||'periodo da verificare')+'), con direzione '+(macroInf.direction||'non disponibile').toLowerCase()+'. Il tasso di disoccupazione è '+fmt(macroLab.latest_value,1)+'% ('+(macroLab.as_of||'periodo da verificare')+'), con direzione '+(macroLab.direction||'non disponibile').toLowerCase()+'. Sono osservazioni riferite a periodi diversi e non necessariamente a prime pubblicazioni point-in-time. Non autorizzano la conclusione che crescita e inflazione siano già entrambe in discesa.'
   :'La fotografia macro di inflazione e lavoro non è abbastanza completa per sostenere una tesi sul ciclo. In particolare, non attribuiamo al mercato un turning point che non è verificato dai dati.';
 const o6=oc.horizons?.['6m'];
 const pricingReading=finite(o6?.rate)&&validDay(o6.as_of)
   ?'Il contratto indicativo a sei mesi per gli Stati Uniti riporta '+fmt(o6.rate,3)+'% al '+date(o6.as_of)+' ('+(oc.kind||'strumento da classificare')+', qualità '+(oc.quality||'non classificata')+'). Questo livello non è un tasso OIS ufficiale e non va confrontato meccanicamente con il range Fed. '+(finite(o6.change_1d_bp)?'La variazione a un giorno riportata è '+sign(o6.change_1d_bp,1,' pb')+'.':'In questo snapshot manca una variazione giornaliera certificata: non possiamo dire di quanto siano cambiate le aspettative in questa seduta.')
   :'Il feed non offre una scadenza 6M USA con strumento e data verificabili. Per parlare di repricing monetario occorre un confronto omogeneo tra scadenze e sessioni.';
 const fxReading=finite(dx)
   ?'La prova valutaria, poi, va trattata con attenzione. Il proxy del dollaro ricavato dai fixing BCE ha registrato '+sign(dx,2,'%')+' al '+date(d.as_of)+'. '+(usd2&&u.date===d.as_of?'Si riferisce alla stessa data del 2Y, ma resta un indice sintetico, non il DXY ICE e non una prova di causalità.':'Il suo fixing non coincide con la data dell’ultimo 2Y USA: confrontarli come se fossero una reazione simultanea sarebbe fuorviante.')+' Il Forex può rispondere anche a differenziali relativi, coperture e avversione al rischio.'
   :'Non abbiamo una variazione datata del proxy USD sufficiente a verificare la reazione del dollaro. Non trasformiamo il silenzio del feed in un segnale FX.';
 const crowded=(cot.EUR?.signal==='EXTREME SHORT'||cot.AUD?.signal==='EXTREME SHORT')
   ?'Il COT aggiunge una sfumatura: '+(cot.EUR?.signal==='EXTREME SHORT'?'sull’euro lo stock speculativo è classificato estremo al ribasso':'')+(cot.EUR?.signal==='EXTREME SHORT'&&cot.AUD?.signal==='EXTREME SHORT'?' e ':'')+(cot.AUD?.signal==='EXTREME SHORT'?'anche sul dollaro australiano il posizionamento è estremo al ribasso':'')+'. Il dato CFTC è settimanale, distinto dal fixing di prezzo. Un affollamento può amplificare un movimento o favorire ricoperture: da solo non indica né il momento né il verso della prossima operazione.'
   :'Il positioning CFTC è un’informazione settimanale, non una fotografia dei flussi di oggi. Senza un dato attuale validato non lo usiamo per confermare il prezzo.';
 const eur=pairData.EURUSD, aud=pairData.AUDCAD;
 const eurText=eur?.decision_frame?.relation||eur?.setup?.structural?.relation;
 const audText=aud?.decision_frame?.relation||aud?.setup?.structural?.relation;
 const cleanPairSentence=x=>String(x||'').replace(/[.!?]+$/,'');
 const pairStory=eurText&&audText&&validDay(pairAsOf)
   ?'Il controllo più utile arriva dalle singole coppie. Nel dossier EUR/USD al '+date(pairAsOf)+' il modello descrive: «'+cleanPairSentence(eurText)+'». Sul cross AUD/CAD, invece: «'+cleanPairSentence(audText)+'». Il primo caso e il secondo non devono produrre la stessa conclusione per il solo fatto di appartenere al Forex: contano il differenziale relativo e la conferma del prezzo. '+(eur.setup?.price?.text?'Il modello classifica il prezzo EUR/USD come «'+eur.setup.price.text+'»; ':'')+(aud.setup?.price?.text?'quello AUD/CAD come «'+aud.setup.price.text+'».':'')
   :'Le tesi relative sulle coppie non sono disponibili con un fixing sufficientemente tracciabile. È meglio non nominare un candidato che attribuirgli una forza non dimostrata.';
 const thesis=sharedDate
   ?'La mia ipotesi di lavoro è che il mercato stia rivalutando il premio richiesto per detenere rischio, e che questa rivalutazione abbia raggiunto anche le aspettative sui tassi. È una tesi coerente con la seduta osservata, non un verdetto sulla recessione né una previsione di tagli della Fed.'
   :stress?'La pista principale è un aumento dell’avversione al rischio. Prima di parlare di svolta macro dobbiamo però osservare anche tassi, differenziali FX e persistenza del movimento.'
   :relief?'La mia ipotesi di lavoro è che il premio per il rischio si stia riducendo. Potrebbe trattarsi di una tregua tecnica, non necessariamente di un miglioramento delle prospettive di crescita: servono durata del movimento e un confronto con gli utili, il credito e il pricing.'
   :bonds?'La domanda principale è se il calo dei rendimenti derivi da un nuovo percorso atteso della banca centrale oppure da un premio per il rischio e una diversa domanda di duration.'
   :yieldsUp?'Il rialzo congiunto dei rendimenti è compatibile con una revisione del percorso monetario oppure con un cambiamento dei premi reali e di durata. La tesi non è ancora validata finché OIS, breakeven e prezzo FX non vengono letti insieme.'
   :divergent?'Tassi USA e dollaro si sono mossi in direzioni opposte sulla stessa data. La divergenza è un invito a cercare differenziali esteri, risk sentiment e positioning, non a presumere che uno dei due prezzi sia sbagliato.'
   :'Per ora le prove raccontano storie parziali. La conclusione non è che non stia accadendo nulla, ma che manca ancora un incastro credibile tra macro, prezzi e aspettative.';
 const falsify=stress?'Questa lettura perderebbe forza se la volatilità rientrasse e gli spread creditizi si restringessero mentre i prezzi azionari recuperano. Guadagnerebbe forza se lo stress restasse diffuso e un repricing OIS/futures sulla stessa base temporale accompagnasse il calo del 2Y. Una nuova accelerazione dell’inflazione, invece, potrebbe riportare l’attenzione sul long-end e complicare ogni conclusione semplicistica sui tagli.'
  :relief?'La distensione sarebbe fragile se VIX e spread HY tornassero ad allargarsi, oppure se il recupero azionario restasse isolato. Un miglioramento più credibile richiederebbe persistenza, partecipazione del mercato e coerenza con credito e aspettative macro.'
  :bonds?'L’interpretazione di un riprezzamento monetario perderebbe forza se OIS/futures non si muovessero nella stessa direzione e se il calo dei Treasury fosse isolato. Divergenze con oro, dollaro e credito richiederebbero una spiegazione alternativa.'
  :yieldsUp?'La lettura di un mercato più hawkish sarebbe indebolita da OIS stabili o in discesa. Se invece il movimento fosse dominato dal long-end e dai real yields, avremmo bisogno di una diagnosi diversa da quella di un rialzo atteso della banca centrale.'
  :divergent?'La divergenza perderebbe rilievo se dollaro e 2Y tornassero a muoversi in modo coerente sulle stesse date. Se persistesse, vanno confrontati differenziali con altre valute, volatilità e flussi di copertura.'
  :'La tesi resta aperta: richiede osservazioni della stessa seduta e differenziali coerenti. Un movimento isolato non basta a identificare un cambio di regime.';
 const sourceDates=[
  ['Cross-asset',n.date],['Treasury 2Y',u.date],['Dollaro proxy BCE',d.as_of],
  ['CPI USA',macroInf?.as_of],['Lavoro USA',macroLab?.as_of],['Futures USD 6M',o6?.as_of],['Coppie FX',pairAsOf],['COT',cot.AUD?.today?.match(/CFTC al (\d{4}-\d{2}-\d{2})/)?.[1]]
 ].filter(x=>x[1]).map(([k,v])=>esc(k)+' '+date(v)).join(' · ');
 const section=(title,body,cl='')=>'<section class="letter-section '+cl+'"><h2>'+title+'</h2><p>'+body+'</p></section>';
 return '<div class="letter-issue"><span>FX QUANT / LETTERA DAI MERCATI</span><span>Ultima evidenza '+date(latest)+' · Consultato '+dayNow().split('-').reverse().join('.')+'</span></div>'
 +'<article class="market-letter"><header class="letter-header"><div class="letter-category">GLOBAL MACRO <span> / </span> RESEARCH NOTE</div><h1>'+esc(headline)+'</h1><p class="letter-subtitle">Quando i prezzi smettono di confermare una storia, è proprio lì che comincia il lavoro dell’analista.</p>'+(tooOld?'<p class="letter-stale">Attenzione: le fonti disponibili non risultano recenti. Questa è una lettura di archivio, non una fotografia live dei mercati.</p>':'')+'</header>'
 +'<div class="letter-opening"><p class="letter-lead">'+esc(opening)+'</p><p>'+esc(follow)+'</p></div>'+researchEvidence(context)
 +'<div class="letter-argument"><span class="letter-margin">IL FILO DEL RAGIONAMENTO</span><div class="letter-main">'
 +section('Il movimento dei bond non basta a spiegare tutto',esc(shape)+' '+esc(pricingReading))
 +section('La macroeconomia non ci concede ancora una risposta facile',esc(macroReading))
 +'<blockquote class="letter-pullquote">«'+esc(thesis)+'»</blockquote>'
 +section('Il dollaro deve ancora dire la sua',esc(fxReading)+' '+esc(crowded))
 +'</div></div>'
 +'<figure class="letter-chart"><figcaption><span>LA PROVA GRAFICA</span><strong>'+esc(stress||relief?'Partiamo dall’azionario, poi cerchiamo conferme.':bonds||yieldsUp?'Partiamo dai Treasury, poi confrontiamo il pricing.':divergent?'Partiamo dal dollaro, poi torniamo ai differenziali.':'Partiamo dalla serie più verificabile.')+'</strong><p>Il primo grafico segue la tesi appena letta; puoi passare alle altre serie per cercare conferme o divergenze. Nessun confronto simultaneo tra date diverse.</p></figcaption><div class="letter-chart-visual">'+homeScreenChart()+'</div></figure>'
 +'<div class="letter-argument letter-argument-after"><span class="letter-margin">DALLA TESI AL PREZZO</span><div class="letter-main">'
 +section('Il passaggio decisivo è sempre relativo',esc(pairStory))
 +section('Che cosa mi farebbe cambiare idea?',esc(falsify))
 +'<p class="letter-outro">Non abbiamo bisogno di una previsione a tutti i costi. Abbiamo bisogno di riconoscere quando una tesi acquista evidenza e quando il mercato smette di sostenerla. È questo il punto di partenza di ogni vera ricerca.</p>'
 +'</div></div>'
 +'<footer class="letter-footer"><div><strong>Continua la ricerca</strong><p>Se vuoi approfondire il nodo centrale della tesi, entra nel <a href="#rates">laboratorio Tassi & OIS</a>; per capire se il ciclo sta girando, leggi la <a href="#macro">Macro</a>; per mettere l’ipotesi alla prova sul prezzo, passa alle <a href="#pairs">28 coppie FX</a> e al <a href="#cot">COT</a>.</p></div><small>'+sourceDates+'</small><small>Rendimenti Treasury ≠ OIS · DXY sintetico ≠ indice ICE · COT settimanale ≠ flusso intraday · Tesi di ricerca ≠ segnale di ingresso.</small></footer>'
 +'</article>';
}

function currencies(){
 if(window.FXQuantCurrencies?.render)return window.FXQuantCurrencies.render({get,FX,FLAGS,NAMES,state,plot,pageHero,esc,fmt,sign,date,finite,validDay,dayNow});
 return pageHero('FX G8 / COUNTRY RESEARCH','Country Research Studio non disponibile','Il modulo Valute G8 non è stato caricato. Verifica i feed e lo script.');
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
 if(window.FXQuantMacro?.render)return window.FXQuantMacro.render({get,FX,FLAGS,NAMES,state,plot,pageHero,esc,fmt,sign,date,finite,validDay,dayNow});
 return pageHero('GLOBAL MACRO / DYNAMICS','Macro Studio non disponibile','Il modulo Macro non è stato caricato. Verifica gli script e le serie storiche.');
}
function rates(){
 if(window.FXQuantRates?.render)return window.FXQuantRates.render({get,FX,FLAGS,NAMES,state,plot,pageHero,esc,fmt,sign,date,finite,validDay,dayNow});
 return pageHero('RATES / MONETARY PRICING','Rates Studio non disponibile','Il modulo Rates & OIS non è stato caricato. Verifica il collegamento agli script.');
}
function cot(){
 if(window.FXQuantCOT?.render)return window.FXQuantCOT.render({get,FX,FLAGS,state,plot,pageHero,esc,fmt,sign,date,finite,validDay,dayNow,qBadge});
 return pageHero('CFTC / POSITIONING','Ricerca COT da caricare','Il modulo COT non è disponibile. Controlla la pubblicazione del relativo script.');
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


function quickEntries(){
 const sections=Object.entries(ROUTES).map(([value,label])=>({key:value,label,subtitle:'SEZIONE · Research terminal',kind:'route',value}));
 const currencies=FX.map(k=>({key:k,label:FLAGS[k]+' '+k+' · '+NAMES[k],subtitle:'VALUTA G8 · Ricerca multidimensionale',kind:'ccy',value:k}));
 const pairs=Object.keys(eurPairs()).sort().map(k=>({key:k,label:getPairName(k),subtitle:'COPPIA FX · Setup e tesi del motore',kind:'pair',value:k}));
 return [...sections,...currencies,...pairs];
}
function renderQuick(q=''){
 const query=String(q||'').toLocaleUpperCase('it-IT').replace(/[\/\s]/g,'').trim();
 const items=quickEntries().filter(x=>!query||((x.label+' '+x.key+' '+x.subtitle).toLocaleUpperCase('it-IT').replace(/[\/\s]/g,'')).includes(query)).slice(0,14);
 $('quick-results').innerHTML=items.length?items.map(e=>'<button type="button" class="quick-entry" data-command="'+esc(e.kind)+':'+esc(e.value)+'"><span><b>'+esc(e.label)+'</b><small>'+esc(e.subtitle)+'</small></span><span>↗</span></button>').join(''):'<div class="empty"><strong>Nessun risultato</strong><p>Prova il nome di una valuta, una coppia o una sezione.</p></div>';
}
function setQuick(open){
 $('quick-layer').classList.toggle('open',!!open);$('quick-layer').setAttribute('aria-hidden',String(!open));
 if(open){$('quick-input').value='';renderQuick();$('quick-input').focus();}
 else $('quicklaunch').focus();
}

function researchRibbon(route){
 const parts=[['macro','Macro'],['rates','Rates'],['currencies','FX G8'],['pairs','Coppie'],['cot','COT'],['risk','Risk']];
 return '<div class="research-ribbon"><div class="ribbon-meta"><span class="ribbon-signal">◉</span> RESEARCH JOURNEY <span class="ribbon-current">'+FLAGS[state.ccy]+' '+state.ccy+' · '+esc(getPairName(state.pair))+'</span></div><div class="ribbon-path">'+parts.map((p,i)=>'<a href="#'+p[0]+'"'+(route===p[0]?' class="current"':'')+'>'+(i?'<small>›</small>':'')+p[1]+'</a>').join('')+'</div></div>';
}
function render(){
 const route=ROUTES[state.route]?state.route:'overview';
 state.charts={};state.chartIndex=0;
 const views={overview,currencies,pairs,macro,rates,cot,risk,news};
 $('content').innerHTML=(route==='overview'?'':researchBridge(route))+views[route]();
 $('crumb-page').textContent=ROUTES[route];
 document.querySelectorAll('#nav [data-route]').forEach(a=>{if(a.dataset.route===route)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
 const ok=Object.keys(state.data).length,missing=Object.keys(SOURCES).length-ok;
 const caseNow=researchCase(),caseOld=!caseNow.latest||!fresh(caseNow.latest,8);
 const dates=[get('rates')?.USD?.date,get('dxy')?.as_of,get('pairs')?.price_asof].filter(validDay);
 $('top-asof').textContent='Riferimenti '+(dates.length?dates.map(date).join(' · '):'da verificare');
 $('top-quality').classList.toggle('warn',missing>0||caseOld);
 $('top-quality').innerHTML='<span class="live-dot"></span>'+(missing>0?ok+'/'+Object.keys(SOURCES).length+' FEED':caseOld?'DATI STORICI':'FONTI CARICATE');
 $('sidebar-feed').textContent=ok+'/'+Object.keys(SOURCES).length+' fonti caricate · dati non intraday';
 const sf=$('sidebar-focus');if(sf)sf.textContent=FLAGS[state.ccy]+' '+state.ccy+' · '+getPairName(state.pair);
 document.title='FX Quant Next — '+ROUTES[route];
}
function saveWatch(){try{localStorage.setItem('fxquant-next-watch',JSON.stringify([...state.watch]))}catch(e){}}
function navigate(){
 const route=location.hash.slice(1).split('?')[0]||'overview';
 state.route=ROUTES[route]?route:'overview';render();window.scrollTo({top:0,behavior:'instant'});
 $('app').classList.remove('menu-open');$('menu-toggle').setAttribute('aria-expanded','false');
}
window.addEventListener('hashchange',navigate);
$('quicklaunch').addEventListener('click',()=>setQuick(true));
$('quickclose').addEventListener('click',()=>setQuick(false));
$('quick-input').addEventListener('input',e=>renderQuick(e.target.value));
$('quick-layer').addEventListener('click',e=>{if(e.target.id==='quick-layer')setQuick(false);});
window.addEventListener('keydown',e=>{
 if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();setQuick(!$('quick-layer').classList.contains('open'));return;}
 if(e.key==='/'&&!/INPUT|TEXTAREA/.test(e.target?.tagName||'')){e.preventDefault();setQuick(true);}
 if(e.key==='Escape'&&$('quick-layer').classList.contains('open')){e.preventDefault();setQuick(false);}
});
$('menu-toggle').addEventListener('click',()=>{const open=!$('app').classList.contains('menu-open');$('app').classList.toggle('menu-open',open);$('menu-toggle').setAttribute('aria-expanded',String(open))});
$('mobile-overlay').addEventListener('click',()=>{$('app').classList.remove('menu-open');$('menu-toggle').setAttribute('aria-expanded','false')});
document.addEventListener('click',e=>{
 const cs_ret=e.target.closest('[data-cs-returnwindow]');
 if(cs_ret){state.csReturnWindow=Number(cs_ret.dataset.csReturnwindow);render();return;}
 const cs_country=e.target.closest('[data-cs-country]');if(cs_country){state.ccy=cs_country.dataset.csCountry;if(state.csOther===state.ccy)state.csOther=FX.find(k=>k!==state.ccy);render();return;}
 const cs_other=e.target.closest('[data-cs-other]');if(cs_other){state.csOther=cs_other.dataset.csOther;render();return;}
 const cs_pw=e.target.closest('[data-cs-pricewindow]');if(cs_pw){state.csPriceWindow=Number(cs_pw.dataset.csPricewindow);render();return;}
 const cs_rm=e.target.closest('[data-cs-ratesmode]');if(cs_rm){state.csRatesMode=cs_rm.dataset.csRatesmode;render();return;}
 const cs_rw=e.target.closest('[data-cs-rateswindow]');if(cs_rw){state.csRatesWindow=Number(cs_rw.dataset.csRateswindow);render();return;}
 const cs_ma=e.target.closest('[data-cs-macro]');if(cs_ma){state.csMacroMode=cs_ma.dataset.csMacro;render();return;}
 const cs_mw=e.target.closest('[data-cs-macrowindow]');if(cs_mw){state.csMacroWindow=Number(cs_mw.dataset.csMacrowindow);render();return;}
 const cs_cw=e.target.closest('[data-cs-cotwindow]');if(cs_cw){state.csCotWindow=Number(cs_cw.dataset.csCotwindow);render();return;}
 const cs_so=e.target.closest('[data-cs-sort]');if(cs_so){state.csSort=cs_so.dataset.csSort;render();return;}
 const cs_op=e.target.closest('[data-cs-openpair]');if(cs_op){
  const key=cs_op.dataset.csOpenpair;
  state.pair=(get('pairs')?.pairs?.[key]?key:key.slice(3)+key.slice(0,3));
  state.spotPair=state.pair;
  state.route='pairs';location.hash='#pairs';render();return;
 }
 const mcc=e.target.closest('[data-ms-country]');if(mcc){state.ccy=mcc.dataset.msCountry;state.msSeriesId=null;if(state.msOther===state.ccy)state.msOther=FX.find(k=>k!==state.ccy);render();return;}
 const mcat=e.target.closest('[data-ms-category]');if(mcat){state.msCategory=mcat.dataset.msCategory;state.msSeriesId=null;render();return;}
 const mv=e.target.closest('[data-ms-view]');if(mv){state.msView=mv.dataset.msView;render();return;}
 const mw=e.target.closest('[data-ms-window]');if(mw){state.msWindow=Number(mw.dataset.msWindow);render();return;}
 const mh=e.target.closest('[data-ms-heat]');if(mh){state.msHeat=mh.dataset.msHeat;render();return;}
 const msort=e.target.closest('[data-ms-heat-sort]');if(msort){state.msHeatSort=msort.dataset.msHeatSort;state.msHeatAsc=!state.msHeatAsc;render();return;}
 const mcomp=e.target.closest('[data-ms-compare]');if(mcomp){state.msCompareMetric=mcomp.dataset.msCompare;render();return;}
 const rc=e.target.closest('[data-rate-ccy]');if(rc){state.ccy=rc.dataset.rateCcy;if(state.against===state.ccy)state.against=FX.find(x=>x!==state.ccy);render();return;}
 const rg=e.target.closest('[data-rs-gov]');if(rg){state.rsGovMode=rg.dataset.rsGov;render();return;}
 const rsw=e.target.closest('[data-rs-window]');if(rsw){state.rsWindow=Number(rsw.dataset.rsWindow);render();return;}
 const rd=e.target.closest('[data-rs-diff]');if(rd){state.rsDiffMode=rd.dataset.rsDiff;render();return;}
 const cm=e.target.closest('[data-cot-mode]');if(cm){state.cotMode=cm.dataset.cotMode;render();return;}
 const cw=e.target.closest('[data-cot-window]');if(cw){state.cotWindow=Number(cw.dataset.cotWindow);render();return;}
 const cf=e.target.closest('[data-cot-filter]');if(cf){state.cotFilter=cf.dataset.cotFilter;render();return;}
 const cs=e.target.closest('[data-cot-sort]');if(cs){
   if(state.cotSort===cs.dataset.cotSort)state.cotSortAsc=!state.cotSortAsc;
   else{state.cotSort=cs.dataset.cotSort;state.cotSortAsc=false;}
   render();return;
 }
 const pick=e.target.closest('[data-command]');
 if(pick){
   const [kind,value]=String(pick.dataset.command||'').split(':');
   if(kind==='ccy'){state.ccy=value;state.route='currencies';location.hash='#currencies';}
   else if(kind==='pair'){state.pair=value;state.spotPair=value;state.route='pairs';location.hash='#pairs';}
   else if(kind==='route'&&ROUTES[value]){state.route=value;location.hash='#'+value;}
   setQuick(false);render();return;
 }
 const atlas=e.target.closest('[data-atlas]');if(atlas){state.atlasLens=atlas.dataset.atlas;render();return}
 const hc=e.target.closest('[data-hchart]');if(hc){state.homeChart=hc.dataset.hchart;render();return}
 const hw=e.target.closest('[data-hwindow]');if(hw){state.homeWindow=Number(hw.dataset.hwindow);render();return}
 const hp=e.target.closest('[data-home-pair]');if(hp){state.spotPair=hp.dataset.homePair;state.pair=state.spotPair;render();return}
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
document.addEventListener('toggle',e=>{if(e.target?.matches?.('details.macro-advanced'))state.msAdvanced=e.target.open;},true);
document.addEventListener('change',e=>{
 if(e.target.id==='cs-other'){state.csOther=e.target.value;render();return;}
 if(e.target.id==='ms-series'){state.msSeriesId=e.target.value;render();return;}
 if(e.target.id==='ms-primary'){state.ccy=e.target.value;state.msSeriesId=null;if(state.msOther===state.ccy)state.msOther=FX.find(k=>k!==state.ccy);render();return;}
 if(e.target.id==='ms-other'){state.msOther=e.target.value;render();return;}
 if(e.target.id==='rs-country'){state.ccy=e.target.value;if(state.against===state.ccy)state.against=FX.find(k=>k!==state.ccy);render();return;}
 if(e.target.id==='rs-other'){state.against=e.target.value;render();return;}
 if(e.target.id==='rate-country'){state.ccy=e.target.value;if(state.against===state.ccy)state.against=FX.find(k=>k!==state.ccy);render();}
 if(e.target.id==='rate-compare'){state.against=e.target.value;render();}
});
document.addEventListener('pointermove',chartEvents);
document.addEventListener('pointerout',e=>{if(e.target.closest('.chart')&&!e.relatedTarget?.closest?.('.chart'))chartHide(e)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('app').classList.remove('menu-open');$('menu-toggle').setAttribute('aria-expanded','false')}});
let refreshInProgress=false;
let lastResearchRefresh=0;
async function loadAll(){
 if(refreshInProgress)return;
 refreshInProgress=true;
 const nextData={},nextErrors={};
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
   nextData[key]=d;
  }catch(e){nextErrors[key]=String(e.message||e);}
  finally{clearTimeout(timer)}
 });
 try{
  await Promise.allSettled(jobs);
  // Rebuild the entire research from the same fetch cycle. A failed source is
  // not silently reused from the previous edition as a current observation.
  state.data=nextData;
  state.errors=nextErrors;
  lastResearchRefresh=Date.now();
  render();
 }finally{refreshInProgress=false;}
}
// Refresh when the reader returns to a long-open tab, and while the site stays
// open. This never claims an edition changed unless the underlying feeds did.
document.addEventListener('visibilitychange',()=>{
 if(document.visibilityState==='visible'&&Date.now()-lastResearchRefresh>30*60*1000)loadAll();
});
setInterval(()=>{
 if(document.visibilityState==='visible'&&Date.now()-lastResearchRefresh>30*60*1000)loadAll();
},30*60*1000);

navigate();
loadAll();
})();
