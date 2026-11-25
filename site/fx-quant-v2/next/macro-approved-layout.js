'use strict';
(function(root){
const E=root.FXQuantRecessionLight,FX=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'],N={USD:'Stati Uniti',EUR:'Area euro',GBP:'Regno Unito',JPY:'Giappone',CHF:'Svizzera',AUD:'Australia',NZD:'Nuova Zelanda',CAD:'Canada'},B={USD:'Fed',EUR:'BCE',GBP:'BoE',JPY:'BoJ',CHF:'SNB',AUD:'RBA',NZD:'RBNZ',CAD:'BoC'},F={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',AUD:'🇦🇺',NZD:'🇳🇿',CAD:'🇨🇦'},A=['Case','Lavoro','Industria','Servizi','Anticipatori','Consumi','Credito'],T={green:'Migliora',red:'Peggiora',amber:'Misto',neutral:'Non valutabile'},S={green:'↗',red:'↘',amber:'→',neutral:'—'},G=['green','amber','red','neutral'],esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),num=(x,n=1)=>Number.isFinite(x)?x.toLocaleString('it-IT',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const names=cs=>cs.map(c=>N[c]).join(', ');
function countryReadings(raw, day, overlay) {
 return Object.fromEntries(FX.map(currency => {
   const r = E.model(raw, day, currency, overlay);
   const i = E.inflationContext(raw, day, currency, overlay);
   const w = E.wageContext(raw, day, currency, overlay);
   const e = E.externalContext(day, currency, overlay);
   const t = E.turningPointMonitor(r);
   const n = E.macroNarrative(r, i, w, e, t);
   const o = E.overviewCountry(r, i, w, e, t, n);
   return [currency, {r, i, w, e, t, n, o, regime: E.regimePosition(o)}];
 }));
}
function globalReading(U) {
 const groups = Object.fromEntries(G.map(tone => [tone, FX.filter(c => U[c].o.reading.aggregateTone === tone)]));
 const counts = G.map(tone => groups[tone].length);
 const covered = FX.reduce((total, c) => total + U[c].o.coverage, 0);
 const priceDirection = direction => FX.filter(c => {
   const headline = U[c].o.head;
   return headline?.available && !headline.stale && headline.direction === direction;
 });
 const laborDirection = tone => FX.filter(c => U[c].r.find(area => area.key === 'jobs')?.signal.tone === tone);
 const dilemma = FX.filter(c => U[c].regime.quadrant === 'down_up');

 let headline = 'Il ciclo globale procede a velocità diverse.';
 if (counts[3] >= 4) headline = 'Un quadro globale ancora incompleto.';
 else if (counts[0] >= 3 && counts[0] > counts[2]) headline = 'I segnali di recupero prevalgono.';
 else if (counts[2] >= 3 && counts[2] > counts[0]) headline = 'La debolezza si sta diffondendo.';
 const narrative = [
   groups.green.length && 'Le aree in miglioramento prevalgono in ' + names(groups.green) + '.',
   groups.red.length && 'Le aree in deterioramento prevalgono in ' + names(groups.red) + '.',
   groups.amber.length && 'Il quadro resta misto in ' + names(groups.amber) + '.',
   groups.neutral.length && 'Per ' + names(groups.neutral) + ' il giudizio complessivo resta parziale.'
 ].filter(Boolean).join(' ');
 const coverageNote = 'Un quadro paese richiede almeno quattro aree valide con osservazioni distribuite su non più di 120 giorni. La copertura conta le singole aree classificabili.';
 const growth = counts[0] || counts[2]
   ? [counts[0] ? 'Miglioramento diffuso in ' + names(groups.green) + '.' : '',
      counts[2] ? 'Deterioramento diffuso in ' + names(groups.red) + '.' : ''].filter(Boolean).join(' ')
   : 'Le osservazioni disponibili non indicano una direzione prevalente dell’attività.';
 return {
   counts, covered, headline, narrative, coverageNote, growth, dilemma,
   priceUp: priceDirection('accelera'), priceDown: priceDirection('rallenta'),
   laborUp: laborDirection('green'), laborDown: laborDirection('red')
 };
}
function countryScope({reading}) {
 if (!reading.aligned) return 'Le evidenze settoriali restano consultabili. Il giudizio complessivo richiede almeno quattro aree valide e periodi sufficientemente allineati.';
 const breadth = {green:'Il miglioramento prevale fra le aree.', red:'Il deterioramento prevale fra le aree.', amber:'Le aree mostrano direzioni miste.'};
 return breadth[reading.aggregateTone] + ' Il giudizio qui sopra evidenzia il principale sviluppo settoriale.';
}
function renderDesk({catalog={},overlay=null,feedStatus=null,dayNow,country:selected='USD'}={}){
 if(!E)return '';
 const raw=catalog,day=dayNow(),chosen=FX.includes(selected)?selected:'USD';
 const U=countryReadings(raw,day,overlay);
const codes=cs=>cs.length?cs.join(' · '):'—';
function metric(label,x){const ok=x?.available&&Number.isFinite(x.value),current=ok&&!x.stale&&x.freq!=='A'&&x.direction;return '<div class="rd-metric"><span>'+esc(label)+'</span><strong>'+ (ok?num(x.value)+'%':'—')+'</strong><small>'+esc(ok?x.period+(current?' · '+x.direction:x.stale||x.freq==='A'?' · dato datato':' · direzione n.d.'):'Non disponibile')+'</small></div>'}
function chart(s){const p=s.points||[];if(p.length<3||p.some(x=>!Number.isFinite(x.value)))return '';const vals=p.map(x=>x.value),threshold=Number.isFinite(s.threshold)?s.threshold:null;let lo=Math.min(...vals,...(threshold===null?[]:[threshold])),hi=Math.max(...vals,...(threshold===null?[]:[threshold]));if(hi===lo){lo-=1;hi+=1}const y=v=>20+(hi-v)/(hi-lo)*100,x=k=>38+k/(p.length-1)*284,path=p.map((v,k)=>(k?'L':'M')+x(k).toFixed(2)+' '+y(v.value).toFixed(2)).join(' ');return '<article class="rd-chart"><header><h4>'+esc(s.title)+'</h4><strong>'+num(vals.at(-1))+' <small>'+esc(s.unit)+'</small></strong></header><svg viewBox="0 0 345 150" role="img" aria-label="'+esc(s.title+', '+p[0].period+'–'+p.at(-1).period)+'"><g stroke="#354354" stroke-width="0.7">'+[20,70,120].map(v=>'<path d="M38 '+v+' H322"/>').join('')+'</g><g fill="#a3adbc" font-size="9"><text x="0" y="23">'+num(hi)+'</text><text x="0" y="123">'+num(lo)+'</text><text x="38" y="141">'+esc(p[0].period)+'</text><text x="322" y="141" text-anchor="end">'+esc(p.at(-1).period)+'</text></g>'+(threshold===null?'':'<path d="M38 '+y(threshold)+' H322" stroke="#d9b778" stroke-dasharray="4 4" opacity=".7"/>')+'<path d="'+path+'" fill="none" stroke="#a9c9e5" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="322" cy="'+y(vals.at(-1))+'" r="3" fill="#a9c9e5"/></svg><small>'+esc(p.at(-1).period+' · '+p.length+' osservazioni · '+(s.stale?'dato datato · ':'')+s.source)+'</small></article>'}
function country(){const {r,i,w,e,t,n,o}=U[chosen],q=o.reading,h=E.countryHistories(raw,day,chosen,overlay,r,{inflation:i,wages:w,external:e});const charts=[...(h.activity||[]).slice(0,1),...(h.inflation||[]).slice(0,1),...(h.wages||[]).slice(0,1),...(h.exports||[]).slice(0,1)].filter(Boolean);return '<div class="rd-section-head"><div><span class="rd-eyebrow">02 / DOSSIER PAESE</span><h2>'+F[chosen]+' '+esc(N[chosen])+'</h2></div><p>'+esc(o.coverage+'/7 aree classificabili · '+q.quality)+'</p></div><div class="rd-country-tabs" aria-label="Scegli economia">'+FX.map(c=>'<button data-ms-country="'+c+'" aria-pressed="'+(c===chosen)+'">'+F[c]+' '+c+'</button>').join('')+'</div><div class="rd-country-body"><div><span class="rd-eyebrow '+q.aggregateTone+'">GIUDIZIO ECONOMICO</span><h3 class="'+q.aggregateTone+'">'+esc(q.aligned?q.label:'Quadro parziale')+'</h3><p class="rd-lead">'+esc(q.economy)+'</p><p class="rd-fine">'+esc(countryScope(o))+'</p><p class="rd-fine">'+esc(t.judgment)+'</p></div><div class="rd-country-side"><article><h4>Perché conta per la '+B[chosen]+'</h4><p>'+esc(q.policy)+'</p><a href="#rates">Verifica il pricing dei tassi ↗</a></article><article><h4>Cosa monitorare adesso</h4><p>'+esc(q.watch)+'</p></article></div></div><div class="rd-metrics">'+metric('Inflazione headline',o.head)+metric('Inflazione core / proxy',o.core)+metric('Salari nominali',o.wage)+metric('Export reale',o.external)+'</div>'+(charts.length?'<div class="rd-chart-grid">'+charts.map(chart).join('')+'</div>':'<p class="rd-empty">Serie storiche confrontabili non disponibili per questa selezione.</p>')+'<details class="rd-detail"><summary>Sette aree · osservazioni, fonti e motivazione del giudizio</summary>'+r.map(a=>'<div class="rd-evidence"><div><h4>'+esc(a.name)+'</h4><span class="'+a.signal.tone+'">'+S[a.signal.tone]+' '+T[a.signal.tone]+'</span></div><ul>'+((a.items||[]).filter(Boolean).map(v=>'<li>'+esc(v.metric.name)+' · '+esc(v.prior)+' → '+esc(v.period)+(v.metric.hideValue?'':' · '+num(v.previous/(v.metric.scale||1),2)+' → '+num(v.current/(v.metric.scale||1),2)+' '+esc(v.metric.unit||'unità fonte'))+' · '+esc(v.source)+(v.stale?' · dato datato':'')+'</li>').join('')||'<li>Non disponibile</li>')+'</ul></div>').join('')+'<p>'+esc(n.growth)+'</p><p>'+esc(n.prices)+'</p><p>'+esc(n.trade)+'</p></details>'}
function countryAccess() {
 return '<section class="rd-country-access" aria-labelledby="rd-country-access-title">'+
  '<h3 id="rd-country-access-title">Apri un dossier paese</h3><div class="rd-country-access-grid">'+
  FX.map(c=>'<button type="button" data-ms-country="'+c+'" data-rd-jump aria-controls="rd-country">'+
   '<span aria-hidden="true">'+F[c]+'</span> '+esc(N[c])+'</button>').join('')+'</div></section>';
}
function render(){
const {counts, covered, headline, narrative, coverageNote, growth, priceUp, priceDown, laborUp, laborDown, dilemma}=globalReading(U);
return '<section class="rd-global"><div><span class="rd-eyebrow">IL QUADRO DI OGGI</span><h2>'+esc(headline)+'</h2><p class="rd-lead">'+esc(narrative)+'</p><p class="rd-fine">'+esc(coverageNote)+'</p>'+countryAccess()+'<button type="button" class="ghost-btn small rd-compare-jump" data-rd-compare-jump>Vai al confronto G8</button><p class="rd-fine">Lettura descrittiva della direzione delle aree.</p></div><aside><span class="rd-eyebrow">DIFFUSIONE · 8 ECONOMIE</span><div class="rd-breadth">'+G.map((g,k)=>'<div><strong class="'+g+'">'+counts[k]+'</strong><span>'+({green:'In recupero',red:'In deterioramento',amber:'Miste',neutral:'Giudizio parziale'}[g])+'</span></div>').join('')+'</div><div class="rd-coverage"><strong data-role="coverage" data-covered="'+covered+'">'+covered+'/56</strong> aree classificate<div class="rd-track" role="progressbar" aria-label="Copertura G8" aria-valuemin="0" aria-valuemax="56" aria-valuenow="'+covered+'"><i style="width:'+(covered/56*100)+'%"></i></div></div></aside></section><div class="rd-insights"><article><h3>Crescita e attività</h3><p>'+esc(growth)+'</p></article><article><h3>Pressioni inflazionistiche</h3><p><span class="red">Accelerano</span> · '+codes(priceUp)+'<br><span class="green">Rallentano</span> · '+codes(priceDown)+'</p><p class="rd-fine">Headline; periodi nazionali diversi.</p></article><article><h3>Tenuta dell’occupazione</h3><p><span class="green">Migliora</span> · '+codes(laborUp)+'<br><span class="red">Peggiora</span> · '+codes(laborDown)+'</p></article><article><h3>Il dilemma crescita–prezzi</h3><p>'+esc(dilemma.length?'Attività in deterioramento e inflazione in accelerazione: '+names(dilemma)+'.':'Nessun dilemma classificato con le regole di allineamento attuali.')+'</p><a href="#rates">Controlla le aspettative monetarie ↗</a></article></div><section class="rd-section" id="rd-compare" tabindex="-1"><div class="rd-section-head"><div><span class="rd-eyebrow">01 / CONFRONTO G8</span><h2>Dove cambia il ciclo</h2></div><p>Seleziona un’economia per leggere il giudizio e le evidenze. I colori esprimono direzione, non forza valutaria.</p></div><div class="rd-matrix-wrap" tabindex="0" role="region" aria-label="Matrice G8 scorrevole"><table aria-label="Direzione economica G8"><thead><tr><th>Economia</th>'+A.map(a=>'<th>'+a+'</th>').join('')+'<th>Giudizio</th></tr></thead><tbody>'+FX.map(c=>'<tr data-row="'+c+'" class="'+(chosen===c?'selected':'')+'"><th scope="row"><button data-ms-country="'+c+'" data-rd-jump>'+F[c]+' '+c+' <small>↗</small></button></th>'+U[c].o.cells.map(a=>'<td><span class="rd-cell '+a.tone+'" title="'+esc(a.name+' · '+T[a.tone]+' · '+a.periods.join(', '))+'"><b>'+S[a.tone]+'</b>'+esc(a.phase?U[c].o.phaseLabels[a.phase]:T[a.tone])+'</span></td>').join('')+'<td class="'+U[c].o.reading.aggregateTone+'">'+esc(U[c].o.reading.aligned?U[c].o.label:'Quadro parziale')+'</td></tr>').join('')+'</tbody></table></div><div class="rd-legend">'+G.map(g=>'<span><b class="'+g+'">'+S[g]+'</b>'+T[g]+'</span>').join('')+'</div></section><section id="rd-country" tabindex="-1" class="rd-section">'+country()+'</section>';}

 const covered=FX.reduce((sum,c)=>sum+U[c].o.coverage,0),mode=feedStatus?.mode||(overlay?'provided':'missing');
 const coreOK=FX.some(c=>Array.isArray(raw[c]));
 const warn=!coreOK||mode==='missing'||mode==='retained';
 const message=!coreOK?'Archivio macro non disponibile. ':'';
 const note=mode==='missing'?'Copertura parziale: fonti supplementari non caricate. Non interpretare i dati mancanti come deterioramento.':mode==='retained'?'Aggiornamento non riuscito: ultimo archivio disponibile '+esc(feedStatus?.as_of)+'. Periodi originali invariati.':'Fonti supplementari · '+esc(feedStatus?.as_of||overlay?.as_of||'data non disponibile');
 return '<section class="rd-root recession-light" data-semaphore-coverage="'+covered+'" data-semaphore-feed="'+esc(mode)+'" data-rd-layout="approved-preview"><div class="rd-source '+(warn?'rd-warning':'')+'" role="status">'+message+note+(warn?' <button type="button" class="ghost-btn small" data-sem-feed-retry>Riprova</button>':'')+'</div>'+render()+'<p class="rd-fine">I segnali non sono un ranking di forza FX né una previsione di recessione. Dati revisionabili, non point-in-time. Periodi osservati, non date di rilascio.</p></section>';
}
root.FXQuantMacroDesk={render:renderDesk, countryReadings, globalReading, countryScope};
})(window);
