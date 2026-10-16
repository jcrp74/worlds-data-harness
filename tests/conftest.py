"""Fixtures sintéticas: no son datos de un encuentro real."""

from datetime import datetime, timezone
import socket

import pytest


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", help="Habilitar pruebas contra LoL Esports")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--live"):
        for item in items:
            if "live" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Red real optativa: usar --live -m live"))


@pytest.fixture(autouse=True)
def block_network(request, monkeypatch):
    if "live" in request.keywords and request.config.getoption("--live"):
        return

    def blocked(*args, **kwargs):
        raise AssertionError("Las pruebas deterministas no pueden conectarse a la red")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def now():
    return datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def card():
    def make(start="2026-10-17T18:00:00Z", league="Worlds", teams=("Equipo Alfa", "Equipo Beta"), extra=""):
        images = "".join(f'<p><img alt="{team}"/>{team}</p>' for team in teams)
        timestamp = f'<time datetime="{start}">hora visible no utilizada</time>' if start is not None else ""
        return (
            f'<div><div>{timestamp}{images}{extra}</div><footer><img alt="{league}"/>'
            f'<p>{league}<span> Play-Ins</span></p><p aria-label="best of 5">Bo5</p></footer></div>'
        )
    return make


@pytest.fixture
def page():
    def make(cards="", extra=""):
        return (
            '<!doctype html><html><head><title>LoL Esports | SCHEDULE</title></head>'
            '<body><section data-tag="date" data-date="Tomorrow"></section>'
            + cards + extra + '</body></html>'
        ).encode("utf-8")
    return make
