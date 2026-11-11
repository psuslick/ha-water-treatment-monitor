"""Timezone-correct, retrospective treatment-context analysis."""
from __future__ import annotations

from bisect import bisect_left
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
from typing import Any


def _date(s: str) -> date:
    return date.fromisoformat(s)


def window_for_schedule(local_day: date, version: dict, zone: ZoneInfo) -> dict | None:
    cadence = version["cadence"]
    if cadence in ("unknown", "demand"):
        return None
    if cadence == "interval":
        if not version.get("anchor_date"):
            return None
        span = int(version["interval_days"])
        if not 1 <= span <= 365:
            return None
        delta = (local_day - _date(version["anchor_date"])).days
        if delta < 0 or delta % span != 0:
            return None
    elif cadence == "weekdays":
        days = set(int(v) for v in str(version.get("weekdays") or "").split(",") if v.strip().isdigit())
        if local_day.weekday() not in days:
            return None
    elif cadence != "daily":
        return None
    hour, minute = map(int, version["start_time"].split(":"))
    local_dt = datetime.combine(local_day, time(hour, minute), tzinfo=zone)
    # Both folds at a DST overlap may be real. We refuse to infer controller behavior there.
    fold_alt = local_dt.replace(fold=1)
    ambiguous = fold_alt.utcoffset() != local_dt.utcoffset()
    utc_dt = local_dt.astimezone(timezone.utc)
    round_trip = utc_dt.astimezone(zone)
    nonexistent = (round_trip.hour, round_trip.minute, round_trip.date()) != (hour, minute, local_day)
    if ambiguous or nonexistent:
        return {"equipment":version["equipment"],"date":local_day.isoformat(),"unresolved":True,
                "reason":"DST ambiguous/repeated time" if ambiguous and not nonexistent else "DST nonexistent time",
                "version_id":version["id"]}
    begin = utc_dt.timestamp()
    # A schedule version is valid at the instant a physical controller cycle starts.
    if begin < version["effective"]:
        return None
    return {"equipment":version["equipment"],"start":begin,"end":begin+float(version["duration_min"])*60,
            "stage_end":begin+min(float(version["stage_min"]),float(version["duration_min"]))*60,
            "version_id":version["id"],"date":local_day.isoformat(),"unresolved":False,"source":"expected"}


def schedule_windows(schedules: list[dict], start: float, end: float, tz_name: str, limit_days: int = 366*6) -> list[dict]:
    """Latest effective revision governs each candidate; older rules never bleed through."""
    if end <= start:
        return []
    zone = ZoneInfo(tz_name)
    begin_day = datetime.fromtimestamp(start-86400, zone).date()
    end_day = datetime.fromtimestamp(end,zone).date()
    days = (end_day-begin_day).days+1
    if days > limit_days:
        raise ValueError("Range exceeds schedule analysis maximum")
    by_equip = defaultdict(list)
    for v in schedules:
        by_equip[v["equipment"]].append(v)
    for versions in by_equip.values():
        versions.sort(key=lambda v:v["effective"])
    result=[]
    for i in range(days):
        d=begin_day+timedelta(days=i)
        for equip,versions in by_equip.items():
            # Each historical version proposes only its own clock time. Keep it
            # only when that exact version was in effect at that clock instant.
            # This prevents an old recurrence from leaking through after a new
            # version changed the clock, cadence, or became demand-triggered.
            for ix,v in enumerate(versions):
                candidate=window_for_schedule(d,v,zone)
                if not candidate:
                    continue
                if candidate.get("unresolved"):
                    # The physical controller behavior at this clock transition is
                    # unknowable; report only versions plausibly effective that day.
                    effective_day=datetime.fromtimestamp(v["effective"],zone).date()
                    if d>=effective_day:
                        result.append(candidate)
                    continue
                instant=candidate["start"]
                if ix+1<len(versions) and versions[ix+1]["effective"]<=instant:
                    continue
                if candidate["start"]<end and candidate["end"]>start:
                    result.append(candidate)

    return sorted(result,key=lambda w:w.get("start",0))


MAX_CONTEXT_SECONDS = 8 * 3600  # Schedules and manual events are limited to eight hours.


def _overlaps(items: list[dict], starts: list[float], start: float, end: float, field: str,
              max_duration: float = MAX_CONTEXT_SECONDS) -> list[dict]:
    """Find nearby context windows without scanning years of unrelated events."""
    lo = bisect_left(starts, start-max_duration)
    hi = bisect_left(starts, end)
    return [w for w in items[lo:hi] if w[field]+(
        float(w["duration_min"])*60 if field=="started" else float(w["end"])-w["start"]
    ) > start]


