from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from worlds_data_harness.estado_actual import Entry, Observation, summarize


def observed(now, entries=(), **kwargs):
    return Observation("https://lolesports.com/en-US/", now, now, entries=entries, **kwargs)


def event(now, **kwargs):
    values = dict(scheduled_start=now - timedelta(hours=1), teams=("A", "B"),
                  evidence_locator="synthetic:1", provider_event_id="fixture-1")
    values.update(kwargs)
    return Entry(**values)


def result(obs, now, zone="America/Lima"):
    return summarize(obs, now=now, timezone_name=zone)


def test_empty_complete_scope_confirms_no_live(now):
    r = result(observed(now, coverage_complete=True), now)
    assert r["matches"] == []
    assert r["live"]["presence"] == "absent"
    assert r["completeness"] == "complete"


def test_empty_partial_scope_does_not_confirm_absence(now):
    r = result(observed(now), now)
    assert r["live"] == {"presence": "unknown", "matches": []}
    assert r["completeness"] == "partial"


def test_scheduled_time_in_past_does_not_imply_live_or_finished(now):
    entry = event(now, state="programado")
    r = result(observed(now, (entry,)), now)
    assert r["matches"][0]["state"] == "programado"
    assert r["live"]["presence"] == "unknown"
    assert r["latest_finished"] is None


def test_live_series_can_have_finished_map(now):
    entry = event(now, state="en_vivo", game_states=("finalizado", "en_vivo"), series_score=(1, 0))
    r = result(observed(now, (entry,)), now)
    assert r["live"]["presence"] == "present"
    assert len(r["live"]["matches"]) == 1
    assert r["latest_finished"] is None


def test_finished_maps_do_not_finish_series(now):
    entry = event(now, game_states=("finalizado",), series_score=(1, 0))
    r = result(observed(now, (entry,)), now)
    assert r["matches"][0]["state"] == "desconocido"
    assert r["latest_finished"] is None


def test_multiple_live_matches_allowed(now):
    entries = (event(now, state="en_vivo"), event(now, state="en_vivo", provider_event_id="fixture-2"))
    assert len(result(observed(now, entries), now)["live"]["matches"]) == 2


def test_latest_uses_finish_time_not_scheduled_time(now):
    a = event(now, state="finalizado", finished_at=now - timedelta(minutes=1))
    b = event(now, provider_event_id="fixture-2", state="finalizado",
              scheduled_start=now - timedelta(minutes=20), finished_at=now - timedelta(minutes=5))
    r = result(observed(now, (a, b)), now)
    assert r["latest_finished"]["provider_event_id"] == "fixture-1"
    assert r["latest_finished_scope"] == "observed_response"


def test_missing_finish_or_tied_finish_is_unknown(now):
    a = event(now, state="finalizado", finished_at=now)
    b = event(now, state="finalizado", provider_event_id="fixture-2")
    assert result(observed(now, (a, b)), now)["latest_finished"] is None
    b = replace(b, finished_at=now)
    assert result(observed(now, (a, b)), now)["latest_finished_reason"] == "ambiguous_finish_order"


def test_expired_observation_keeps_historical_evidence_not_current_live(now):
    obs = observed(now, (event(now, state="en_vivo"),),
                   provider_updated_at=now - timedelta(hours=1),
                   sporting_valid_until=now - timedelta(minutes=1))
    r = result(obs, now)
    assert r["live"]["presence"] == "unknown"
    assert r["freshness"]["sporting_status"] == "expired"
    assert r["matches"][0]["state"] == "en_vivo"  # observado, con caducidad explícita


