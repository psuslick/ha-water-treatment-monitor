"""Regression cases based on live HA audit of 2026-11-02 and interface requirements."""
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from test_archive import dbmod, analysis
import pytest

TZ=ZoneInfo('America/New_York')

def ts(iso):return dbmod.timestamp(iso)

def test_user_configured_import_boundary_filters_commissioning_without_deleting_recorder():
    """Synthetic 45-pair sequence: 13 earlier tests and 32 valid later runs."""
    with TemporaryDirectory() as t:
        a=dbmod.Archive(f'{t}/wtm.db');a.initialize()
        source='binary_sensor.demo_well_pump'
        a.bind_source(source)
        floor=ts('2026-01-01T12:00:00+00:00')
        assert a.initialize_import_floor(source,'2026-01-01T12:00:00+00:00')
        assert not a.initialize_import_floor(source,'2026-01-01T12:00:00+00:00')
        assert float(a.metadata()['import_floor'])==floor
        early=ts('2026-01-01T00:00:00+00:00')
        commissioning=[(early+i*300,4.0) for i in range(11)]
        commissioning.extend([(early+3600,1100),(early+7200,28000)])
        # All commissioning stops are before the valid era in this synthetic replay.
        verified=[(floor+i*1000,128.5) for i in range(32)]
        cycles=sorted(commissioning+verified)
        assert len(cycles)==45
        records=[]
        for when,secs in cycles:
            records.extend([(when,'on',False),(when+secs,'off',False)])
        start=early-3600;end=floor+33*1000
        result=a.import_recorder(records,start,end)
        assert result['rows_skipped_before_floor']==26
        assert a.count()['pump_runs']==32
        assert a.count()['pump_edges']==64
        assert a.count()['quality_ranges']==0
        assert a.run_metrics({'test':(start,end)})['test']['count']==32
        assert a.run_metrics({'test':(start,end)})['test']['mean_seconds']==128.5
        assert a.all_runs(start,end)[0]['started']==floor
        assert result['coverage_from']==floor
        assert not a.add_live_edge(early,'on',reliable_start=True)['edge_inserted']
        result2=a.import_recorder(records,start,end)
        assert result2['new_edges']==0
        assert result2['rows_skipped_before_floor']==26
        assert a.count()['pump_runs']==32
        later=floor+35*1000
        a.add_live_edge(later,'on',reliable_start=True)
        a.add_live_edge(later+1400,'off')
        assert a.count()['pump_runs']==33


def test_import_floor_is_source_specific_and_existing_data_is_never_silently_deleted():
    with TemporaryDirectory() as t:
        other=dbmod.Archive(f'{t}/other.db');other.initialize()
        assert not other.initialize_import_floor('binary_sensor.other_well_pump',None)
        assert 'import_floor' not in other.metadata()
        a=dbmod.Archive(f'{t}/legacy.db');a.initialize()
        prior=ts('2026-01-01T00:00:00+00:00')
        a.add_live_edge(prior,'on',reliable_start=True)
        a.add_live_edge(prior+4,'off')
        assert a.count()['pump_runs']==1
        with pytest.raises(RuntimeError,match='older pump edges'):
            a.initialize_import_floor('binary_sensor.demo_well_pump','2026-01-01T12:00:00+00:00')
        assert a.count()['pump_runs']==1
        assert a.count()['pump_edges']==2


def sched(start,end='02:10',minutes=10):
    return {'id':1,'equipment':'softener','effective':0,'start_time':start,'duration_min':minutes,
            'stage_min':5,'cadence':'daily','interval_days':1,'anchor_date':None,'weekdays':''}


def test_exact_overlap_and_separate_starts_vs_overlaps():
    start=ts('2026-11-02T01:55:00-05:00');end=ts('2026-11-02T02:15:00-05:00')
    run_start=ts('2026-11-02T01:59:00-05:00')
    second=ts('2026-11-02T02:02:00-05:00')
    runs=[{'started':run_start,'stopped':run_start+120,'seconds':120,'quality':'usable'},
          {'started':second,'stopped':second+60,'seconds':60,'quality':'usable'}]
    result=analysis.analyze(runs,[sched('02:00')],[],start,end,'America/New_York')
    win=result['windows'][0]
    assert win['pump_active_seconds']==120
    assert win['stage_pump_active_seconds']==120
    assert win['runs_overlapping_window']==2
    assert win['pump_starts_inside_window']==1
    d=result['daily'][0]
    assert d['ordinary']==60 and d['expected']==120 and d['manual']==0
    assert d['ordinary']+d['expected']+d['manual']==180
    assert result['ordinary_baseline']['count']==0


