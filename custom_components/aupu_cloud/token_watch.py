"""Warn before the account token expires.

The AUPU auth server exposes no refresh-token contract (verified: every
candidate refresh endpoint answers 404), so a REST entry stops working once
the 10-day JWT expires. This module only surfaces that deadline in advance: it
never mints, extends or forges a token.
"""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_ACCESS_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

ISSUE_TOKEN_EXPIRING = "token_expiring"
WARN_BEFORE = timedelta(days=3)
RECHECK_EVERY = timedelta(hours=6)


def token_expiry(token: str) -> datetime | None:
    """Return the ``exp`` claim of a JWT, or None when it cannot be read."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        exp = claims.get("exp")
        return datetime.fromtimestamp(float(exp), tz=timezone.utc) if exp else None
    except (IndexError, TypeError, ValueError, AttributeError):
        return None


def _issue_id(entry) -> str:
    return f"{entry.entry_id}_{ISSUE_TOKEN_EXPIRING}"


@callback
def async_check_token(hass: HomeAssistant, entry) -> None:
    """Create, refresh or clear the expiry issue for one config entry."""
    issue_id = _issue_id(entry)
    token = entry.data.get(CONF_ACCESS_TOKEN)
    expires = token_expiry(token) if isinstance(token, str) else None

    if expires is None:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    left = expires - datetime.now(timezone.utc)
    if left <= timedelta(0):
        # Core already owns the "reauthenticate" issue once calls start failing.
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    if left > WARN_BEFORE:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    days = left.days + (1 if left.seconds or left.microseconds else 0)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_TOKEN_EXPIRING,
        translation_placeholders={
            "days": str(days),
            "date": expires.astimezone().strftime("%Y-%m-%d %H:%M"),
            "title": entry.title,
        },
        data={"entry_id": entry.entry_id},
    )


def async_setup_token_watch(hass: HomeAssistant, entry) -> None:
    """Check now and every few hours; unload with the config entry."""

    @callback
    def _tick(_now=None) -> None:
        async_check_token(hass, entry)

    entry.async_on_unload(async_track_time_interval(hass, _tick, RECHECK_EVERY))
    _tick()