@pytest.mark.parametrize("change", ["received_in_future", "received_before_request", "provider_future"])
def test_clock_anomalies_invalidate_current_confirmation(now, change):
    obs = observed(now, (event(now, state="en_vivo"),))
    if change == "received_in_future":
        obs = replace(obs, received_at=now + timedelta(seconds=5))
    elif change == "received_before_request":
        obs = replace(obs, received_at=now - timedelta(seconds=1))
    else:
        obs = replace(obs, provider_updated_at=now + timedelta(seconds=1))
    r = result(obs, now)
    assert r["live"]["presence"] == "unknown"
    assert r["freshness"]["observation_age_seconds"] == (0 if change == "provider_future" else None)


@pytest.mark.parametrize("change", ["future_live", "future_finish", "finish_before_start"])
def test_contradictory_event_times(now, change):
    entry = event(now, state="finalizado", finished_at=now)
    if change == "future_live":
        entry = replace(entry, state="en_vivo", scheduled_start=now + timedelta(hours=1), finished_at=None)
    elif change == "future_finish":
        entry = replace(entry, finished_at=now + timedelta(seconds=1))
    else:
        entry = replace(entry, finished_at=entry.scheduled_start - timedelta(seconds=1))
    r = result(observed(now, (entry,)), now)
    assert r["live"]["presence"] == "unknown"
    assert r["latest_finished"] is None
    assert "contradictory_event_time" in r["warnings"]


def test_duplicate_ids_collapse_but_conflicts_are_quarantined(now):
    a = event(now, series_score=(1, 0))
    b = replace(a, evidence_locator="synthetic:2")
    r = result(observed(now, (a, b)), now)
    assert len(r["matches"]) == 1
    assert "duplicate_event_collapsed" in r["warnings"]
    conflict = replace(b, series_score=(2, 0))
    for entries in [(a, conflict), (conflict, a)]:
        r = result(observed(now, entries, coverage_complete=True), now)
        assert r["matches"] == []
        assert r["coverage"]["discarded_conflicting_event_ids"] == ["fixture-1"]
        assert r["live"]["presence"] == "unknown"


def test_unresolved_same_slot_not_merged(now):
    a = event(now, provider_event_id=None)
    b = replace(a, evidence_locator="synthetic:2")
    r = result(observed(now, (a, b)), now)
    assert len(r["scheduled_entries"]) == 2
    assert r["matches"] == []
    assert "possible_duplicate_unresolved_entries" in r["warnings"]


def test_correction_replaces_logical_result_without_accumulation(now):
    a = event(now, state="finalizado", finished_at=now, series_score=(3, 1))
    before = observed(now, (a,))
    after = replace(before, entries=(replace(a, series_score=(3, 2)),))
    assert result(before, now) == result(before, now)
    assert result(after, now)["matches"][0]["series_score"] == [3, 2]
    assert result(before, now)["matches"][0]["series_score"] == [3, 1]


def test_zones_convert_same_instant_and_preserve_provenance(now):
    obs = observed(now, (event(now),), evidence_sha256="fixturehash", http_date="untrusted HTTP Date", http_age_seconds=900)
    lima = result(obs, now)
    seoul = result(obs, now, "Asia/Seoul")
    assert lima["now_utc"] == seoul["now_utc"]
    assert lima["now_local"].endswith("-05:00")
    assert seoul["now_local"].endswith("+09:00")
    assert lima["provider_updated_at"] is None
    assert lima["freshness"]["sporting_age_seconds"] is None
    assert lima["matches"][0]["provenance"]["evidence_sha256"] == "fixturehash"


def test_naive_times_and_unknown_states_rejected(now):
    with pytest.raises(ValueError):
        event(now, scheduled_start=datetime(2026, 10, 16))
    with pytest.raises(ValueError):
        event(now, state="win")


def test_source_failure_never_returns_partial_data_as_available(now):
    r = result(observed(now, (event(now, state="en_vivo"),), errors=("network_error",), coverage_complete=True), now)
    assert r["completeness"] == "unavailable"
    assert r["coverage"]["complete"] is False
    assert r["matches"] == r["scheduled_entries"] == []
    assert r["live"]["presence"] == "unknown"
