"""Prueba optativa. No se conserva el HTML ni se presupone un partido en curso."""

import pytest

from worlds_data_harness.estado_actual import summarize, utc_now
from worlds_data_harness.lolesports import query_schedule


@pytest.mark.live
def test_public_calendar_contract():
    observation = query_schedule()
    assert observation.errors == (), f"Fuente real no comprobada: {observation.errors}"
    assert observation.http_status == 200
    result = summarize(observation, now=utc_now(), timezone_name="America/Lima")
    assert result["completeness"] == "partial"
    assert result["provider_updated_at"] is None
    assert result["live"]["presence"] == "unknown"
    assert result["latest_finished"] is None
    for entry in result["scheduled_entries"]:
        assert entry["scheduled_start_utc"].startswith("2026-")
        assert entry["provider_event_id"] is None
