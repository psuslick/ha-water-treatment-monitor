"""Water Treatment Monitor onboarding: only observes an existing sensor."""
from __future__ import annotations

import time

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN
from .db import timestamp


class WaterTreatmentMonitorFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Offer a native GUI bridge for existing pH entry/button helpers."""
        return WaterTreatmentMonitorOptionsFlow()

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("water_treatment_monitor_primary")
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            start = str(user_input.get("import_start", "")).strip()
            if start:
                try:
                    if timestamp(start) > time.time() + 60:
                        raise ValueError("Import start cannot be in the future")
                except (ValueError, TypeError):
                    errors["import_start"] = "invalid_timestamp"
            if not errors:
                return self.async_create_entry(
                    title="Water Treatment Monitor",
                    data={"pump_entity": user_input["pump_entity"], "import_start": start},
                )
        supplied = user_input or {}
        schema = vol.Schema({
            vol.Required("pump_entity", default=supplied.get("pump_entity", "")):
                selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor")),
            vol.Optional("import_start", default=supplied.get("import_start", "")):
                selector.TextSelector(selector.TextSelectorConfig(multiline=False)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class WaterTreatmentMonitorOptionsFlow(OptionsFlowWithReload):
    """Opt-in legacy HA pH helper capture, without hardcoded entity IDs."""

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            button = user_input.get("ph_button")
            number = user_input.get("ph_value")
            if bool(button) != bool(number):
                errors["base"] = "both_ph_helpers_required"
            else:
                return self.async_create_entry(data={
                    "ph_button": button or "",
                    "ph_value": number or "",
                })
        current = self.config_entry.options
        fields = {}
        button_field = vol.Optional("ph_button", **({"default": current["ph_button"]} if current.get("ph_button") else {}))
        value_field = vol.Optional("ph_value", **({"default": current["ph_value"]} if current.get("ph_value") else {}))
        fields[button_field] = selector.EntitySelector(selector.EntitySelectorConfig(domain="input_button"))
        fields[value_field] = selector.EntitySelector(selector.EntitySelectorConfig(domain="input_number"))
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields), errors=errors)
