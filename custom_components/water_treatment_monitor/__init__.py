"""Water Treatment Monitor, observational only. No actuator services."""
from __future__ import annotations

import asyncio
import logging
import datetime
import time
from datetime import timedelta
from functools import partial
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.recorder import get_instance, history
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, DB_FILENAME, SIGNAL_UPDATE
from .db import Archive
from . import websocket

_LOGGER=logging.getLogger(__name__)
PLATFORMS=["sensor"]


class Monitor:
    def __init__(self,hass:HomeAssistant,entry:ConfigEntry) -> None:
        self.hass=hass
        self.entry=entry
        self.pump_entity=entry.data["pump_entity"]
        self.archive=Archive(hass.config.path(DB_FILENAME))
        self.write_lock=asyncio.Lock()
        self.last_error=None
        self.backfill_state="not_started"
        self.last_backfill=None
        self.health_data={}

    async def initialize(self):
        await self.hass.async_add_executor_job(self.archive.initialize)
        await self.hass.async_add_executor_job(self.archive.bind_source,self.pump_entity)
        await self.hass.async_add_executor_job(self.archive.initialize_import_floor,self.pump_entity,self.entry.data.get("import_start"))
        await self.hass.async_add_executor_job(self.archive.add_gap,time.time(),"HA integration setup; telemetry continuity not independently verified")
        self.health_data=await self.hass.async_add_executor_job(self.archive.integrity)

    @callback
    def on_event(self,event) -> None:
        if event.data.get("entity_id")!=self.pump_entity:
            return
        before=event.data.get("old_state")
        after=event.data.get("new_state")
        if after is None or (before and before.state==after.state):
            return
        state=after.state
        if state not in ("on","off","unknown","unavailable"):
            return
        reliable=bool(state=="on" and before and before.state=="off")
        # A background task is scoped to the config entry and never blocks HA event loop.
        self.entry.async_create_background_task(self.hass,self.record_edge(after.last_changed.timestamp(),state,reliable),"water_treatment_record_edge")

    async def record_edge(self,when:float,state:str,reliable:bool):
        try:
            async with self.write_lock:
                await self.hass.async_add_executor_job(self.archive.add_live_edge,when,state,"live",reliable)
            async_dispatcher_send(self.hass,SIGNAL_UPDATE)
        except Exception:
            _LOGGER.exception("Failed to persist pump edge")
            self.last_error="Pump event write failed. Check HA logs and archive health."

    async def maybe_weekly_snapshot(self):
        """Crash-consistent weekly local rollback points (last 12); not off-device backup."""
        try:
            async with self.write_lock:
                meta=await self.hass.async_add_executor_job(self.archive.metadata)
                if time.time()-float(meta.get("last_auto_snapshot_at",0))<7*86400:
                    return
                folder=Path(self.hass.config.path("water_treatment_snapshots"))
                name="auto-"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".sqlite3"
                await self.hass.async_add_executor_job(self.archive.snapshot,str(folder/name))
                await self.hass.async_add_executor_job(self.archive.set_meta,"last_auto_snapshot_at",str(time.time()))
                # Only auto-* snapshots are managed. Manual snapshots are never removed.
                def prune():
                    for old in sorted(folder.glob("auto-*.sqlite3"))[:-12]:old.unlink()
                await self.hass.async_add_executor_job(prune)
        except Exception:
            _LOGGER.exception("Failed to create weekly Water Treatment archive snapshot")
            self.last_error="Automatic local archive snapshot failed; check HA logs"

    async def backfill(self,days:int=10) -> dict:
        if not 1<=days<=31:
            raise ValueError("Backfill lookback must be 1–31 days; Recorder may retain less")
        self.backfill_state="running"
        until=dt_util.utcnow()
        since=until-timedelta(days=days)
        try:
            # Official Recorder executor, not direct SQL access into HA's database.
            instance=get_instance(self.hass)
            rows_map=await instance.async_add_executor_job(partial(
                history.get_significant_states,self.hass,since,until,
                entity_ids=[self.pump_entity],include_start_time_state=True,
                significant_changes_only=True,minimal_response=False,
                no_attributes=True))
            rows=[]
            previous=None
            for index,record in enumerate(rows_map.get(self.pump_entity,[])):
                state=record.state
                when=record.last_changed.timestamp()
                # Source state before the query start is a snapshot, never a transition.
                anchor = (index==0)
                if anchor and when<since.timestamp():when=since.timestamp()
                if state==previous:
                    continue
                previous=state
                rows.append((when,state,anchor))
            async with self.write_lock:
                result=await self.hass.async_add_executor_job(self.archive.import_recorder,rows,since.timestamp(),until.timestamp())
            result["history_state_rows"]=len(rows)
            self.backfill_state="finished"; self.last_backfill=result
            self.health_data=await self.hass.async_add_executor_job(self.archive.integrity)
            async_dispatcher_send(self.hass,SIGNAL_UPDATE)
            return result
        except Exception as exc:
            self.backfill_state="failed"
            self.last_error=f"Recorder backfill failed: {exc}"
            _LOGGER.exception("Recorder backfill failed")
            raise


async def async_setup(hass:HomeAssistant,config:dict)->bool:
    hass.data.setdefault(DOMAIN,{"manager":None})
    frontend=Path(__file__).parent / "frontend" / "water-treatment-card.js"
    await hass.http.async_register_static_paths([
        StaticPathConfig("/water_treatment_monitor/water-treatment-card.js",str(frontend),False)
    ])
    websocket.register(hass)
    return True


async def async_setup_entry(hass:HomeAssistant,entry:ConfigEntry)->bool:
    manager=Monitor(hass,entry)
    await manager.initialize()
    hass.data[DOMAIN]["manager"]=manager
    unsub=hass.bus.async_listen(EVENT_STATE_CHANGED,manager.on_event)
    entry.async_on_unload(unsub)
    async def refresh(_now):
        async_dispatcher_send(hass,SIGNAL_UPDATE)
    entry.async_on_unload(async_track_time_interval(hass,refresh,timedelta(minutes=2)))
    async def weekly_check(_now):
        await manager.maybe_weekly_snapshot()
    entry.async_on_unload(async_track_time_interval(hass,weekly_check,timedelta(hours=24)))
    await hass.config_entries.async_forward_entry_setups(entry,PLATFORMS)
    # Listener registered before backfill so transition edges are never missed.
    async def bootstrap():
        try:
            await manager.backfill()
        finally:
            await manager.maybe_weekly_snapshot()
    entry.async_create_background_task(hass,bootstrap(),"water_treatment_initial_backfill")
    return True


async def async_unload_entry(hass:HomeAssistant,entry:ConfigEntry)->bool:
    if not await hass.config_entries.async_unload_platforms(entry,PLATFORMS):
        return False
    entry.async_unload()
    manager=hass.data.get(DOMAIN,{}).get("manager")
    if manager:
        try:
            await hass.async_add_executor_job(manager.archive.add_gap,time.time(),"Integration unloaded")
        except Exception:
            _LOGGER.exception("Unable to record integration unload gap")
    hass.data[DOMAIN]["manager"]=None
    return True
