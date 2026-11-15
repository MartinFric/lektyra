"""The API guard (review 2026-11-15, point 6) with `serve --lan`: the PC's own names on the home network count."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lektyra.adapters.web.api import HOSTS, SameMachine, lan_hosts, own_origins


def _client(lan: frozenset[str]) -> TestClient:
    inner = FastAPI()

    @inner.get("/x")
    def read() -> str:
        return "ok"

    @inner.post("/x")
    def change() -> str:
        return "ok"

    return TestClient(SameMachine(inner, HOSTS | lan, own_origins(8765, lan)))


def test_the_home_network_names_reach_the_api_only_with_lan() -> None:
    home = {"host": "nisspc.local:8765", "origin": "http://nisspc.local:8765"}
    assert _client(frozenset()).get("/x", headers={"host": home["host"]}).status_code == 403
    lan = _client(frozenset({"nisspc", "nisspc.local", "192.168.100.26"}))
    assert lan.get("/x", headers={"host": home["host"]}).status_code == 200
    assert lan.get("/x", headers={"host": "NISSPC.local:8765"}).status_code == 200
    assert lan.post("/x", headers=home).status_code == 200
    assert lan.get("/x", headers={"host": "192.168.100.26:8765"}).status_code == 200


def test_other_names_and_pages_stay_out_with_lan() -> None:
    lan = _client(frozenset({"nisspc", "nisspc.local", "192.168.100.26"}))
    assert lan.get("/x", headers={"host": "evil.example"}).status_code == 403
    assert lan.post("/x", headers={"host": "nisspc.local:8765", "origin": "https://evil.example"}).status_code == 403


def test_lan_hosts_names_this_pc() -> None:
    names = lan_hosts()
    assert "lektyra.lan" in names  # the Mac's /etc/hosts name (runbook)
    assert any(n.endswith(".local") for n in names)
    assert all(n == n.lower() for n in names)
