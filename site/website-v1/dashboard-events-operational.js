(()=>{
  'use strict';

  const PATH='../../live_data/sections/CALENDAR_OPERATIONAL_VIEW.json';
  const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
  const MONTHS=['Gen','Feb','Mar','Apr','Mag','Giu','Lug','Ago','Set','Ott','Nov','Dic'];
  const TYPE={
    INFLATION:['Inflazione','Prezzi'],
    LABOUR:['Lavoro','Occupazione'],
    LABOUR_COST:['Costo lavoro','Salari'],
    GROWTH:['Crescita','Attività'],
    CENTRAL_BANK_DECISION:['Decisione CB','Policy']
  };
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const today=()=>{const d=new Date();return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`;};
  const dateLabel=s=>{if(!s)return '—';const d=new Date(`${s}T00:00:00Z`);return Number.isNaN(d.getTime())?'—':`${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;};
  const shortRef=s=>String(s||'').replace(/September/gi,'Set').replace(/October/gi,'Ott').replace(/November/gi,'Nov').replace(/December/gi,'Dic').replace(/quarter/gi,'trim.');
  const risk=x=>String(x?.importance||'').toUpperCase()==='HIGH'?['ALTO','high']:String(x?.importance||'').toUpperCase()==='MEDIUM'?['MEDIO','med']:['BASSO','low'];
  const typeInfo=x=>TYPE[String(x?.event_type||'').toUpperCase()]||['Evento macro','Macro'];
  const catalyst=x=>{
    if(String(x?.event_type||'').toUpperCase()==='CENTRAL_BANK_DECISION') return `${x.bank||x.ccy||'CB'} · decisione`;
    const [label]=typeInfo(x); return `${x.ccy||'G8'} · ${label}`;
  };
  const focus=x=>{
    const [,focusLabel]=typeInfo(x); const ref=shortRef(x?.reference_period);
    return ref?`${focusLabel} · ${ref}`:focusLabel;
  };

  function render(data){
    const card=document.querySelector('.card.calendar');
    const host=card?.querySelector('.calendar-table');
    if(!card||!host)return;
    const h=card.querySelector('.card-head h2'); if(h)h.innerHTML='<span>◈</span>Event Risk · prossimi catalyst';
    let sub=card.querySelector('.event-risk-subline');
    if(!sub){sub=document.createElement('div');sub.className='subline event-risk-subline';card.querySelector('.card-head')?.insertAdjacentElement('afterend',sub);}
    sub.textContent='Eventi ufficiali G8 che possono cambiare pricing e tesi · consenso solo se verificato';

    const events=(Array.isArray(data?.events)?data.events:[])
      .filter(x=>x?.status==='UPCOMING'&&x?.date&&String(x.date)>=today()&&FLAGS[x.ccy])
      .sort((a,b)=>String(a.date).localeCompare(String(b.date))||((b.importance==='HIGH')-(a.importance==='HIGH')))
      .slice(0,7);

    const head='<div class="thead event-head"><span>QUANDO</span><span>CCY</span><span>CATALYST</span><span>FOCUS</span><span>RISCHIO</span></div>';
    if(!events.length){host.innerHTML=head+'<div class="event-row"><span>—</span><b>—</b><small>Nessun catalyst futuro disponibile</small><em>—</em><i>—</i></div>';return;}
    host.innerHTML=head+events.map(x=>{const [r,cls]=risk(x);return `<div class="event-row" title="${esc(x.title||'')}"><span>${esc(dateLabel(x.date))}</span><b>${FLAGS[x.ccy]} ${esc(x.ccy)}</b><small>${esc(catalyst(x))}</small><em>${esc(focus(x))}</em><i class="event-risk ${cls}">${r}</i></div>`;}).join('');
    document.documentElement.dataset.dashboardEvents='OPERATIONAL';
  }

  const style=document.createElement('style');
  style.textContent=`
    .calendar .calendar-table>.event-head,.calendar .calendar-table>.event-row{display:grid!important;grid-template-columns:72px 74px minmax(145px,1.35fr) minmax(120px,1fr) 76px!important;gap:12px!important;align-items:center!important}
    .calendar .event-head{font-size:10px;letter-spacing:.08em;color:#7f9db3}
    .calendar .event-row{min-height:43px;border-top:1px solid rgba(121,164,190,.13)}
    .calendar .event-row>span,.calendar .event-row>b,.calendar .event-row>small,.calendar .event-row>em,.calendar .event-row>i{min-width:0}
    .calendar .event-row>b{font-size:12px;color:#e7f2f8;white-space:nowrap}
    .calendar .event-row>small{font-size:11px;color:#d8e8f1;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .calendar .event-row>em{font-size:10px;color:#87a6ba;font-style:normal;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .calendar .event-risk{justify-self:start;font-size:9px;font-style:normal;font-weight:800;letter-spacing:.06em;padding:4px 7px;border-radius:6px;background:rgba(127,157,179,.12);color:#a9c1d1}
    .calendar .event-risk.high{background:rgba(227,99,116,.13);color:#ff8b9a}.calendar .event-risk.med{background:rgba(216,169,92,.13);color:#e7bd73}.calendar .event-risk.low{color:#8eb4ca}
    @media(max-width:760px){.calendar .calendar-table>.event-head,.calendar .calendar-table>.event-row{grid-template-columns:58px 64px minmax(130px,1fr) 72px!important}.calendar .event-head span:nth-child(4),.calendar .event-row em{display:none}.calendar .event-head span:nth-child(5){display:block}}
  `;
  document.head.appendChild(style);

  fetch(PATH,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(render).catch(e=>console.warn('[GMFQ dashboard events]',e));
})();