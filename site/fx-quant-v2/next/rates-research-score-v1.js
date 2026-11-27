'use strict';
/* Research-only 6M repricing diagnostic. No FX ranking input. */
(function(root){
 const FX=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
 const finite=Number.isFinite;
 const dateOK=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&Number.isFinite(Date.parse(x))&&new Date(Date.parse(x)).toISOString().slice(0,10)===x;
 const days=(a,b)=>dateOK(a)&&dateOK(b)?(Date.parse(b)-Date.parse(a))/864e5:NaN;
 const fresh=(a,b)=>days(a,b)>=0&&days(a,b)<=7;
 const offset=(d,n)=>new Date(Date.parse(d)+n*864e5).toISOString().slice(0,10);
 const same=(a,b)=>finite(a)&&finite(b)&&Math.abs(a-b)<.011;
 const grade=m=>m==='VARIAZIONE FONTE UFFICIALE'?'UFFICIALE':m==='CONTRATTO IDENTICO · RICERCA SECONDARIA'?'SECONDARIA':m==='PROXY BANK-BILL · NON OIS'?'PROXY':'NON VERIFICATA';
 const clamp=x=>Math.max(-1,Math.min(1,x));
 function sovereign(row,today){
  const w=row?.weekly2_validation;
  if(!fresh(row?.date,today)||w?.end_date!==row.date||days(w.start_date,w.end_date)!==7||
   !same(row['2Y'],w.end_value)||!(finite(w.start_value)&&finite(w.end_value)&&finite(w.change_bp)&&Math.abs((w.end_value-w.start_value)*100-w.change_bp)<=.051))return null;
  return {bp:w.change_bp,from:w.start_date,to:w.end_date,source:w.source,kind:'GOV_2Y_NOT_OIS'};
 }
 function observedWeeklyPair(h,last){
  if(!h||!last||!dateOK(last.asof)||!finite(last.rate))return null;
  const points=h.tenors?.['6m']||[],z=points.find(p=>p.date===last.asof);
  const a=points.find(p=>p.date===offset(last.asof,-7)),b=points.find(p=>p.date===offset(last.asof,-14));
  if(!z||!a||!b||[z,a,b].some(p=>p.derived||!finite(p.rate))||!same(z.rate*100,last.rate*100))return null;
  if(![z,a,b].every(p=>p.source_class===z.source_class))return null;
  if(h.kind!=='OIS'&&(!z.contract||z.contract!==a.contract||z.contract!==b.contract))return null;
  if(h.kind==='OIS'&&z.source_class!=='OFFICIAL_TENOR')return null;
  const current=(z.rate-a.rate)*100,previous=(a.rate-b.rate)*100;
  if(!same(current,last.week?.bp))return null;
  return {current,previous,acceleration:Math.round((current-previous)*100)/100,from:b.date,mid:a.date,to:z.date,contract:z.contract||'OIS 6M'};
 }
 // Recent exact observed week on the currently listed secondary contract.
 // Never represent it as the latest weekly change or an official rate.
 function recentSecondaryWeek(h,last,today){
  if(h?.kind!=='FUTURES SECONDARI'||last?.week||!fresh(last?.asof,today)||!last.contract||!finite(last.rate))return null;
  const pts=h.tenors?.['6m']||[];
  const eligible=p=>p&&p.contract===last.contract&&p.source_class==='SECONDARY_SAME_CONTRACT'&&p.derived===false&&finite(p.rate)&&dateOK(p.date);
  const anchor=pts.find(p=>p.date===last.asof);
  if(!eligible(anchor)||!same(anchor.rate*100,last.rate*100))return null;
  const to=offset(last.asof,-1),from=offset(to,-7);
  const z=pts.find(p=>p.date===to),x=pts.find(p=>p.date===from);
  if(!fresh(to,today)||!eligible(z)||!eligible(x))return null;
  return {bp:Math.round((z.rate-x.rate)*10000)/100,from,to,contract:last.contract,source:h.source,kind:'RECENT_EXACT_SECONDARY_WEEK'};
 }
 function evaluate({pricing,archive,snapshot,operational,research,nzd,history,rates,today,currency,other}={}){
  if(!pricing?.readCurrency||!FX.includes(currency)||!dateOK(today))return null;
  function one(c){
   const m=pricing.readCurrency(c,snapshot,operational,research,nzd,today),r=m.rows.find(x=>x.tenor==='6m');
   const w=fresh(r?.asof,today)&&r.week&&finite(r.week.bp)?r.week:null;
   const quality=grade(w?.method),week=quality!=='NON VERIFICATA'?w:null;
   const h=archive?.country?.(history,c,60);
   const hist=h?.kind===m.kind&&h.source===m.source&&fresh(history?.as_of,today)?h:null;
   const moves=hist?archive.horizonMoves(hist):[];
   const twenty=moves.find(x=>x.days===20&&x.to===r.asof&&finite(x.bp)&&!x.derived&&!x.approximateWindow&&!/rollover possibile/i.test(x.basis||''));
   const acceleration=week?observedWeeklyPair(hist,r):null;
   // +/-25bp is an explicit illustrative scale, not a fitted sensitivity.
   // Non-official sources never get promoted to an official score.
   const score=week?5+5*clamp(week.bp/25):null;
   return {currency:c,kind:m.kind,source:m.source,asof:r.asof,level:r.rate,one:r.one?.bp??null,week:week?.bp??null,
    referenceFrom:week?.from||null,score,quality,officialScore:quality==='UFFICIALE'?score:null,
    twenty:twenty?.bp??null,twentyBasis:twenty?.basis||null,acceleration,recentSecondaryWeek:recentSecondaryWeek(hist,r,today),gov:sovereign(rates?.[c],today)};
  }
  const row=one(currency),peer=FX.includes(other)&&other!==currency?one(other):null;
  const matched=peer&&finite(row.week)&&finite(peer.week)&&row.asof===peer.asof&&row.referenceFrom&&row.referenceFrom===peer.referenceFrom;
  const relative=matched?{bp:row.week-peer.week,from:row.referenceFrom,to:row.asof,
   quality:row.kind===peer.kind&&row.quality==='UFFICIALE'&&peer.quality==='UFFICIALE'?'SAME_TYPE_OFFICIAL':'MIXED_OR_INDICATIVE'}:null;
  return {row,peer,relative,eligibleForTrading:false,affectsFxRanking:false,method:'UNCALIBRATED_25BP_WEEKLY_6M'};
 }
 function render(x,esc=s=>String(s??'')){
  if(!x)return '';
  const a=x.row,n=v=>finite(v)?v.toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:2}):'—',bp=v=>finite(v)?(v>0?'+':'')+n(v)+' pb':'—';
  const q=a.quality==='UFFICIALE'?'Fonte ufficiale':a.quality==='SECONDARIA'?'Ricerca secondaria':a.quality==='PROXY'?'Proxy bank-bill':'Confronto non verificato';
  const tone=v=>!finite(v)?'neutral':v>0?'up':v<0?'down':'flat';
  return '<details class="rates-score-research" data-rates-score-research-v1><summary><strong>Rates Score · ricerca</strong> · '+esc(a.currency)+' '+esc(a.score===null?'Non valutabile':n(a.score)+'/10')+' · '+esc(q)+'</summary>'+
   '<p>Riferimento 6M: '+esc(a.kind||'n.d.')+' · '+esc(a.asof||'n.d.')+' · '+esc(a.source||'Fonte assente')+'. Il punteggio 5 è neutro; ±25 pb settimanali corrispondono a 0/10 o 10/10. Scala sperimentale non calibrata, non una probabilità o un segnale FX. Nessun ranking tra fonti disomogenee.</p>'+
   '<ul><li>Livello 6M: '+esc(n(a.level))+'%</li><li class="'+tone(a.one)+'">Ultimo confronto giornaliero: '+esc(bp(a.one))+'</li><li class="'+tone(a.week)+'">Variazione settimanale: '+esc(bp(a.week))+'</li><li>20 giorni feriali esatti: '+esc(bp(a.twenty))+(a.twentyBasis?' · '+esc(a.twentyBasis):'')+'</li>'+
   '<li>Accelerazione settimanale (due intervalli consecutivi omogenei): '+esc(bp(a.acceleration?.acceleration))+'</li>'+
   '<li>Governativo 2Y, variazione settimanale separata: '+esc(bp(a.gov?.bp))+(a.gov?' · '+esc(a.gov.from+' → '+a.gov.to):'')+' · non OIS</li></ul>'+
   (x.peer?'<p>Confronto '+esc(a.currency+'/'+x.peer.currency)+': '+(x.relative?esc(bp(x.relative.bp)+' · '+x.relative.from+' → '+x.relative.to+' · '+(x.relative.quality==='SAME_TYPE_OFFICIAL'?'stesso tipo di strumento ufficiale':'strumenti disomogenei o indicativi')):'Intervallo iniziale e finale comune non verificato: differenza non calcolata.')+'</p>':'')+
   '<p>Il 2Y non sostituisce il 6M. Le variazioni secondarie e proxy rimangono indicative. Il ranking operativo non viene modificato.</p></details>';
 }
 const api={evaluate,render,sovereign,observedWeeklyPair,recentSecondaryWeek};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FXQuantRatesResearchScore=api;
})(typeof window==='undefined'?globalThis:window);
