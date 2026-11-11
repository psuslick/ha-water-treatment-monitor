"""Local, permission-checked frontend API. No physical device-control commands."""
from __future__ import annotations

import base64
import hashlib
import logging
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .analysis import analyze, periods_now, coverage_for_periods
from .const import DOMAIN, SIGNAL_UPDATE
from .db import timestamp

_LOGGER=logging.getLogger(__name__)
TYPES=("schedules","manual_runs","ph_tests","quality_ranges")


def manager(hass):
    x=hass.data.get(DOMAIN,{}).get("manager")
    if x is None:
        raise ValueError("Water Treatment Monitor is not configured")
    return x


def _validate(table:str,values:dict) -> dict:
    """Whitelisted fields, strong numeric/date bounds, no implicit timezone parsing."""
    x={}
    if table=="schedules":
        x["equipment"]=str(values["equipment"]).lower()
        if x["equipment"] not in ("softener","neutralizer"):raise ValueError("Invalid equipment")
        x["effective"]=timestamp(values["effective"])
        if x["effective"]>time.time()+10*365*86400:raise ValueError("Effective date too far in future")
        x["start_time"]=str(values["start_time"])
        try:
            hours,mins=map(int,x["start_time"].split(":"))
            if not 0<=hours<=23 or not 0<=mins<=59 or len(x["start_time"])!=5: raise ValueError()
        except Exception as e:raise ValueError("Start time must be HH:MM") from e
        x["duration_min"]=float(values["duration_min"])
        x["stage_min"]=float(values.get("stage_min",0))
        if not 0<x["duration_min"]<=480 or not 0<=x["stage_min"]<=x["duration_min"]:raise ValueError("Invalid durations")
        x["cadence"]=str(values["cadence"])
        if x["cadence"] not in ("daily","interval","weekdays","demand","unknown"):raise ValueError("Invalid cadence")
        x["interval_days"]=int(values.get("interval_days",1))
        if x["cadence"]=="interval" and not 1<=x["interval_days"]<=365:raise ValueError("Interval must be 1–365 days")
        x["anchor_date"]=values.get("anchor_date") or None
        if x["cadence"]=="interval":
            if not x["anchor_date"]:raise ValueError("Interval needs a verified anchor date")
            datetime.fromisoformat(x["anchor_date"])
        x["weekdays"]=str(values.get("weekdays", ""))
        if x["cadence"]=="weekdays":
            try: ds=[int(d) for d in x["weekdays"].split(",")]
            except (ValueError,TypeError):raise ValueError("Weekdays must be 0,1,...6")
            if not ds or any(d<0 or d>6 for d in ds):raise ValueError("Weekdays must be 0 through 6")
    elif table=="manual_runs":
        x["equipment"]=str(values["equipment"]).lower()
        if x["equipment"] not in ("softener","neutralizer"):raise ValueError("Invalid equipment")
        x["started"]=timestamp(values["started"])
        x["duration_min"]=float(values["duration_min"])
        if not 0<x["duration_min"]<=480:raise ValueError("Invalid duration")
    elif table=="quality_ranges":
        x["started"]=timestamp(values["started"])
        x["ended"]=timestamp(values["ended"])
        if x["ended"] <= x["started"]:raise ValueError("Quality range must end after it begins")
        x["effect"]=str(values["effect"])
        x["reason"]=str(values["reason"])
        if x["effect"] not in ("exclude","review") or x["reason"] not in ("commissioning","unverified","maintenance","other"):
            raise ValueError("Invalid quality annotation")
    elif table=="ph_tests":
        x["sampled"]=timestamp(values["sampled"])
        x["location"]=str(values["location"]).lower()
        if x["location"] not in ("raw","treated"):raise ValueError("Invalid pH location")
        x["ph"]=round(float(values["ph"]),2)
        if not 0<=x["ph"]<=14:raise ValueError("pH must be 0 to 14")
    else:raise ValueError("Unknown record type")
    for key in ("duration_min", "stage_min", "ph"):
        if key in x and not math.isfinite(x[key]):
            raise ValueError(f"{key} must be a finite number")
    x["notes"]=str(values.get("notes", ""))[:400]
    return x


@websocket_api.websocket_command({vol.Required("type"):"water_treatment_monitor/get",
    vol.Optional("start"):vol.Coerce(float),vol.Optional("end"):vol.Coerce(float)})
