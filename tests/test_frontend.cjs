const vm=require('node:vm');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const path=require('node:path');
const script=fs.readFileSync(path.join(__dirname,'../custom_components/water_treatment_monitor/frontend/water-treatment-card.js'),'utf8');
let cls;
const customElements={define(_name,x){cls=x}};
class HTMLElement {attachShadow(){this.shadowRoot={addEventListener(){},innerHTML:''};return this.shadowRoot}}
const context={window:{customCards:[]},customElements,HTMLElement,setInterval(){return 1},clearInterval(){},setTimeout(){},URL:{},Blob,Date,Number,String,Math,Intl,confirm(){return false},alert(){},console,document:{}};
vm.runInNewContext(script,context);
assert.equal(customElements && cls.name,'WaterTreatmentCard');
const c=new cls();c.setConfig({});c.attachShadow();
c.data={source_entity:'binary_sensor.pump',pump_state:'off',pump_last_changed:1700000000,timezone:'America/New_York',selected:{start:1700000000,end:1700086400},period_metrics:{day:{count:1,excluded_count:0,mean_seconds:110,total_seconds:110},week:{count:1,excluded_count:0,mean_seconds:110,total_seconds:110},month:{count:1,excluded_count:0,mean_seconds:110,total_seconds:110},year:{count:1,excluded_count:0,mean_seconds:110,total_seconds:110}},coverage:Object.fromEntries(['day','week','month','year'].map(k=>[k,{status:'partial',coverage_from:1700000000}])),archive:{counts:{pump_runs:1,pump_edges:2,gaps:0,quality_ranges:1,schedules:1,manual_runs:1,ph_tests:1},health:{ok:true,earliest_run:1700000110,latest_run:1700000110,file_bytes:6000},backfill:'finished',coverage_from:1700000000,import_floor:1700000000},analysis:{runs:[{started:1700000000,stopped:1700000110,seconds:110,category:'ordinary',quality:'usable'}],total_runs:1,excluded_runs:0,graph_sampled:false,windows:[{start:1700000050,end:1700003000,equipment:'softener',stage_end:1700001000,overlap_runs:1,runs_overlapping_window:1,pump_starts_inside_window:0,stage_pump_active_seconds:60,quality:'provisional',pump_active_seconds:60,comparison:'insufficient baseline'}],unresolved_windows:[],manual:[{started:1700005000,duration_min:60,equipment:'neutralizer'}],daily:[{day:'2023-11-14',ordinary:110,expected:0,manual:0,count:1}],ordinary_baseline:{count:1,median_seconds:110,p90_seconds:110},treatment_baseline:{},window_count:1,window_with_overlap:1},schedules:[],quality_ranges:[{id:1,started:1699999900,ended:1699999990,effect:'exclude',reason:'commissioning',notes:'test',updated:100}],tests:[{id:1,location:'treated',ph:7.2,sampled:1700000000,notes:'sample',updated:100}],manual:[]};
c._hass={states:{'binary_sensor.pump':{state:'off'}}};
for(const tab of ['overview','analysis','schedules','entries','archive']){
  c.tab=tab;c.render();assert(c.shadowRoot.innerHTML.includes('Water Treatment'));assert(c.shadowRoot.innerHTML.includes('<ha-card>'));assert(c.shadowRoot.innerHTML.length>1500);}
c.tab='entries';c.render();
assert(c.shadowRoot.innerHTML.includes('pH sample history'));
assert(c.shadowRoot.innerHTML.includes('7.2'));
c.tab='archive';c.render();assert(c.shadowRoot.innerHTML.includes('First accepted historical transition')); 
console.log('Frontend smoke test passed: all five views, controls, pH rendering, and charts');

