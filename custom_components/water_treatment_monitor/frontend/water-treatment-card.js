/* Water Treatment Monitor 2.0.0 RC4 — independent local dashboard component.
   No CDN; data via authenticated HA WebSocket; never controls any equipment. */
const WTM_NS='http://www.w3.org/2000/svg';
const WTM_COLORS={ordinary:'#38a3ba',expected:'#798ced',manual:'#ce9a66',excluded:'#777e8d',mixed:'#a27ed3',pump:'#e26e72',softener:'#798ced',neutralizer:'#39a77e'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const localInput=t=>{const d=new Date((t??Date.now()/1000)*1000);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)};
const stamp=v=>v?new Date(v*1000).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):'Not recorded';
const duration=s=>s==null?'—':(s<60?`${Math.round(s)} s`:`${(s/60).toFixed(1)} min`);
const num=v=>v==null?'—':Number(v).toLocaleString();
const rel=v=>v?.toLowerCase().replace(/_/g,' ')||'unknown';
const fmtDate=d=>new Date(d*1000).toLocaleDateString(undefined,{month:'short',day:'numeric'});
const dims={w:1050,h:240,left:130,right:20,top:26,bottom:34};
const svgRect=(x,y,w,h,color,alpha=1,tip='')=>`<rect x="${x.toFixed(2)}" y="${y}" width="${Math.max(w,1.7).toFixed(2)}" height="${h}" rx="3" fill="${color}" opacity="${alpha}"><title>${esc(tip)}</title></rect>`;

