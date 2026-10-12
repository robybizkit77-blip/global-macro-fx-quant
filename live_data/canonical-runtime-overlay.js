(()=>{
  'use strict';
  const fetchJson=async(path)=>{
    const r=await fetch(path,{cache:'no-store'});
    if(!r.ok) throw new Error(`canonical-overlay-http-${r.status}:${path}`);
    return r.json();
  };
  const syncInPlace=(target,fresh,name)=>{
    if(Array.isArray(target)){
      if(!Array.isArray(fresh)) throw new Error(`canonical-overlay-type-mismatch:${name}`);
      target.splice(0,target.length,...fresh);
      return;
    }
    if(!target || typeof target!=='object' || Array.isArray(fresh) || !fresh || typeof fresh!=='object')
      throw new Error(`canonical-overlay-type-mismatch:${name}`);
    if(Object.isFrozen(target) || !Object.isExtensible(target))
      throw new Error(`canonical-overlay-immutable-target:${name}`);
    for(const k of Object.keys(target)) delete target[k];
    Object.assign(target,fresh);
  };

  window.__GMFQ_CANONICAL_OVERLAY_STATE=Object.freeze({status:'LOADING',decision_effect:'NONE'});
  window.__GMFQ_CANONICAL_OVERLAY_READY=(async()=>{
    const [macroThermometer,macroSeries]=await Promise.all([
      fetchJson('live_data/sections/MACRO_THERMOMETER_DATA.json'),
      fetchJson('live_data/sections/MACRO_SERIES.json')
    ]);

    // Both canonical Macro surfaces already exist on the legacy global data bag.
    // Mutate those exact objects in place so every legacy consumer keeps the
    // original object identity while receiving canonical section content.
    const thermometerTarget=window.__GMFQ_DATA?.MACRO_THERMOMETER_DATA;
    const seriesTarget=window.__GMFQ_DATA?.MACRO_SERIES;
    if(!thermometerTarget) throw new Error('canonical-overlay-missing-target:MACRO_THERMOMETER_DATA');
    if(!seriesTarget) throw new Error('canonical-overlay-missing-target:MACRO_SERIES');

    syncInPlace(thermometerTarget,macroThermometer,'MACRO_THERMOMETER_DATA');
    syncInPlace(seriesTarget,macroSeries,'MACRO_SERIES');
    const state={
      status:'PASS_CANONICAL_MACRO_OVERLAY',
      sections:['MACRO_THERMOMETER_DATA','MACRO_SERIES'],
      decision_effect:'DATA_REFRESH_ONLY',
      object_identity_preserved:true,
      changes_signal_rules:false,
      changes_bias_rules:false,
      changes_sizing_rules:false
    };
    window.__GMFQ_CANONICAL_OVERLAY_STATE=Object.freeze(state);
    window.dispatchEvent(new CustomEvent('gmfq:canonical-overlay-ready',{detail:window.__GMFQ_CANONICAL_OVERLAY_STATE}));
    return window.__GMFQ_CANONICAL_OVERLAY_STATE;
  })().catch(e=>{
    window.__GMFQ_CANONICAL_OVERLAY_STATE=Object.freeze({status:'WITHHELD_OVERLAY_ERROR',decision_effect:'NONE',error:String(e&&e.message||e)});
    console.error('canonical-runtime-overlay',e);
    throw e;
  });
})();
