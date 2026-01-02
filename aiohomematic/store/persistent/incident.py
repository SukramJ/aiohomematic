# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Incident store for persistent diagnostic snapshots.

This module provides IncidentStore which persists diagnostic incidents
for post-mortem analysis. Unlike Journal events which expire after TTL,
incidents are preserved indefinitely (up to max count/age) and survive restarts.

Overview
--------
The IncidentStore captures significant events like:
- PingPong mismatch threshold crossings
- Connection losses and restorations
- RPC errors and timeouts
- Device unavailability

Each incident includes:
- Timestamp and severity
- Interface context
- Journal excerpt at time of incident
- Additional debugging context

Persistence Strategy
--------------------
- Save-on-incident: Automatically saves after each recorded incident
- Load-on-demand: Only loads from disk when diagnostics are requested
- Time-based cleanup: Old incidents are removed on load (default: 7 days)
- Size-based limit: Maximum number of incidents (default: 50)

Public API
----------
- IncidentStore: Persistent incident storage with size/time limits
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, Final
import uuid

from aiohomematic.const import INCIDENT_STORE_MAX_INCIDENTS
from aiohomematic.store.persistent.base import BasePersistentCache
from aiohomematic.store.types import IncidentSeverity, IncidentSnapshot, IncidentType

if TYPE_CHECKING:
    from aiohomematic.interfaces import ConfigProviderProtocol
    from aiohomematic.store.storage import StorageProtocol
    from aiohomematic.store.types import PingPongJournal

_LOGGER: Final = logging.getLogger(__name__)

# Default retention period for incidents
DEFAULT_MAX_AGE_DAYS: Final = 7


