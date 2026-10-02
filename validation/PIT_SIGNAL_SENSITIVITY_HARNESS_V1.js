/* GMFQ PIT Signal Sensitivity Harness V1
   Validation-only utility. Does not mutate production runtime.
   Frozen engine target: 9.3-pair-attention-hierarchy / rules fingerprint 3356baf0
*/
(function(root){
  'use strict';

  function median(arr){
    const xs=(arr||[]).filter(Number.isFinite).slice().sort((a,b)=>a-b);
    if(!xs.length) return null;
    const m=Math.floor(xs.length/2);
    return xs.length%2 ? xs[m] : (xs[m-1]+xs[m])/2;
  }

  function robustScaleDiffs(vals){
    const diffs=[];
    for(let i=1;i<vals.length;i++){
      const d=Number(vals[i])-Number(vals[i-1]);
      if(Number.isFinite(d)) diffs.push(Math.abs(d));
    }
    const m=median(diffs);
    return (m && Number.isFinite(m) && m>0) ? m : null;
  }

  function macroSeriesPolarity(category,label){
    const l=String(label||'').toLowerCase();
    if(category==='Lavoro'){
      if(l.includes('disoccup')) return -1;
      if(l.includes('sussidi disoccupazione')) return -1;
      if(l.includes('claims')) return -1;
      if(l.includes('costo unitario')) return 0;
      return 1;
    }
    if(category==='Crescita'){
      if(l.includes('tasso di risparmio')) return 0;
      return 1;
    }
    if(category==='Inflazione') return 1;
    if(category==='Liquidità') return 1;
    return 0;
  }

  function normalizedSeriesImpulse(x,category){
    const vals=(x?.values||[]).map(Number).filter(Number.isFinite);
    if(vals.length<8) return null;
    const pol=macroSeriesPolarity(category,x.label);
    if(pol===0) return null;
    const scale=robustScaleDiffs(vals.slice(-80));
    if(!scale) return null;
    const d0=(vals.at(-1)-vals.at(-2))*pol/scale;
    const d1=(vals.at(-2)-vals.at(-3))*pol/scale;
    return {current:d0,previous:d1,label:x.label};
  }

  function blockDynamics(seriesList,category){
    const list=(seriesList||[]).filter(x=>x.category===category);
    const impulses=list.map(x=>normalizedSeriesImpulse(x,category)).filter(Boolean);
    if(!impulses.length) return null;
    const current=median(impulses.map(x=>x.current));
    const previous=median(impulses.map(x=>x.previous));
    if(current==null || previous==null) return null;
    const direction=Math.abs(current)<0.20?0:Math.sign(current);
    const acceleration=current-previous;
    const accelDir=Math.abs(acceleration)<0.20?0:Math.sign(acceleration);
    const turning=(Math.sign(previous)!==0 && direction!==0 && Math.sign(previous)!==direction);
    return {category,direction,speed:Math.abs(current),acceleration,accelDir,turning,n:impulses.length,current,previous};
  }

  function snapshotSeries(series, checkpoint){
    return (series||[]).map(s=>{
      const pairs=(s.dates||[]).map((d,i)=>({date:String(d),value:Number(s.values?.[i])}))
        .filter(x=>x.date<=checkpoint && Number.isFinite(x.value));
      return {...s,dates:pairs.map(x=>x.date),values:pairs.map(x=>x.value)};
    });
  }

  function compareBlock(firstReleaseSeries,currentRevisedSeries,category,checkpoint){
    const a=blockDynamics(snapshotSeries(firstReleaseSeries,checkpoint),category);
    const b=blockDynamics(snapshotSeries(currentRevisedSeries,checkpoint),category);
    return {
      checkpoint,category,
      first_release:a,
      current_revised:b,
      direction_changed:(a?.direction??null)!==(b?.direction??null),
      turning_changed:(a?.turning??null)!==(b?.turning??null),
      acceleration_direction_changed:(a?.accelDir??null)!==(b?.accelDir??null),
      speed_delta:(a&&b)?b.speed-a.speed:null
    };
  }

  function comparePanel(firstReleaseSeries,currentRevisedSeries,checkpoints,categories=['Crescita','Lavoro']){
    const rows=[];
    for(const checkpoint of checkpoints||[]){
      for(const category of categories){
        rows.push(compareBlock(firstReleaseSeries,currentRevisedSeries,category,checkpoint));
      }
    }
    const usable=rows.filter(x=>x.first_release&&x.current_revised);
    return {
      rows,
      summary:{
        comparisons:usable.length,
        direction_changes:usable.filter(x=>x.direction_changed).length,
        turning_changes:usable.filter(x=>x.turning_changed).length,
        acceleration_direction_changes:usable.filter(x=>x.acceleration_direction_changed).length
      }
    };
  }

  root.GMFQ_PIT_SIGNAL_SENSITIVITY_V1={
    frozen_model_rules_version:'9.3-pair-attention-hierarchy',
    frozen_rules_fingerprint:'3356baf0',
    median,robustScaleDiffs,macroSeriesPolarity,normalizedSeriesImpulse,blockDynamics,
    snapshotSeries,compareBlock,comparePanel
  };
})(typeof window!=='undefined'?window:globalThis);