class WaterTreatmentCard extends HTMLElement {
  setConfig(config){this.config=config||{};}
  set hass(hass){this._hass=hass; const src=this.data?.source_entity;const state=src?hass.states[src]?.state:null;
    if(this._lastState!==state){this._lastState=state;if(this.data&&!this._shouldHoldForm())this.render();}}
  connectedCallback(){
    if(this._connected)return;this._connected=true;
    if(!this._initialized){
      this.tab='overview';this.range=1;this.customStart=Date.now()/1000-7*86400;this.customEnd=Date.now()/1000;
      this.edit=null;this.busy=false;this.data=null;this._formDirty=false;this._initialized=true;
    }
    if(!this.shadowRoot)this.attachShadow({mode:'open'});
    if(!this._handlersBound){
      this.shadowRoot.addEventListener('click',e=>this.click(e));
      this.shadowRoot.addEventListener('input',e=>{if(e.target?.closest?.('form[data-form]'))this._formDirty=true});
      this.shadowRoot.addEventListener('change',e=>this.change(e));
      this.shadowRoot.addEventListener('submit',e=>this.submit(e));
      this._handlersBound=true;
    }
    this.refresh();this.timer=setInterval(()=>{if(!this.busy)this.refresh(false)},60000);
  }
  disconnectedCallback(){clearInterval(this.timer);this._connected=false;}
  getCardSize(){return 14;}
  _shouldHoldForm(){return this._formDirty || !!this.shadowRoot?.activeElement?.closest?.('form[data-form]')}
  _unsavedOkay(){return !this._formDirty || confirm('Discard unsaved Water Treatment changes?')}
  _showFormError(message){
    const root=this.shadowRoot;
    if(!root)return;
    const form=root.querySelector?.('form[data-form]');
    if(form?.insertAdjacentHTML){
      form.querySelector?.('.wtm-form-error')?.remove();
      form.insertAdjacentHTML('afterbegin',`<div class="alert bad wtm-form-error" style="grid-column:1/-1">${esc(message)}</div>`);
    }
  }
  async call(type,extras={}) {if(!this._hass?.callWS)throw new Error('Home Assistant WebSocket not available');return this._hass.callWS({type:`water_treatment_monitor/${type}`,...extras});}
  async refresh(loading=true){if(this.busy && loading)return;if(loading)this.busy=true;try{
    const end=this.range===0?this.customEnd:Math.floor(Date.now()/1000)+2;
    const start=this.range===0?this.customStart:end-this.range*86400;
    const result=await this.call('get',{start,end});this.data=result;this.error='';
  }catch(e){this.error=String(e?.message||e)}finally{this.busy=false;if(!this._shouldHoldForm())this.render();}}
  styles(){return `<style>
:host {display:block;--wtm-muted:var(--secondary-text-color,#8793a6);--wtm-fg:var(--primary-text-color,#e4e8ef);--wtm-bg:var(--card-background-color,#1b2430);--wtm-line:var(--divider-color,#384556);font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif);color:var(--wtm-fg)}
*{box-sizing:border-box}ha-card{padding:0;background:var(--wtm-bg);overflow:hidden} .shell{padding:18px 20px 22px;max-width:1400px;margin:auto}
.top{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}.title{font-size:24px;font-weight:750;letter-spacing:-.8px}.sub{font-size:12px;color:var(--wtm-muted)}
.tabs{display:flex;gap:5px;overflow:auto;padding:17px 0 13px;border-bottom:1px solid var(--wtm-line);margin-bottom:16px}.tab{background:transparent;border:0;color:var(--wtm-muted);border-radius:9px;font-weight:650;padding:10px 14px;cursor:pointer;white-space:nowrap}.tab.active{background:var(--primary-color,#448aff);color:white}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:12px 0 20px}.metric{border:1px solid var(--wtm-line);border-radius:13px;padding:14px;min-width:0}.metric strong{display:block;font-size:25px;margin:5px 0;font-variant-numeric:tabular-nums}.metric small{font-size:11px;color:var(--wtm-muted);line-height:1.5;display:block}.eyebrow{font-size:11px;font-weight:700;letter-spacing:.6px;color:var(--wtm-muted);text-transform:uppercase}
.pill{font-size:11px;border-radius:40px;padding:5px 8px;background:var(--secondary-background-color,#293543);white-space:nowrap}.on{color:#4ecdb0}.off{color:var(--wtm-muted)}.warn{color:#dba24a}.bad{color:#e26e72}
h3{font-size:16px;margin:10px 0 6px}.panel{border:1px solid var(--wtm-line);border-radius:14px;padding:15px;margin:12px 0}.hint{font-size:12px;color:var(--wtm-muted);line-height:1.6}.key{display:flex;align-items:center;gap:5px;font-size:11px}.legend{display:flex;flex-wrap:wrap;gap:12px;margin:7px 0 14px}.dot{width:9px;height:9px;border-radius:3px;display:inline-block}.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.spacer{flex:1}.split{display:grid;grid-template-columns:1fr 1fr;gap:12px}.forms{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px} .field{display:flex;flex-direction:column;gap:4px;min-width:0}label{font-size:12px;color:var(--wtm-muted)}
input,select,textarea{width:100%;max-width:100%;color:var(--wtm-fg);background:var(--secondary-background-color,#222e3b);border:1px solid var(--wtm-line);padding:9px;border-radius:8px;font:inherit} textarea{resize:vertical;min-height:50px}
button{border:1px solid var(--wtm-line);border-radius:8px;background:var(--secondary-background-color,#293543);color:var(--wtm-fg);padding:9px 12px;cursor:pointer;font:inherit;font-size:12px}button.primary{background:var(--primary-color,#3987d8);color:white;border:0}button.danger{color:#e38f8f}button:disabled{opacity:.5;cursor:wait}.alert{background:var(--secondary-background-color,#293543);padding:11px 14px;border-radius:9px;font-size:12px;margin:10px 0}.tablewrap{overflow:auto;max-height:470px;border-radius:10px;border:1px solid var(--wtm-line)}table{width:100%;border-collapse:collapse;font-size:12px;text-align:left}th,td{padding:10px 12px;border-bottom:1px solid var(--wtm-line);white-space:nowrap}th{color:var(--wtm-muted);position:sticky;top:0;background:var(--wtm-bg);font-weight:650}svg{width:100%;height:auto;display:block}.desc{font-size:12px;color:var(--wtm-muted)}.actions{display:flex;gap:8px;flex-wrap:wrap;margin:11px 0 0}.actions button{margin-right:2px} .notice{border-left:3px solid #c69a4f;padding:6px 12px;margin:12px 0;font-size:12px;background:var(--secondary-background-color,#26303b)}.small{font-size:11px}.form-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.inputbox{min-width:0} .muted{color:var(--wtm-muted)}.sparkline{stroke:#38a3ba;fill:none;stroke-width:2}.gridline{stroke:var(--wtm-line);stroke-width:1;opacity:.8}
@media (max-width:900px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.forms,.split{grid-template-columns:1fr}}
@media (max-width:520px){.metrics,.form-grid{grid-template-columns:1fr}.shell{padding:13px}.title{font-size:20px}}
</style>`}
  nav(){return `<div class="tabs">${[['overview','Overview'],['analysis','Analysis'],['schedules','Schedules'],['entries','Manual runs & pH'],['archive','Archive & backups']].map(([id,name])=>`<button class="tab ${this.tab===id?'active':''}" data-tab="${id}">${name}</button>`).join('')}</div>`}
  metric(name,val,foot){return `<div class="metric"><span class="eyebrow">${esc(name)}</span><strong>${esc(val)}</strong><small>${esc(foot)}</small></div>`}
  rangePicker(){return `<div class="controls"><span class="hint">Analysis range</span><select id="range" style="width:auto">${[[1,'24 hours'],[7,'7 days'],[30,'30 days'],[90,'90 days'],[365,'1 year'],[1825,'5 years'],[0,'Custom dates']].map(([n,label])=>`<option value="${n}" ${this.range===n?'selected':''}>${label}</option>`).join('')}</select>${this.range===0?`<label>From <input id="range-from" type="datetime-local" value="${localInput(this.customStart)}"></label><label>To <input id="range-to" type="datetime-local" value="${localInput(this.customEnd)}"></label><button data-action="apply-range">Apply</button>`:''}<button data-action="refresh">Refresh</button></div>`}
  status(){const state=this._hass?.states[this.data?.source_entity]?.state||this.data?.pump_state||'unavailable';const a=this.data?.archive||{};return `<span class="pill ${state==='on'?'on':state==='off'?'off':'bad'}">Well pump: ${esc(state.toUpperCase())}</span><span class="pill ${a.health?.ok?'on':'bad'}">Archive: ${a.health?.ok?'healthy':'check error'}</span>`}
  render(){if(!this.shadowRoot)return;let html=this.styles()+`<ha-card><div class="shell"><div class="top"><div><div class="title">Water Treatment</div><div class="sub">Historic pump evidence, expected treatment windows and editable water-quality records</div></div><div class="controls">${this.data?this.status():''}</div></div>`;
    if(this.error)html+=`<div class="alert bad">${esc(this.error)}. Check integration setup and logs.</div>`;
    if(this.data){html+=this.nav()+this.rangePicker();if(this.tab==='overview')html+=this.overview();if(this.tab==='analysis')html+=this.analysis();if(this.tab==='schedules')html+=this.schedules();if(this.tab==='entries')html+=this.entries();if(this.tab==='archive')html+=this.archive();}else html+=`<div class="panel">${this.busy?'Reading the archive and Recorder backfill…':'No data received yet. Install/configure the Water Treatment Monitor integration first.'}</div>`;
    this.shadowRoot.innerHTML=html+'</div></ha-card>';
  }
  coverageSummary(key){const cov=this.data.coverage?.[key];const c=cov?.status||'no_archive';return c==='observed_window'?'Observed, not independently certified':c==='partial'?`Partial archive since ${stamp(cov.coverage_from)}`:c==='interrupted'?'Continuity interruption or excluded interval':'No usable archive period';}
  overview(){const d=this.data,a=d.archive,st=this._hass?.states[d.source_entity]?.state||d.pump_state,metrics=d.period_metrics||{};
    const met=Object.entries(metrics).map(([key,m])=>this.metric(`${key} average`,duration(m.mean_seconds),`${num(m.count)} usable relay intervals; ${num(m.excluded_count||0)} excluded · ${this.coverageSummary(key)}`)).join('');
    let last=a.health?.latest_run;
    return `<div class="metrics">${this.metric('Pump relay',String(st).toUpperCase(),st==='on'?`Reported ON for approximately ${duration(Math.max(0,Date.now()/1000-d.pump_last_changed))}; this is not a validated completed run`:`Last state change ${stamp(d.pump_last_changed)}`)}${this.metric('Last usable relay run',last?stamp(last):'Not archived',`Source: ${d.source_entity}`)}${this.metric('Archived relay intervals',num(a.counts.pump_runs),a.coverage_from?`Coverage recorded from ${stamp(a.coverage_from)}`:'Backfill pending or no available Recorder history')}${this.metric('Backfill',rel(a.backfill),a.last_backfill?`${a.last_backfill.new_edges} new edges in latest import`:'First import may be in progress')}</div>
    <h3>Average quality-qualified relay interval</h3><div class="metrics">${met}</div>
    <section class="panel"><h3>Pump activity against treatment schedule</h3><p class="hint">Expected periods are based on the schedule revision effective at each point in time; overlapping pump cycles are measurements, not proof of regeneration.</p>${this.timeline()}</section>
    <div class="split"><section class="panel"><h3>Expected window comparison</h3>${this.windowSummary()}</section><section class="panel"><h3>Recent relay intervals</h3>${this.runTable(8)}</section></div>`;
  }
  windowSummary(){const a=this.data.analysis;const missing=a.windows.filter(w=>!w.runs_overlapping_window).length;return `<div class="metrics" style="grid-template-columns:1fr 1fr">${this.metric('Expected windows',num(a.window_count),'In selected range')}${this.metric('No pump overlap',num(missing),'Review; not a failed-regeneration verdict')}</div>${a.unresolved_windows.length?`<div class="notice">${a.unresolved_windows.length} scheduled times fall on ambiguous or nonexistent DST times and require physical-controller verification.</div>`:''}<p class="hint">A pressure tank can satisfy some demand without starting the pump. Check sensor availability and phase timings before investigating a missing overlap.</p>${Object.entries(a.treatment_baseline||{}).map(([equip,v])=>`<p class="hint"><strong>${esc(equip)}:</strong> ${v.sample_windows} comparable windows with pumping; median ${duration(v.median_pump_seconds)}, P90 ${duration(v.p90_pump_seconds)}. Provisional context, not calibrated acceptance limits.</p>`).join('')}` }
  timeline(){const a=this.data.analysis,lo=this.data.selected.start,hi=this.data.selected.end,left=dims.left,width=dims.w-dims.left-dims.right;
    const x=t=>left+(t-lo)/(hi-lo)*width;const rows=[['Pump',60],['Softener expected',100],['Neutralizer expected',140],['Manual reports',180]];
    let svg=`<svg viewBox="0 0 ${dims.w} ${dims.h}" role="img" aria-label="Pump run and predicted treatment window timeline">`;
    for(let i=0;i<=6;i++){const at=lo+(hi-lo)*i/6;svg+=`<line class="gridline" x1="${x(at)}" x2="${x(at)}" y1="38" y2="199"/><text x="${x(at)}" y="221" font-size="10" text-anchor="middle" fill="currentColor">${esc(fmtDate(at))}</text>`}
    for(const [name,y] of rows){svg+=`<text x="4" y="${y+12}" fill="currentColor" font-size="12">${esc(name)}</text><line class="gridline" x1="${left}" x2="${dims.w-dims.right}" y1="${y+21}" y2="${y+21}"/>`}
    for(const w of a.windows){if(w.end<lo||w.start>hi)continue;const y=w.equipment==='softener'?100:140;const b=Math.max(w.start,lo),e=Math.min(w.end,hi);const color=WTM_COLORS[w.equipment];svg+=svgRect(x(b),y,e> b?x(e)-x(b):0,18,color,.52,`${w.equipment} expected: ${stamp(w.start)} – ${stamp(w.end)}; ${w.runs_overlapping_window} overlaps; ${w.pump_starts_inside_window} starts`);if(w.stage_end>w.start){const stageEnd=Math.min(w.stage_end,hi);svg+=svgRect(x(b),y,Math.max(0,x(stageEnd)-x(b)),5,color,1,'Initial backwash stage')};}
    for(const w of a.manual){const b=Math.max(w.started,lo),e=Math.min(w.started+w.duration_min*60,hi);if(e<=b)continue;svg+=svgRect(x(b),180,x(e)-x(b),18,WTM_COLORS.manual,.90,`${w.equipment} reported manual: ${stamp(w.started)}, ${w.duration_min}m`)}
    for(const r of a.runs){const b=Math.max(r.started,lo),e=Math.min(r.stopped,hi);if(e<=b)continue;svg+=svgRect(x(b),60,x(e)-x(b),18,r.category==='ordinary'?WTM_COLORS.pump:(WTM_COLORS[r.category]||WTM_COLORS.expected),.98,`Observed pump: ${stamp(r.started)} to ${stamp(r.stopped)}; ${duration(r.seconds)}; ${rel(r.category)}`)}
    return svg+'</svg>'+`<div class="legend">${[['Pump (ordinary)',WTM_COLORS.pump],['Pump (treatment-associated)',WTM_COLORS.expected],['Mixed-context pump run',WTM_COLORS.mixed],['Excluded/unverified evidence',WTM_COLORS.excluded],['Scheduled softener',WTM_COLORS.softener],['Scheduled neutralizer',WTM_COLORS.neutralizer],['Manual report',WTM_COLORS.manual]].map(([t,c])=>`<span class="key"><i class="dot" style="background:${c}"></i>${esc(t)}</span>`).join('')}</div><p class="hint">Hover over bars for timestamps. At multiweek ranges individual pump runs are shown as small ticks; use 24 hours for precise alignment.</p>`;
  }
  runTable(max){const rows=[...this.data.analysis.runs].reverse().slice(0,max);return this.table(['Ended','Seconds','Context','Quality'],rows.map(r=>[stamp(r.stopped),r.seconds.toFixed(1),rel(r.category),r.quality||'usable']));}
  table(headers,rows){if(!rows.length)return '<p class="hint">No records in this range. This is not evidence that no physical events occurred.</p>';
    return `<div class="tablewrap"><table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c && typeof c==='object' && c.html?c.html:esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`}
  analysis(){const a=this.data.analysis;const baseline=a.ordinary_baseline;return `<div class="metrics">${this.metric('Ordinary run median',duration(baseline.median_seconds),`${baseline.count} unexcluded ordinary relay intervals`)}${this.metric('Ordinary P90',duration(baseline.p90_seconds),'90th percentile, selected range')}${this.metric('Treatment windows',a.window_count,`${a.window_with_overlap} with observed pump overlap`)}${this.metric('Usable relay runs',num(a.total_runs),`${num(a.excluded_runs)} excluded; ${a.graph_sampled?'plot sampled':'all plotted'}`)}</div>
    ${a.graph_sampled?'<div class="notice">Scatter plot downsampled to 6,000 points. Daily totals, expected-window comparisons and aggregate statistics include all archived runs.</div>':''}
    <section class="panel"><h3>Run duration by event</h3><p class="hint">Recorded relay intervals, by stop time. Quality-excluded intervals, if any, are shown as gray capped markers; they do not set the plot scale or baselines.</p>${this.scatter()}</section>
    <section class="panel"><h3>Daily pump runtime by context</h3><p class="hint">Measured seconds are apportioned exactly across ordinary, expected and manual windows, and split at HA-local midnight. Excluded intervals are not included in the bars.</p>${this.dailyChart()}</section>
    <section class="panel"><h3>Ordinary-use anomaly candidates</h3><p class="hint">Visible only after at least 20 ordinary runs establish a provisional baseline. Short/long exceptions are statistical leads, not diagnosis or emergency alarms.</p>${this.table(['Completed','Review','Duration','Provisional boundary'],(a.ordinary_anomalies||[]).slice(-80).map(v=>[stamp(v.time),v.type,duration(v.seconds),duration(v.threshold)]))}</section>
    <section class="panel"><h3>Backwash window performance</h3>${this.table(['Start','Equipment','Starts inside','Runs overlapping','Total active','Initial stage','Quality','Comparison'],a.windows.slice(-100).map(w=>[stamp(w.start),w.equipment,String(w.pump_starts_inside_window),String(w.runs_overlapping_window),duration(w.pump_active_seconds),duration(w.stage_pump_active_seconds),w.quality,w.comparison]))}</section>
    <section class="panel"><h3>Expected cycles without recorded pump overlap</h3>${this.table(['Expected cycle','Equipment','Recorded overlaps','Coverage'],a.windows.filter(w=>!w.runs_overlapping_window).slice(-60).map(w=>[stamp(w.start),w.equipment,String(w.runs_overlapping_window),w.quality]))}</section>`}
  scatter(){const rs=this.data.analysis.runs;if(!rs.length)return '<p class="hint">No paired relay intervals in the selected range. Try backfill or expand the range.</p>';
    const w=1050,h=260,l=62,t=22,bar=205,b=35,xmax=this.data.selected.end,xmin=this.data.selected.start,max=Math.max(60,...rs.filter(r=>r.quality!=='excluded').map(r=>r.seconds))*1.15;
    let s=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Pump run duration scatter plot">`;
    for(let i=0;i<=5;i++){const y=bar-i/5*(bar-t);s+=`<line x1="${l}" x2="1030" y1="${y}" y2="${y}" class="gridline"/><text x="${l-8}" y="${y+4}" fill="currentColor" text-anchor="end" font-size="10">${Math.round(max*i/5)}s</text>`}
    for(const r of rs){const x=l+(r.stopped-xmin)/(xmax-xmin)*968,y=bar-Math.min(r.seconds,max)/max*(bar-t),col=r.quality==='excluded'?WTM_COLORS.excluded:r.category==='ordinary'?WTM_COLORS.ordinary:r.category==='mixed'?WTM_COLORS.mixed:r.category==='manual'?WTM_COLORS.manual:WTM_COLORS.expected;
      s+=`<circle cx="${x}" cy="${y}" r="3.4" fill="${col}" opacity=".75"><title>${esc(stamp(r.stopped)+' · '+duration(r.seconds)+' · '+rel(r.category)+(r.quality==='excluded'?' · excluded from baseline':''))}</title></circle>`}
    const p90=this.data.analysis.ordinary_baseline.p90_seconds;
    if(p90!=null){const y=bar-p90/max*(bar-t);s+=`<line x1="${l}" x2="1030" y1="${y}" y2="${y}" stroke="#d3a852" stroke-dasharray="6,5"/><text x="1018" y="${y-7}" text-anchor="end" font-size="10" fill="#d3a852">Ordinary P90 ${esc(duration(p90))}</text>`}
    return s+'</svg>'}
  dailyChart(){const rows=this.data.analysis.daily;if(!rows.length)return '<p class="hint">No quality-qualified relay activity in this range.</p>';
    const max=Math.max(60,...rows.map(d=>d.ordinary+d.expected+d.manual));const width=1050,h=260,l=55,t=26,base=218;let s=`<svg viewBox="0 0 ${width} ${h}" role="img" aria-label="Daily pump runtime stacked bars">`;
    for(let i=0;i<5;i++){const y=base-i*(base-t)/4;s+=`<line class="gridline" x1="${l}" x2="1030" y1="${y}" y2="${y}"/><text x="${l-8}" y="${y+4}" text-anchor="end" font-size="10" fill="currentColor">${Math.round(max*i/4/60)}m</text>`}
    const gap=(1030-l)/rows.length,barW=Math.max(1,Math.min(32,gap*.78));for(let i=0;i<rows.length;i++){let y=base;const r=rows[i];for(const key of ['ordinary','expected','manual']){const size=r[key]/max*(base-t);y-=size;s+=svgRect(l+i*gap+gap/2-barW/2,y,barW,size,WTM_COLORS[key],.9,`${r.day}: ${key}: ${duration(r[key])}`)}}
    for(let i=0;i<rows.length;i+=Math.max(1,Math.ceil(rows.length/12))){s+=`<text x="${l+i*gap+gap/2}" y="241" text-anchor="middle" fill="currentColor" font-size="10">${esc(rows[i].day.slice(5))}</text>`}
    return s+'</svg>'+`<div class="legend">${[['Ordinary',WTM_COLORS.ordinary],['Expected-window overlap',WTM_COLORS.expected],['Manual overlap',WTM_COLORS.manual]].map(([name,c])=>`<span class="key"><i class="dot" style="background:${c}"></i>${name}</span>`).join('')}</div>`}
  timeZoneNotice(){const browser=Intl.DateTimeFormat().resolvedOptions().timeZone;
    const controller=this.data?.timezone;
    return controller&&browser!==controller?`<div class="notice">Your browser time zone is ${esc(browser)}, but HA is ${esc(controller)}. Date/time inputs below use the browser time zone; controller start clocks and daily charts use HA time. Verify timestamp conversions before saving.</div>`:'';
  }
  fields(info){return info.map(([name,label,type,value,opts])=>`<div class="field"><label for="${name}">${esc(label)}</label>${type==='select'?`<select name="${name}" id="${name}">${opts.map(([val,text])=>`<option value="${esc(val)}" ${String(value)===String(val)?'selected':''}>${esc(text)}</option>`).join('')}</select>`:type==='textarea'?`<textarea name="${name}" id="${name}">${esc(value)}</textarea>`:`<input name="${name}" id="${name}" type="${type}" value="${esc(value??'')}" ${type==='number'?'step="any"':''} ${['anchor_date','weekdays'].includes(name)?'':'required'}>`}</div>`).join('')}
  schedules(){const r=this.edit?.table==='schedules'?this.edit.record:null;
    const model={equipment:r?.equipment||'softener',effective:r?.effective||Date.now()/1000,start_time:r?.start_time||'02:00',duration_min:r?.duration_min||90,stage_min:r?.stage_min??0,cadence:r?.cadence||'unknown',interval_days:r?.interval_days||1,anchor_date:r?.anchor_date||'',weekdays:r?.weekdays||'',notes:r?.notes||''};
    const form=this.fields([['equipment','Equipment','select',model.equipment,[['softener','Water softener'],['neutralizer','Calcite neutralizer']]],['effective','Effective from (date/time)','datetime-local',localInput(model.effective)],['start_time','Controller start time (HA local)','time',model.start_time],['duration_min','Total active cycle (minutes)','number',model.duration_min],['stage_min','Initial backwash phase (minutes)','number',model.stage_min],['cadence','Actual recurrence','select',model.cadence,[['unknown','Unknown — no predicted runs'],['demand','Demand-triggered — no predicted dates'],['daily','Every day'],['interval','Every N days'],['weekdays','Selected weekdays']]],['interval_days','Every N days (if interval)','number',model.interval_days],['anchor_date','Known anchor date (if interval)','date',model.anchor_date],['weekdays','Weekdays 0=Mon … 6=Sun (comma-separated)','text',model.weekdays],['notes','Source / controller verification notes','textarea',model.notes]]);
    return `${this.timeZoneNotice()}<section class="panel"><h3>${r?'Correct historical schedule':'Record a new controller schedule revision'}</h3><p class="hint">Schedule revisions are committed in one operation. They describe the physical controller; these inputs do not change the controller. A new revision supersedes the preceding schedule from its effective time onward. Historical corrections have audit records.</p><form data-form="schedules" class="form-grid">${form}<div class="actions" style="grid-column:1/-1"><button class="primary" type="submit">${r?'Save correction':'Commit new revision'}</button>${r?'<button type="button" data-action="cancel-edit">Cancel edit</button>':''}</div></form></section>
    <section class="panel"><h3>Schedule history</h3>${this.recordTable('schedules')}</section><div class="notice">Never assume a demand-controlled softener ran on a specific date just because its controller has a preferred clock time. Use a manual-event entry for observed/reported runs.</div>`}
  entries(){const editM=this.edit?.table==='manual_runs'?this.edit.record:null;const editP=this.edit?.table==='ph_tests'?this.edit.record:null;
    const formM=this.fields([['equipment','Equipment','select',editM?.equipment||'softener',[['softener','Softener'],['neutralizer','Neutralizer']]],['started','Reported start','datetime-local',localInput(editM?.started)],['duration_min','Reported duration (min)','number',editM?.duration_min||60],['notes','Notes / evidence','textarea',editM?.notes||'']]);
    const formP=this.fields([['sampled','Sample date/time','datetime-local',localInput(editP?.sampled)],['location','Location','select',editP?.location||'treated',[['treated','Final treated'],['raw','Raw well']]],['ph','pH measurement','number',editP?.ph??7],['notes','Meter, calibration, notes','textarea',editP?.notes||'']]);
    return `${this.timeZoneNotice()}<div class="split"><section class="panel"><h3>${editM?'Correct manual backwash':'Record one-off manual backwash'}</h3><p class="hint">Reported event, not a valve state measurement.</p><form data-form="manual_runs" class="form-grid" style="grid-template-columns:repeat(2,minmax(0,1fr))">${formM}<div class="actions" style="grid-column:1/-1"><button type="submit" class="primary">${editM?'Update':'Add manual run'}</button>${editM?'<button type="button" data-action="cancel-edit">Cancel edit</button>':''}</div></form></section>
      <section class="panel"><h3>${editP?'Correct pH sample':'Record pH sample'}</h3><p class="hint">Date-specific samples. Multiple samples on a day are supported; editing changes only the selected record.</p><form data-form="ph_tests" class="form-grid" style="grid-template-columns:repeat(2,minmax(0,1fr))">${formP}<div class="actions" style="grid-column:1/-1"><button type="submit" class="primary">${editP?'Update':'Record pH'}</button>${editP?'<button type="button" data-action="cancel-edit">Cancel edit</button>':''}</div></form></section></div>
      <section class="panel"><h3>pH trend</h3>${this.phChart()}</section><section class="panel"><h3>Manual backwash records</h3>${this.recordTable('manual_runs')}</section><section class="panel"><h3>pH sample history</h3>${this.recordTable('ph_tests')}</section>`}
  phChart(){const rows=this.data.tests||[];if(!rows.length)return '<p class="hint">No saved pH samples in the selected range.</p>';
    const lo=this.data.selected.start,hi=this.data.selected.end,w=1050,h=230,l=55,right=30,top=14,base=192;
    let s=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Raw and treated pH history">`;
    for(let v=4;v<=10;v+=1){const y=base-(v-4)/6*(base-top);s+=`<line class="gridline" x1="${l}" x2="${w-right}" y1="${y}" y2="${y}"/><text x="${l-8}" y="${y+4}" text-anchor="end" font-size="10" fill="currentColor">${v}</text>`}
    for(const loc of ['raw','treated']){const vals=rows.filter(x=>x.location===loc&&x.ph>=4&&x.ph<=10).sort((a,b)=>a.sampled-b.sampled);if(!vals.length)continue;const col=loc==='raw'?'#d5a16c':'#36ad9d';
      let p=vals.map(v=>`${l+(v.sampled-lo)/(hi-lo)*(w-l-right)},${base-(v.ph-4)/6*(base-top)}`).join(' ');if(vals.length>1)s+=`<polyline points="${p}" fill="none" stroke="${col}" stroke-width="2"/>`;
      for(const v of vals){const x=l+(v.sampled-lo)/(hi-lo)*(w-l-right),y=base-(v.ph-4)/6*(base-top);s+=`<circle cx="${x}" cy="${y}" r="4" fill="${col}"><title>${esc(loc+' pH '+v.ph+' · '+stamp(v.sampled))}</title></circle>`}}
    return s+'</svg><p class="hint">For visual readability the plot shows pH 4–10; samples outside this range remain in the records below.</p>'}
  recordTable(table){const data=table==='schedules'?this.data.schedules:table==='quality_ranges'?this.data.quality_ranges:table==='ph_tests'?this.data.tests:this.data.manual;
    const columns=table==='schedules'?['Equipment','Effective','Start','Cadence','Duration','Actions']:table==='quality_ranges'?['From','Until','Effect','Reason','Notes','Actions']:table==='manual_runs'?['Equipment','Started','Minutes','Notes','Actions']:['Sampled','Location','pH','Notes','Actions'];
    const rows=data.slice().sort((a,b)=>(b.effective??b.started??b.sampled)-(a.effective??a.started??a.sampled)).slice(0,500).map(r=>{const actions=`<button data-action="edit" data-table="${table}" data-id="${r.id}">Edit</button> <button data-action="delete" class="danger" data-table="${table}" data-id="${r.id}">Delete</button>`;
      return table==='quality_ranges'?[stamp(r.started),stamp(r.ended),r.effect,r.reason,r.notes||'',{html:actions}]:table==='schedules'?[r.equipment,stamp(r.effective),r.start_time,r.cadence+ (r.cadence==='interval'?` (${r.interval_days}d)`:''),`${r.duration_min}m`,{html:actions}]:table==='manual_runs'?[r.equipment,stamp(r.started),String(r.duration_min),r.notes||'',{html:actions}]:[stamp(r.sampled),r.location,String(r.ph),r.notes||'',{html:actions}]});
    return this.table(columns,rows)}
  qualityEditor(){
    const r=this.edit?.table==='quality_ranges'?this.edit.record:null;
    const model={started:r?.started??Date.now()/1000-3600,ended:r?.ended??Date.now()/1000,
      effect:r?.effect||'exclude',reason:r?.reason||'unverified',notes:r?.notes||''};
    const form=this.fields([
      ['started','From','datetime-local',localInput(model.started)],
      ['ended','Until','datetime-local',localInput(model.ended)],
      ['effect','Treatment of observations','select',model.effect,[['exclude','Exclude from statistics'],['review','Review only; keep in statistics']]],
      ['reason','Evidence category','select',model.reason,[['commissioning','Commissioning/contact testing'],['unverified','Unverified telemetry'],['maintenance','Maintenance'],['other','Other']]],
      ['notes','Why this interval is annotated','textarea',model.notes]
    ]);
    return `<section class="panel"><h3>${r?'Correct quality annotation':'Annotate unreliable historical intervals'}</h3>
      <p class="hint">Keep raw relay edges permanently; excluded time ranges remove overlapping runs from baselines and computed period averages. Audit history records edits and deletion. Review-only ranges do not exclude statistics.</p>
      <form data-form="quality_ranges" class="form-grid">${form}<div class="actions" style="grid-column:1/-1"><button class="primary" type="submit">${r?'Update annotation':'Record annotation'}</button>${r?'<button type="button" data-action="cancel-edit">Cancel edit</button>':''}</div></form>
      <h3>Quality annotation history</h3>${this.recordTable('quality_ranges')}</section>`;
  }
  archive(){const d=this.data.archive,h=d.health,count=d.counts;return `<div class="metrics">${this.metric('Verified pump runs',num(count.pump_runs),`Earliest: ${stamp(h.earliest_run)}`)}${this.metric('Raw pump edges',num(count.pump_edges),'Stored even after Recorder purge')}${this.metric('Data health',h.ok?'Healthy':'ERROR',h.ok?'SQLite integrity check passed':h.result)}${this.metric('Database size',(h.file_bytes/1024/1024).toFixed(2)+' MB',`Sensor health gaps: ${num(count.gaps)}`)}</div>
      <section class="panel"><h3>Historical coverage</h3><p>Archive earliest supported observation: <strong>${stamp(d.coverage_from)}</strong></p>${d.import_floor?`<p>First accepted historical transition: <strong>${stamp(d.import_floor)}</strong> (verified-era import boundary). Earlier commissioning transitions are not stored in this archive.</p>`:""}<p class="hint">Period averages include only verified complete relay runs. A period is partial until observations span its beginning. HA restarts, sensor outages and missed transitions may interrupt continuity even within an archived period.</p><div class="notice">Recorder has a configurable purge period (commonly 10 days). Older relay transitions that were never archived cannot be recovered. Re-importing the same Recorder events is safe because edges are deduplicated.</div>
      <div class="actions"><button data-action="backfill">Re-run available Recorder backfill</button><button data-action="backup">Make consistent SQLite snapshot</button><button class="primary" data-action="export">Export complete history (CSV ZIP)</button></div><p class="hint">Last snapshot: ${esc(d.last_backup||'none')}. An on-device snapshot is not protection against NVMe failure. Include the archive in HA backups and retain an off-device copy.</p></section>
      ${this.qualityEditor()}
      <section class="panel"><h3>Data quality</h3><div class="metrics">${this.metric('Total relay intervals',num(count.pump_runs),'Includes any user-annotated intervals')}${this.metric('Manual backwashes',num(count.manual_runs),'User-reported')}${this.metric('Schedule revisions',num(count.schedules),'Historical controller settings')}${this.metric('Quality annotations',num(count.quality_ranges),'Editable audited ranges')}</div>${d.error?`<div class="alert bad">${esc(d.error)}</div>`:''}</section>`}
  async click(e){const t=e.target.closest('button');if(!t)return;
    if(t.dataset.tab){if(!this._unsavedOkay())return;this._formDirty=false;this.tab=t.dataset.tab;this.edit=null;this.render();return}
    const action=t.dataset.action;
    if(action==='refresh'){await this.refresh();return}
    if(action==='apply-range'){const root=this.shadowRoot;this.customStart=new Date(root.getElementById('range-from').value).getTime()/1000;this.customEnd=new Date(root.getElementById('range-to').value).getTime()/1000;await this.refresh();return}
    if(action==='cancel-edit'){if(!this._unsavedOkay())return;this._formDirty=false;this.edit=null;this.render();return}
    if(action==='edit'){if(!this._unsavedOkay())return;this._formDirty=false;const table=t.dataset.table,id=Number(t.dataset.id);const source=table==='schedules'?this.data.schedules:table==='quality_ranges'?this.data.quality_ranges:table==='ph_tests'?this.data.tests:this.data.manual;this.edit={table,record:source.find(r=>r.id===id)};this.tab=table==='schedules'?'schedules':table==='quality_ranges'?'archive':'entries';this.render();return}
    if(action==='delete'){if(!this._unsavedOkay())return;this._formDirty=false;const table=t.dataset.table,id=Number(t.dataset.id);if(!confirm('Delete this historical record? A copy of its prior content will remain in the audit log.'))return;await this.mutate(table,'delete',{},id);return}
    if(action==='backfill'){if(!confirm('Backfill all recoverable runs from the last 10 days of Recorder? Existing archive records will be deduplicated.'))return;await this.perform('backfill',{days:10});return}
    if(action==='backup'){await this.perform('backup');return}
    if(action==='export'){try{this.busy=true;const res=await this.call('export');const binary=atob(res.base64);const array=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)array[i]=binary.charCodeAt(i);const url=URL.createObjectURL(new Blob([array],{type:'application/zip'}));const link=document.createElement('a');link.href=url;link.download=res.filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),12000);}catch(err){this.error=String(err?.message||err)}finally{this.busy=false;this.render()}return}
  }
  change(e){if(e.target?.closest?.('form[data-form]'))this._formDirty=true;if(e.target?.id==='range'){this.range=Number(e.target.value);if(this.range===0)this.render();else this.refresh();}}
  async submit(e){const form=e.target.closest('form[data-form]');if(!form)return;e.preventDefault();const table=form.dataset.form;const vals=Object.fromEntries(new FormData(form));
    for(const key of ['effective','started','ended','sampled'])if(vals[key])vals[key]=new Date(vals[key]).getTime()/1000;
    if(table==='schedules'){vals.start_time=vals.start_time.slice(0,5);vals.duration_min=Number(vals.duration_min);vals.stage_min=Number(vals.stage_min);vals.interval_days=Number(vals.interval_days)}
    if(table==='manual_runs')vals.duration_min=Number(vals.duration_min);
    if(table==='ph_tests')vals.ph=Number(vals.ph);
    const edit=this.edit?.table===table?this.edit.record:null;
    if(edit){vals.updated=edit.updated}
    await this.mutate(table,edit?'update':'create',vals,edit?.id);
  }
  async mutate(table,operation,values,record_id){try{
    this.busy=true;
    const payload={table,operation,values};if(record_id!=null)payload.record_id=record_id;
    await this.call('mutate',payload);
    this._formDirty=false;this.edit=null;this.error='';
    await this.refresh(false);
  }catch(err){this.error=String(err?.message||err);this._showFormError(this.error)}
  finally{this.busy=false;if(!this._shouldHoldForm())this.render()}}
  async perform(name,args={}){try{this.busy=true;const result=await this.call(name,args);this.error='';if(name==='backup')alert(`SQLite snapshot created: ${result.path}. Copy this file off the HA device for disaster recovery.`);await this.refresh(false);}catch(err){this.error=String(err?.message||err)}finally{this.busy=false;this.render()}}
}
customElements.define('water-treatment-monitor-card',WaterTreatmentCard);
window.customCards=window.customCards||[];
window.customCards.push({type:'water-treatment-monitor-card',name:'Water Treatment Monitor',description:'Durable well-pump monitoring, expected regeneration and editable pH history',preview:false});
