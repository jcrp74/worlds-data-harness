"""Contrato temporal y reglas puras; no realiza solicitudes ni escribe archivos."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo

State = Literal["programado", "en_vivo", "finalizado", "desconocido"]
STATES = {"programado", "en_vivo", "finalizado", "desconocido"}
UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Se requiere un datetime con zona horaria")
    return value.astimezone(UTC)


def iso(value: datetime) -> str:
    return aware(value).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Entry:
    scheduled_start: datetime
    teams: tuple[str | None, str | None]
    evidence_locator: str
    provider_event_id: str | None = None
    state: State = "desconocido"
    finished_at: datetime | None = None
    series_score: tuple[int, int] | None = None
    game_states: tuple[State, ...] = ()

    def __post_init__(self) -> None:
        aware(self.scheduled_start)
        if self.finished_at is not None:
            aware(self.finished_at)
        if self.state not in STATES or any(s not in STATES for s in self.game_states):
            raise ValueError("Estado de encuentro no reconocido")
        if len(self.teams) != 2:
            raise ValueError("Se requieren dos plazas de equipo")
        if self.provider_event_id is not None and not self.provider_event_id.strip():
            raise ValueError("Identificador vacío")
        if self.series_score is not None and (
            len(self.series_score) != 2
            or any(type(n) is not int or n < 0 for n in self.series_score)
        ):
            raise ValueError("Marcador inválido")


@dataclass(frozen=True)
class Observation:
    source_url: str
    requested_at: datetime
    received_at: datetime
    entries: tuple[Entry, ...] = ()
    http_status: int | None = None
    http_date: str | None = None
    http_age_seconds: int | None = None
    evidence_sha256: str | None = None
    response_bytes: int = 0
    coverage_complete: bool = False
    provider_updated_at: datetime | None = None
    # Solo una política documentada podría proporcionar este límite deportivo.
    # El adaptador HTML no lo establece a partir de Cache-Control ni HTTP Date.
    sporting_valid_until: datetime | None = None
    retry_not_before: datetime | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


def summarize(observation: Observation, *, now: datetime, timezone_name: str) -> dict:
    now = aware(now)
    zone = ZoneInfo(timezone_name)
    requested = aware(observation.requested_at)
    received = aware(observation.received_at)
    warnings = set(observation.warnings)
    clock_valid = requested <= received <= now
    if not clock_valid:
        warnings.add("clock_order_invalid")

    sporting_age = None
    provider_time_valid = True
    if observation.provider_updated_at is not None:
        sporting_age = (now - aware(observation.provider_updated_at)).total_seconds()
        if sporting_age < 0:
            sporting_age = None
            provider_time_valid = False
            warnings.add("provider_timestamp_in_future")
    stale = observation.sporting_valid_until is not None and (
        now >= aware(observation.sporting_valid_until)
    )
    if stale:
        warnings.add("sporting_data_expired")
    if observation.provider_updated_at is None:
        warnings.add("sporting_freshness_unknown")

    # Un ID contradictorio se pone en cuarentena. No se elige una versión por orden
    # de llegada ni se fusionan entradas sin ID mediante nombres u horas.
    identified: dict[str, Entry] = {}
    conflicts: set[str] = set()
    unidentified = []
    for entry in observation.entries:
        if entry.provider_event_id is None:
            unidentified.append(entry)
            continue
        key = entry.provider_event_id
        if key in identified:
            if replace(identified[key], evidence_locator="") != replace(entry, evidence_locator=""):
                conflicts.add(key)
                warnings.add("conflicting_duplicate_event")
            else:
                warnings.add("duplicate_event_collapsed")
        else:
            identified[key] = entry
    entries = unidentified + [e for k, e in identified.items() if k not in conflicts]
    entries.sort(key=lambda e: (aware(e.scheduled_start), e.provider_event_id or "", e.evidence_locator))
    seen_slots = set()
    for entry in unidentified:
        slot = (aware(entry.scheduled_start), entry.teams)
        if slot in seen_slots:
            warnings.add("possible_duplicate_unresolved_entries")
        seen_slots.add(slot)

    def serialize(entry: Entry) -> dict:
        return {
            "provider_event_id": entry.provider_event_id,
            "identity_status": "provider_id" if entry.provider_event_id else "unresolved",
            "scheduled_start_utc": iso(entry.scheduled_start),
            "scheduled_start_local": aware(entry.scheduled_start).astimezone(zone).isoformat(),
            "teams": list(entry.teams),
            "state": entry.state,
            "finished_at": iso(entry.finished_at) if entry.finished_at else None,
            "series_score": list(entry.series_score) if entry.series_score is not None else None,
            "game_states": list(entry.game_states),
            "provenance": {
                "source_id": "lolesports_public_html",
                "evidence_sha256": observation.evidence_sha256,
                "locator": entry.evidence_locator,
            },
        }

    matches = [e for e in entries if e.provider_event_id is not None]
    usable = not observation.errors
    contradictory_time = any(
        (e.state == "en_vivo" and aware(e.scheduled_start) > now)
        or (e.finished_at is not None and (
            aware(e.finished_at) > now or aware(e.finished_at) < aware(e.scheduled_start)
        )) for e in matches
    )
    if contradictory_time:
        warnings.add("contradictory_event_time")
    complete = usable and observation.coverage_complete and not conflicts and not unidentified
    current = usable and clock_valid and provider_time_valid and not stale and not contradictory_time
    live_matches = [serialize(e) for e in matches if e.state == "en_vivo"] if current else []
    if live_matches:
        live_presence = "present"
    elif current and complete and all(e.state in {"programado", "finalizado"} for e in matches):
        live_presence = "absent"
    else:
        live_presence = "unknown"

    finished = [e for e in matches if e.state == "finalizado"]
    latest = None
    latest_reason = "no_confirmed_finished_match"
    if finished and all(e.finished_at is not None for e in finished) and usable and clock_valid and provider_time_valid and not contradictory_time and not conflicts:
        last_time = max(aware(e.finished_at) for e in finished)
        latest_candidates = [e for e in finished if aware(e.finished_at) == last_time]
        if len(latest_candidates) == 1:
            latest = serialize(latest_candidates[0])
            latest_reason = "latest_within_observed_coverage"
        else:
            latest_reason = "ambiguous_finish_order"
    elif finished:
        latest_reason = "finish_time_missing_or_source_unavailable"

    if not observation.coverage_complete:
        warnings.add("coverage_partial")
    if unidentified:
        warnings.add("event_identity_unresolved")
    if live_presence == "unknown":
        warnings.add("live_state_unknown")
    if latest is None:
        warnings.add("latest_finished_unknown")
    if conflicts:
        complete = False
    completeness = "unavailable" if not usable else (
        "complete" if complete and current and live_presence != "unknown" else "partial"
    )
    return {
        "schema_version": "1.0",
        "tournament": "worlds-2026",
        "now_utc": iso(now),
        "now_local": now.astimezone(zone).isoformat(),
        "timezone": timezone_name,
        "requested_at": iso(requested),
        "received_at": iso(received),
        "source": {
            "id": "lolesports_public_html",
            "url": observation.source_url,
            "adapter_version": "1",
            "http_status": observation.http_status,
            "evidence_sha256": observation.evidence_sha256,
            "response_bytes": observation.response_bytes,
            "http_date": observation.http_date,
            "http_age_seconds": observation.http_age_seconds,
        },
        "provider_updated_at": iso(observation.provider_updated_at) if observation.provider_updated_at else None,
        "freshness": {
            "observation_age_seconds": (now - received).total_seconds() if clock_valid else None,
            "sporting_age_seconds": sporting_age,
            "sporting_status": "expired" if stale else "unknown",
            "sporting_valid_until": iso(observation.sporting_valid_until) if observation.sporting_valid_until else None,
        },
        "coverage": {
            "complete": complete,
            "scope": "observed_response",
            "pagination_followed": False,
            "discarded_conflicting_event_ids": sorted(conflicts),
        },
        "scheduled_entries": [serialize(e) for e in entries] if usable else [],
        "matches": [serialize(e) for e in matches] if usable else [],
        "live": {"presence": live_presence, "matches": live_matches},
        "latest_finished": latest,
        "latest_finished_scope": "observed_response",
        "latest_finished_reason": latest_reason,
        "completeness": completeness,
        "warnings": sorted(warnings),
        "errors": sorted(set(observation.errors)),
        "recheck": {
            "mode": "on_demand",
            "not_before": iso(observation.retry_not_before) if observation.retry_not_before else None,
            "recommended_at": None,
            "reason": "sporting_update_cadence_unverified",
        },
    }
