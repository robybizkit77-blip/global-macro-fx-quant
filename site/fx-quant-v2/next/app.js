'use strict';
/* FX Quant NEXT - Independent user-experience prototype.
 * The operational FX engine, pricing and source files remain read-only.
 * No invented live quotes, synthetic rankings, or automatic trade signals.
 */
(function(){
const FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',AUD:'🇦🇺',NZD:'🇳🇿',CAD:'🇨🇦'};
const NAMES={USD:'Stati Uniti',EUR:'Area euro',GBP:'Regno Unito',JPY:'Giappone',CHF:'Svizzera',AUD:'Australia',NZD:'Nuova Zelanda',CAD:'Canada'};
const ROUTES={overview:'Panoramica',currencies:'Valute G8',pairs:'Coppie FX',macro:'Scenario macro',rates:'Tassi & OIS',cot:'COT',risk:'Rischio',news:'Notizie',library:'Research Library'};
const SOURCES={
 rates:'../../../live_data/sections/NATIVE_RATES_DATA.json',
 audDailyResearch:'../aud-rba-f2-history-research.json',
 chfResearch:'../chf-snb-paired-history.json',
 nzdPostroll:'../nzd-b2-postroll-web-research.json',
 chfSpot:'../../../live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json',
 nzdDirectionalProxy:'../../../live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json',
 dxy:'../../../live_data/sections/DXY_SYNTHETIC_ECB.json',
 morningDesk:'./morning-desk-current.json',
 currencyPrices:'../../../live_data/sections/ECB_G8_PRICE_HISTORY.json',
 pairs:'../../../live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json',
 thesisHistory:'./pair-thesis-history.json',
 macro:'../../../live_data/sections/MACRO_THERMOMETER_DATA.json',
 macroObserved:'../../control-room-preview/macro-v3-current-evidence.json',
 macroSeries:'../../../live_data/sections/MACRO_SERIES.json',
 cbEstimated:'../../../live_data/sections/CB_PRICING_ESTIMATED.json',
 cb:'../../../live_data/sections/NATIVE_CB_DATA.json',
 cot:'../../../live_data/sections/V247_COT_STORIES.json',
 cotHistory:'../../../live_data/sections/V250_COT_CHART_DATA.json',
 cotPriorReference:'../design-studio-cot-v1-data.json',
 risk:'../cross-asset-live-data.json',
 ois:'../ois-pricing-snapshot.json',
 news:'../../../live_data/sections/NEWS_PULSE_OPERATIONAL.json',
 calendar:'../../../live_data/sections/CALENDAR_OPERATIONAL_VIEW.json',
 themes:'../../../live_data/sections/TOP_THEMES.json'
};
let firstResearchLoaded=false;
const state={data:{},errors:{},route:'overview',ccy:'USD',against:'EUR',pair:'EURUSD',pairFilter:'all',pairSearch:'',pairDetailOpen:false,pairPriceWindow:60,pairShowReferences:true,watch:new Set(),window:20,rateMode:'both',riskStream:'VIX',riskWindow:20,macroMetric:'inflation',newsMode:'pulse',chartIndex:0,charts:{},atlasLens:'rates',homeChart:null,homeWindow:20,homeEvidenceOpen:false,homeDossierOpen:false,spotPair:'EURUSD',cotWindow:26,cotMode:'net',cotFilter:'all',cotSort:'percentile',cotSortAsc:false,rsWindow:60,rsGovMode:'both',rsDiffMode:'2y',msCategory:'Inflazione',msSeriesId:null,msView:'level',msWindow:24,msHeat:'inflation',msHeatSort:'ccy',msHeatAsc:true,msOther:'EUR',msCompareMetric:'inflation',msAdvanced:false,csOther:'EUR',csPriceWindow:60,csRatesMode:'spread',csRatesWindow:60,csMacroMode:'inflation',csMacroWindow:36,csCotWindow:26,csSort:'currency',csReturnWindow:20};
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
const get=k=>k==='estimatedMacro'?estimatedMacro():(state.data[k]||null);
function estimatedMacro(){
 if(!window.FXQuantMacroEstimated?.evaluate)return {status:'STIMA_SOSPESA',reason:'Modulo stimato non caricato'};
 return window.FXQuantMacroEstimated.evaluate({
  observed:state.data.macroObserved,prices:state.data.currencyPrices,
  ois:state.data.ois,rates:state.data.rates,model:state.data.pairs,
  now:dayNow(),rankingFn:window.FXQuantPairRankings?.currencyRanking
 });
}
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
 const referenceLines=(Array.isArray(opts.referenceLines)?opts.referenceLines:[])
  .filter(r=>r&&finite(r.value)&&(r.kind==='favorable'||r.kind==='adverse')).slice(0,2);
 const count=Math.max(0,...normalized.map(x=>x.values.length));
 if(count<2||!normalized.some(x=>x.values.length>1))return '<div class="empty"><strong>Storico non disponibile</strong><p>Non disegniamo curve se mancano osservazioni validate e confrontabili.</p></div>';
 const values=normalized.flatMap(l=>l.values.map(p=>p.value)).concat(referenceLines.map(r=>r.value));
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
 // Reference marks are deliberately short and anchored at the RIGHT EDGE.
 // They describe thresholds computed from the last valid fixing ONLY;
 // drawing a full-width line would falsely imply an unchanged historical level.
 referenceLines.forEach(r=>{
  const color=r.kind==='favorable'?'#9bd4b2':'#e3a19a',label=r.kind==='favorable'?'FAV.':'CONTR.';
  const y=Y(r.value),xStart=W-R-134,xEnd=W-R;
  body+='<g data-reference-marker="'+r.kind+'"><line data-reference-line="'+r.kind+'" x1="'+xStart+'" x2="'+xEnd+'" y1="'+y.toFixed(2)+'" y2="'+y.toFixed(2)+'" stroke="'+color+'" stroke-width="1.9" stroke-dasharray="7 5" opacity=".98"/>';
  body+='<text data-reference-label="'+r.kind+'" x="'+(W-R-5)+'" y="'+(y-6).toFixed(2)+'" font-size="10" font-weight="650" text-anchor="end" fill="'+color+'">'+label+' '+fmt(r.value,opts.precision??2)+'</text></g>';
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
function pairCoverage(k){
 const model=get('pairs'),prices=get('currencyPrices'),rates=get('rates'),today=dayNow();
 const p=typeof window!=='undefined'&&window.FXQuantDecisionJourney?.profile?
  window.FXQuantDecisionJourney.profile(k,model,prices,today):null;
 const y=typeof window!=='undefined'&&window.FXQuantRatesBridge?.snapshot?
  window.FXQuantRatesBridge.snapshot(rates,prices,k,model?.price_asof,today,get('audDailyResearch'),get('chfResearch'),get('nzdPostroll')):null;
 return {price:!!(p?.fresh&&p.closes?.length>=22),reference:!!p?.watch?.ready,
  rateShort:!!(y?.ready&&y.short),rateMedium:!!(y?.ready&&y.medium),rateResearch:!!(y?.ready&&y.researchOnly)};
}
function pairCoverageLabels(c){
 const items=[['FX daily',c.price,'fixing BCE'],['Rif. daily',c.reference,'riferimenti nella direzione favorita'],
  ['2Y breve',c.rateShort,'5 intervalli comuni governativi 2Y'],['2Y medio',c.rateMedium,'20 intervalli comuni governativi 2Y']];
 return '<span class="pair-data-coverage" aria-label="Disponibilità dei dati">'+
  items.map(([label,ok,meaning])=>'<span class="pair-data-state '+(ok&&c.rateResearch&&label.startsWith('2Y')?'research':ok?'available':'missing')+
   '" title="'+(ok?'Disponibile: ':'Non verificabile: ')+meaning+'"><span aria-hidden="true">'+
   (ok?'✓':'–')+'</span>'+label+'</span>').join('')+'</span>';
}
function pairRow(k,compact=false){
 const p=eurPairs()[k],s=p?.setup||{},q=pQuality(s);
 return '<button type="button" class="pair-row '+(state.pair===k?'active':'')+'" data-pair="'+k+
  '"><span><strong>'+esc(getPairName(k))+'</strong><span class="subtitle">'+
  esc(s.structuralFav?'Contesto: '+s.structuralFav:'Valutazione da approfondire')+' · '+
  esc(s.price?.text||'Prezzo non classificato')+'</span>'+pairCoverageLabels(pairCoverage(k))+
  '</span><span class="right">'+qBadge(q)+'<span class="arrow">›</span></span>'+(compact?'':'')+'</button>';
}
function pairCoverageIntro(){
 const all=Object.keys(eurPairs()),counts={price:0,reference:0,rateShort:0,rateMedium:0};
 all.forEach(k=>{const c=pairCoverage(k);Object.keys(counts).forEach(t=>{if(c[t])counts[t]++})});
 if(!all.length)return '<p class="pair-coverage-intro">Stato copertura non verificabile: nessuna coppia caricata.</p>';
 return '<p class="pair-coverage-intro" aria-label="Copertura verificata delle 28 coppie">'+
  '<strong>'+counts.price+'/'+all.length+'</strong> FX daily · '+
  '<strong>'+counts.reference+'/'+all.length+'</strong> rif. daily · '+
  '<strong>'+counts.rateShort+'/'+all.length+'</strong> 2Y breve · '+
  '<strong>'+counts.rateMedium+'/'+all.length+'</strong> 2Y medio'+
  '<small>2Y = governativi, non OIS. Per AUD: RBA F2 di ricerca (ambra, non Core). CHF e NZD espongono storico e date di ricerca senza aggiungere false conferme FX/2Y. Il trattino indica dati insufficienti o direzione non definita, non un giudizio sul trade.</small></p>';
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
 let keys=state.homeChart||'fx',w=Number(state.homeWindow||20),lines=[],label='',unit='',result='',asof='';
 const u=get('rates')?.USD,d=get('dxy'),r=get('risk')?.streams||{};
 if(keys==='fx'){
  const h=fxHomeDesk(),rows=(get('currencyPrices')?.rows||[])
    .filter(x=>validDay(x?.Date)&&x.Date<=dayNow()&&FX.every(c=>c==='EUR'||finite(x[c])&&x[c]>0))
    .sort((a,b)=>a.Date.localeCompare(b.Date));
  if(!h.ready||rows.length<6)return '<div class="empty"><strong>Forza G8 non disponibile</strong><p>Servono sei fixing BCE completi e un modello delle 28 coppie sulla stessa data.</p></div>';
  const subset=rows.slice(-Math.max(6,w+1)),base=subset[0];
  const selected=[h.strength5[0]?.ccy,h.strength5.at(-1)?.ccy,h.strength1[0]?.ccy,'USD']
   .filter((c,i,a)=>c&&a.indexOf(c)===i).slice(0,4);
  const colors=['#81e8b7','#ff8290','#ffc77f','#65cfff'];
  lines=selected.map((c,i)=>({name:FLAGS[c]+' '+c+' / EUR',color:colors[i],
    values:subset.map(x=>({label:x.Date,value:c==='EUR'?0:Math.log(base[c]/x[c])*100}))}));
  label='G8 · performance relativa vs EUR';unit='%';asof=h.asof;
  result='Ogni linea mostra la variazione della valuta rispetto all’euro dal primo fixing del grafico. Prezzi BCE, stesso calendario, non quotazioni live né segnali.';
 }else if(keys==='nasdaq'){
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
 +'<div class="analyst-toolbar"><div class="chart-tabset">'+choose('',[{label:'Forza G8 FX',value:'fx'},{label:'Nasdaq',value:'nasdaq'},{label:'2Y / 10Y',value:'rates'},{label:'USD proxy',value:'dxy'},{label:'VIX',value:'vix'},{label:'HY',value:'hy'}],keys,'data-hchart')+'</div><div class="chart-tabset">'+choose('',[{label:'5',value:5},{label:'20',value:20},{label:'60',value:60}],w,'data-hwindow')+'</div></div>'
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
 const max=[r.NASDAQCOM?.date,r.VIX?.date,r.HY_OAS?.date,u.date,d.as_of,pairDate].filter(x=>validDay(x)&&x<=dayNow()).sort().pop()||null;
 const near=d=>validDay(d)&&validDay(max)&&d<=dayNow()&&d<=max&&
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
 if(typeof window!=='undefined'&&window.FXQuantResearchEditorial?.create){
  return window.FXQuantResearchEditorial.create({
   get,state,caseNow:researchCase(),finite,validDay,fmt,sign,date,dayNow,esc,NAMES
  }).render(route);
 }

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


/* FX FIRST — the homepage is a currency research desk, not a cross-asset newsletter.
   ECB EUR-base fixings are converted into relative value changes consistently:
   positive % = the named currency strengthened against EUR. No spot/intraday claim.
   Never classify a pair as a trade merely because its model favours one currency. */
function fxHomeDesk(){
 const prices=get('currencyPrices'),pairs=get('pairs'),pairMap=pairs?.pairs||{};
 const rows=(prices?.rows||[]).filter(x=>validDay(x?.Date)&&x.Date<=dayNow()
   &&FX.every(c=>c==='EUR'||finite(x[c])&&x[c]>0)).sort((a,b)=>a.Date.localeCompare(b.Date));
 const end=rows.at(-1),previous=rows.at(-2),baseline=rows.at(-6);
 const ready=!!(end&&previous&&baseline&&end.Date===prices.last_as_of&&end.Date===pairs?.price_asof);
 const recent=ready&&fresh(end.Date,8);
 const empty='Il fixing BCE delle otto valute e il motore delle 28 coppie non sono allineati su una data recente. Non attribuiamo forza relativa o vantaggi FX al mercato attuale senza una fotografia coerente.';
 if(!ready)return {ready:false,recent:false,asof:end?.Date||null,headline:'FOREX G8 · Perché manca ancora una lettura relativa verificabile',
  opening:empty,why:'Prima di parlare di valute forti o deboli servono almeno sei fixing G8 completi e lo stesso giorno di riferimento per il modello delle 28 coppie.',
  policy:'Nessuna conclusione monetaria o macro viene sostituita a una misura di prezzo mancante.',
  market:'Le coppie rimangono accessibili nella sezione FX, ma non vengono presentate come opportunità attuali.',
  verdict:'Tesi FX non valutabile con le fonti disponibili; nessuna selezione automatica.',watch:'Verificare la pubblicazione dei fixing e l’allineamento del modello FX.',
  meta:'G8 e 28 coppie non allineati',metrics:[],strength1:[],strength5:[]};
 const getMove=(from,to,c)=>c==='EUR'?0:100*Math.log(from[c]/to[c]);
 const calc=from=>FX.map(ccy=>({ccy,value:getMove(from,end,ccy)})).sort((a,b)=>b.value-a.value);
 const strength1=calc(previous),strength5=calc(baseline);
 const lead1=strength1[0],lag1=strength1.at(-1),lead5=strength5[0],lag5=strength5.at(-1);
 const move1=c=>strength1.find(x=>x.ccy===c)?.value;
 const move5=c=>strength5.find(x=>x.ccy===c)?.value;
 const fmtMove=x=>sign(x,2,'%');
 const label=c=>FLAGS[c]+' '+c;
 const dayPhrase='Nel fixing BCE del '+date(end.Date);
 const yesterday=label(lead1.ccy)+' '+fmtMove(lead1.value)+' e '+label(lag1.ccy)+' '+fmtMove(lag1.value);
 const five=label(lead5.ccy)+' '+fmtMove(lead5.value)+' e '+label(lag5.ccy)+' '+fmtMove(lag5.value);
 const shortLeader5=move5(lead1.ccy);
 const nzdContext=lead1.ccy==='NZD'&&finite(shortLeader5)?
  'Il recupero del NZD non equivale ancora a un cambio di trend: sulle cinque sedute precedenti il suo saldo relativo è '+fmtMove(shortLeader5)+'.':
  'La seduta e il movimento a cinque fixing non vanno confusi: una giornata forte può essere un recupero all’interno di una tendenza più debole.';
 const eurusd=pairMap.EURUSD,usdjpy=pairMap.USDJPY,audchf=pairMap.AUDCHF;
 const pFav=p=>p?.setup?.structuralFav||p?.decision_frame?.fav||null;
 const pQuality=p=>p?.setup?.quality||'NON VALUTABILE';
 const pPrice=p=>p?.setup?.price?.state||'NEUTRAL';
 const knownPair=(p)=>p&&['GOOD','BAD','NEUTRAL'].includes(pPrice(p));
 const pairEvidence=knownPair(eurusd)&&knownPair(usdjpy)?
  (pFav(eurusd)==='USD'?'EUR/USD: il modello attribuisce a USD un vantaggio parziale'+
   (pPrice(eurusd)==='GOOD'?' che il prezzo già riflette':' che il prezzo non conferma ancora')+
   '; stato '+pQuality(eurusd)+'. ':'EUR/USD non ha una prevalenza strutturale USD verificata. ')+
  (pFav(usdjpy)==='USD'&&pPrice(usdjpy)==='BAD'?
   'USD/JPY: la struttura favorisce USD, ma il prezzo favorisce JPY; divergenza da monitorare, non segnale di acquisto. ':
   'USD/JPY richiede il confronto autonomo tra struttura e prezzo. '):
  'Non ci sono dati sufficienti per una conclusione puntuale e confrontabile su EUR/USD e USD/JPY. ';
 const aussieEvidence=audchf&&pFav(audchf)==='AUD'&&pPrice(audchf)==='GOOD'?
  'AUD/CHF: la struttura e il prezzo del modello favoriscono AUD, ma negli ultimi cinque fixing '+label('CHF')+
  ' ha sovraperformato '+label('AUD')+'. Gli orizzonti del modello e del movimento breve differiscono; è una verifica da fare, non una contraddizione automaticamente risolta.':
  '';
 const qdist=pairs?.quality_distribution||{};
 const clean=qdist.PULITO||0,total=pairs?.pair_count||28;
 const riskPairs=(qdist['CON RISCHI']||0),unusable=(qdist['NON VALUTABILE']||0),pending=(qdist['DA CONFERMARE']||0),watching=(qdist['DA MONITORARE']||0);
 const policyUSD=get('ois')?.currencies?.USD?.horizons?.['6m'],policyEUR=get('ois')?.currencies?.EUR?.horizons?.['6m'];
 const govUSD=get('rates')?.USD,govEUR=get('rates')?.EUR;
 const sameGov=govUSD?.date===end.Date&&govEUR?.date===end.Date&&finite(govUSD['2Y'])&&finite(govEUR['2Y']);
 const diff=sameGov?(govUSD['2Y']-govEUR['2Y'])*100:null;
 const comparableMoney=policyUSD?.as_of===end.Date&&policyEUR?.as_of===end.Date&&
    finite(policyUSD.change_1d_bp)&&finite(policyEUR.change_1d_bp);
 const ratesText=sameGov?
  'Il differenziale governativo 2Y USA–Eurozona è '+sign(diff,0,' pb')+' alla stessa data. '+
   (comparableMoney?'Anche i contratti monetari a sei mesi riportano variazioni giornaliere comparabili, da verificare per strumento.':
    'Ma non c’è una coppia omogenea di variazioni giornaliere 6M USA/EUR: non posso chiamarlo un nuovo repricing relativo delle banche centrali.'):
  'Non abbiamo due rendimenti governativi 2Y USA/EUR sulla stessa data del fixing: nessun differenziale corrente viene forzato.';
 const ma=get('macro')?.currencies||{},usdInf=ma.USD?.inflation,eurInf=ma.EUR?.inflation;
 const macroContext=eurusd?.decision_frame?.macroSide==='USD'?
   'La componente Macro del modello favorisce USD rispetto a EUR, mentre il confronto Tassi/CB non produce un vincitore completo.':
   'Il motore Macro/Tassi non dà un orientamento completo per EUR/USD.';
 const cot=get('cot')||{},dateMatch=cot.AUD?.today?.match(/CFTC al (\d{4}-\d{2}-\d{2})/)?.[1];
 const cotValid=validDay(dateMatch)&&dateMatch<=end.Date;
 const nzdCrowded=cot.NZD?.today?.match(/Net\/OI\s+([+-]?\d+(?:\.\d+)?)%/);
 const audCrowded=cot.AUD?.today?.match(/Net\/OI\s+([+-]?\d+(?:\.\d+)?)%/);
 const crowded=cotValid&&nzdCrowded&&audCrowded&&
   Math.abs(Number(nzdCrowded[1]).toFixed(1))>=30&&Math.abs(Number(audCrowded[1]).toFixed(1))>=30;
 const positioning=crowded?
  'Nel COT del '+date(dateMatch)+' NZD e AUD sono entrambi net short con Net/OI oltre −30%: il posizionamento è concentrato. '+
  'Il rialzo giornaliero del NZD potrebbe includere ricoperture, ma i dati non identificano le operazioni né dimostrano flussi di short covering.':
  'Il COT è settimanale: non lo usiamo per attribuire gli ultimi movimenti FX a ricoperture che non possiamo osservare.';
 const r=get('risk')?.streams||{},vix=r.VIX||{};
 const vixSame=vix.date===end.Date&&finite(vix.value)&&finite(vix.previous);
 const vixDelta=vixSame?vix.value-vix.previous:null;
 const riskContext=vixSame&&finite(vixDelta)?
  'Il VIX nello stesso giorno '+(vixDelta<0?'è sceso':'è salito')+' di '+fmt(Math.abs(vixDelta),2)+
  ' punti: '+(vixDelta<0?'è compatibile con un allentamento della pressione sulle valute sensibili al rischio.':
   'potrebbe rendere più fragile un recupero delle valute cicliche.')+
  ' Tuttavia il VIX da solo non spiega il NZD né dimostra un flusso FX; il confronto azioni/credito richiede altre date.':
  'La lettura cross-asset non ha una conferma di volatilità sulla stessa data FX; non la useremo per spiegare i movimenti delle valute.';
 const staleLead=!recent?'Il quadro seguente è storico, non una lettura della seduta in corso. ':'';
 const metrics=[
  {label:label(lead1.ccy)+' · ultimo fixing',value:fmtMove(lead1.value),source:'BCE · vs EUR',day:end.Date,key:'currencies'},
  {label:label(lag1.ccy)+' · ultimo fixing',value:fmtMove(lag1.value),source:'BCE · vs EUR',day:end.Date,key:'currencies'},
  {label:label(lead5.ccy)+' · 5 fixing',value:fmtMove(lead5.value),source:'BCE · vs EUR',day:end.Date,key:'currencies'},
  {label:label(lag5.ccy)+' · 5 fixing',value:fmtMove(lag5.value),source:'BCE · vs EUR',day:end.Date,key:'currencies'}
 ];
 const prefix='FX G8 · ';
 const headline=recent?
   prefix+label(lead1.ccy)+(lead1.value>0?' guida l’ultimo fixing':' tiene meglio nell’ultimo fixing')+
   ', mentre il confronto su cinque sedute premia '+label(lead5.ccy):
   prefix+'fotografia storica: confrontare prima i fixing e le 28 coppie';
 const opening=staleLead+dayPhrase+' la valuta più forte rispetto al fixing precedente è '+label(lead1.ccy)+
   ' ('+fmtMove(lead1.value)+'), la più debole è '+label(lag1.ccy)+' ('+fmtMove(lag1.value)+
   '). Nelle ultime cinque sedute, invece, in testa c’è '+label(lead5.ccy)+' ('+fmtMove(lead5.value)+
   ') e in fondo '+label(lag5.ccy)+' ('+fmtMove(lag5.value)+'). Sono confronti valutari relativi, non prezzi live.';
 const why=nzdContext+' '+(sameGov?ratesText:'')+' '+macroContext;
 const policy=pairEvidence+aussieEvidence;
 const market=positioning+' '+riskContext;
 const verdict=recent?
   'Il messaggio FX è una rotazione di forza relativa, non una direzione unica del dollaro o delle valute cicliche. '+
   (clean===0?'Sulle '+total+' coppie non ci sono setup classificati puliti: ':'Il motore segnala '+clean+' coppie pulite, ma serve ancora il timing tecnico: ')+
   riskPairs+' con rischi, '+unusable+' non valutabili, '+pending+' da confermare e '+watching+' da monitorare. La solidità di una tesi non equivale a un ingresso interessante.':
   'Le variazioni dei fixing sono datate e non supportano un verdetto operativo aggiornato. Non promuoviamo coppie fuori dalla loro finestra di validità.';
 const watch='Prima osserverei se '+label(lead1.ccy)+' consolida il recupero oltre un solo fixing e se '+label(lag5.ccy)+
   ' smette di perdere terreno. Poi controllerei se su USD/JPY il prezzo smette di contraddire la struttura e se EUR/USD offre qualcosa di nuovo oltre alla conferma già prezzata. Per attribuire i movimenti alla politica monetaria serviranno variazioni OIS/futures USA–Europa comparabili.';
 return {ready:true,recent,asof:end.Date,headline,opening,why,policy,market,verdict,watch,
  meta:'Fixing BCE '+date(end.Date)+' · 1 e 5 fixing · '+total+' coppie',
  strength1,strength5,metrics,
  highlight:[lead1.ccy,lag1.ccy,lead5.ccy,lag5.ccy],
  last:end.Date,positioning};
}

function overview(){
 // Independent FREE GitHub desk replaces the historical morning when—and only when—
 // a source-validated edition actually exists. A missing feed cannot blank Home.
 const hourly=typeof window==='undefined'?null:
  window.FXQuantHourlyDesk?.render?.({feed:get('hourlyDesk'),risk:get('risk'),currencyPrices:get('currencyPrices'),esc,date,dayNow});
 if(hourly)return hourly;
 const morning=get('morningDesk');
 if(typeof window!=='undefined' && window.FXQuantMorningDesk?.build && morning){
  // A new, independently dated FX snapshot must never rewrite the archived
  // morning narrative or be mistaken for a pre-release trading signal.
  const estimated=get('estimatedMacro');
  const currentResearch={
   estimated,rates:get('rates'),calendar:get('calendar'),
   selectResearchPairs:window.FXQuantPairRankings?.selectResearchPairs,
   watchForPair:x=>{
    if(!window.FXQuantPairRankings?.pairDecisionWatch)return null;
    const profile=window.FXQuantDecisionJourney?.profile?.(
     x.key,get('pairs'),get('currencyPrices'),dayNow(),estimated);
    return window.FXQuantPairRankings.pairDecisionWatch(x,profile);
   }
  };
  const edition=window.FXQuantMorningDesk.build({
   feed:morning,plot,esc,date,dayNow,currentResearch
  });
  if(edition){
   const post=window.FXQuantMorningDesk.postRelease?.(morning,get('news'),esc,dayNow)||'';
   return post ? edition.replace('<section class="morning-prose"',post+'<section class="morning-prose"') : edition;
  }
 }
 const context=researchCase();
 const fxDesk=fxHomeDesk();
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
 const latest=context.latest;
 const focusDate=context.leadDate||latest;
 const tooOld=!focusDate||!fresh(focusDate,8);
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
 const spreadShift=usd2&&usd10?u.chg10_bp-u.chg2_bp:null;
 const shape=finite(spreadShift)?
   'Al '+date(u.date)+' il Treasury USA 2Y è variato di '+sign(u.chg2_bp,1,' pb')+
   ' e il 10Y di '+sign(u.chg10_bp,1,' pb')+'. '+
   (Math.abs(spreadShift)<1?'La curva 10Y−2Y è rimasta pressoché ferma: movimento quasi parallelo, non una rotazione tra scadenze. ':
     'Lo spread 10Y−2Y si è '+(spreadShift>0?'allargato':'ristretto')+' di '+fmt(Math.abs(spreadShift),1)+
     ' pb: il movimento non è parallelo. ')+
   'Per attribuirlo alla banca centrale servono variazioni OIS/futures della stessa scadenza e data; il prezzo dei Treasury non identifica da solo gli operatori né il motivo.':
   'Non abbiamo 2Y e 10Y USA con variazioni verificabili sulla stessa seduta: non attribuiamo al mercato una modifica della curva non misurata.';
 const macroInf=m.inflation,macroLab=m.labour;
 const macroReading=finite(macroInf?.latest_value)&&finite(macroLab?.latest_value)
   ?'Il quadro macro complica la lettura. L’ultimo dato di inflazione headline USA presente nel nostro archivio è '+fmt(macroInf.latest_value,2)+'% ('+(macroInf.as_of||'periodo da verificare')+'), con direzione '+(macroInf.direction||'non disponibile').toLowerCase()+'. Il tasso di disoccupazione è '+fmt(macroLab.latest_value,1)+'% ('+(macroLab.as_of||'periodo da verificare')+'), con direzione '+(macroLab.direction||'non disponibile').toLowerCase()+'. Sono osservazioni riferite a periodi diversi e non necessariamente a prime pubblicazioni point-in-time. Non autorizzano la conclusione che crescita e inflazione siano già entrambe in discesa.'
   :'La fotografia macro di inflazione e lavoro non è abbastanza completa per sostenere una tesi sul ciclo. In particolare, non attribuiamo al mercato un turning point che non è verificato dai dati.';
 const o6=oc.horizons?.['6m'];
 const pricingReading=finite(o6?.rate)&&validDay(o6.as_of)&&o6.as_of<=dayNow()
   ?'Il contratto indicativo a sei mesi per gli Stati Uniti riporta '+fmt(o6.rate,3)+'% al '+date(o6.as_of)+' ('+(oc.kind||'strumento da classificare')+', qualità '+(oc.quality||'non classificata')+'). Questo livello non è un tasso OIS ufficiale e non va confrontato meccanicamente con il range Fed. '+(finite(o6.change_1d_bp)?'La variazione a un giorno riportata è '+sign(o6.change_1d_bp,1,' pb')+'.':'In questo snapshot manca una variazione giornaliera certificata: non possiamo dire di quanto siano cambiate le aspettative in questa seduta.')
   :'Il feed non offre una scadenza 6M USA con strumento e data verificabili. Per parlare di repricing monetario occorre un confronto omogeneo tra scadenze e sessioni.';
 // The 6M level is context, not evidence of a same-session Fed repricing.
 // Do not align different dates or instruments; no absent daily delta is inferred.
 const money6Valid=finite(o6?.rate)&&validDay(o6?.as_of)&&o6.as_of<=dayNow();
 const money6SameSession=money6Valid&&o6.as_of===focusDate;
 const pricingQuick=!money6Valid
   ?'Per la seduta esaminata non abbiamo una scadenza monetaria USA a sei mesi utilizzabile. Il movimento dei Treasury, da solo, non dimostra un riprezzamento Fed.'
   :'Il riferimento USA a sei mesi è '+fmt(o6.rate,3)+'% ('+(oc.kind||'strumento da verificare')+
    ', '+(oc.quality||'qualità non classificata')+', '+date(o6.as_of)+'). '+
    (!money6SameSession?'Non coincide con la data del focus ('+date(focusDate)+'): non prova che le aspettative siano cambiate durante quel movimento.':
     finite(o6.change_1d_bp)?'La variazione dichiarata è '+sign(o6.change_1d_bp,1,' pb')+
      ', sullo stesso giorno del focus. È una misura dello strumento indicato, non automaticamente dell’intero sentiero Fed.':
      'Manca una variazione giornaliera omogenea: conosciamo il livello indicativo, non il repricing di quella seduta.');
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
 ].filter(x=>x[1]&&(!validDay(x[1])||x[1]<=dayNow())).map(([k,v])=>esc(k)+' '+date(v)).join(' · ');
 const section=(title,body,cl='')=>'<section class="letter-section '+cl+'"><h2>'+title+'</h2><p>'+body+'</p></section>';
 const metric=(label,value,day,source,key)=>({label,value:validDay(day)&&day<=dayNow()?value:'—',day:validDay(day)&&day<=dayNow()?date(day):'n.d.',source,key});
 const nasdaq=metric('Nasdaq · 1D',sign(n?.change_1d_pct,2,'%'),n?.date,'Nasdaq / FRED','risk');
 const vixMove=metric('VIX · variazione',finite(vx?.value)&&finite(vx?.previous)?sign(vx.value-vx.previous,2,' pt'):'—',vx?.date,'Cboe','risk');
 const hyMove=metric('High Yield · OAS',finite(hy?.value)&&finite(hy?.previous)?sign((hy.value-hy.previous)*100,0,' pb'):'—',hy?.date,'ICE / FRED','risk');
 const us2=metric('Treasury USA · 2Y',sign(u?.chg2_bp,1,' pb'),u?.date,'Treasury','rates');
 const us10=metric('Treasury USA · 10Y',sign(u?.chg10_bp,1,' pb'),u?.date,'Treasury','rates');
 const dollar=metric('USD · proxy BCE',sign(dx,2,'%'),d?.as_of,'BCE / fixing','currencies');
 const legacyHeadlineMetrics=(stress||relief)
  ?[nasdaq,vixMove,hyMove,us2]
  :(bonds||yieldsUp)?[us2,us10,dollar,hyMove]
  :divergent?[dollar,us2,us10,hyMove]
  :[us2,nasdaq,dollar,hyMove];
 const headlineMetrics=fxDesk.ready?fxDesk.metrics:legacyHeadlineMetrics;
 const kpis=headlineMetrics.map(x=>'<a href="#'+x.key+'" class="dashboard-kpi">'
   +'<span class="dashboard-kpi-label">'+esc(x.label)+'</span><strong>'+esc(x.value)+'</strong>'
   +'<span class="dashboard-kpi-meta">'+esc(x.source)+' · '+esc(x.day)+'</span></a>').join('');
 const firstChart=stress||relief?'Nasdaq, volatilità e credito: il movimento è condiviso?':
   bonds||yieldsUp?'Treasury USA: calo dei rendimenti o repricing monetario?':
   divergent?'Dollaro e front-end: perché non confermano?':
   'Confronta i prezzi prima di scegliere una spiegazione';
 const focusText=stress||relief?'Partiamo dal Nasdaq perché è una delle tre prove che definiscono il quadro di rischio. Sotto trovi la stessa seduta per VIX e credito.':
  bonds||yieldsUp?'Il movimento della curva USA va confrontato con EUR e JPY, e con eventuali variazioni monetarie sulla stessa data. Non ogni calo dei rendimenti è un nuovo taglio Fed prezzato.':
  divergent?'Partiamo dal proxy del dollaro perché diverge dalla variazione del front-end sulla stessa data. La divergenza non è una strategia automatica.':
  'Il grafico visualizza uno stream reale con la propria data. Dove le fonti non coincidono, non deduciamo simultaneità.';
 const internalLinks=[
   {url:'currencies',head:'Valute G8',lead:'Perché una valuta guadagna o perde forza relativa?'},
   {url:'pairs',head:'28 coppie FX',lead:'Vantaggio relativo, prezzo e rischi: cosa è già incorporato?'},
   {url:'rates',head:'Tassi & OIS',lead:'Differenziali e aspettative monetarie: confermano i cambi?'},
   {url:'cot',head:'Positioning COT',lead:'Posizioni concentrate e cambiamenti dei fondi.'}
  ];
 const links=internalLinks.map(x=>'<a class="dashboard-research-link" href="#'+x.url+'"><strong>'+esc(x.head)+'</strong><span>'+esc(x.lead)+'</span><b aria-hidden="true">↗</b></a>').join('');
 // Evidence-led story. Separate dates, rate expectations, currency confirmation and COT.
 const deskVixDate=validDay(vx.date)&&vx.date<=dayNow()?vx.date:null;
 const deskVixDelta=deskVixDate&&finite(vx.value)&&finite(vx.previous)?vx.value-vx.previous:null;
 const deskNasDate=validDay(n.date)&&n.date<=dayNow()?n.date:null;
 const deskNasMove=deskNasDate&&finite(n.change_1d_pct)?n.change_1d_pct:null;
 const deskHYDate=validDay(hy.date)&&hy.date<=dayNow()?hy.date:null;
 const deskHYBp=deskHYDate&&finite(hy.value)&&finite(hy.previous)?(hy.value-hy.previous)*100:null;
 const deskRateDate=validDay(u.date)&&u.date<=dayNow()?u.date:null;
 const deskRatesOk=deskRateDate&&finite(u.chg2_bp)&&finite(u.chg10_bp);
 const deskSameRisk=deskVixDate&&deskVixDate===deskNasDate&&deskNasDate===deskHYDate&&finite(deskVixDelta)&&finite(deskNasMove)&&finite(deskHYBp);
 const deskOtherRates=[['Eurozona',get('rates')?.EUR],['Giappone',get('rates')?.JPY]].filter(x=>x[1]?.date===deskRateDate&&finite(x[1]?.chg2_bp));
 const deskFuturesJpy=get('ois')?.currencies?.JPY?.horizons?.['6m'];
 const deskInfChange=Array.isArray(macroInf?.history)&&macroInf.history.length>1&&finite(macroInf.history.at(-1))&&finite(macroInf.history.at(-2))?macroInf.history.at(-1)-macroInf.history.at(-2):null;
 const deskLabChange=Array.isArray(macroLab?.history)&&macroLab.history.length>1&&finite(macroLab.history.at(-1))&&finite(macroLab.history.at(-2))?macroLab.history.at(-1)-macroLab.history.at(-2):null;
 const deskPeriod=x=>/^\d{4}-\d{2}$/.test(String(x||''))?x.slice(5,7)+'/'+x.slice(0,4):date(x);
 const deskFxDate=validDay(d.as_of)&&d.as_of<=dayNow()?d.as_of:null;
 const deskPairValid=validDay(pairAsOf)&&pairAsOf<=dayNow()&&fresh(pairAsOf,8);
 const deskClean=get('pairs')?.quality_distribution?.PULITO||0;
 const deskCount=get('pairs')?.pair_count||0;
 const deskCotDate=cot.USD?.today?.match(/CFTC al (\d{4}-\d{2}-\d{2})/)?.[1]||null;
 const deskCotOk=validDay(deskCotDate)&&deskCotDate<=dayNow();
 const deskVixRecent=deskVixDate&&fresh(deskVixDate,8);
 // A newer rates/FX observation takes editorial precedence over an older VIX close.
 const deskRiskLeading=deskVixRecent&&(!validDay(focusDate)||deskVixDate>=focusDate);
 const storyHeadline=tooOld?'Cosa dicono i dati disponibili, senza fingere un mercato in tempo reale':
   deskRiskLeading&&deskVixDelta<0&&deskRatesOk&&u.chg2_bp<0?
     'La volatilità arretra, scendono i Treasury: il Forex non dà una conferma uniforme':
   deskRiskLeading&&deskVixDelta>0&&deskRatesOk&&u.chg2_bp<0?
     'Volatilità più alta e Treasury più bassi: i mercati stanno riducendo rischio?':
   deskRiskLeading&&deskVixDelta<0?'Il rischio si distende, ma la conferma tra mercati è incompleta':
   context.kind==='yield-selloff'?'I rendimenti risalgono: è repricing monetario o pressione sulle obbligazioni?':
   context.kind==='bond-rally'?'I rendimenti scendono: l’aspettativa Fed non è ancora misurata':
   context.kind==='fx-divergence'?'Treasury e dollaro divergono: il prezzo FX racconta un’altra storia':
   headline;
 const readingOpening=tooOld?
  'Le ultime osservazioni disponibili sono storiche. Ricostruiamo il quadro e le contraddizioni senza presentarlo come un aggiornamento intraday.':
  deskRiskLeading&&finite(deskVixDelta)?
   'Il cambiamento più chiaro sul rischio è nel VIX: al '+date(deskVixDate)+' '+
   (deskVixDelta<0?'è sceso di ':'è salito di ')+fmt(Math.abs(deskVixDelta),2)+' punti a '+fmt(vx.value,2)+
   '. '+(finite(deskNasMove)&&finite(deskHYBp)&&deskNasDate===deskHYDate?
     'Nell’ultima seduta comune a Nasdaq e credito ('+date(deskNasDate)+'), il Nasdaq ha fatto '+
     sign(deskNasMove,2,'%')+' e lo spread high yield '+sign(deskHYBp,0,' punti base')+'. ':
     'Non abbiamo ancora una chiusura completa e sincronizzata di azioni e credito. ')+
   (deskSameRisk?'Le tre osservazioni sono riferite allo stesso giorno.':
     'Queste rilevazioni non appartengono tutte alla stessa seduta: è un possibile allentamento dello stress, non un risk-on simultaneo già provato.'):
  deskRatesOk?'Nella seduta del '+date(deskRateDate)+' i governativi USA si sono mossi di '+
    sign(u.chg2_bp,1,' pb')+' sul 2Y e '+sign(u.chg10_bp,1,' pb')+' sul 10Y. Mancano però dati cross-asset sincronizzati per attribuire una causa.':
    'La fotografia più recente non permette ancora di stabilire un movimento comune tra azioni, credito e tassi.';
 const readingWhy=deskRatesOk?
  'Sui bond si vede un movimento più ampio degli Stati Uniti. Al '+date(deskRateDate)+
   ' i Treasury 2Y e 10Y sono scesi rispettivamente di '+fmt(Math.abs(u.chg2_bp),1)+
   ' e '+fmt(Math.abs(u.chg10_bp),1)+' punti base. '+
   (deskOtherRates.length?
     'Anche '+deskOtherRates.map(x=>x[0]).join(' e ')+' registra rendimenti brevi in '+
     (deskOtherRates.every(x=>x[1].chg2_bp<0)?'calo':'movimento')+' nella stessa seduta. ':
     'Le curve estere non hanno ancora date confrontabili. ')+
   'Questo rende debole una spiegazione basata soltanto sulla Fed. '+
   (money6Valid&&finite(o6?.change_1d_bp)&&o6.as_of===deskRateDate?
     'La variazione USD a sei mesi è '+sign(o6.change_1d_bp,1,' pb')+
     ': è un’indicazione sul singolo contratto, non sull’intero sentiero della banca centrale. ':
     'Nel pricing USD a sei mesi manca una variazione giornaliera omogenea: non possiamo certificare un repricing Fed. ')+
   (deskFuturesJpy?.as_of===deskRateDate&&finite(deskFuturesJpy.change_1d_bp)?
     'Il future monetario giapponese a sei mesi, invece, segna '+sign(deskFuturesJpy.change_1d_bp,1,' pb')+
     ': qui il repricing è osservabile, ma sullo strumento specifico.':''):
  'I tassi non hanno ancora variazioni giornaliere abbastanza documentate: attribuire la seduta alla Fed sarebbe una conclusione non sostenuta.';
 const readingPricing=finite(macroInf?.latest_value)&&finite(macroLab?.latest_value)?
   'La macro USA non dà un via libera alla narrativa di recessione e tagli. Nell’archivio del sito l’inflazione è '+
   fmt(macroInf.latest_value,2)+'% ('+deskPeriod(macroInf.as_of)+')'+
   (finite(deskInfChange)?', '+(deskInfChange>0?'in aumento':'in diminuzione')+' rispetto alla rilevazione precedente':'')+
   ', mentre la disoccupazione è '+fmt(macroLab.latest_value,1)+'% ('+deskPeriod(macroLab.as_of)+')'+
   (finite(deskLabChange)?', '+(deskLabChange>0?'in aumento':'in calo')+' sul dato precedente':'')+
   '. I periodi sono differenti e non abbiamo qui la sorpresa rispetto al consenso: sono un controllo della tesi, non la causa dimostrata dei prezzi.':
   'L’archivio macro non consente di incrociare inflazione e lavoro con sufficiente qualità: la tesi sul ciclo resta aperta.';
 const deskFxText=deskFxDate&&finite(dx)?
   'Sul Forex il proxy USD dai fixing BCE ha fatto '+sign(dx,2,'%')+' al '+date(deskFxDate)+'. '+
   (deskRatesOk&&deskRateDate===deskFxDate?
     (Math.sign(dx)===Math.sign(u.chg2_bp)?
       'Anche il Treasury breve si è mosso nello stesso verso, ma questo non prova un rapporto causale. ':
       'Il Treasury breve si è mosso in senso diverso: i rendimenti USA da soli non spiegano il prezzo. '):
    'Il fixing ha una data diversa dai tassi, quindi non è una reazione simultanea. '):
   'La reazione valutaria del dollaro non ha ancora data e variazione verificabili. ';
 const deskPairText=deskPairValid?
   (pairData.EURUSD?.decision_frame?.fav==='USD'?
     'EUR/USD presenta un vantaggio strutturale soltanto parziale per USD; '+
     (pairData.EURUSD?.setup?.price?.state==='GOOD'?
       'il prezzo è già dalla parte del dollaro, non è una nuova opportunità dimostrata. ':
       'il prezzo non ha ancora confermato pienamente. '):
    'EUR/USD non offre un vantaggio completo e verificato. ')+
   (pairData.USDJPY?.decision_frame?.fav==='USD'&&pairData.USDJPY?.setup?.price?.state==='BAD'?
     'Su USD/JPY il prezzo invece favorisce JPY nonostante la struttura orientata a USD: è una divergenza concreta. ':
     'USD/JPY richiede un controllo autonomo di struttura e prezzo. '):
   'Il dossier delle coppie non è allineato a un fixing recente, quindi non viene usato come conferma. ';
 const deskCotText=deskCotOk?
   (cot.USD?.signal==='EXTREME LONG'&&cot.EUR?.signal==='EXTREME SHORT'?
     'Il COT del '+date(deskCotDate)+' vede USD estremo long ed EUR estremo short: la posizione è già affollata e una ricopertura è un rischio, non una previsione.':
     'Il COT del '+date(deskCotDate)+' misura posizioni settimanali, non i flussi della seduta.'):
   'Il posizionamento CFTC non ha una data validata per confermare il prezzo.';
 const readingMarket=deskFxText+deskPairText+deskCotText;
 const deskUSD6MoveConfirmed=money6Valid&&o6?.as_of===deskRateDate&&finite(o6.change_1d_bp);
 const deskRatesJudgment=deskRatesOk?
   (u.chg2_bp<0?
     'I rendimenti USA sono scesi; '+(deskUSD6MoveConfirmed?'lo strumento USD a sei mesi mostra anche una variazione osservata, ma non esaurisce il percorso Fed. ':'non c’è una variazione USD a sei mesi omogenea per attribuire la seduta alla Fed. '):
    u.chg2_bp>0?'I rendimenti USA sono saliti: '+(deskUSD6MoveConfirmed?'il contratto monetario offre una verifica, ma non prova l’intera narrativa. ':'senza variazione USD a sei mesi omogenea non è dimostrato un nuovo sentiero Fed. '):
    'Il breve USA non fornisce un nuovo impulso netto. '):'Le variazioni governative omogenee restano incomplete. ';
 const deskPairsJudgment=deskPairValid&&deskCount===28&&deskClean===0?
   'Nel motore delle 28 coppie nessuna è classificata “pulita” al '+date(pairAsOf)+
   ': la tesi può avere senso senza offrire un trade interessante.':
   'La tesi FX deve ancora essere verificata sul prezzo delle singole coppie.';
 const readingVerdict=tooOld?
   'Questa è una fotografia storica, non un verdetto sulla seduta attuale. Servono osservazioni nuove e confrontabili.':
   deskRiskLeading&&finite(deskVixDelta)&&deskVixDelta<0?
     'La tensione di volatilità si sta attenuando, ma le chiusure di azionario e credito non sono tutte sulla stessa data: non chiamerei ancora questo un miglioramento macro generalizzato. '+deskRatesJudgment+deskPairsJudgment:
   deskRiskLeading&&finite(deskVixDelta)&&deskVixDelta>0?
     'Il rischio mostra maggiore tensione, ma servono azioni e credito allineati alla stessa seduta per parlare di stress diffuso. '+deskRatesJudgment+deskPairsJudgment:
   context.kind==='yield-selloff'?
     'Il cambiamento principale è il rialzo dei rendimenti USA, non la vecchia chiusura del VIX. '+deskRatesJudgment+deskPairsJudgment:
   context.kind==='bond-rally'?
     'Il cambiamento principale è il calo dei rendimenti, ma non è ancora possibile identificarne la causa monetaria. '+deskRatesJudgment+deskPairsJudgment:
   context.kind==='fx-divergence'?
     'La divergenza tra dollaro e rendimenti è il punto da spiegare. Non forzerei un trade sulla base del solo tasso USA. '+deskPairsJudgment:
   'Le prove disponibili non individuano un regime unico abbastanza solido. Nessun segnale operativo è dimostrato dal quadro generale.';
 const readingWatch=deskRiskLeading&&finite(deskVixDelta)?
   'Cercherei una prossima chiusura comune di Nasdaq, VIX e spread HY: '+
   (deskVixDelta<0?'credito e volatilità ancora in rientro confermerebbero la distensione; un nuovo allargamento HY la indebolirebbe.':
     'stress condiviso con azionario e credito rafforzerebbe la lettura difensiva; la normalizzazione la indebolirebbe.')+
   ' Nei tassi servono variazioni OIS/futures comparabili. Sulle coppie, controllo USD/JPY e se EUR/USD ha già incorporato il vantaggio USD.':
   deskRatesOk?
     'Il test decisivo è il prossimo repricing OIS/futures sulla stessa data: se non segue il movimento del 2Y USA, la lettura monetaria perde forza. Poi verifico se USD/JPY e EUR/USD seguono davvero il vantaggio relativo.':
     'Monitorerei prima date allineate tra rischio e tassi, poi la risposta dei prezzi FX: un movimento isolato non cambia il giudizio.';
 return '<article class="market-letter market-dashboard" aria-label="Dashboard di ricerca FX Quant">'
 +'<header class="dashboard-heading"><div class="dashboard-topline"><span>FX QUANT / FOREX G8 & 28 COPPIE</span><span>Fixing FX '+date(fxDesk.asof)+' · Ultimo feed '+date(latest)+' · '+dayNow().split('-').reverse().join('.')+'</span></div>'
 +'<div class="dashboard-title-row dashboard-reading-title"><div><h1>'+esc(fxDesk.headline)+'</h1><div class="letter-opening"><p class="letter-lead">'+esc(fxDesk.opening)+'</p></div></div></div>'
 +(fxDesk.ready&&!fxDesk.recent?'<p class="letter-stale">Fixing FX storici: non rappresentano dati di mercato attuali.</p>':'')
 +'</header>'
 +'<section class="dashboard-reading-story" aria-label="Il racconto del desk"><div class="dashboard-reading-eyebrow">LA LETTURA FX DEL DESK · '+date(fxDesk.asof)+'</div>'
 +'<div class="dashboard-reading-body"><p>'+esc(fxDesk.why)+'</p><p>'+esc(fxDesk.policy)+'</p><p>'+esc(fxDesk.market)+'</p>'
 +'<p class="dashboard-reading-verdict"><strong>Il mio giudizio.</strong> '+esc(fxDesk.verdict)+'</p>'
 +'<p class="dashboard-reading-watch"><strong>Che cosa monitorare.</strong> '+esc(fxDesk.watch)+'</p></div>'
 +'<div class="dashboard-fx-shortlist" aria-label="Coppie da approfondire">'+(fxDesk.ready?
 '<span>APRI I DOSSIER FX</span>'+['EURUSD','USDJPY','AUDCHF']
 .filter(k=>pairData[k]).map(k=>'<button type="button" data-pair="'+k+'">'+esc(getPairName(k))+
 ' · '+esc(pairData[k].setup?.price?.text||'Prezzo da verificare')+' ↗</button>').join(''):'')+'</div>'
 +'<nav class="dashboard-reading-source-links" aria-label="Verifica la lettura nei dossier"><a href="#currencies">Valute G8 ↗</a><a href="#pairs">28 coppie FX ↗</a><a href="#rates">Tassi & OIS ↗</a><a href="#macro">Macro ↗</a><a href="#cot">COT ↗</a><a href="#risk">Rischio ↗</a><a href="#news">Notizie ↗</a></nav>'
 +'<p class="dashboard-reading-quality">I fixing BCE e le 28 coppie guidano la lettura. Macro, tassi, COT, volatilità e credito servono a spiegare o mettere alla prova le tesi FX, non a sostituirle.</p></section>'
 +'<section class="dashboard-main dashboard-reading-chart"><div class="dashboard-section-head"><span>IL PREZZO FX DIETRO LA LETTURA</span><p>Confronta i movimenti delle valute prima di cercare conferme in altri mercati.</p></div>'
 +'<div class="dashboard-chart-grid"><figure class="letter-chart dashboard-chart"><figcaption><span>DATI DI MERCATO</span><strong>Chi sta guadagnando terreno nel G8?</strong><p>Forza relativa nei fixing BCE, confrontabile tra valute e date; nessuna quotazione intraday.</p></figcaption>'
 +'<div class="letter-chart-visual">'+homeScreenChart()+'</div></figure></div></section>'
 +'<details class="dashboard-technical" data-home-evidence'+(state.homeEvidenceOpen?' open':'')+'>'
 +'<summary><span class="dashboard-technical-overline">SE VUOI VERIFICARE I NUMERI</span><strong>Apri dati, scenari e prove del desk</strong><small>Indicatori con date e fonti, percorso decisionale, conferme e invalidazioni. Tutto il contenuto resta disponibile.</small></summary>'
 +'<div class="dashboard-technical-content">'
 +'<section class="dashboard-metrics" aria-label="Indicatori che supportano il tema di mercato"><div class="dashboard-section-head"><span>FORZA RELATIVA G8</span><p>Variazioni contro EUR, stesso fixing BCE per tutte le valute.</p></div><div class="dashboard-kpi-grid">'+kpis+'</div></section>'
 +'<section class="dashboard-original-reading"><span class="dashboard-analysis-kicker">CONTESTO CROSS-ASSET SECONDARIO</span><p>'+esc(opening)+'</p></section>'
 +(typeof window!=='undefined'&&window.FXQuantDecisionJourney?.build?window.FXQuantDecisionJourney.build({get,state,plot,fmt,sign,date,dayNow,esc}).overview():'<section class="decision-overview"><p>Percorso operativo non caricato. Nessuna selezione viene proposta.</p></section>')
 +'<aside class="dashboard-analysis"><span class="dashboard-analysis-kicker">CONTESTO INTER-MERCATO</span><h2>Quali segnali esterni possono influire sulle valute?</h2><p>'+esc(follow)+'</p>'
 +'<div class="dashboard-analysis-judgment"><strong>Che cosa sta già prezzando il mercato?</strong><p>'+esc(pricingQuick)+'</p></div>'
 +'<div class="dashboard-analysis-watch"><strong>Che cosa potrebbe smentirci?</strong><p>'+esc(falsify)+'</p></div></aside>'
 +'<section class="dashboard-proof"><div class="dashboard-section-head"><span>LE PROVE CHE SOSTENGONO LA TESI</span><p>Solo osservazioni verificabili nella seduta considerata.</p></div>'+researchEvidence(context)+'</section>'
 +'<details class="dashboard-dossier" data-home-dossier'+(state.homeDossierOpen?' open':'')+'><summary><span>PER CHI VUOLE APPROFONDIRE</span><strong>Il ragionamento macro completo</strong><small>Curva, inflazione, lavoro, pricing, Forex e invalidazioni.</small></summary>'
 +'<div class="letter-argument"><span class="letter-margin">LA TESI IN PROFONDITÀ</span><div class="letter-main">'
 +section('Il movimento dei bond non basta a spiegare tutto',esc(shape)+' '+esc(pricingReading))
 +section('La macroeconomia non ci concede ancora una risposta facile',esc(macroReading))
 +section('Il dollaro deve ancora dire la sua',esc(fxReading)+' '+esc(crowded))
 +'</div></div><div class="letter-argument letter-argument-after"><span class="letter-margin">DALLA TESI AL PREZZO</span><div class="letter-main">'
 +section('Il passaggio decisivo è sempre relativo',esc(pairStory))
 +section('Che cosa mi farebbe cambiare idea?',esc(falsify))
 +'</div></div></details>'
 +'</div></details>'
 +'<section class="dashboard-deep-links"><div class="dashboard-section-head"><span>APPROFONDISCI LA TESI FX</span><p>I mercati esterni hanno valore quando modificano una lettura valutaria.</p></div><div class="dashboard-link-grid">'+links+'</div></section>'
 +'<footer class="letter-footer dashboard-footer"><small>'+sourceDates+'</small><small>Rendimenti Treasury ≠ OIS · USD proxy BCE ≠ indice ICE · COT settimanale ≠ flusso intraday. Nessun dato qui è un ordine operativo.</small></footer>'
 +'</article>';
}

function currencies(){
 if(window.FXQuantCurrencies?.render)return window.FXQuantCurrencies.render({get,FX,FLAGS,NAMES,state,plot,pageHero,esc,fmt,sign,date,finite,validDay,dayNow});
 return pageHero('FX G8 / COUNTRY RESEARCH','Country Research Studio non disponibile','Il modulo Valute G8 non è stato caricato. Verifica i feed e lo script.');
}
function pairs(){
 const estimate=get('estimatedMacro');
 const estimateActive=estimate?.status==='STIMA_OPERATIVA_NON_VALIDATA';
 const activePair=estimateActive?estimate.pairs.find(x=>x.key===state.pair):null;
 const all=eurPairs(),keys=Object.keys(all).sort(),p=all[state.pair],s=p?.setup||{},fr=p?.decision_frame||s.structural||{};
 const monitor=window.FXQuantThesisMonitor?.analyze?.(get('pairs'),get('thesisHistory'),state.pair)||{ready:false};
 const fav=activePair?.favored||null,quality=activePair?.quality||'STIMA NON DISPONIBILE';
 const choice='<label class="pair-sel-control" for="pair-primary-select"><span>COPPIA DA ANALIZZARE</span><select id="pair-primary-select" aria-label="Seleziona una delle 28 coppie">'+
  keys.map(k=>'<option value="'+esc(k)+'"'+(k===state.pair?' selected':'')+'>'+esc(getPairName(k))+'</option>').join('')+'</select></label>';
 const report=monitor.ready?monitor.changed.length?
   'Dal '+date(monitor.previousAsOf)+' al '+date(monitor.asof)+': '+monitor.changed.length+' classificazioni cambiate. '+monitor.judgement:
   'Nessuna delle classificazioni monitorate è cambiata rispetto al '+date(monitor.previousAsOf)+'. Non significa che il mercato sia immobile.'
  :'La lettura corrente usa il modello stimato. La cronologia delle variazioni di tesi resta in consolidamento.';
 const favMeaning=fav?'La tesi fondamentale favorisce '+fav+' rispetto a '+(fav===state.pair.slice(0,3)?state.pair.slice(3):state.pair.slice(0,3))+'.':'La stima fondamentale è equilibrata tra le due valute: monitoriamo quale driver cambia per primo.';
 const driverReading=window.FXQuantPairRankings?.pairDriverReading?.(activePair,estimate)||null;
 const headline=driverReading||activePair?.thesisReason||estimate?.reason||'La lettura corrente si fonda sulle componenti macro e di forza relativa disponibili, con i limiti esposti nel dossier.';
 const tradeText=activePair?.tradeReason||'Il timing dipenderà da un movimento relativo coerente fra macro, tassi e prezzo.';
 const pairProfile=activePair&&window.FXQuantDecisionJourney?.profile?
  window.FXQuantDecisionJourney.profile(state.pair,get('pairs'),get('currencyPrices'),dayNow(),estimate):null;
 const gate=window.FXQuantPairRankings?.pairDecisionWatch?.(activePair,pairProfile)||{
  improve:'Servono nuove evidenze macro/tassi e un prezzo datato.',
  weaken:'Il giudizio corrente è sospeso: non emerge una tesi direzionale da invalidare.',
  note:'Nessun riferimento di ingresso H4 disponibile.'
 };
 const pairCatalyst=window.FXQuantPairRankings?.pairCatalystWatch?.(
  activePair,get('calendar'),dayNow())||null;
 const context='Stima operativa Macro Strength '+date(estimate?.asof)+' · fixing BCE '+date(estimate?.priceAsOf)+
   ' · vecchio motore del '+date(get('pairs')?.macro_baseline_asof)+' archiviato, non utilizzato per il giudizio corrente';
 const watchLabel=state.watch.has(state.pair)?'★ Nella watchlist':'☆ Salva nella watchlist';
 const main='<section class="panel pairs-reading-compact" aria-label="Sintesi operativa della coppia selezionata">'+
  '<div class="pairs-reading-head"><div><span class="mini-overline">IL GIUDIZIO FX · '+esc(getPairName(state.pair))+'</span><h2>'+esc(favMeaning)+'</h2></div>'+
  '<span class="badge info">'+esc(quality)+'</span></div>'+
  '<p class="pairs-primary-story">'+esc(headline)+'</p>'+
  '<div class="pairs-three-answers">'+
   '<div><span>TESI FONDAMENTALE</span><strong>'+esc(activePair?.thesisStrength||'NON VALUTABILE')+'</strong></div>'+
   '<div><span>TRADE ATTRACTIVENESS</span><strong>'+esc(activePair?.tradeAttractiveness||'NON VALUTABILE')+'</strong></div>'+
   '<div><span>TIMING · COSA OSSERVARE</span><strong>'+esc(tradeText)+'</strong></div></div>'+
  '<p class="pairs-next-action"><strong>Rafforzerebbe il quadro.</strong> '+esc(gate.improve)+
  ' <strong>Lo indebolirebbe.</strong> '+esc(gate.weaken)+'</p>'+
  (pairCatalyst?.text?'<p class="pairs-next-action pairs-event-watch"><strong>Evento da monitorare.</strong> '+
   esc(pairCatalyst.text)+'</p>':'')+
  '<p class="pairs-vintage">'+esc(context)+'. '+esc(gate.note)+
  ' La baseline macro non viene aggiornata automaticamente quando cambia il prezzo.</p></section>';
 // Do not show a large empty historical panel when same-day model labels
 // were revised after the archived snapshot. Current estimated rankings do not
 // reuse those archived categorical changes as operational signals.
 const historyDetail=monitor.ready?
  '<details class="pairs-optional-panel"><summary><span><strong>Archivio storico · Come è cambiata la tesi?</strong><small>'+esc(report)+'</small></span><span class="pairs-open-icon">+</span></summary>'+
  (window.FXQuantThesisMonitor?.render?.(get('pairs'),get('thesisHistory'),state.pair)||'')+'</details>':'';
 const originalDecision=typeof window!=='undefined'&&window.FXQuantDecisionJourney?.build?
  window.FXQuantDecisionJourney.build({get,state,plot,fmt,sign,date,dayNow,esc}).pair():
  '<div class="empty">Grafico e lettura del prezzo non disponibili.</div>';
 const detail='<details class="pairs-optional-panel pairs-optional-chart"><summary><span><strong>Apri grafico, pricing e analisi completa</strong><small>Fixing BCE, 5/20 sedute, tassi differenziali, rischi e livelli di riferimento</small></span><span class="pairs-open-icon">+</span></summary>'+
  '<div class="pairs-details-body">'+originalDecision+'</div></details>';
 const chooser='<section class="pairs-chooser"><div class="pairs-chooser-top">'+choice+
  '<button class="watch-btn '+(state.watch.has(state.pair)?'saved':'')+'" type="button" data-watch="'+state.pair+'">'+watchLabel+'</button></div>'+
  '<p>28 coppie G8, una sola tesi alla volta. Parti dal giudizio; approfondisci soltanto ciò che conta.</p></section>';
 const ranking=window.FXQuantPairRankings?.render?
  window.FXQuantPairRankings.render({get,FX,FLAGS,state,esc,sign,date,dayNow}):
  '<section class="panel"><p>Ranking non caricato. I feed e le tesi restano consultabili dal selettore.</p></section>';
 const drill=state.pairDetailOpen?
  '<div class="fx-rank-detail-head" id="fx-selected-thesis"><h2>Tesi completa · '+esc(getPairName(state.pair))+
  '</h2><button type="button" class="fx-rank-back" data-pair-close="1">↑ Torna alla classifica</button></div>'+
  chooser+main+historyDetail+detail:'';
 return pageHero('FX / PAIR EXPLORER','Dal G8 alle <em>coppie da approfondire.</em>',
  'Prima la classifica visiva delle valute e delle 28 coppie; poi, scegliendo una coppia, trovi il ragionamento completo su macro, pricing, COT e prezzo.')
  +ranking+drill+
  '<p class="pairs-compact-footer">Classifiche descrittive, non segnali di trading: forza relativa BCE e priorità di ricerca non sono un backtest. Ogni fonte conserva la propria data.</p>';
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
 const streams=get('risk')?.streams||{},a=streams[state.riskStream],x=window.FXQuantRiskEvidence?.read?.(streams,dayNow())||{ready:false,asof:null,headline:'Date cross-asset non verificabili',observation:'Mancano intervalli comuni verificati.',judgement:'Il regime non può essere certificato.',monitor:'Controllare fonti e date.',sourceDates:'date da verificare',quality:'NON VALIDATO'};
 const streamOpts=[['SP500','S&P 500'],['NASDAQCOM','Nasdaq'],['VIX','VIX'],['IG_OAS','Credito IG'],['HY_OAS','Credito HY']];
 const pts=priceHistory(state.riskStream).slice(-Number(state.riskWindow));
 return pageHero('CROSS-ASSET / RISK RADAR','Il rischio non ha <em>un solo termometro.</em>','Unisci azionario, volatilità e credito. Tocca un indicatore per esplorare le serie; le conferme valgono soltanto quando gli orologi sono coerenti.')
 +'<div class="grid cols-4">'+stat('S&P 500',fmt(streams.SP500?.value),date(streams.SP500?.date),sign(streams.SP500?.change_1d_pct,2,'%'),streams.SP500?.change_1d_pct>0?'up':'down')
 +stat('Nasdaq Composite',fmt(streams.NASDAQCOM?.value),date(streams.NASDAQCOM?.date),sign(streams.NASDAQCOM?.change_1d_pct,2,'%'),streams.NASDAQCOM?.change_1d_pct>0?'up':'down')
 +stat('VIX',fmt(streams.VIX?.value),date(streams.VIX?.date),sign(streams.VIX?.change_1d_pct,2,'%'),streams.VIX?.change_1d_pct>0?'down':'up')
 +stat('HY OAS',fmt(streams.HY_OAS?.value)+'%',date(streams.HY_OAS?.date),finite(streams.HY_OAS?.previous)?sign((streams.HY_OAS.value-streams.HY_OAS.previous)*100,0,' pb'):'',streams.HY_OAS?.value>streams.HY_OAS?.previous?'down':'up')+'</div>'
 +'<p class="source-caption">Indicatori rapidi: ciascuno mostra la propria ultima rilevazione, NON necessariamente la stessa seduta. '+esc(x.sourceDates)+'</p>'
 +sectionTitle('Risk Radar interattivo','Cinque stream, nessun proxy confuso con un altro')
 +'<div class="grid tilted"><section class="panel"><div class="panel-head"><div><span class="mini-overline">CROSS-ASSET / SCELTA LIBERA</span><h2>'+esc(streamOpts.find(v=>v[0]===state.riskStream)?.[1]||state.riskStream)+'</h2><p>'+esc(a?.publisher||'Fonte da verificare')+' · '+date(a?.date)+'</p></div></div><div class="filters"><div class="pill-controls">'+streamOpts.map(v=>'<button class="pill '+(v[0]===state.riskStream?'active':'')+'" data-risk="'+v[0]+'" type="button" aria-pressed="'+String(v[0]===state.riskStream)+'">'+v[1]+'</button>').join('')+'</div><div class="pill-controls">'+choose('',[{label:'5 sedute',value:5},{label:'20 sedute',value:20},{label:'Tutto',value:9999}],state.riskWindow,'data-risk-window')+'</div></div>'
 +plot({lines:[{name:streamOpts.find(v=>v[0]===state.riskStream)?.[1],color:state.riskStream==='VIX'||state.riskStream.includes('OAS')?'#ed6679':'#83cdec',values:pts}],unit:state.riskStream.includes('OAS')?'%':'',label:'Grafico '+state.riskStream})+'<div class="chart-summary" style="margin-top:11px">Ultima rilevazione: '+fmt(a?.value)+' · '+(state.riskStream.includes('OAS')?'Variazione dello spread '+sign(finite(a?.value)&&finite(a?.previous)?(a.value-a.previous)*100:null,1,' pb'):'Variazione percentuale '+sign(a?.change_1d_pct,2,'%'))+'. '+esc(a?.not_intraday?'Dato di chiusura, non intraday.':'Verificare orario di rilevazione.')+'</div></section>'
 +'<section class="panel glow risk-research-reading" data-risk-asof="'+esc(x.asof||'')+'"><span class="mini-overline">LETTURA DEL DESK · '+date(x.asof)+'</span>'
 +'<h2 class="focus-headline" style="font-size:22px">'+esc(x.headline)+'</h2>'
 +'<p class="focus-subtitle"><strong>Cosa è successo.</strong> '+esc(x.observation)+'</p>'
 +'<div class="divider"></div><div class="flow-track"><div class="flow-item"><label>Perché conta</label><p>'+esc(x.judgement)+'</p></div>'
 +'<div class="flow-item"><label>Cosa potrebbe smentire la tesi</label><p>'+esc(x.monitor)+'</p></div></div>'
 +'<div class="notice '+(x.stale||!x.ready?'warn':'')+'" style="margin-top:14px">'+esc(x.quality+' · Ultimi feed indipendenti: '+x.sourceDates+'. Sono prezzi di chiusura e spread OAS, non ordini o flussi di copertura dimostrati.')+'</div></section></div>';
}
function news(){
 const n=get('news');
 const calendarFeed=get('calendar');
 const operationalCalendar=window.FXQuantMacroCalendar?.render?.(calendarFeed,dayNow())||
  '<section class="panel"><div class="empty">Calendario macro operativo non disponibile: verifica il caricamento del modulo e delle fonti.</div></section>';
 const evidence=window.FXQuantNewsEvidence?.parse?.(n,dayNow())||{
  pulse:[],official:[],latest:null,gap:'I dati sulle notizie non sono validati.',quality:'NON VALIDATO'};
 const list=state.newsMode==='pulse'?evidence.pulse:evidence.official;
 const type=state.newsMode==='pulse'?'MERCATI / OSSERVAZIONI DATATE':'COMUNICAZIONI UFFICIALI';
 const newsCard=x=>'<article class="timeline-item news-evidence-item" data-news-kind="'+esc(state.newsMode)+'" data-news-asof="'+esc(x.asof)+'">'
  +'<span class="mini-overline">'+esc(x.kind)+' · '+esc(x.ccy||x.source)+' · '+date(x.asof)+(x.time?' · '+esc(x.time)+' IT':'')+'</span>'
  +'<h3>'+esc(x.displayTitle||x.title)+'</h3>'
  +(state.newsMode==='pulse'&&x.body?'<p class="news-evidence-fact"><strong>Il fatto.</strong> '+esc(x.body)+'</p>':'')
  +'<p class="news-evidence-meaning"><strong>Perché monitorarla.</strong> '+esc(x.why)+'</p>'
  +'<div class="news-evidence-citation"><span>'+esc(x.source)+'</span>'
  +(x.url?'<a href="'+esc(x.url)+'" target="_blank" rel="noopener noreferrer">Fonte originale ↗</a>':'')+'</div>'
  +'<details class="news-evidence-details"><summary>Verifiche e limiti dell’evidenza</summary>'
  +'<div class="news-evidence-detail-body"><p><strong>Cosa verificare.</strong> '+esc(x.verify)+'</p>'
  +'<p><strong>Reazione di mercato.</strong> '+esc(x.impact)+'</p>'
  +'<p class="source-caption"><strong>Qualità.</strong> '+esc(x.quality)+'</p>'
  +(x.displayTitle&&x.displayTitle!==x.title?'<p class="source-caption"><strong>Titolo originale.</strong> '+esc(x.title)+'</p>':'')
  +'</div></details></article>';
 return pageHero('NOTIZIE / EVENTI','Dalla notizia <em>alla prova.</em>',
    'Distingui ciò che è stato pubblicato da quello che cambia davvero le aspettative. Una variazione dei futures non è automaticamente una sorpresa macro o la reazione a un comunicato.')
  +operationalCalendar
  +'<div class="filters"><div class="pill-controls">'+choose('',[
    {label:'Movimenti di mercato ('+evidence.pulse.length+')',value:'pulse'},
    {label:'Comunicazioni ufficiali ('+evidence.official.length+')',value:'official'}
   ],state.newsMode,'data-news-mode')+'</div><span class="data-date">Ultima data disponibile '+date(evidence.latest)+'</span></div>'
  +'<div class="grid tilted news-edition-grid"><section class="panel news-evidence-panel"><div class="panel-head"><div><span class="mini-overline">'+type+'</span>'
  +'<h2>'+(state.newsMode==='pulse'?'Cosa è cambiato nei mercati':'Comunicazioni ufficiali: cosa hanno pubblicato le istituzioni')+'</h2>'
  +'<p>Prima il fatto documentato, poi la sua rilevanza. Le prove e i limiti restano espandibili.</p></div></div>'
  +'<div class="timeline">'+(list.length?list.slice(0,20).map(newsCard).join(''):
    '<div class="empty"><strong>Nessuna voce con data verificabile</strong><p>Non sostituiamo eventi mancanti con notizie presunte.</p></div>')
  +'</div></section>'
  +'<aside class="panel glow news-research-reading"><span class="mini-overline">IL GIUDIZIO DEL DESK / NOTIZIE</span>'
  +'<h2 class="focus-headline">Dalla fonte ai prezzi, senza scorciatoie.</h2>'
  +'<p class="focus-subtitle">'+esc(evidence.gap)+'</p>'
  +'<p>Un comunicato non dimostra da solo una sorpresa macro o una reazione FX: servono confronto con le attese e variazioni misurate sulla stessa finestra.</p>'
  +'<div class="news-research-links"><a href="#rates">Tassi & OIS <span aria-hidden="true">↗</span></a>'
  +'<a href="#currencies">Valute G8 <span aria-hidden="true">↗</span></a>'
  +'<a href="#pairs">Coppie FX <span aria-hidden="true">↗</span></a></div>'
  +'<p class="news-research-quality">'+esc(evidence.quality)+' · Impatto intraday da verificare.</p></aside></div>';
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
// A G8 selection re-renders the country dossier. Keep the reader's open
// disclosures (including nested research) instead of collapsing the whole page.
// These are visual states only: data, ranking and FX reasoning remain untouched.
const G8_DISCLOSURES=[
 'details.strength-evidence-fold',
 'details.strength-shadow-fold',
 'details.strength-pair-fold',
 'details.orient-thesis-details',
 'details.strength-method-fold'
];
function g8OpenDisclosures(root){
 return G8_DISCLOSURES.filter(selector=>root.querySelector(selector)?.open);
}
function render(){
 const route=ROUTES[state.route]?state.route:'overview';
 const openG8=route==='currencies'?g8OpenDisclosures($('content')):[];
 // Presentation-only hook for route-scoped colors; no change to calculations or data.
 $('content').dataset.view=route;
 state.charts={};state.chartIndex=0;
 const views={overview,currencies,pairs,macro,rates,cot,risk,news,library:()=>window.FXQuantResearchLibrary?.render()||'<section class="empty">Archivio report non disponibile: controlla il caricamento della pagina.</section>'};
 $('content').innerHTML=(route==='overview'||route==='pairs'||route==='cot'||route==='risk'||route==='news'||route==='library'?'':researchBridge(route))+views[route]();
 // Restore after replacing the DOM; nested details must not close when the
 // user changes currency, comparison, return window or research sorting.
 for(const selector of openG8){
  const panel=$('content').querySelector(selector);
  if(panel)panel.open=true;
 }
 syncRouteChrome(route);
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
function syncRouteChrome(route){
 $('crumb-page').textContent=ROUTES[route];
 document.querySelectorAll('#nav [data-route]').forEach(a=>{
  if(a.dataset.route===route)a.setAttribute('aria-current','page');
  else a.removeAttribute('aria-current');
 });
}
function navigate(){
 const route=location.hash.slice(1).split('?')[0]||'overview';
 state.route=ROUTES[route]?route:'overview';
 // On cold entry, keep the HTML loading state until all research sources have
 // settled. Never flash an empty-data/legacy Home before the hourly edition.
 if(firstResearchLoaded)render();
 else syncRouteChrome(state.route);
 window.scrollTo({top:0,behavior:'instant'});
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
// Keep the pair's open analysis panel mounted when its own chart controls change.
// Replacing #content would recreate <details> closed and jump back to the rankings.
function selectG8Country(trigger){
 const ccy=trigger.dataset.csCountry;
 if(!FX.includes(ccy))return;
 // Keep the clicked row at the same visual position and restore keyboard
 // focus to the equivalent row in the freshly rendered currency dossier.
 const sourceClass=trigger.classList.contains('orient-rank-row')?'orient-rank-row':
  trigger.classList.contains('orient-country')?'orient-country':'strength-row';
 const selector='.'+sourceClass+'[data-cs-country="'+ccy+'"]';
 const oldTop=trigger.getBoundingClientRect().top;
 const oldScroll=window.scrollY;
 state.ccy=ccy;
 if(state.csOther===ccy)state.csOther=FX.find(k=>k!==ccy);
 render();
 const replacement=$('content').querySelector(selector);
 if(replacement){
  replacement.focus({preventScroll:true});
  window.scrollTo({top:Math.max(0,oldScroll+replacement.getBoundingClientRect().top-oldTop),behavior:'instant'});
 }else{
  window.scrollTo({top:oldScroll,behavior:'instant'});
 }
}
function refreshPairPriceChart(focusSelector){
 const body=document.querySelector('#content details.pairs-optional-chart .pairs-details-body');
 if(state.route!=='pairs'||!state.pairDetailOpen||!body||!window.FXQuantDecisionJourney?.build){render();return;}
 const scrollTop=window.scrollY;
 state.charts={};state.chartIndex=0;
 body.innerHTML=window.FXQuantDecisionJourney.build({get,state,plot,fmt,sign,date,dayNow,esc}).pair();
 body.querySelector(focusSelector)?.focus({preventScroll:true});
 window.scrollTo({top:scrollTop,behavior:'instant'});
}
document.addEventListener('click',e=>{
 const calendarResearch=e.target.closest('[data-cal-research]');
 if(calendarResearch&&state.route==='news'){
  const mode=calendarResearch.dataset.calResearch;
  const ccy=calendarResearch.dataset.calCurrency;
  if(!FX.includes(ccy)||!['rates','currencies','pairs'].includes(mode))return;
  e.preventDefault();
  state.ccy=ccy;
  if(state.against===ccy)state.against=FX.find(x=>x!==ccy);
  if(mode==='pairs'){
   const requested=calendarResearch.dataset.calPair||'';
   const reverse=requested.slice(3)+requested.slice(0,3);
   const available=get('pairs')?.pairs||{};
   const resolved=available[requested]?requested:available[reverse]?reverse:null;
   if(resolved){
    state.pair=resolved;state.spotPair=resolved;state.pairDetailOpen=true;
   }else{
    // The pair source is missing. Open the explorer without a fictitious setup.
    state.pairDetailOpen=false;
   }
  }
  state.route=mode;
  // Hashchange owns cross-route rendering, avoiding double-paint.
  if(location.hash==='#'+mode)render();
  else location.hash='#'+mode;
  return;
 }
 const libraryFilter=e.target.closest('[data-library-type]');
 if(libraryFilter && state.route==='library' && window.FXQuantResearchLibrary){
  window.FXQuantResearchLibrary.setCategory(libraryFilter.dataset.libraryType);
  window.FXQuantResearchLibrary.sync();return;
 }
 const pv12=e.target.closest('[data-v12-reference-toggle]');if(pv12){state.pairShowReferences=!state.pairShowReferences;refreshPairPriceChart('[data-v12-reference-toggle]');return;}
 const pv9=e.target.closest('[data-v9-price-window]');if(pv9){const windowSize=Number(pv9.dataset.v9PriceWindow);if(![20,60,120].includes(windowSize))return;state.pairPriceWindow=windowSize;refreshPairPriceChart('[data-v9-price-window="'+windowSize+'"]');return;}
 const cs_ret=e.target.closest('[data-cs-returnwindow]');
 if(cs_ret){state.csReturnWindow=Number(cs_ret.dataset.csReturnwindow);render();return;}
 const cs_country=e.target.closest('[data-cs-country]');if(cs_country){selectG8Country(cs_country);return;}
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
  state.pairDetailOpen=true;
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
   else if(kind==='pair'){state.pair=value;state.spotPair=value;state.pairDetailOpen=true;state.route='pairs';location.hash='#pairs';}
   else if(kind==='route'&&ROUTES[value]){state.route=value;location.hash='#'+value;}
   setQuick(false);render();return;
 }
 const atlas=e.target.closest('[data-atlas]');if(atlas){state.atlasLens=atlas.dataset.atlas;render();return}
 const hc=e.target.closest('[data-hchart]');if(hc){state.homeChart=hc.dataset.hchart;render();return}
 const hw=e.target.closest('[data-hwindow]');if(hw){state.homeWindow=Number(hw.dataset.hwindow);render();return}
 const hp=e.target.closest('[data-home-pair]');if(hp){state.spotPair=hp.dataset.homePair;state.pair=state.spotPair;render();return}
 const c=e.target.closest('[data-ccy]');if(c){state.ccy=c.dataset.ccy;if(state.against===state.ccy)state.against=FX.find(k=>k!==state.ccy);render();return}
 const closePair=e.target.closest('[data-pair-close]');if(closePair){state.pairDetailOpen=false;render();document.getElementById('fx-ranking-desk')?.scrollIntoView({behavior:'smooth',block:'start'});return;}
 const p=e.target.closest('[data-pair]');if(p){state.pair=p.dataset.pair;state.pairDetailOpen=true;if(state.route!=='pairs')location.hash='#pairs';else{render();document.getElementById('fx-selected-thesis')?.scrollIntoView({behavior:'smooth',block:'start'});}return}
 const f=e.target.closest('[data-pfilter]');if(f){state.pairFilter=f.dataset.pfilter;render();return}
 const w=e.target.closest('[data-watch]');if(w){state.watch.has(w.dataset.watch)?state.watch.delete(w.dataset.watch):state.watch.add(w.dataset.watch);saveWatch();render();return}
 const a=e.target.closest('[data-window]');if(a){state.window=Number(a.dataset.window);render();return}
 const b=e.target.closest('[data-rate-mode]');if(b){state.rateMode=b.dataset.rateMode;render();return}
 const k=e.target.closest('[data-metric]');if(k){state.macroMetric=k.dataset.metric;render();return}
 const rs=e.target.closest('[data-risk]');if(rs){state.riskStream=rs.dataset.risk;render();return}
 const rw=e.target.closest('[data-risk-window]');if(rw){state.riskWindow=Number(rw.dataset.riskWindow);render();return}
 const nn=e.target.closest('[data-news-mode]');if(nn){state.newsMode=nn.dataset.newsMode;render();return}
});
document.addEventListener('input',e=>{
 if(e.target.id==='library-search'&&state.route==='library'&&window.FXQuantResearchLibrary){
  window.FXQuantResearchLibrary.setQuery(e.target.value);
  window.FXQuantResearchLibrary.sync();return;
 }
 if(e.target.id==='pair-search'){state.pairSearch=e.target.value;const list=$('pair-results');if(!list)return;const keys=pairListKeys();list.innerHTML=keys.length?keys.map(k=>pairRow(k)).join(''):'<div class="empty"><strong>Nessuna coppia trovata</strong><p>Prova un nome o un filtro diverso.</p></div>';}})
document.addEventListener('toggle',e=>{
 if(e.target?.matches?.('details.macro-advanced'))state.msAdvanced=e.target.open;
 if(e.target?.matches?.('details[data-home-evidence]'))state.homeEvidenceOpen=e.target.open;
 if(e.target?.matches?.('details[data-home-dossier]'))state.homeDossierOpen=e.target.open;
},true);
document.addEventListener('change',e=>{
 if(e.target.id==='pair-primary-select'){const k=e.target.value;if(eurPairs()[k]){state.pair=k;state.pairDetailOpen=true;render()}return;}
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
 // This source is OPTIONAL: it lives exclusively on gh-pages, outside the
 // certified operational-data contract. HTTP 404/invalid free-desk output never
 // changes the existing dashboard or its source-count/readiness receipts.
 jobs.push((async()=>{
  const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),10000);
  try{
   const r=await fetch('../../../market-desk/hourly-market-desk-current.json',{cache:'no-store',signal:ctl.signal});
   if(!r.ok)return;
   const d=await r.json();
   if(d?.schema==='GMFQ_NEXT_FREE_HOURLY_DESK_V1'&&d.status==='ACTIVE'&&
      Array.isArray(d.news)&&d.news.length>0&&d.news.length<=6&&
      validDay(d.generated_at_utc?.slice(0,10))&&
      d.generated_at_utc.slice(0,10)<=dayNow())nextData.hourlyDesk=d;
  }catch(e){
   // The independent editorial feed is not a required operational source.
  }finally{clearTimeout(timer)}
 })());
 try{
  await Promise.allSettled(jobs);
  // Rebuild the entire research from the same fetch cycle. A failed source is
  // not silently reused from the previous edition as a current observation.
  state.data=nextData;
  state.errors=nextErrors;
  lastResearchRefresh=Date.now();
  firstResearchLoaded=true;
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