def _segments(start: float, end: float, expected: list[dict], manual: list[dict]) -> list[tuple[float,float,str]]:
    """Partition one interval; manual context takes precedence over schedule context.

    Duration is conserved: no second can be assigned to two daily chart categories.
    """
    if end<=start:return []
    bounds={start,end}
    for w in expected:
        bounds.add(max(start,w["start"]));bounds.add(min(end,w["end"]))
    for m in manual:
        bounds.add(max(start,m["started"]));bounds.add(min(end,m["started"]+m["duration_min"]*60))
    times=sorted(bounds)
    out=[]
    for s,e in zip(times,times[1:]):
        if e<=s:continue
        mid=(s+e)/2
        if any(m["started"]<=mid<m["started"]+m["duration_min"]*60 for m in manual): cat="manual"
        elif any(w["start"]<=mid<w["end"] for w in expected):cat="expected"
        else:cat="ordinary"
        out.append((s,e,cat))
    return out


def _daily_split(s: float, e: float, tz: ZoneInfo):
    """Yield exact portions at HA-local midnight, including 23/25 hour DST days."""
    while s<e:
        local_day=datetime.fromtimestamp(s,tz).date()
        tomorrow=datetime.combine(local_day+timedelta(days=1),time.min,tzinfo=tz).timestamp()
        cutoff=min(e,tomorrow)
        if cutoff<=s:raise RuntimeError("Local midnight did not advance")
        yield local_day.isoformat(),cutoff-s
        s=cutoff


def _pctl(arr: list[float], p: float) -> float | None:
    if not arr:return None
    arr=sorted(arr)
    x=(len(arr)-1)*p;lo=int(x);hi=min(len(arr)-1,lo+1)
    return round(arr[lo]+(arr[hi]-arr[lo])*(x-lo),1)


def analyze(runs: list[dict], schedules: list[dict], manual: list[dict], start: float, end: float,
            tz_name: str, gaps: list[dict] | None = None, quality_ranges: list[dict] | None = None,
            coverage_from: float | None = None) -> dict:
    """Time-conserving, quality-aware analysis; does not certify physical valve operation."""
    windows=schedule_windows(schedules,start,end,tz_name)
    unresolved=[w for w in windows if w.get("unresolved")]
    valid=sorted((w for w in windows if not w.get("unresolved")),key=lambda v:v["start"])
    manuals=sorted(manual,key=lambda v:v["started"])
    win_starts=[w["start"] for w in valid]
    man_starts=[m["started"] for m in manuals]
    source_gaps=gaps or []
    excluded_ranges=[r for r in (quality_ranges or []) if r.get("effect")=="exclude"]
    decorated=[]
    daily=defaultdict(lambda:{"ordinary":0.0,"expected":0.0,"manual":0.0,"excluded":0.0,"count":0,"excluded_count":0})
    ordinary=[]
    active_runs=sorted((r for r in runs if r["stopped"]>start and r["started"]<end),key=lambda r:r["started"])
    usable=[r for r in active_runs if r.get("quality","usable")!="excluded"]
    excluded_count=0
    zone=ZoneInfo(tz_name)
    for r in active_runs:
        is_excluded=r.get("quality")=="excluded"
        s,e=max(r["started"],start),min(r["stopped"],end)
        overlapping_expected=_overlaps(valid,win_starts,r["started"],r["stopped"],"start")
        overlapping_manual=_overlaps(manuals,man_starts,r["started"],r["stopped"],"started")
        if is_excluded:
            segments=[(s,e,"excluded")]
            kind="excluded"
        else:
            segments=_segments(s,e,overlapping_expected,overlapping_manual)
            # Baselines need entirely ordinary runs; partial treatment overlap is not ordinary.
            full_context=_segments(r["started"],r["stopped"],overlapping_expected,overlapping_manual)
            categories={cat for _,_,cat in full_context}
            kind=next(iter(categories)) if len(categories)==1 else "mixed"
            if kind=="ordinary" and start<=r["stopped"]<end:
                ordinary.append(r["seconds"])
        if start<=r["stopped"]<end:
            key=datetime.fromtimestamp(r["stopped"],zone).date().isoformat()
            daily[key]["excluded_count" if is_excluded else "count"]+=1
            if is_excluded:excluded_count+=1
            decorated.append({**r,"category":kind})
        for part_start,part_end,cat in segments:
            for day,seconds in _daily_split(part_start,part_end,zone):
                daily[day][cat]+=seconds
    # Individual expected regeneration windows. A run may overlap without STARTING inside.
    run_starts=[r["started"] for r in usable]
    observed=[]
    for w in valid:
        # Runs may begin before the window, but cannot exceed 24h by ingestion.
        matching=[r for r in usable[max(0,bisect_left(run_starts,w["start"]-86400)):bisect_left(run_starts,w["end"])]
                  if r["stopped"]>w["start"]]
        overlap=lambda stop:sum(max(0,min(r["stopped"],stop)-max(r["started"],w["start"])) for r in matching)
        bad_quality=any(q["started"]<w["end"] and q["ended"]>w["start"] for q in excluded_ranges)
        gaps_inside=any(w["start"]<=g["ts"]<w["end"] for g in source_gaps)
        quality=("no_archive" if coverage_from is not None and w["end"] <= coverage_from
                 else "partial" if coverage_from is not None and w["start"] < coverage_from
                 else "excluded_context" if bad_quality else "interrupted" if gaps_inside else "provisional")
        active_seconds=round(overlap(w["end"]),1)
        n_starts=sum(w["start"]<=r["started"]<w["end"] for r in matching)
        observed.append({**w,"runs_overlapping_window":len(matching),"overlap_runs":len(matching),
                         "pump_starts_inside_window":n_starts,"pump_active_seconds":active_seconds,
                         "stage_pump_active_seconds":round(overlap(w["stage_end"]),1),"quality":quality,
                         "interpretation":"pump activity observed" if matching else "no recorded pump overlap; not proof of failure"})
    by_eq=defaultdict(list)
    for w in observed:
        if w["quality"]=="provisional" and w["runs_overlapping_window"]:
            by_eq[w["equipment"]].append(w["pump_active_seconds"])
    baseline={key:{"sample_windows":len(vals),"median_pump_seconds":_pctl(vals,.5),
                   "p90_pump_seconds":_pctl(vals,.9)} for key,vals in by_eq.items()}
    typical=_pctl(ordinary,.5);ordinary_p90=_pctl(ordinary,.9)
    anomalies=[]
    if len(ordinary)>=20 and typical and ordinary_p90:
        upper=max(3*typical,1.5*ordinary_p90);lower=.4*typical
        for r in decorated:
            if r["category"]!="ordinary":continue
            if r["seconds"]>upper:
                anomalies.append({"time":r["stopped"],"type":"provisional long ordinary run", "seconds":r["seconds"],"threshold":round(upper,1)})
            elif r["seconds"]<lower:
                anomalies.append({"time":r["stopped"],"type":"provisional short ordinary run", "seconds":r["seconds"],"threshold":round(lower,1)})
    for w in observed:
        b=baseline.get(w["equipment"])
        w["comparison"]="unreliable context" if w["quality"]!="provisional" else "insufficient baseline"
        if w["quality"]=="provisional" and b and b["sample_windows"]>=5 and w["runs_overlapping_window"]:
            median=b["median_pump_seconds"]
            if median and (w["pump_active_seconds"]>2.5*median or w["pump_active_seconds"]<.4*median):
                w["comparison"]="review runtime variation"
            else:w["comparison"]="within provisional range"
    limited=len(decorated)>6000
    if limited:
        step=len(decorated)/6000
        sampled=[decorated[int(i*step)] for i in range(6000)]
    else:sampled=decorated
    day=datetime.fromtimestamp(start,zone).date()
    last=datetime.fromtimestamp(end-.001,zone).date()
    while day<=last:
        daily[day.isoformat()];day+=timedelta(days=1)
    return {"runs":sampled,"total_runs":len(decorated)-excluded_count,"excluded_runs":excluded_count,
            "graph_sampled":limited,"ordinary_anomalies":anomalies[-200:],
            "windows":observed,"unresolved_windows":unresolved,"manual":manuals,
            "daily":[{"day":d,**{k:round(v,1) if isinstance(v,float) else v for k,v in vals.items()}}
                     for d,vals in sorted(daily.items())],
            "ordinary_baseline":{"count":len(ordinary),"median_seconds":_pctl(ordinary,.5),"p90_seconds":_pctl(ordinary,.9)},
            "treatment_baseline":baseline,"window_count":len(observed),
            "window_with_overlap":sum(w["runs_overlapping_window"]>0 for w in observed)}

