(()=>{
'use strict';
const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const H=['policy','3m','6m','12m'];
const SRC='live_data/sections/OIS_OPERATIONAL_VIEW.json';
const state={status:'INIT',data:null,error:null,loaded_at:null};
window.GMFQ_OIS_OPERATIONAL_UI=state;
function fmtRate(v){return v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v))?Number(v).toFixed(3).replace(/0+$/,'').replace(/\.$/,'')+'%':'—';}
function fmtBp(v){if(v===null||v===undefined||v===''||!Number.isFinite(Number(v)))return '—';const n=Number(v);return `${n>0?'+':''}${n.toFixed(1)} bp`;}
function clsBp(v){if(v===null||v===undefined||v===''||!Number.isFinite(Number(v)))return 'neu';return Number(v)>0?'up':Number(v)<0?'down':'neu';}
function rowRate(r,h){if(r.operational_status==='WITHHELD')return null;if(h==='policy')return r.policy_rate;return r?.horizons?.[h]?.rate;}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function validate(d){
 if(!d||d.schema!=='GMFQ_OIS_OPERATIONAL_VIEW_V1')throw new Error('schema OIS operational inatteso');
 if(!['GREEN_8_OF_8','PARTIAL_WITHHELD'].includes(d.status))throw new Error('OIS operational status inatteso');
 if(d?.summary?.g8_total!==8||d.summary.operational_green+d.summary.operational_withheld!==8)throw new Error('copertura OIS incoerente');
 for(const c of CCYS){
   const r=d?.currencies?.[c];
   if(!r)throw new Error('valuta OIS mancante: '+c);
   if(!['GREEN_OFFICIAL','GREEN_ESTIMATED','WITHHELD'].includes(r.operational_status))throw new Error('status OIS invalido '+c);
   const sq=r.secondary_quote_context;
   if(sq){
     if(!['USD','EUR','CHF'].includes(c)||r.operational_status!=='WITHHELD')throw new Error('futures info context non ammesso '+c);
     if(sq.status!=='INDICATIVE_OBSERVATIONS_NON_OIS'||sq.full_curve_usable!==false||sq.cross_date_join_allowed!==false||sq.policy_delta_allowed!==false||sq.repricing_signal_allowed!==false||sq.backtest_eligible_as_official!==false)throw new Error('futures info governance '+c);
     for(const [h,q] of Object.entries(sq.horizons||{})){
       if(!['3m','6m','12m'].includes(h)||!Number.isFinite(Number(q?.rate_indicative))||!/^\d{4}-\d{2}-\d{2}$/.test(q?.quote_as_of||''))throw new Error('futures quote invalid '+c+'/'+h);
     }
   }
   const p=r.market_direction_proxy;
   if(p){
     if(c!=='NZD')throw new Error('market direction proxy consentito solo per NZD');
     if(p.status!=='LIVE_DIRECTIONAL_PROXY_READY')throw new Error('NZD market direction proxy non READY');
     if(p.substitutes_for_ois_level!==false)throw new Error('NZD proxy non puo sostituire OIS');
     if(p.policy_delta_from_proxy_allowed!==false)throw new Error('NZD proxy non puo generare policy delta');
     for(const h of ['3m','6m','12m']){
       if(!Number.isFinite(Number(p?.horizons?.[h]?.implied_bank_bill_rate)))throw new Error('NZD proxy horizon mancante '+h);
     }
   }
 }
 return d;
}
function ensureHost(){
 let host=document.getElementById('v401OisBlock');
 if(host)return host;
 const desk=document.getElementById('ratesdesk');
 if(!desk)return null;
 host=document.createElement('div');
 host.id='v401OisBlock';
 host.dataset.owner='GMFQ_OIS_OPERATIONAL_UI_V1';
 host.className='gmfqOisOperationalMount';
 const anchor=document.getElementById('v233RatesGrid')||document.getElementById('v233RatesRead')||document.getElementById('v233CurrencyCards');
 if(anchor&&desk.contains(anchor)){
   const shell=anchor.closest('.v272Truth');
   if(shell&&shell.parentElement===desk) shell.insertAdjacentElement('afterend',host);
   else anchor.insertAdjacentElement('afterend',host);
 } else {
   desk.appendChild(host);
 }
 return host;
}
function style(){
 if(document.getElementById('gmfq-ois-operational-style'))return;
 const s=document.createElement('style');s.id='gmfq-ois-operational-style';s.textContent=`
 #v401OisBlock{display:block!important;margin-top:14px;max-width:100%;min-width:0;overflow:hidden;border:1px solid #173d55;background:#081723;border-radius:12px;padding:12px}#v401OisBlock .oisOp{display:grid;gap:12px;min-width:0}.oisOpHead{display:flex;gap:10px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}.oisOpTitle{font-size:16px;font-weight:900}.oisOpSub{color:#8eabba;font-size:11px;line-height:1.45;max-width:760px}.oisOpBadges{display:flex;gap:6px;flex-wrap:wrap}.oisBadge{font-size:9px;font-weight:850;border:1px solid #31536a;border-radius:999px;padding:4px 7px}.oisBadge.off{color:#20df76;border-color:rgba(32,223,118,.45);background:rgba(32,223,118,.07)}.oisBadge.est{color:#f2bb49;border-color:rgba(242,187,73,.45);background:rgba(242,187,73,.07)}
 .oisPathGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;min-width:0}.oisPathCard{border:1px solid #173d55;background:#071a28;border-radius:9px;padding:9px;min-width:0}.oisPathTop{display:flex;align-items:center;justify-content:space-between;gap:6px}.oisPathCcy{font-size:14px;font-weight:900}.oisPathMeta{font-size:8px;border-radius:999px;padding:3px 5px;border:1px solid #31536a}.oisPathMeta.off{color:#20df76;border-color:rgba(32,223,118,.4)}.oisPathMeta.est{color:#f2bb49;border-color:rgba(242,187,73,.4)}.oisPathCard svg{width:100%;height:72px;display:block;margin-top:5px}.oisPathVals{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:3px;font-size:8px;color:#7696a8}.oisPathVals b{display:block;color:#dcecf4;font-size:10px;margin-top:2px}.oisAsOf{font-size:8px;color:#6e91a2;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .oisProxyBox{margin-top:8px;border:1px solid rgba(35,183,255,.3);background:rgba(35,183,255,.055);border-radius:8px;padding:7px;display:grid;gap:6px}.oisProxyHead{display:flex;justify-content:space-between;gap:6px;align-items:center}.oisProxyTitle{font-size:8px;font-weight:900;letter-spacing:.05em;color:#8fdcff}.oisProxyFlag{font-size:7px;font-weight:900;color:#ffca62;border:1px solid rgba(255,202,98,.45);border-radius:999px;padding:2px 5px;white-space:nowrap}.oisProxyGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.oisProxyCell{min-width:0;border-left:1px solid rgba(49,83,106,.55);padding-left:5px}.oisProxyCell:first-child{border-left:0;padding-left:0}.oisProxyHz{font-size:7px;color:#7899aa}.oisProxyRate{font-size:10px;font-weight:850;color:#dcecf4;margin:1px 0}.oisProxyMove{font-size:7px;color:#86a6b7;line-height:1.35}.oisProxyMove .up{color:#20df76}.oisProxyMove .down{color:#b99aff}.oisProxyNote{font-size:7px;color:#7493a4;line-height:1.35}
 .oisReprice{overflow-x:auto;max-width:100%}.oisReprice table{min-width:760px;width:100%}.oisReprice th,.oisReprice td{font-size:9px;padding:6px 5px}.oisReprice td.up{color:#20df76}.oisReprice td.down{color:#b99aff}.oisReprice td.neu{color:#91aebe}.oisQuality{font-size:8px;font-weight:850;border-radius:999px;padding:3px 5px;border:1px solid #31536a}.oisQuality.off{color:#20df76;border-color:rgba(32,223,118,.4)}.oisQuality.est{color:#f2bb49;border-color:rgba(242,187,73,.4)}.oisFoot{font-size:9px;color:#7899aa;line-height:1.45}.oisFail{border:1px solid rgba(255,82,99,.45);background:rgba(255,82,99,.06);color:#ff929d;border-radius:8px;padding:10px;font-size:11px}
 .oisScenarioBox{margin-top:8px;border:1px solid rgba(194,177,250,.36);background:rgba(194,177,250,.06);border-radius:9px;padding:9px;display:grid;gap:8px}.oisScenarioGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.oisScenarioCell{min-width:0;display:grid;gap:2px}.oisScenarioCell span,.oisScenarioCell small{color:#aeb8d5;font-size:9px}.oisScenarioCell b{color:#d4c6ff;font-size:13px;font-weight:850} 
 .oisSaronTruth{display:grid;gap:6px;margin-top:8px;padding:8px;border:1px solid rgba(242,187,73,.3);background:rgba(242,187,73,.04);border-radius:8px;color:#e3d7b6;font-size:10px;line-height:1.5;overflow-wrap:anywhere}.oisSaronTruth strong{font-size:10px;color:#f2cf7b}.oisSaronTruthRows{display:grid;gap:3px}.oisSaronTruthRows span b{color:#fff}.oisSaronTruth small{font-size:10px;line-height:1.5;color:#bcae85}\n .oisResearchQuotes{margin-top:8px;border:1px solid rgba(242,187,73,.32);background:rgba(242,187,73,.045);border-radius:9px;padding:9px;display:grid;gap:8px}.oisResearchHead{font-size:10px;line-height:1.45;font-weight:800;color:#f2cf7b}.oisResearchGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.oisResearchCell{min-width:0;border-left:1px solid rgba(242,187,73,.2);padding-left:6px}.oisResearchCell:first-child{border:0;padding-left:0}.oisResearchHz{font-size:9px;color:#9ab4c2}.oisResearchRate{font-size:12px;font-weight:850;color:#f0f6fa;margin-top:2px}.oisResearchDate{font-size:9px;color:#b3a47f;margin-top:2px;overflow-wrap:anywhere}.oisResearchNote{font-size:10px;line-height:1.45;color:#c9b98d}
 @media(max-width:1050px){.oisPathGrid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.oisPathGrid{grid-template-columns:1fr}.oisPathVals{grid-template-columns:repeat(4,minmax(52px,1fr))}.oisProxyGrid{grid-template-columns:repeat(3,minmax(0,1fr))}}
 `;document.head.appendChild(s);
}
function pathSvg(r,min,max){
 const vals=H.map(h=>rowRate(r,h));
 const W=220,HGT=72,pad=10,span=Math.max(.01,max-min);const pts=[];
 vals.forEach((v,i)=>{if(v===null||v===undefined||!Number.isFinite(Number(v)))return;const x=pad+i*((W-2*pad)/3);const y=pad+(max-Number(v))/span*(HGT-2*pad);pts.push([x,y,i]);});
 const poly=pts.length>1?`<polyline points="${pts.map(p=>p[0]+','+p[1]).join(' ')}" fill="none" stroke="#23b7ff" stroke-width="2"/>`:'';
 const dots=pts.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="#eef7ff" stroke="#23b7ff" stroke-width="1.5"/>`).join('');
 return `<svg viewBox="0 0 ${W} ${HGT}" aria-label="Policy path ${esc(r.operational_status)}"><line x1="10" x2="210" y1="62" y2="62" stroke="#173d55"/>${poly}${dots}</svg>`;
}
function proxyMove(v){return `<span class="${clsBp(v)}">${fmtBp(v)}</span>`;}
function proxyHtml(c,r){
 const p=r?.market_direction_proxy;
 if(c!=='NZD'||!p)return '';
 const cells=['3m','6m','12m'].map(h=>{const x=p?.horizons?.[h]||{};return `<div class="oisProxyCell"><div class="oisProxyHz">${h.toUpperCase()}</div><div class="oisProxyRate">${fmtRate(x.implied_bank_bill_rate)}</div><div class="oisProxyMove">1D ${proxyMove(x.change_1d_bp)}<br>1W ${proxyMove(x.change_1w_bp)}</div></div>`;}).join('');
 return `<div class="oisProxyBox" data-ois-proxy="NZD_ASX_BB_DIRECTIONAL" title="${esc(p.basis_warning||'Directional market-rates proxy; non OCR/OIS')}"><div class="oisProxyHead"><span class="oisProxyTitle">ASX BB DIRECTIONAL</span><span class="oisProxyFlag">NON OIS</span></div><div class="oisProxyGrid">${cells}</div><div class="oisProxyNote">Bank-bill/FRA proxy · solo direzione di mercato · as-of ${esc(p.as_of||'—')}</div></div>`;
}

/* NZD research bridge. ASX bank-bill futures minus frozen RBNZ historical
   cash-bill OCR gap (24 bp, descriptive 10-50bp). This is NOT a forward
   bill/OIS basis, spot OIS, policy delta, or official rate. No runtime mutation.
   The separate Rates research overlay has the calibrated scenario methodology.
*/
function nzdScenario(r){
 if(r?.operational_status!=='WITHHELD'||r?.official_status!=='WITHHELD'||
    r?.backtest_eligible_as_official!==false||r?.change_1d_available!==false||
    r?.change_1w_available!==false)return null;
 const p=r.market_direction_proxy;
 if(!p||p.status!=='LIVE_DIRECTIONAL_PROXY_READY'||
    p.source_quality!=='OFFICIAL_EXCHANGE_DIRECTIONAL_PROXY'||
    p.source!=='ASX official NZ futures end-of-day total traded report'||
    p.instrument!=='ASX New Zealand 90 Day Bank Accepted Bill Futures (BB)'||
    p.substitutes_for_ois_level!==false||
    p.policy_delta_from_proxy_allowed!==false||
    !/^\d{4}-\d{2}-\d{2}$/.test(p.as_of||''))return null;
 const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Rome',
   year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const day=(s)=>{const v=Date.parse(s+'T00:00:00Z');
   return Number.isFinite(v)&&new Date(v).toISOString().slice(0,10)===s?v:null;};
 const asof=day(p.as_of),current=day(today);
 if(asof===null||current===null||current<asof||current-asof>5*86400000||
    p.source_url!=='https://www.asx.com.au/data/futures/reports/EODWebMarketSummary'+
      p.as_of.slice(2).replaceAll('-','')+'ZFT.htm')return null;
 const tenors={ '3m':90,'6m':180,'12m':365 },points={},expiries=new Set();
 for(const [h,days] of Object.entries(tenors)){
   const v=p.horizons?.[h]||{},bb=v.implied_bank_bill_rate,price=v.settlement_price;
   const exp=day(v.expiration||'');
   if(typeof bb!=='number'||!Number.isFinite(bb)||bb< -5||bb>25||
      typeof price!=='number'||!Number.isFinite(price)||
      Math.abs(100-price-bb)>.0002||exp===null||exp<=asof||
      Math.abs((exp-asof)/86400000-days)>65||expiries.has(v.expiration)||
      v.mapping!==('nearest listed expiry to trade_date+'+days+'d; no interpolation'))
      return null;
   expiries.add(v.expiration);
   points[h]={rate:Math.round((bb-.24)*100)/100,
     lower:Math.round((bb-.50)*100)/100,
     upper:Math.round((bb-.10)*100)/100,expiration:v.expiration};
 }
 return {as_of:p.as_of,points,source:p.source,quality:'SCENARIO_RESEARCH_NOT_OIS',
   official_ois:false,policy_delta_allowed:false,backtest_eligible:false};
}
function nzdScenarioHtml(s){
 if(!s)return '';
 const cells=['3m','6m','12m'].map(h=>{const p=s.points[h];return '<div class="oisScenarioCell" data-scenario-horizon="'+h+'"><span>'+h.toUpperCase()+'</span><b>≈'+fmtRate(p.rate)+'</b><small>'+fmtRate(p.lower)+'–'+fmtRate(p.upper)+'</small></div>';}).join('');
 return '<div class="oisScenarioBox" data-ois-nzd-scenario="RESEARCH_ONLY_NOT_OIS"><div class="oisResearchHead">SCENARIO NZD · 3M / 6M / 12M · NON OIS</div><div class="oisScenarioGrid">'+cells+'</div><div class="oisResearchNote">Futures ASX Bank Bill meno 24 bp di differenziale storico cash bill–OCR RBNZ; fascia descrittiva 10–50 bp, non probabilistica. Scadenze di futures, non curva OIS spot. As-of '+esc(s.as_of)+'. Nessun delta di policy, FX, backtest o segnale.</div></div>';
}

// ICE SA3 codes identify the FIRST day of a future 3-month compounded
// SARON accrual window, not a spot OIS tenor. Render only fully source-audited
// dated contracts. Quarantined, legacy expiry-based or mismatched quote days
// never receive a seemingly precise maturity explanation.
function chfTenorTruth(c,r){
 if(c!=='CHF'||r?.operational_status!=='GREEN_ESTIMATED'||
    r?.method_id!=='TRADINGVIEW_DATED_FUTURES_SSR_V2'||
    r?.official_status!=='WITHHELD'||r?.source_conflict_status)return '';
 const day=s=>{
   if(!/^\\d{4}-\\d{2}-\\d{2}$/.test(s||''))return null;
   const t=Date.parse(s+'T00:00:00Z');
   return Number.isFinite(t)&&new Date(t).toISOString().slice(0,10)===s?t:null;
 };
 const thirdWed=(year,month)=>{
   const weekday=new Date(Date.UTC(year,month-1,1)).getUTCDay();
   return Date.UTC(year,month-1,1+((3-weekday+7)%7)+14);
 };
 const display=s=>s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4);
 const windows=[];
 for(const [h,target] of [['3m',90],['6m',180],['12m',365]]){
   const p=r.horizons?.[h]||{},m=/^SA3([HMUZ])(\\d{4})$/.exec(p.contract||'');
   if(!m||p.symbol!=='ICEEUR:'+p.contract||p.quote_timestamp_verified!==true||
      p.quote_timestamp_source!=='SSR_DAILY_BAR_DATA_UPDATE_TIME'||
      p.mapping!=='nearest ICE SARON accrual start to today+'+target+'d; no interpolation')return '';
   const month={H:3,M:6,U:9,Z:12}[m[1]],year=Number(m[2]);
   const start=thirdWed(year,month),nextMonth=month===12?3:month+3;
   const end=thirdWed(month===12?year+1:year,nextMonth)-86400000;
   const observed=day(p.quote_as_of),actualStart=day(p.accrual_start),actualEnd=day(p.expiration);
   const price=Number(p.futures_price),rate=Number(p.rate);
   if(observed===null||actualStart!==start||actualEnd!==end||start<=observed||
      !Number.isFinite(price)||!Number.isFinite(rate)||Math.abs(100-price-rate)>.0002)return '';
   const shift=Math.round((start-observed)/86400000)-target;
   if(Math.abs(shift)>50)return '';
   windows.push('<span><b>'+h.toUpperCase()+'</b> · '+esc(p.contract)+
     ' · inizio '+display(p.accrual_start)+' ('+Math.abs(shift)+
     ' gg '+(shift<0?'prima':shift>0?'dopo':'dal target esatto')+')</span>');
 }
 return '<div class="oisSaronTruth" data-ois-chf-window="AUDITED_SARON_ACCRUAL_START">'+
   '<strong>CHF · finestre reali dei futures</strong>'+
   '<div class="oisSaronTruthRows">'+windows.join('')+'</div>'+
   '<small>NON OIS SPOT: ogni contratto misura il SARON composto in un trimestre futuro. Gli orizzonti 3M/6M/12M sono approssimazioni, non date di decisione SNB. Il differenziale futures–tasso SNB non equivale a rialzi o tagli prezzati.</small></div>';
}
function secondaryQuotesHtml(c,r){
 const ctx=r?.secondary_quote_context;
 if(!ctx||r.operational_status!=='WITHHELD'||!['USD','EUR','CHF'].includes(c))return '';
 const cells=['3m','6m','12m'].map(h=>{
   const q=ctx.horizons?.[h];
   if(!q)return `<div class="oisResearchCell"><div class="oisResearchHz">${h.toUpperCase()}</div><div class="oisResearchRate">—</div></div>`;
   return `<div class="oisResearchCell" title="${esc(q.contract)}"><div class="oisResearchHz">${h.toUpperCase()} · ${esc(q.contract)}</div><div class="oisResearchRate">${fmtRate(q.rate_indicative)}</div><div class="oisResearchDate">${esc(q.quote_as_of)}</div></div>`;
 }).join('');
 const note=ctx.date_mismatch?'Scadenze di sessioni diverse: non unire i punti in una curva.':'Prezzi indicativi dei singoli contratti; nessun percorso OIS certificato.';
 return `<div class="oisResearchQuotes" data-ois-secondary-ccy="${esc(c)}"><div class="oisResearchHead">FUTURES · QUOTAZIONI INDICATIVE · NON OIS</div><div class="oisResearchGrid">${cells}</div><div class="oisResearchNote">${note} Non producono policy delta, repricing o segnali di trading.</div></div>`;
}
function render(){
 const host=ensureHost();if(!host)return false;style();
 if(state.status==='ERROR'){host.innerHTML=`<div class="oisFail"><b>OIS operativo non disponibile.</b><br>${esc(state.error)}. Nessun fallback stimato come dato ufficiale.</div>`;return true;}
 if(state.status!=='READY'||!state.data){host.innerHTML='<div class="oisOpSub">Caricamento OIS operativo…</div>';return true;}
 const d=state.data;const rows=CCYS.map(c=>[c,d.currencies[c]]);
 const finite=rows.flatMap(([,r])=>H.map(h=>rowRate(r,h)).filter(v=>v!==null&&v!==undefined&&Number.isFinite(Number(v))).map(Number));let min=Math.min(...finite),max=Math.max(...finite);if(!finite.length){min=0;max=1;}const pad=Math.max(.15,(max-min)*.08);min-=pad;max+=pad;
 const cards=rows.map(([c,r])=>{const est=r.operational_status==='GREEN_ESTIMATED',scenario=c==='NZD'?nzdScenario(r):null;return `<div class="oisPathCard" data-ois-ccy="${c}"><div class="oisPathTop"><span class="oisPathCcy">${c}</span><span class="oisPathMeta ${est||scenario?'est':'off'}">${scenario?'SCENARIO':r.operational_status==='WITHHELD'?'WITHHELD':est?'ESTIMATED':'OFFICIAL'}</span></div>${r.operational_status==='WITHHELD'?(scenario?'<div class="oisOpSub">OIS non certificata · scenario di ricerca separato</div>':'<div class="oisOpSub">Curva OIS non certificata · nessun livello sostitutivo</div>'):pathSvg(r,min,max)}${scenario?'':`<div class="oisPathVals">${H.map(h=>`<span>${h==='policy'?'POLICY':h.toUpperCase()}<b>${fmtRate(rowRate(r,h))}</b></span>`).join('')}</div>`}${chfTenorTruth(c,r)}${nzdScenarioHtml(scenario)}${proxyHtml(c,r)}${secondaryQuotesHtml(c,r)}<div class="oisAsOf" title="${esc(r.source)}">as-of ${esc(scenario?.as_of||r.as_of||'—')} · conf. ${esc(r.confidence||'—')}</div></div>`;}).join('');
 const trs=rows.map(([c,r])=>{const est=r.operational_status==='GREEN_ESTIMATED';const cells=['3m','6m','12m'].flatMap(h=>r.operational_status==='WITHHELD'?[null,null]:[r?.horizons?.[h]?.change_1d_bp,r?.horizons?.[h]?.change_1w_bp]).map(v=>`<td class="${clsBp(v)}">${fmtBp(v)}</td>`).join('');return `<tr><td><b>${c}</b> <span class="oisQuality ${est?'est':'off'}">${r.operational_status==='WITHHELD'?'WITHHELD':est?'EST':'OFF'}</span></td>${cells}<td>${r.change_1d_available?'SI':'NO'}/${r.change_1w_available?'SI':'NO'}</td></tr>`;}).join('');
 host.innerHTML=`<div class="oisOp"><div class="oisOpHead"><div><div class="oisOpTitle">OIS / Policy Pricing — G8 Operational</div><div class="oisOpSub">Riferimenti monetari G8: i dati ufficiali possono essere futures oppure OIS diretti (GBP). Le stime sono indicative, non OIS certificate. Le variazioni non confrontabili restano assenti e le stime non entrano come OIS ufficiali nel backtest.</div></div><div class="oisOpBadges"><span class="oisBadge off">${d.summary.green_official} FONTI UFFICIALI</span><span class="oisBadge est">${d.summary.green_estimated} ESTIMATED</span><span class="oisBadge">${d.summary.operational_green}/8 OPERATIVO · ${d.summary.operational_withheld} OIS SENZA PRICING ${nzdScenario(d.currencies.NZD)?'· 1 SCENARIO NZD':''}</span></div></div><div class="oisPathGrid">${cards}</div><div class="oisReprice"><table><thead><tr><th>Valuta</th><th>3M Δ1D</th><th>3M Δ1W</th><th>6M Δ1D</th><th>6M Δ1W</th><th>12M Δ1D</th><th>12M Δ1W</th><th>Storico 1D/1W</th></tr></thead><tbody>${trs}</tbody></table></div><div class="oisFoot">NULL ≠ 0 bp: “—” significa storico insufficiente o punto non disponibile. Il monitor usa esclusivamente <code>OIS_OPERATIONAL_VIEW.json</code>; il box ASX NZD mostra futures bancari; lo scenario con differenziale RBNZ è ricerca separata e non viene promosso a OIS.</div></div>`;
 return true;
}
let repairQueued=false;
function queueRepair(){
 if(repairQueued||state.status!=='READY')return;
 repairQueued=true;
 requestAnimationFrame(()=>{
   repairQueued=false;
   const host=document.getElementById('v401OisBlock');
   const cards=host?.querySelectorAll('.oisPathCard')?.length||0;
   const proxyExpected=!!state.data?.currencies?.NZD?.market_direction_proxy;
   const proxyCount=host?.querySelectorAll('[data-ois-proxy="NZD_ASX_BB_DIRECTIONAL"]')?.length||0;
   const scenarioExpected=!!nzdScenario(state.data?.currencies?.NZD);
   const scenarioCount=host?.querySelectorAll('[data-ois-nzd-scenario]')?.length||0;
   const secondaryExpected=CCYS.filter(c=>!!state.data?.currencies?.[c]?.secondary_quote_context).length;
   const secondaryCount=host?.querySelectorAll('[data-ois-secondary-ccy]')?.length||0;
   if(!host||cards!==8||(proxyExpected&&proxyCount!==1)||scenarioCount!==Number(scenarioExpected)||secondaryCount!==secondaryExpected)render();
 });
}
let observer=null;
function attachRepairObserver(){
 const desk=document.getElementById('ratesdesk');
 if(!desk){setTimeout(attachRepairObserver,100);return;}
 if(observer)return;
 observer=new MutationObserver(queueRepair);
 observer.observe(desk,{childList:true,subtree:true});
}
async function load(){
 try{state.status='LOADING';render();const r=await fetch(SRC,{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);state.data=validate(await r.json());state.status='READY';state.loaded_at=new Date().toISOString();state.error=null;render();attachRepairObserver();}
 catch(e){state.status='ERROR';state.error=String(e?.message||e);render();}
}
window.gmfqRenderOisOperational=render;
window.gmfqOisOperationalUiAudit=function(){const hosts=document.querySelectorAll('#v401OisBlock');const host=hosts[0]||null;const rows=host?.querySelectorAll('.oisPathCard')?.length||0;const proxyExpected=!!state.data?.currencies?.NZD?.market_direction_proxy;const proxyCount=host?.querySelectorAll('[data-ois-proxy="NZD_ASX_BB_DIRECTIONAL"]')?.length||0;const scenarioExpected=!!nzdScenario(state.data?.currencies?.NZD);const scenarioCount=host?.querySelectorAll('[data-ois-nzd-scenario]')?.length||0;const secondaryExpected=CCYS.filter(c=>!!state.data?.currencies?.[c]?.secondary_quote_context).length;const secondaryCount=host?.querySelectorAll('[data-ois-secondary-ccy]')?.length||0;return {status:state.status,host:!!host,host_count:hosts.length,cards:rows,nzd_proxy_expected:proxyExpected,nzd_proxy_count:proxyCount,nzd_scenario_expected:scenarioExpected,nzd_scenario_count:scenarioCount,secondary_expected:secondaryExpected,secondary_count:secondaryCount,ok:state.status==='READY'&&hosts.length===1&&rows===8&&(!proxyExpected||proxyCount===1)&&scenarioCount===Number(scenarioExpected)&&secondaryExpected===secondaryCount,summary:state.data?.summary||null,error:state.error};};
const base=window.renderNativeRatesDesk;if(typeof base==='function'){window.renderNativeRatesDesk=function(){const out=base.apply(this,arguments);setTimeout(render,0);return out;};}
const prev=window.showView;if(typeof prev==='function'){window.showView=function(v){const out=prev.apply(this,arguments);if(v==='ratesdesk')setTimeout(render,0);return out;};}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',load,{once:true});else load();
})();