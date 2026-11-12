"""Repairs flow: hand the expiry warning straight to the reauth dialog."""
from __future__ import annotations

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.data_entry_flow import FlowType

from .const import DOMAIN


async def async_create_fix_flow(hass, issue_id, data):
    """Called by the repairs manager when the user clicks 'fix'."""
    return AupuTokenExpiryRepairFlow()


class AupuTokenExpiryRepairFlow(RepairsFlow):
    """Start a reauth flow for the entry behind the issue."""

    async def async_step_init(self, user_input=None):
        entry_id = (self.data or {}).get("entry_id")
        entry = self.hass.config_entries.async_get_entry(entry_id) if entry_id else None
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        result = await self.hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        return self.async_abort(
            reason="reauth_started",
            next_flow=(FlowType.CONFIG_FLOW, result["flow_id"]),
        )