def periods_now(now: datetime, tz_name: str) -> dict[str,tuple[float,float]]:
    zone=ZoneInfo(tz_name)
    local=now.astimezone(zone)
    d=local.date()
    anchors={"day":d,"week":d-timedelta(days=d.weekday()),"month":d.replace(day=1),"year":d.replace(month=1,day=1)}
    return {k:(datetime.combine(v,time.min,tzinfo=zone).timestamp(),now.timestamp()) for k,v in anchors.items()}


def coverage_for_periods(periods: dict, coverage_from: float | None, gaps: list[dict],
                         source_ok: bool, quality_ranges: list[dict] | None = None) -> dict:
    result={}
    for name,(start,end) in periods.items():
        flags=[]
        if coverage_from is None:flags.append("no_archive")
        elif coverage_from>start:flags.append("period_starts_before_archive")
        if not source_ok:flags.append("source_unavailable")
        if any(start<=g["ts"]<end for g in gaps):flags.append("recorded_gap")
        if any(q.get("effect")=="exclude" and q["started"]<end and q["ended"]>start
               for q in (quality_ranges or [])):flags.append("excluded_quality_interval")
        if "no_archive" in flags:state="no_archive"
        elif "period_starts_before_archive" in flags:state="partial"
        elif flags:state="interrupted"
        else:state="observed_window"
        result[name]={"status":state,"coverage_from":coverage_from,"warnings":flags,
                      "note":"An observed window is not independent proof of uninterrupted physical telemetry."}
    return result
