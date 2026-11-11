"""Native HA read-only statistical entities from durable archive."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
from .const import DOMAIN,SIGNAL_UPDATE
from .analysis import periods_now, coverage_for_periods


async def async_setup_entry(hass,entry,async_add_entities):
    mgr=hass.data[DOMAIN]["manager"]
    sensors=[WaterStat(mgr,p,kind) for p in ("day","week","month","year") for kind in ("count","runtime","average")]
    sensors.append(WaterHealth(mgr))
    async_add_entities(sensors)


class WaterStat(SensorEntity):
    _attr_has_entity_name=False
    _attr_should_poll=False
    def __init__(self,manager,period,kind):
        self.manager=manager;self.period=period;self.kind=kind
        self._attr_unique_id=f"wtm_{period}_{kind}"
        self._attr_name=f"Water Treatment {period.title()} {kind.title()}"
        self._attr_icon="mdi:timer-outline" if kind!="count" else "mdi:counter"
        if kind!="count":
            self._attr_native_unit_of_measurement="s"
            self._attr_device_class=SensorDeviceClass.DURATION
        self._attr_native_value=None
        self._attr_extra_state_attributes={}

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass,SIGNAL_UPDATE,self._refresh_scheduled))
        await self._refresh()

    @callback
    def _refresh_scheduled(self):
        """Dispatcher listener runs on the Home Assistant event loop."""
        self.hass.async_create_task(self._refresh())

    async def _refresh(self):
        period=periods_now(dt_util.utcnow(),self.manager.hass.config.time_zone)
        metrics=await self.hass.async_add_executor_job(self.manager.archive.run_metrics,{self.period:period[self.period]})
        meta=await self.hass.async_add_executor_job(self.manager.archive.metadata)
        gaps=await self.hass.async_add_executor_job(self.manager.archive.list_records,"gaps",period[self.period][0],period[self.period][1],1000)
        quality=await self.hass.async_add_executor_job(self.manager.archive.list_records,"quality_ranges",None,None,5000)
        source=self.hass.states.get(self.manager.pump_entity)
        cover=coverage_for_periods({self.period:period[self.period]},float(meta["coverage_from"]) if "coverage_from" in meta else None,
                                    gaps, bool(source and source.state in ("on","off")),quality)[self.period]
        stat=metrics[self.period]
        if self.kind=="count": self._attr_native_value=stat["count"] if cover["status"]!="no_archive" else None
        elif self.kind=="runtime": self._attr_native_value=stat["total_seconds"] if cover["status"]!="no_archive" else None
        else: self._attr_native_value=stat["mean_seconds"]
        self._attr_extra_state_attributes={"coverage":cover["status"],"coverage_from":cover["coverage_from"],"n_usable":stat["count"],"n_excluded":stat["excluded_count"],"period_end":period[self.period][1]}
        self.async_write_ha_state()


class WaterHealth(SensorEntity):
    _attr_has_entity_name=False
    _attr_should_poll=False
    _attr_name="Water Treatment Archive Health"
    _attr_unique_id="wtm_archive_health"
    _attr_icon="mdi:database-check"
    def __init__(self,manager):
        self.manager=manager;self._attr_native_value="loading"

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass,SIGNAL_UPDATE,self._refresh_scheduled))
        await self._refresh()

    @callback
    def _refresh_scheduled(self):
        """Dispatcher listener runs on the Home Assistant event loop."""
        self.hass.async_create_task(self._refresh())

    async def _refresh(self):
        info=await self.hass.async_add_executor_job(self.manager.archive.integrity)
        self._attr_native_value="healthy" if info["ok"] else "error"
        self._attr_extra_state_attributes={**info,"backfill":self.manager.backfill_state,"last_error":self.manager.last_error}
        self.async_write_ha_state()