class IncidentStore(BasePersistentCache):
    """
    Persistent store for diagnostic incidents.

    Stores incident snapshots that survive application restarts.
    Uses a "save-on-incident, load-on-demand" strategy:

    - When an incident is recorded, it's automatically persisted
    - Historical incidents are only loaded when diagnostics are requested
    - Old incidents (beyond max_age_days) are cleaned up on load

    Features:
        - Persistent storage via StorageProtocol
        - Automatic save after each incident (debounced)
        - Lazy loading on first diagnostics request
        - Time-based cleanup (default: 7 days)
        - Size-based limiting (default: 50 incidents)
        - Journal excerpt capture at incident time

    """

    __slots__ = ("_incidents", "_loaded", "_max_age_days", "_max_incidents")

    def __init__(
        self,
        *,
        storage: StorageProtocol,
        config_provider: ConfigProviderProtocol,
        max_incidents: int = INCIDENT_STORE_MAX_INCIDENTS,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ) -> None:
        """
        Initialize the incident store.

        Args:
            storage: Storage instance for persistence.
            config_provider: Provider for configuration access.
            max_incidents: Maximum number of incidents to store (default: 50).
            max_age_days: Maximum age of incidents in days (default: 7).

        """
        super().__init__(storage=storage, config_provider=config_provider)
        self._max_incidents: Final = max_incidents
        self._max_age_days: Final = max_age_days
        self._incidents: list[IncidentSnapshot] = []
        self._loaded: bool = False

    @property
    def incident_count(self) -> int:
        """Return the number of stored incidents (in-memory only)."""
        return len(self._incidents)

    @property
    def incidents(self) -> list[IncidentSnapshot]:
        """Return the list of stored incidents (in-memory only)."""
        return list(self._incidents)

    @property
    def is_loaded(self) -> bool:
        """Return True if historical incidents have been loaded from disk."""
        return self._loaded

    def clear_incidents(self) -> None:
        """Clear all incidents from memory (does not affect persistence)."""
        self._incidents.clear()
        self._content["incidents"] = []

    async def get_all_incidents(self) -> list[IncidentSnapshot]:
        """
        Return all incidents including historical ones from disk.

        Loads from disk on first call.
        """
        await self._ensure_loaded()
        return list(self._incidents)

    async def get_diagnostics(self) -> dict[str, Any]:
        """
        Return diagnostics data for HA Diagnostics.

        Loads historical incidents from disk on first call.
        """
        await self._ensure_loaded()
        return {
            "total_incidents": len(self._incidents),
            "max_incidents": self._max_incidents,
            "max_age_days": self._max_age_days,
            "incidents_by_type": self._count_by_type(),
            "incidents_by_severity": self._count_by_severity(),
            "recent_incidents": [i.to_dict() for i in self._incidents[-10:]],
        }

    async def get_incidents_by_interface(self, *, interface_id: str) -> list[IncidentSnapshot]:
        """
        Return incidents for a specific interface.

        Loads historical incidents from disk on first call.
        """
        await self._ensure_loaded()
        return [i for i in self._incidents if i.interface_id == interface_id]

    async def get_incidents_by_type(self, *, incident_type: IncidentType) -> list[IncidentSnapshot]:
        """
        Return incidents of a specific type.

        Loads historical incidents from disk on first call.
        """
        await self._ensure_loaded()
        return [i for i in self._incidents if i.incident_type == incident_type]

    async def get_recent_incidents(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """
        Return recent incidents as list of dicts.

        Loads historical incidents from disk on first call.
        """
        await self._ensure_loaded()
        return [i.to_dict() for i in self._incidents[-limit:]]

    async def record_incident(
        self,
        *,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        message: str,
        interface_id: str | None = None,
        context: dict[str, Any] | None = None,
        journal: PingPongJournal | None = None,
    ) -> IncidentSnapshot:
        """
        Record a new incident and persist it.

        The incident is saved to disk automatically (debounced).
        Does NOT load historical incidents - only adds to current session.

        Args:
            incident_type: Type of incident.
            severity: Severity level.
            message: Human-readable description.
            interface_id: Interface where incident occurred (optional).
            context: Additional debugging context (optional).
            journal: Journal to extract excerpt from (optional).

        Returns:
            The created IncidentSnapshot.

        """
        # Generate unique incident ID
        incident_id = f"{incident_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Extract journal excerpt if available
        journal_excerpt: list[dict[str, Any]] = []
        if journal is not None:
            journal_excerpt = journal.get_recent_events(limit=20)

        incident = IncidentSnapshot(
            incident_id=incident_id,
            timestamp_iso=datetime.now().isoformat(timespec="milliseconds"),
            incident_type=incident_type,
            severity=severity,
            interface_id=interface_id,
            message=message,
            context=context or {},
            journal_excerpt=journal_excerpt,
        )

        self._incidents.append(incident)

        # Enforce size limit
        while len(self._incidents) > self._max_incidents:
            evicted = self._incidents.pop(0)
            _LOGGER.debug(
                "INCIDENT STORE: Evicted oldest incident %s to maintain limit %d",
                evicted.incident_id,
                self._max_incidents,
            )

        # Update content for persistence
        self._content["incidents"] = [i.to_dict() for i in self._incidents]

        _LOGGER.info(  # i18n-log: ignore
            "INCIDENT STORE: Recorded %s incident: %s (interface: %s)",
            severity.value.upper(),
            message,
            interface_id or "N/A",
        )

        # Auto-save with debouncing (2 second delay to batch rapid incidents)
        await self.save_delayed(delay=2.0)

        return incident

    def _count_by_severity(self) -> dict[str, int]:
        """Count incidents by severity."""
        counts: dict[str, int] = {}
        for incident in self._incidents:
            key = incident.severity.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _count_by_type(self) -> dict[str, int]:
        """Count incidents by type."""
        counts: dict[str, int] = {}
        for incident in self._incidents:
            key = incident.incident_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _create_empty_content(self) -> dict[str, Any]:
        """Create empty content structure."""
        return {"incidents": []}

    async def _ensure_loaded(self) -> None:
        """Load historical incidents from disk if not already loaded."""
        if self._loaded:
            return

        # Remember current in-memory incidents (from this session)
        current_session_incidents = list(self._incidents)

        # Load from disk
        await self.load()

        # Merge: disk incidents first, then current session incidents
        # (avoiding duplicates by incident_id)
        existing_ids = {i.incident_id for i in self._incidents}
        for incident in current_session_incidents:
            if incident.incident_id not in existing_ids:
                self._incidents.append(incident)

        # Re-sort by timestamp and enforce limits
        self._incidents.sort(key=lambda i: i.timestamp_iso)
        while len(self._incidents) > self._max_incidents:
            self._incidents.pop(0)

        self._loaded = True

    def _process_loaded_content(self, *, data: dict[str, Any]) -> None:
        """
        Rebuild incidents list from loaded data.

        Applies time-based cleanup: incidents older than max_age_days are removed.
        """
        self._incidents.clear()
        incidents_data = data.get("incidents", [])

        # Calculate cutoff time for age-based cleanup
        cutoff_time = datetime.now() - timedelta(days=self._max_age_days)

        loaded_count = 0
        expired_count = 0

        for incident_dict in incidents_data:
            try:
                incident = IncidentSnapshot.from_dict(data=incident_dict)

                # Check age - skip old incidents
                try:
                    if (datetime.fromisoformat(incident.timestamp_iso)) < cutoff_time:
                        expired_count += 1
                        continue
                except ValueError:
                    pass  # Keep incidents with unparsable timestamps

                self._incidents.append(incident)
                loaded_count += 1
            except (KeyError, ValueError) as err:
                _LOGGER.warning(  # i18n-log: ignore
                    "INCIDENT STORE: Failed to restore incident: %s",
                    err,
                )

        if expired_count > 0:
            _LOGGER.debug(
                "INCIDENT STORE: Removed %d incidents older than %d days",
                expired_count,
                self._max_age_days,
            )

        if loaded_count > 0:
            _LOGGER.debug(
                "INCIDENT STORE: Loaded %d incidents from storage",
                loaded_count,
            )
