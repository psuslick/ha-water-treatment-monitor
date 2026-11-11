"""Pure-Python tests that run without Home Assistant installed."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import zipfile
import io

DIR=Path(__file__).parents[1]/'custom_components'/'water_treatment_monitor'

def load(name):
    spec=importlib.util.spec_from_file_location(name,DIR/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

dbmod=load('db');analysis=load('analysis')


def test_cycle_rebuild_and_dedupe():
    with TemporaryDirectory() as t:
        a=dbmod.Archive(f'{t}/monitor.sqlite3');a.initialize()
        base=1_700_000_000
        a.add_gap(base-100,'setup')
        assert a.add_live_edge(base,'off')['edge_inserted']
        assert a.add_live_edge(base+10,'on',reliable_start=True)['edge_inserted']
        assert a.add_live_edge(base+125,'off')['run_inserted']
        assert a.add_live_edge(base+125,'off')['edge_inserted'] is False
        assert a.count()['pump_runs']==1
        assert a.run_metrics({'day':(base,base+86400)})['day']['mean_seconds']==115
        a.import_recorder([(base,'off',True),(base+10,'on',False),(base+125,'off',False)],base,base+86400)
        assert a.count()['pump_runs']==1
        a.add_live_edge(base+150,'on',reliable_start=True)
        a.add_gap(base+170,'unavailable')
        a.add_live_edge(base+250,'off')
        assert a.count()['pump_runs']==1
        a.add_live_edge(base+260,'on',reliable_start=True)
        a.add_live_edge(base+380,'off')
        assert a.count()['pump_runs']==2
        a.import_recorder([(base,'off',True),(base+10,'on',False),(base+125,'off',False),(base+150,'on',False),(base+250,'off',False),(base+260,'on',False),(base+380,'off',False)],base,base+86400)
        assert a.count()['pump_runs']==2
        assert a.integrity()['ok']
        s=a.snapshot(f'{t}/snapshot.sqlite3')
        assert Path(s['path']).exists()
        data=a.export_zip()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert 'pump_runs.csv' in z.namelist()


def test_mutations_audit_and_correction():
    with TemporaryDirectory() as t:
        a=dbmod.Archive(f'{t}/monitor.sqlite3');a.initialize()
        version={'equipment':'softener','effective':1_700_000_000,'start_time':'02:00',
                 'duration_min':70,'stage_min':10,'cadence':'daily','interval_days':1,
                 'anchor_date':None,'weekdays':'','notes':'physical controller'}
        id=a.mutate_record('schedules','create',version,None,'user')['id']
        old=a.list_records('schedules')[0]
        version['duration_min']=75;version['updated']=old['updated']
        a.mutate_record('schedules','update',version,id,'user')
        assert a.list_records('schedules')[0]['duration_min']==75
        assert len(a.list_records('audit_log'))==2
        a.mutate_record('schedules','delete',{},id,'user')
        assert not a.list_records('schedules')
        assert len(a.list_records('audit_log'))==3


def test_version_superseding_and_demand_schedule():
    date=datetime(2026,11,1,tzinfo=ZoneInfo('America/New_York')).timestamp()
    old={'id':1,'equipment':'softener','effective':date-86400*7,'start_time':'01:00','duration_min':70,'stage_min':10,'cadence':'daily','interval_days':1,'anchor_date':None,'weekdays':''}
    new={'id':2,**old,'effective':date,'cadence':'demand','start_time':'01:00'}
    windows=analysis.schedule_windows([old,new],date-86400*2,date+86400*2,'America/New_York')
    assert not [w for w in windows if w.get('start',0)>=date and w['equipment']=='softener']
    assert [w for w in windows if w.get('start',0)<date and w['equipment']=='softener']


def test_dst_ambiguous_and_nonexistent():
    v={'id':1,'equipment':'softener','effective':0,'start_time':'01:30','duration_min':60,'stage_min':10,'cadence':'daily','interval_days':1,'anchor_date':None,'weekdays':''}
    zone=ZoneInfo('America/New_York')
    assert analysis.window_for_schedule(datetime(2026,11,1).date(),v,zone)['unresolved']
    v['start_time']='02:30'
    assert analysis.window_for_schedule(datetime(2026,3,8).date(),v,zone)['unresolved']
    assert not analysis.window_for_schedule(datetime(2026,11,2).date(),v,zone)['unresolved']


def test_coverage_partial_and_empty():
    periods={'year':(1000,2000)}
    assert analysis.coverage_for_periods(periods,None,[],True)['year']['status']=='no_archive'
    assert analysis.coverage_for_periods(periods,1500,[],True)['year']['status']=='partial'
    assert analysis.coverage_for_periods(periods,500,[{'ts':1200}],True)['year']['status']=='interrupted'


def test_old_schedule_does_not_reappear_after_clock_move():
    zone=ZoneInfo('America/New_York')
    morning=datetime(2026,11,10,8,tzinfo=zone).timestamp()
    old={'id':1,'equipment':'neutralizer','effective':morning-86400*4,
         'start_time':'10:00','duration_min':45,'stage_min':5,'cadence':'daily','interval_days':1,'anchor_date':None,'weekdays':''}
    new={**old,'id':2,'effective':morning,'cadence':'unknown','start_time':'02:00'}
    windows=analysis.schedule_windows([old,new],morning-86400,morning+86400,'America/New_York')
    assert not [w for w in windows if w.get('start',0)>=morning and w['equipment']=='neutralizer']


def test_ordinary_anomaly_and_daily_empty_days():
    start=1700000000;end=start+4*86400
    runs=[]
    for i in range(25):
        stopped=start+3600+i*300
        seconds=110 if i<24 else 590
        runs.append({'started':stopped-seconds,'stopped':stopped,'seconds':seconds,'origin':'test'})
    a=analysis.analyze(runs,[],[],start,end,'America/New_York')
    assert a['total_runs']==25
    assert len(a['ordinary_anomalies'])==1
    assert len(a['daily'])>=4
    assert a['ordinary_baseline']['median_seconds']==110