@websocket_api.async_response
async def ws_get(hass,connection,msg):
    try:
        m=manager(hass)
        now=dt_util.utcnow()
        start=float(msg.get("start",(now-timedelta(days=7)).timestamp()))
        end=float(msg.get("end",now.timestamp()+1))
        if start>=end or end-start>366*6*86400 or end>now.timestamp()+86400*366:
            raise ValueError("Invalid range; maximum six years")
        current=m.hass.states.get(m.pump_entity)
        state=current.state if current else "unavailable"
        periods=periods_now(now,hass.config.time_zone)
        # Work with real SQLite queries in the executor; never block HA's event loop.
        jobs=[
            ("runs",m.archive.all_runs,(start-86400,end)),
            ("schedules",m.archive.list_records,("schedules",None,None,5000)),
            ("quality_ranges",m.archive.list_records,("quality_ranges",None,None,5000)),
            ("manual",m.archive.list_records,("manual_runs",start-86400,end,10000)),
            ("tests",m.archive.list_records,("ph_tests",start,end,10000)),
            ("metrics",m.archive.run_metrics,(periods,)),
            ("metadata",m.archive.metadata,()),
            ("counts",m.archive.count,()),
            ("health",m.archive.integrity,()),
            ("gaps",m.archive.list_records,("gaps",min(start,*[a for a,b in periods.values()]),None,20000)),
        ]
        # DB calls are each off-thread; ordered reads give a near-consistent view.
        vals={}
        for name,fn,args in jobs:
            vals[name]=await hass.async_add_executor_job(fn,*args)
        runs=vals["runs"]
        first=float(vals["metadata"]["coverage_from"]) if "coverage_from" in vals["metadata"] else None
        analysis=await hass.async_add_executor_job(analyze,runs,vals["schedules"],vals["manual"],
                                                   start,end,hass.config.time_zone,vals["gaps"],vals["quality_ranges"],first)
        coverage=coverage_for_periods(periods,first,vals["gaps"],state in ("on","off"),vals["quality_ranges"])
        connection.send_result(msg["id"],{
            "source_entity":m.pump_entity,"pump_state":state,"pump_last_changed":current.last_changed.timestamp() if current else None,
            "timezone":hass.config.time_zone,"now":now.timestamp(),"selected":{"start":start,"end":end},
            "analysis":analysis,"period_metrics":vals["metrics"],"coverage":coverage,
            "schedules":list(reversed(vals["schedules"])),
            "quality_ranges":list(reversed(vals["quality_ranges"])),"manual":list(reversed(vals["manual"])),"tests":list(reversed(vals["tests"])),
            "archive":{"counts":vals["counts"],"health":vals["health"],"coverage_from":first,
                "import_floor":float(vals["metadata"]["import_floor"]) if "import_floor" in vals["metadata"] else None,
                "backfill":m.backfill_state,"last_backfill":m.last_backfill,"error":m.last_error,"last_backup":vals["metadata"].get("last_backup")},
        })
    except Exception as exc:
        _LOGGER.exception("Water Treatment Monitor data request failed")
        connection.send_error(msg["id"],"wtm_failed",str(exc))


@websocket_api.websocket_command({vol.Required("type"):"water_treatment_monitor/mutate",
    vol.Required("table"):vol.In(TYPES),vol.Required("operation"):vol.In(("create","update","delete")),
    vol.Optional("record_id"):vol.Coerce(int),vol.Optional("values",default={}):dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_mutate(hass,connection,msg):
    try:
        m=manager(hass); table=msg["table"];operation=msg["operation"]
        values=_validate(table,msg["values"]) if operation!="delete" else {}
        if "updated" in msg["values"]:values["updated"]=msg["values"]["updated"]
        async with m.write_lock:
            response=await hass.async_add_executor_job(m.archive.mutate_record,table,operation,values,msg.get("record_id"),connection.user.id)
        async_dispatcher_send(hass,SIGNAL_UPDATE)
        connection.send_result(msg["id"],response)
    except Exception as exc:
        connection.send_error(msg["id"],"wtm_invalid",str(exc))


@websocket_api.websocket_command({vol.Required("type"):"water_treatment_monitor/backfill",
    vol.Optional("days",default=10):vol.All(vol.Coerce(int),vol.Range(min=1,max=31))})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_backfill(hass,connection,msg):
    try:
        data=await manager(hass).backfill(msg["days"])
        connection.send_result(msg["id"],data)
    except Exception as exc:
        connection.send_error(msg["id"],"wtm_backfill_failed",str(exc))


@websocket_api.websocket_command({vol.Required("type"):"water_treatment_monitor/backup"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_backup(hass,connection,msg):
    try:
        m=manager(hass)
        filename="water-treatment-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".sqlite3"
        target=hass.config.path("water_treatment_snapshots",filename)
        async with m.write_lock:
            result=await hass.async_add_executor_job(m.archive.snapshot,target)
            await hass.async_add_executor_job(m.archive.set_meta,"last_backup",datetime.now(timezone.utc).isoformat())
        connection.send_result(msg["id"],result)
    except Exception as exc:
        connection.send_error(msg["id"],"wtm_backup_failed",str(exc))


@websocket_api.websocket_command({vol.Required("type"):"water_treatment_monitor/export"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_export(hass,connection,msg):
    try:
        m=manager(hass)
        content=await hass.async_add_executor_job(m.archive.export_zip)
        if len(content)>16*1024*1024:
            raise ValueError("Export exceeds 16 MB. Use Backup Now for SQLite snapshot and retrieve via HA File editor/SSH")
        connection.send_result(msg["id"],{"filename":"water-treatment-export-"+datetime.now(timezone.utc).strftime("%Y%m%d")+".zip",
            "sha256":hashlib.sha256(content).hexdigest(),"base64":base64.b64encode(content).decode("ascii")})
    except Exception as exc:
        connection.send_error(msg["id"],"wtm_export_failed",str(exc))


def register(hass):
    for fn in (ws_get,ws_mutate,ws_backfill,ws_backup,ws_export):
        websocket_api.async_register_command(hass,fn)
