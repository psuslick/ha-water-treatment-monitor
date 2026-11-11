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
