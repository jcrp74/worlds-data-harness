import json
from pathlib import Path

import pytest

from worlds_data_harness import __main__ as cli
from worlds_data_harness.estado_actual import Observation
from worlds_data_harness.lolesports import SOURCE_URL


def test_cli_partial_json_and_atomic_output(monkeypatch, capsys, tmp_path, now):
    monkeypatch.setattr(cli, "query_schedule", lambda **kwargs: Observation(SOURCE_URL, now, now))
    monkeypatch.setattr(cli, "utc_now", lambda: now)
    path = tmp_path / "result.json"
    path.write_text("previous", encoding="utf-8")
    assert cli.main(["estado_actual", "--output", str(path)]) == 2
    printed = capsys.readouterr().out
    assert json.loads(printed) == json.loads(path.read_text(encoding="utf-8"))
    assert json.loads(printed)["completeness"] == "partial"
    assert list(tmp_path.iterdir()) == [path]


def test_unavailable_has_distinct_exit(monkeypatch, capsys, now):
    monkeypatch.setattr(cli, "query_schedule", lambda **kwargs: Observation(SOURCE_URL, now, now, errors=("network_error",)))
    monkeypatch.setattr(cli, "utc_now", lambda: now)
    assert cli.main(["estado_actual"]) == 1
    assert json.loads(capsys.readouterr().out)["errors"] == ["network_error"]


def test_unavailable_preserves_previous_output(monkeypatch, tmp_path, now, capsys):
    monkeypatch.setattr(cli, "query_schedule", lambda **kwargs: Observation(SOURCE_URL, now, now, errors=("network_error",)))
    monkeypatch.setattr(cli, "utc_now", lambda: now)
    path = tmp_path / "previous.json"
    path.write_bytes(b"previous good result")
    assert cli.main(["estado_actual", "--output", str(path)]) == 1
    assert path.read_bytes() == b"previous good result"
    assert "se conserva" in capsys.readouterr().err


@pytest.mark.parametrize("args", [
    ["--timeout", "0"], ["--timeout", "nan"], ["--timeout", "inf"], ["--timeout", "121"],
    ["--timezone", "not/a/zone"], ["--timezone", "../UTC"],
    ["--tournament", "worlds-2025"], ["--url", "https://other.invalid"],
])
def test_invalid_arguments_never_query(args, monkeypatch):
    def unexpected(**kwargs):
        raise AssertionError("No debe haber consultas con argumentos inválidos")
    monkeypatch.setattr(cli, "query_schedule", unexpected)
    with pytest.raises(SystemExit) as raised:
        cli.main(["estado_actual", *args])
    assert raised.value.code == 2


@pytest.mark.parametrize("failure", ["fsync", "replace"])
def test_failed_write_preserves_previous_file_and_cleans_temp(tmp_path, monkeypatch, failure):
    path = tmp_path / "existing.json"
    path.write_bytes(b"previous")
    def fail(*args):
        raise OSError("simulated interruption")
    monkeypatch.setattr(cli.os, failure, fail)
    with pytest.raises(OSError):
        cli.atomic_write(path, "new data")
    assert path.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [path]


def test_output_failure_reports_separate_exit(monkeypatch, now, tmp_path):
    monkeypatch.setattr(cli, "query_schedule", lambda **kwargs: Observation(SOURCE_URL, now, now))
    monkeypatch.setattr(cli, "utc_now", lambda: now)
    with pytest.raises(SystemExit) as raised:
        cli.main(["estado_actual", "--output", str(tmp_path / "missing" / "x.json")])
    assert raised.value.code == 74
