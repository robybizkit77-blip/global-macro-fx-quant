/* FX Quant V2 working-rate model.
 * Non-canonical illustrative inputs, not an FX signal or a backtest history.
 * No historical bridging across the 30 Oct NZD benchmark change.
 */
(function (root) {
  "use strict";
  const SCHEMA = "GMFQ_FXV2_CHF_NZD_BENCHMARK_RESEARCH_V1";
  const iso = s => typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s) &&
    !Number.isNaN(Date.parse(s+"T00:00:00Z"));
  const valid = (v,min=-5,max=30) => typeof v === "number" &&
    Number.isFinite(v) && v>=min && v<=max;
  const round = (n,d=4) => Number(n.toFixed(d));
  const age = (now,then) => Math.round((Date.parse(now+"T12:00:00Z") -
    Date.parse(then+"T12:00:00Z"))/86400000);
  const within=(now,then,maxDays=14) => iso(now) && iso(then) &&
    age(now,then)>=0 && age(now,then)<=maxDays;

  function derive(canonical, research, today) {
    const out={schema:"GMFQ_FXV2_WORKING_RATES_V1",rates:{},warnings:[],
      eligible_for_fx_engine:false,eligible_for_backtests:false,
      scenario_only:true};
    if (!canonical || !research || research.schema!==SCHEMA ||
        research.eligible_for_fx_pair_engine!==false ||
        research.canonical_government_rates_untouched!==true ||
        research.eligible_for_backtests!==false || !iso(today)) return out;

    const chf=research.CHF;
    if(chf && chf.pair_status==="OFFICIAL_SNBSAMEBASIS_RESEARCH_REVIEW_REQUIRED" &&
       chf.eligible_for_core===false && chf.eligible_for_automatic_promotion===false &&
       chf.separate_10y?.not_joinable_with_paired_2y===true &&
       within(today,chf.paired_date) && within(today,chf.separate_10y?.as_of) &&
       chf.separate_10y.as_of>=chf.paired_date &&
       (!iso(canonical.CHF?.date) || canonical.CHF.date<chf.separate_10y.as_of) &&
       valid(chf["2Y"]) && valid(chf["10Y"]) &&
       valid(chf.separate_10y["10Y"]) &&
       valid(chf.curve_bp,-1000,2000) &&
       Math.abs(round(100*(chf["10Y"]-chf["2Y"]),1)-chf.curve_bp)<0.11) {
      const observed10=chf.separate_10y["10Y"];
      const delta10=observed10-chf["10Y"];
      if(Math.abs(delta10)<=0.5) {
        // Scenario, NOT a newly observed 2Y: assume the same %point shift as 10Y.
        const modeled2=round(chf["2Y"]+delta10,4);
        out.rates.CHF={
          date:chf.separate_10y.as_of,"2Y":modeled2,"10Y":observed10,
          curve_bp:round((observed10-modeled2)*100,1),
          chg2_bp:round(delta10*100,2),chg10_bp:round(delta10*100,2),
          source:"SNB 10Y spot osservato; SNB 2Y stimato da shift parallelo della coppia "+chf.paired_date,
          quality:"STIMA 2Y / SNB 10Y OSSERVATO",
          estimated:true,source_date:chf.paired_date,
          evidence_date:chf.separate_10y.as_of,
          tenor_quality:{"2Y":"STIMATO","10Y":"OSSERVATO"},
          working_method:"PARALLEL_10Y_SHIFT_2Y",
          assumptions:"2Y="+chf["2Y"]+"% + (10Y "+observed10+"% − "+chf["10Y"]+"%)",
          comparison_start:chf.paired_date,
          no_core_effect:true,
          no_inferred_market_move:true
        };
        out.warnings.push("CHF: lo shift 2Y da 10Y è un'ipotesi, non una quotazione 2Y.");
      }
    }
    const nzd=research.NZD;
    if(nzd && nzd.status==="RBNZ_GOVT_B2_WEB_RESEARCH_UNAPPROVED" &&
       nzd.cross_roll_change_allowed===false &&
       nzd.independent_xlsx_reconciled===false &&
       nzd.eligible_for_core===false &&
       within(today,nzd.latest_date) && iso(nzd.roll_date) &&
       nzd.roll_date<nzd.latest_date &&
       (!iso(canonical.NZD?.date) || canonical.NZD.date<nzd.latest_date) &&
       Array.isArray(nzd.after_roll) && nzd.after_roll.length>=2) {
      const first=nzd.after_roll[0],last=nzd.after_roll.at(-1);
      if(first.date===nzd.roll_date && last.date===nzd.latest_date &&
         valid(first["2Y"])&&valid(first["10Y"])&&
         valid(last["2Y"])&&valid(last["10Y"]) &&
         valid(nzd.latest_2Y)&&valid(nzd.latest_10Y) &&
         Math.abs(last["2Y"]-nzd.latest_2Y)<0.0001 &&
         Math.abs(last["10Y"]-nzd.latest_10Y)<0.0001) {
        out.rates.NZD={
          date:last.date,"2Y":last["2Y"],"10Y":last["10Y"],
          curve_bp:round((last["10Y"]-last["2Y"])*100,1),
          chg2_bp:round((last["2Y"]-first["2Y"])*100,2),
          chg10_bp:round((last["10Y"]-first["10Y"])*100,2),
          source:"RBNZ B2, lettura web dopo roll benchmark "+nzd.roll_date+"; XLSX non riconciliato",
          quality:"PROXY RBNZ B2 (NON CERTIFICATO XLSX)",estimated:true,
          source_date:first.date,evidence_date:last.date,
          tenor_quality:{"2Y":"WEB_PROXY","10Y":"WEB_PROXY"},
          working_method:"POST_ROLL_B2_SAME_BENCHMARK",
          assumptions:"Usare solo osservazioni del benchmark dal "+nzd.roll_date+" in avanti.",
          comparison_start:first.date,no_core_effect:true,
          no_cross_roll_change:true
        };
        out.warnings.push("NZD: livelli B2 indicativi; variazione prima/dopo il roll non utilizzata.");
      }
    }
    return out;
  }
  const api=Object.freeze({derive});
  root.FXV2RatesWorking=api;
  if(typeof module==="object"&&module&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
