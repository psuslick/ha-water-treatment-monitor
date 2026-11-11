"""Dedicated, durable, indexed SQLite event archive (no HA internals edited)."""
from __future__ import annotations

import csv
from contextlib import contextmanager
import io
import json
import math
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import zipfile

SCHEMA = 2
TABLES_EXPORT = ("pump_runs", "pump_edges", "gaps", "quality_ranges", "schedules", "manual_runs", "ph_tests", "audit_log", "metadata")


def timestamp(value: str | float | int) -> float:
    if isinstance(value, (int, float)):
        result = float(value)
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("Timestamp must include a timezone offset")
        result = dt.timestamp()
    if not math.isfinite(result):
        raise ValueError("Invalid timestamp")
    return result


def iso(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="milliseconds")


class Archive:
    """Every operation opens its own connection; call from HA executor only."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA:
                raise RuntimeError(f"Archive schema {version} is newer than supported schema {SCHEMA}")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pump_edges (
                ts REAL NOT NULL, state TEXT NOT NULL, origin TEXT NOT NULL,
                PRIMARY KEY(ts, state), CHECK(state IN ('on','off','unknown','unavailable')));
            CREATE INDEX IF NOT EXISTS idx_pump_edges_ts ON pump_edges(ts);
            CREATE TABLE IF NOT EXISTS gaps (
                ts REAL PRIMARY KEY, reason TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pump_runs (
                started REAL NOT NULL, stopped REAL NOT NULL, seconds REAL NOT NULL,
                origin TEXT NOT NULL, PRIMARY KEY(started,stopped),
                CHECK(stopped > started), CHECK(seconds > 0));
            CREATE INDEX IF NOT EXISTS idx_pump_runs_stopped ON pump_runs(stopped);
            CREATE TABLE IF NOT EXISTS quality_ranges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started REAL NOT NULL, ended REAL NOT NULL,
                effect TEXT NOT NULL CHECK(effect IN ('exclude','review')),
                reason TEXT NOT NULL CHECK(reason IN ('commissioning','unverified','maintenance','other')),
                notes TEXT NOT NULL DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL,
                CHECK(ended > started));
            CREATE INDEX IF NOT EXISTS idx_quality_intervals ON quality_ranges(started,ended);
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment TEXT NOT NULL CHECK(equipment IN ('softener','neutralizer')),
                effective REAL NOT NULL, start_time TEXT NOT NULL,
                duration_min REAL NOT NULL CHECK(duration_min > 0 AND duration_min <= 480),
                stage_min REAL NOT NULL CHECK(stage_min >= 0),
                cadence TEXT NOT NULL CHECK(cadence IN ('daily','interval','weekdays','demand','unknown')),
                interval_days INTEGER NOT NULL DEFAULT 1,
                anchor_date TEXT, weekdays TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created REAL NOT NULL, updated REAL NOT NULL,
                UNIQUE(equipment, effective));
            CREATE INDEX IF NOT EXISTS idx_schedule_effective ON schedules(equipment,effective);
            CREATE TABLE IF NOT EXISTS manual_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment TEXT NOT NULL CHECK(equipment IN ('softener','neutralizer')),
                started REAL NOT NULL, duration_min REAL NOT NULL CHECK(duration_min > 0 AND duration_min <= 480),
                notes TEXT NOT NULL DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_manual_started ON manual_runs(started);
            CREATE TABLE IF NOT EXISTS ph_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sampled REAL NOT NULL, location TEXT NOT NULL CHECK(location IN ('raw','treated')),
                ph REAL NOT NULL CHECK(ph >= 0 AND ph <= 14),
                notes TEXT NOT NULL DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_ph_sampled ON ph_tests(sampled);
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, changed REAL NOT NULL,
                actor TEXT NOT NULL, table_name TEXT NOT NULL,
                row_id INTEGER, operation TEXT NOT NULL, before_json TEXT, after_json TEXT);
            CREATE INDEX IF NOT EXISTS idx_audit_changed ON audit_log(changed);
            """)
            db.execute(f"PRAGMA user_version={SCHEMA}")
            self._set_default(db, "created_at", str(time.time()))

    @staticmethod
    def _set_default(db: sqlite3.Connection, key: str, value: str) -> None:
        db.execute("INSERT OR IGNORE INTO metadata (key,value) VALUES (?,?)", (key,value))

    def bind_source(self, pump_entity: str) -> None:
        """Prevent silently mixing two different pump sensors in one archive."""
        with self.connect() as db:
            row = db.execute("SELECT value FROM metadata WHERE key='pump_entity'").fetchone()
            if row and row[0] != pump_entity:
                raise RuntimeError(f"Archive belongs to {row[0]}; refusing to ingest {pump_entity}")
            db.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES ('pump_entity',?)",(pump_entity,))

    def initialize_import_floor(self, pump_entity: str, configured_start: str | None = None) -> bool:
        """Optionally set an immutable first reliable import time for this archive.

        Users choose the boundary when configuring the integration. Nothing
        earlier is added to this archive; Home Assistant Recorder is untouched.
        Existing archives and their import floors are never silently rewritten.
        """
        if not configured_start:
            return False
        cutoff = timestamp(configured_start)
        if cutoff > time.time() + 60:
            raise ValueError("Import start must not be in the future")
        with self.connect() as db:
            source = db.execute("SELECT value FROM metadata WHERE key='pump_entity'").fetchone()
            if source and source[0] != pump_entity:
                raise RuntimeError("Import cutoff source differs from bound pump entity")
            configured = db.execute("SELECT value FROM metadata WHERE key='import_floor'").fetchone()
            if configured:
                if abs(float(configured[0]) - cutoff) > 0.001:
                    raise RuntimeError("Existing archive import floor differs; backup and deliberate migration required")
                return False
            if db.execute("SELECT 1 FROM pump_edges WHERE ts < ? LIMIT 1", (cutoff,)).fetchone() or db.execute("SELECT 1 FROM pump_runs WHERE started < ? LIMIT 1", (cutoff,)).fetchone():
                raise RuntimeError("Archive contains older pump edges/runs; backup and migrate explicitly before introducing a cutoff")
            db.execute("INSERT INTO metadata(key,value) VALUES ('import_floor',?)", (str(cutoff),))
            self._audit(db, "system", "metadata", None, "initialize_import_floor",
                        None, {"pump_entity": pump_entity, "cutoff": cutoff,
                               "basis": "User-configured earliest reliable pump observation"})
        return True

    @staticmethod
    def _import_floor(db: sqlite3.Connection) -> float | None:
        row = db.execute("SELECT value FROM metadata WHERE key='import_floor'").fetchone()
        return float(row[0]) if row else None

    def metadata(self) -> dict[str, str]:
        with self.connect() as db:
            return {r["key"]: r["value"] for r in db.execute("SELECT * FROM metadata")}

    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO metadata(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,str(value)))

    def add_gap(self, when: float, reason: str) -> None:
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO gaps VALUES (?,?)", (when,reason))

    def add_live_edge(self, when: float, state: str, origin: str = "live", reliable_start: bool = False) -> dict:
        """Persist raw edge, then capture a run if a trustworthy ON edge preceded OFF."""
        if state not in ("on", "off", "unknown", "unavailable"):
            raise ValueError("Invalid pump state")
        with self.connect() as db:
            floor = self._import_floor(db)
            if floor is not None and when < floor:
                return {"edge_inserted":False,"run_inserted":False,"below_import_floor":True}
            prev = db.execute("SELECT ts,state,origin FROM pump_edges WHERE ts<? ORDER BY ts DESC LIMIT 1", (when,)).fetchone()
            cur = db.execute("INSERT OR IGNORE INTO pump_edges(ts,state,origin) VALUES (?,?,?)", (when,state, "live_validated" if reliable_start and state=="on" else origin))
            result = {"edge_inserted": bool(cur.rowcount), "run_inserted": False}
            if cur.rowcount and state in ("unknown", "unavailable"):
                db.execute("INSERT OR IGNORE INTO gaps(ts,reason) VALUES (?,?)",
                           (when, f"Relay source became {state}"))
            if cur.rowcount:
                db.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES ('coverage_from',?)",(str(when),))
            # A delayed edge may arrive out of timestamp order: rebuild rather
            # than silently missing a now-completable historic interval.
            if cur.rowcount and db.execute("SELECT 1 FROM pump_edges WHERE ts>? LIMIT 1",(when,)).fetchone():
                self._rebuild_runs(db)
                result["run_inserted"] = False
                result["reconciled"] = True
                return result
            if not cur.rowcount or state != "off" or prev is None or prev["state"] != "on" or prev["origin"] not in ("live_validated", "recorder_validated"):
                return result
            if db.execute("SELECT 1 FROM gaps WHERE ts>? AND ts<=? LIMIT 1", (prev["ts"],when)).fetchone():
                return result
            delta = when-prev["ts"]
            if delta <= 0 or delta > 86400:
                return result
            inserted = db.execute("INSERT OR IGNORE INTO pump_runs(started,stopped,seconds,origin) VALUES (?,?,?,?)",(prev["ts"],when,delta,"live"))
            result.update(run_inserted=bool(inserted.rowcount),start=prev["ts"],stop=when,seconds=delta)
            return result

    def import_recorder(self, rows: list[tuple[float, str, bool]], start: float, end: float) -> dict:
        """Recorder snapshots at window start are anchors, never fabricated edges."""
        now = time.time()
        if end > now + 60 or start >= end:
            raise ValueError("Invalid recorder import window")
        new_edges=0
        with self.connect() as db:
            floor = self._import_floor(db)
            accepted=[]
            previous_state=None
            for ts,state,is_anchor in sorted(rows, key=lambda x:x[0]):
                if state not in ("on","off","unknown","unavailable") or not start<=ts<=end:
                    continue
                # The import floor is a hard ingestion boundary, not a quality
                # annotation. Do not archive, pair, or claim coverage before it.
                if floor is not None and ts < floor:
                    continue
                accepted.append((ts,state,is_anchor))
                if state == previous_state:
                    continue
                previous_state=state
                # Recorder first state is a snapshot, not a verified transition.
                origin="recorder_anchor" if is_anchor else "recorder_validated"
                new_edges+=bool(db.execute("INSERT OR IGNORE INTO pump_edges VALUES (?,?,?)",(ts,state,origin)).rowcount)
                if state in ("unknown", "unavailable"):
                    db.execute("INSERT OR IGNORE INTO gaps(ts,reason) VALUES (?,?)",
                               (ts, f"Recorder relay source {state}"))
            # A successful backfill extends observability of archive, not proof of sensor health.
            cur=db.execute("SELECT value FROM metadata WHERE key='coverage_from'").fetchone()
            # Do not claim archive coverage for a history query returning zero states.
            earliest = min((row[0] for row in accepted), default=None)
            coverage = min(float(cur[0]),earliest) if cur and earliest is not None else (float(cur[0]) if cur else earliest)
            if coverage is not None:
                db.execute("INSERT INTO metadata(key,value) VALUES ('coverage_from',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(coverage),))
            db.execute("INSERT INTO metadata(key,value) VALUES ('backfill_last',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(now),))
            if accepted:
                self._rebuild_runs(db)
            count=db.execute("SELECT COUNT(*) FROM pump_runs").fetchone()[0]
        return {"new_edges":new_edges,"total_runs":count,"coverage_from":coverage,
                "import_floor":floor,"rows_accepted":len(accepted),
                "rows_skipped_before_floor":sum(1 for ts,_,_ in rows if floor is not None and ts < floor)}

    @staticmethod
    def _rebuild_runs(db: sqlite3.Connection) -> None:
        """Recompute from durable edges; deterministic and deduplicated."""
        # Keep a newly recorded live edge even if it was not yet committed by Recorder.
        gaps=[r[0] for r in db.execute("SELECT ts FROM gaps ORDER BY ts")]
        import bisect
        db.execute("DELETE FROM pump_runs")
        prev=None
        for edge in db.execute("SELECT ts,state,origin FROM pump_edges ORDER BY ts"):
            ts,state,origin=edge
            if state=="off" and prev and prev[1]=="on" and prev[2] in ("live_validated","recorder_validated"):
                duration=ts-prev[0]
                pos=bisect.bisect_right(gaps,prev[0])
                if 0<duration<=86400 and not (pos<len(gaps) and gaps[pos]<=ts):
                    db.execute("INSERT OR IGNORE INTO pump_runs VALUES (?,?,?,?)",(prev[0],ts,duration,"reconstructed"))
            prev=(ts,state,origin)

    def _audit(self, db, actor: str, table: str, row_id: int | None, action: str, before: dict | None, after: dict | None) -> None:
        db.execute("INSERT INTO audit_log(changed,actor,table_name,row_id,operation,before_json,after_json) VALUES (?,?,?,?,?,?,?)",
                   (time.time(),actor,table,row_id,action,json.dumps(before) if before else None,json.dumps(after) if after else None))

    def mutate_record(self, table: str, operation: str, values: dict, row_id: int | None, actor: str) -> dict:
        if table not in ("schedules","manual_runs","ph_tests","quality_ranges"):
            raise ValueError("Invalid table")
        allowed={
            "schedules": ("equipment","effective","start_time","duration_min","stage_min","cadence","interval_days","anchor_date","weekdays","notes"),
            "manual_runs": ("equipment","started","duration_min","notes"),
            "ph_tests": ("sampled","location","ph","notes"),
            "quality_ranges": ("started","ended","effect","reason","notes"),
        }[table]
        if operation not in ("create","update","delete"):
            raise ValueError("Invalid operation")
        with self.connect() as db:
            before=None
            if operation != "create":
                if row_id is None:
                    raise ValueError("Record ID required")
                row=db.execute(f"SELECT * FROM {table} WHERE id=?",(row_id,)).fetchone()
                if row is None:
                    raise ValueError("Record no longer exists; refresh the dashboard")
                before=dict(row)
            if operation == "delete":
                db.execute(f"DELETE FROM {table} WHERE id=?",(row_id,))
                after=None
            else:
                after={key:values[key] for key in allowed if key in values}
                if any(key not in after for key in allowed if key not in ("notes","anchor_date","weekdays","interval_days")):
                    raise ValueError("Missing required fields")
                after.setdefault("notes", "")
                if table=="quality_ranges":
                    if after["ended"] <= after["started"]:
                        raise ValueError("Exclusion end must be after start")
                    if after["effect"] not in ("exclude", "review") or after["reason"] not in ("commissioning", "unverified", "maintenance", "other"):
                        raise ValueError("Invalid quality classification")
                if table=="schedules":
                    after.setdefault("anchor_date",None)
                    after.setdefault("weekdays", "")
                    after.setdefault("interval_days",1)
                after["updated"]=time.time()
                if operation=="create":
                    after["created"]=after["updated"]
                    keys=list(after)
                    placeholders=','.join('?' for _ in keys)
                    cur=db.execute(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({placeholders})",tuple(after.values()))
                    row_id=cur.lastrowid
                else:
                    # Reject stale concurrent edits rather than silently overwrite a newer entry.
                    if "updated" in values:
                        updated=float(values["updated"])
                        if not math.isfinite(updated) or abs(updated-float(before["updated"]))>.00001:
                            raise ValueError("This record changed elsewhere; refresh before editing")
                    db.execute(f"UPDATE {table} SET {','.join(f'{key}=?' for key in after)} WHERE id=?", (*after.values(),row_id))
                after=dict(db.execute(f"SELECT * FROM {table} WHERE id=?",(row_id,)).fetchone())
            self._audit(db,actor,table,row_id,operation,before,after)
            return {"ok":True,"id":row_id}

    def list_records(self, table: str, start: float | None = None, end: float | None = None, limit: int = 2000) -> list[dict]:
        if table not in ("pump_runs","schedules","manual_runs","ph_tests","quality_ranges","gaps","audit_log"):
            raise ValueError("Invalid table")
        time_col={"pump_runs":"stopped","schedules":"effective","manual_runs":"started","ph_tests":"sampled","quality_ranges":"started","gaps":"ts","audit_log":"changed"}[table]
        where=[];params=[]
        if start is not None:
            where.append(f"{time_col} >= ?");params.append(start)
        if end is not None:
            where.append(f"{time_col} < ?");params.append(end)
        stmt=f"SELECT * FROM {table}"+(" WHERE "+" AND ".join(where) if where else "")+f" ORDER BY {time_col} DESC LIMIT ?"
        with self.connect() as db:
            return [dict(r) for r in db.execute(stmt,(*params,min(limit,20000)))]

    def all_runs(self, start: float, end: float) -> list[dict]:
        """Complete range for server-side analysis (not limited by graph point count)."""
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                """SELECT r.*, CASE WHEN EXISTS (
                  SELECT 1 FROM quality_ranges q WHERE q.effect='exclude'
                  AND q.started < r.stopped AND q.ended > r.started
                ) THEN 'excluded' ELSE 'usable' END AS quality
                FROM pump_runs r WHERE r.stopped>? AND r.started<? ORDER BY r.started""",(start,end))]

    def count(self) -> dict:
        with self.connect() as db:
            return {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                    for name in ("pump_runs","pump_edges","quality_ranges","schedules","manual_runs","ph_tests","gaps")}

    def run_metrics(self, periods: dict[str, tuple[float,float]]) -> dict:
        out={}
        with self.connect() as db:
            for key,(start,end) in periods.items():
                rows=[r[0] for r in db.execute("""SELECT r.seconds FROM pump_runs r
                    WHERE r.stopped>=? AND r.stopped<? AND NOT EXISTS (
                      SELECT 1 FROM quality_ranges q WHERE q.effect='exclude'
                      AND q.started < r.stopped AND q.ended > r.started)
                    ORDER BY r.seconds""",(start,end))]
                excluded=db.execute("""SELECT COUNT(*) FROM pump_runs r
                    WHERE r.stopped>=? AND r.stopped<? AND EXISTS (
                      SELECT 1 FROM quality_ranges q WHERE q.effect='exclude'
                      AND q.started < r.stopped AND q.ended > r.started)""",(start,end)).fetchone()[0]
                n=len(rows)
                def percentile(p):
                    if not n:return None
                    idx=(n-1)*p;lo=int(idx);hi=min(n-1,lo+1)
                    return round(rows[lo]+(rows[hi]-rows[lo])*(idx-lo),1)
                out[key]={"count":n,"excluded_count":excluded,"total_seconds":round(sum(rows),1),"mean_seconds":round(sum(rows)/n,1) if n else None,
                          "median_seconds":percentile(.5),"p90_seconds":percentile(.9),"max_seconds":round(rows[-1],1) if n else None}
        return out

    def integrity(self) -> dict:
        with self.connect() as db:
            result=db.execute("PRAGMA quick_check").fetchone()[0]
            first,latest=db.execute("""SELECT MIN(r.stopped),MAX(r.stopped) FROM pump_runs r
                WHERE NOT EXISTS (SELECT 1 FROM quality_ranges q WHERE q.effect='exclude'
                    AND q.started < r.stopped AND q.ended > r.started)""").fetchone()
            return {"ok":result=="ok","result":result,"earliest_run":first,"latest_run":latest,"file_bytes":self.path.stat().st_size}

    def snapshot(self, destination: str) -> dict:
        """SQLite online backup is consistent even while WAL is enabled."""
        path=Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError("Backup path exists")
        with self.connect() as src:
            dest=sqlite3.connect(path)
            try:
                src.backup(dest)
                dest.commit()
            finally:
                dest.close()
        return {"path":str(path),"size":path.stat().st_size}

    def export_zip(self) -> bytes:
        """Portable CSV export with raw records, audit, and metadata."""
        out=io.BytesIO()
        with self.connect() as db, zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
            for table in TABLES_EXPORT:
                rows=db.execute(f"SELECT * FROM {table}")
                columns=[col[0] for col in rows.description]
                tmp=io.StringIO();w=csv.writer(tmp);w.writerow(columns)
                w.writerows([list(row) for row in rows])
                z.writestr(f"{table}.csv",tmp.getvalue())
            z.writestr("README.txt","Water Treatment Monitor export. UTC values are Unix timestamps (seconds). Contains all pump edges, runs, schedules, manual entries, pH tests, audit and metadata.\n")
        return out.getvalue()