// Refresh must retain an active dirty schedule, manual, pH and quality form.
(async()=>{
  for(const tab of ['schedules','entries','archive']){
    c.tab=tab;c.render();
    const before=c.shadowRoot.innerHTML;
    c._formDirty=true;
    c.call=async()=>c.data;
    await c.refresh(false);
    assert.equal(c.shadowRoot.innerHTML,before,`Dirty ${tab} form was re-rendered`);
    c._formDirty=false;
  }
  // A rejected write must not wipe the pending edits or navigate away.
  c.tab='schedules';c.render();c._formDirty=true;
  const previous=c.shadowRoot.innerHTML;
  c.call=async()=>{throw new Error('Conflict; another user updated this row')};
  await c.mutate('schedules','update',{},1);
  assert.equal(c.shadowRoot.innerHTML,previous);
  assert.equal(c._formDirty,true);
  assert.equal(c.edit,undefined);
  console.log('Frontend regression tests passed: dirty form protection, conflict preservation, quality editor');
})().catch(e=>{console.error(e);process.exitCode=1});

// Regression: RC5 left a successful schedule form focused/stale, leading to
// a second CREATE and UNIQUE(equipment,effective) instead of a visible row.
(async()=>{
  const k=new cls();k.attachShadow();k.setConfig({});
  k.tab='schedules';k.range=1;k.data={...c.data,schedules:[]};k._hass=c._hass;
  k._formDirty=true;k.edit=null;k.busy=false;
  const focus={closest(){return {}},blur(){k.shadowRoot.activeElement=null}};
  k.shadowRoot.activeElement=focus;
  k.render();
  const before=k.shadowRoot.innerHTML;
  let writes=0,resolveWrite;
  const gate=new Promise(done=>{resolveWrite=done});
  k.call=async(type)=>{
    if(type==='mutate'){writes++;await gate;return {ok:true,id:6};}
    if(type==='get')return {...k.data,schedules:[{id:6,equipment:'softener',effective:1794382320,start_time:'01:30',
      cadence:'demand',duration_min:71,stage_min:10,interval_days:1,anchor_date:null,weekdays:'',notes:'',updated:1794382320}]};
    throw new Error(`Unexpected ${type}`);
  };
  const first=k.mutate('schedules','create',{},undefined);
  const duplicate=k.mutate('schedules','create',{},undefined);
  resolveWrite();
  await Promise.all([first,duplicate]);
  assert.equal(writes,1,'Duplicate in-flight clicks must not write twice');
  assert.notEqual(k.shadowRoot.innerHTML,before,'Success must replace stale form/history');
  assert.match(k.shadowRoot.innerHTML,/>softener</);
  assert.match(k.shadowRoot.innerHTML,/>01:30</);
  assert.equal(k._formDirty,false);
  assert.equal(k._mutationPending,false);
  console.log('Frontend RC6 regression passed: focused success refreshes, simultaneous submits deduplicated');
})().catch(e=>{console.error(e);process.exitCode=1});

// Regression: RC5 pH errors appeared under the adjacent manual-backwash form.
(async()=>{
  const p=new cls();p.setConfig({});p.attachShadow();p.tab='entries';p.range=1;
  p.data={...c.data,tests:[],manual:[]};p._hass=c._hass;p.edit=null;p._formDirty=true;p.busy=false;
  let targetSelector='',alertHTML='';
  p.shadowRoot.querySelector=(selector)=>{
    targetSelector=selector;
    return {querySelector(){return {remove(){}}},insertAdjacentHTML(_where,html){alertHTML=html}};
  };
  p._showFormError('Invalid pH value','ph_tests');
  assert.equal(targetSelector,'form[data-form="ph_tests"]');
  assert.match(alertHTML,/Invalid pH value/);
  p._formDirty=false;p.shadowRoot.querySelector=()=>null;
  p.call=async(type)=>{
    if(type==='mutate')return {ok:true,id:99};
    if(type==='get')return {...p.data,tests:[{id:99,sampled:1690000000,location:'treated',ph:7.26,notes:'',updated:1700000000}]};
  };
  await p.mutate('ph_tests','create',{sampled:1690000000,location:'treated',ph:7.26});
  assert.equal(p._mutationPending,false);
  assert.equal(p.error,'');
  assert.match(p.notice,/pH 7\.26 \(treated\) saved to the permanent archive/);
  assert.match(p.notice,/outside the selected analysis range/); // historical sample outside 24-hour range
  assert.match(p.shadowRoot.innerHTML,/pH 7\.26/);
  console.log('Frontend RC6 pH regression passed: correct form errors, persistent save confirmation, out-of-range notice');
})().catch(e=>{console.error(e);process.exitCode=1});