def test_midnight_splitting_dst_and_manual_precedence():
    a=ts('2026-11-02T23:59:30-05:00')
    r={'started':a,'stopped':a+60,'seconds':60,'quality':'usable'}
    result=analysis.analyze([r],[],[],a-120,a+120,'America/New_York')
    assert [x['ordinary'] for x in result['daily'] if x['ordinary']>0]==[30,30]
    # Manual + scheduled overlap must not count the same 30 s twice.
    s=ts('2026-11-02T02:00:00-05:00')
    r={'started':s-30,'stopped':s+90,'seconds':120,'quality':'usable'}
    manual=[{'equipment':'neutralizer','started':s+30,'duration_min':1,'id':2}]
    result=analysis.analyze([r],[sched('02:00')],manual,s-60,s+120,'America/New_York')
    d=next(x for x in result['daily'] if x['ordinary'] or x['expected'] or x['manual'])
    assert (d['ordinary'],d['expected'],d['manual'])==(30,30,60)
    assert d['ordinary']+d['expected']+d['manual']==120
    # DST fall-back is a 25 h local day and should not lose 60 seconds at midnight.
    d0=ts('2026-11-01T00:00:00-04:00')
    d1=ts('2026-11-02T00:00:00-05:00')
    assert d1-d0==25*3600
    assert list(analysis._daily_split(d1-30,d1+30,TZ))==[('2026-11-01',30),('2026-11-02',30)]


def test_gap_exclusion_and_quality_not_attributed():
    start=ts('2026-11-02T01:55:00-05:00');end=start+1800
    on=start+300
    run={'started':on,'stopped':on+120,'seconds':120,'quality':'excluded'}
    exclusions=[{'started':start,'ended':end,'effect':'exclude','reason':'unverified'}]
    result=analysis.analyze([run],[sched('02:00')],[],start,end,'America/New_York',[],exclusions)
    assert result['total_runs']==0 and result['excluded_runs']==1
    assert result['windows'][0]['quality']=='excluded_context'
    assert result['windows'][0]['pump_active_seconds']==0
    assert sum(v['ordinary']+v['expected']+v['manual'] for v in result['daily'])==0
    assert sum(v['excluded'] for v in result['daily'])==120
    assert analysis.coverage_for_periods({'part':(start,end)},start-100,[],True,exclusions)['part']['status']=='interrupted'


def test_migrate_schema_1_to_2():
    import sqlite3
    with TemporaryDirectory() as t:
        path=f'{t}/old.db'
        with sqlite3.connect(path) as c:
            c.execute('PRAGMA user_version=1')
            c.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            c.execute('INSERT INTO metadata VALUES (?,?)',('existing','preserved'))
        a=dbmod.Archive(path);a.initialize()
        assert a.metadata()['existing']=='preserved'
        assert a.count()['quality_ranges']==0
        with a.connect() as c:assert c.execute('PRAGMA user_version').fetchone()[0]==2


def test_archive_refuses_source_change():
    with TemporaryDirectory() as t:
        a=dbmod.Archive(f'{t}/wtm.db');a.initialize()
        a.bind_source('binary_sensor.demo_well_pump')
        a.bind_source('binary_sensor.demo_well_pump')
        with pytest.raises(RuntimeError):a.bind_source('binary_sensor.another_pump')
        assert a.metadata()['pump_entity']=='binary_sensor.demo_well_pump'


def test_backwash_window_before_recorder_coverage_is_not_marked_provisional():
    start=ts('2026-11-02T01:50:00-05:00');end=start+1800
    result=analysis.analyze([], [sched('02:00')], [],start,end,'America/New_York',[],[],end+1)
    assert result['windows'][0]['quality']=='no_archive'
    assert result['windows'][0]['comparison']=='unreliable context'


def test_import_floor_does_not_reset_an_existing_archive_if_optional_setting_omitted():
    with TemporaryDirectory() as t:
        a=dbmod.Archive(f'{t}/wtm.db');a.initialize()
        src='binary_sensor.demo_well_pump'
        a.bind_source(src)
        assert a.initialize_import_floor(src,'2026-01-01T12:00:00+00:00')
        floor=float(a.metadata()['import_floor'])
        assert a.initialize_import_floor(src,None) is False
        assert float(a.metadata()['import_floor'])==floor
        with pytest.raises(RuntimeError,match='differs'):
            a.initialize_import_floor(src,'2026-01-01T12:00:01+00:00')
        assert float(a.metadata()['import_floor'])==floor

def test_import_floor_rejects_future_timestamp():
    import datetime
    future=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=1)).isoformat()
    with TemporaryDirectory() as t:
        a=dbmod.Archive(f'{t}/wtm.db');a.initialize()
        with pytest.raises(ValueError,match='future'):
            a.initialize_import_floor('binary_sensor.demo_well_pump',future)


def test_ph_sample_is_durable_audited_and_not_limited_by_chart_range():
    """DB keeps backdated pH records independently of dashboard date filters."""
    with TemporaryDirectory() as temp:
        archive=dbmod.Archive(f"{temp}/monitor.db")
        archive.initialize()
        sampled=ts("2025-09-21T12:00:00-04:00")
        result=archive.mutate_record(
            "ph_tests","create",
            {"sampled":sampled,"location":"treated","ph":7.26,
             "notes":"Entered via helper pH button"},None,"home_assistant:ph_button")
        assert result["ok"] and result["id"] > 0
        assert archive.list_records("ph_tests",sampled-1,sampled+1)[0]["ph"] == 7.26
        assert archive.list_records("ph_tests",sampled+86400,sampled+2*86400) == []
        assert archive.count()["ph_tests"] == 1
        audits=archive.list_records("audit_log")
        assert any(row["table_name"]=="ph_tests" and row["actor"]=="home_assistant:ph_button" for row in audits)
