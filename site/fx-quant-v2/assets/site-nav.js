(()=>{
"use strict";
const pages=[
["home","Home","index.html","⌂"],["valute","Valute G8","valute.html","◈"],["coppie","Coppie FX","coppie.html","⇄"],["tassi","Tassi 2Y/10Y","tassi.html","↗"],["ois","OIS & Pricing","ois.html","⌁"],["macro","Macro G8","macro.html","▤"],["banche","Banche Centrali","banche.html","◉"],["cot","COT","cot.html","◎"],["cross","Cross-Asset","cross-asset.html","▣"],["liquidita","Liquidità & Credito","liquidita-credito.html","◌"],["calendario","Calendario & News","calendario-news.html","◷"],["ricerca","Research Library","research.html","▥"]
];
const statuses={
home:"Feed misti: date e qualità nei singoli blocchi",valute:"Serie di ricerca incorporate: consultare as-of",coppie:"Pair Setup canonico; tesi non equivale a ingresso",tassi:"Governativi 2Y/10Y; stime etichettate",ois:"OIS, futures e proxy separati; non stesso strumento",macro:"Snapshot macro: non è una sorpresa intraday",banche:"Snapshot CB; verificare data delle dichiarazioni",cot:"COT settimanale: non descrive le posizioni odierne",cross:"Snapshot cross-asset con date per serie",liquidita:"Fonti miste e storici: non è un indice sintetico",calendario:"Eventi e notizie con rispettive date",ricerca:"Indice di report HTML già pubblicati"
};
function init(){
 const page=document.body?.dataset.fxv2Page||"home";
 const host=document.createElement("header");
 host.id="fxv2-global-header";
 const links=pages.map(([id,label,url,sym])=>'<a href="./'+url+'"'+(id===page?' aria-current="page"':'')+'>'+sym+' '+label+'</a>').join("");
 host.innerHTML='<a class="fxv2-skip" href="#fxv2-main">Vai al contenuto</a>'+
 '<div class="fxv2-inner"><div class="fxv2-first">'+
 '<a class="fxv2-brand" href="./index.html"><span class="fxv2-logo">FQ</span><span class="fxv2-brandcopy"><strong>GLOBAL MACRO FX QUANT</strong><small>V2 · RESEARCH DESK</small></span></a>'+
 '<span class="fxv2-status">Sito nuovo · fase di integrazione</span>'+
 '<a class="fxv2-old" href="../control-room-preview/#/home" target="_blank" rel="noopener">Control Room V10</a>'+
 '<button class="fxv2-toggle" type="button" aria-controls="fxv2-nav" aria-expanded="false">☰ Sezioni</button>'+
 '</div><nav class="fxv2-nav" id="fxv2-nav" aria-label="Navigazione completa FX Quant V2">'+links+'</nav>'+
 '<div class="fxv2-datameta"><b>QUALITÀ DATI</b> · '+(statuses[page]||'Controllare date e fonti')+' · Nessuna modifica al motore operativo</div></div>';
 document.body.prepend(host);
 const main=document.querySelector("main, .shell:not(header .shell), section.main, article")||document.querySelector("body > section, body > div:not(.topline)");
 if(main&&!main.id)main.id="fxv2-main";
 else if(!main){const a=document.querySelector("body > *:not(#fxv2-global-header)");if(a&&!a.id)a.id="fxv2-main";}
 const toggle=host.querySelector(".fxv2-toggle"),nav=host.querySelector(".fxv2-nav");
 const close=()=>{nav.classList.remove("fxv2-open");toggle.setAttribute("aria-expanded","false");};
 toggle.addEventListener("click",()=>{const open=nav.classList.toggle("fxv2-open");toggle.setAttribute("aria-expanded",String(open));});
 host.addEventListener("keydown",e=>{if(e.key==="Escape")close();});
 document.addEventListener("click",e=>{if(!host.contains(e.target))close();});
 nav.addEventListener("click",e=>{if(e.target.closest("a"))close();});
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});else init();
})();