import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.app import app
from server.session import (
    ALLOWED_WS_ORIGINS,
    MAX_SESSIONS,
    SESSIONS,
    session_count,
)

ORIGIN = {"Origin": "http://127.0.0.1:8765"}


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    SESSIONS.clear()


def _ws(client, path="/Evolution/ws"):
    return client.websocket_connect(path, headers=ORIGIN)


def test_health(client):
    response = client.get("/Evolution/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["sessions"] == 0
    assert body["max_sessions"] == MAX_SESSIONS
    assert "python" in body


def test_index_under_evolution(client):
    for path in ("/Evolution", "/Evolution/"):
        response = client.get(path)
        assert response.status_code == 200
        assert b"Evolution" in response.content
        assert b'<base href="/Evolution/">' in response.content


def test_no_root_routes(client):
    assert client.get("/").status_code == 404
    assert client.get("/static").status_code == 404


def test_ws_connect_sends_tick_zero_snapshot(client):
    with _ws(client) as ws:
        snap = ws.receive_json()
        assert snap["v"] == 1
        assert snap["tick"] == 0
        assert snap["control_id"] == 1
        assert snap["pending_possess"] is False
        assert snap["population"] == 10
        assert snap["clock"]["mode"] == "awaiting_player"
        assert snap["clock"]["speed"] == 1.0
        assert snap["clock"]["timeout_ms"] == 15000
        assert snap["clock"]["timeout_remaining_ms"] > 0
        assert snap["events"] == []
        assert "deal_preview" in snap


def test_origin_rejected_without_allowlist(client):
    with pytest.raises(WebSocketDisconnect) as raised:
        with client.websocket_connect(
            "/Evolution/ws", headers={"Origin": "http://evil.example"}
        ):
            pass
    assert raised.value.code == 1008


def test_origin_rejected_when_missing(client):
    with pytest.raises(WebSocketDisconnect) as raised:
        with client.websocket_connect("/Evolution/ws"):
            pass
    assert raised.value.code == 1008


def test_shipped_origins_are_exact():
    assert ALLOWED_WS_ORIGINS == {
        "https://roleplaycardgame.com",
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    }
    assert "*" not in ALLOWED_WS_ORIGINS
    assert "testserver" not in ALLOWED_WS_ORIGINS


def test_patched_origin_is_accepted(client, monkeypatch):
    extra = "http://example.test"
    monkeypatch.setattr(
        "server.session.ALLOWED_WS_ORIGINS",
        ALLOWED_WS_ORIGINS | {extra},
    )
    with client.websocket_connect(
        "/Evolution/ws", headers={"Origin": extra}
    ) as ws:
        snap = ws.receive_json()
        assert snap["v"] == 1


def test_session_cap_close_1013(client, monkeypatch):
    monkeypatch.setattr("server.session.MAX_SESSIONS", 1)
    with _ws(client) as ws:
        ws.receive_json()
        assert session_count() == 1
        with pytest.raises(WebSocketDisconnect) as raised:
            with _ws(client):
                pass
        assert raised.value.code == 1013


def test_act_rejected_when_not_awaiting_player(client):
    with _ws(client) as ws:
        snap = ws.receive_json()
        tick = snap["tick"]
        ws.send_json({"op": "clock", "mode": "pause"})
        paused = ws.receive_json()
        assert paused["clock"]["mode"] == "pause"
        ws.send_json({"op": "act", "action": "produce"})
        err = ws.receive_json()
        assert err["v"] == 1
        assert err["error"] == "invalid_command"
        assert err["detail"] == "not awaiting player"
        ws.send_json({"op": "ping"})
        later = ws.receive_json()
        assert later["tick"] == tick


def test_self_target_rejected(client):
    with _ws(client) as ws:
        snap = ws.receive_json()
        actor = snap["control_id"]
        ws.send_json({"op": "act", "action": "deal", "target_id": actor})
        err = ws.receive_json()
        assert err["error"] == "invalid_command"
        ws.send_json({"op": "ping"})
        later = ws.receive_json()
        assert later["tick"] == 0


def test_timeout_skip_produces(client):
    with _ws(client) as ws:
        ws.receive_json()
        ws.send_json({"op": "clock", "timeout_ms": 80})
        ws.receive_json()
        time.sleep(0.35)
        session = next(iter(SESSIONS.values()))
        assert session.world.tick_index >= 1
        player = next(
            s for s in session.world.survivors() if s.id == session.world.control_id
        )
        assert player.action == "produce"
        snap = ws.receive_json()
        assert snap["tick"] >= 1


def test_pause_freezes_timeout(client):
    with _ws(client) as ws:
        ws.receive_json()
        ws.send_json({"op": "clock", "timeout_ms": 200})
        ws.receive_json()
        ws.send_json({"op": "clock", "mode": "pause"})
        paused = ws.receive_json()
        assert paused["clock"]["mode"] == "pause"
        remaining = paused["clock"]["timeout_remaining_ms"]
        time.sleep(0.4)
        session = next(iter(SESSIONS.values()))
        assert session.world.tick_index == 0
        ws.send_json({"op": "ping"})
        later = ws.receive_json()
        assert later["tick"] == 0
        assert later["clock"]["mode"] == "pause"
        assert later["clock"]["timeout_remaining_ms"] == remaining


def test_spectate_query_starts_watching(client):
    with _ws(client, "/Evolution/ws?spectate=1") as ws:
        snap = ws.receive_json()
        assert snap["clock"]["mode"] == "watching"
        assert snap["control_id"] is None
        assert snap["pending_possess"] is False
        assert snap["spectate_id"] == 1


def test_seed_query(client):
    with _ws(client, "/Evolution/ws?seed=123") as ws:
        snap = ws.receive_json()
        assert snap["seed"] == 123
        assert snap["tick"] == 0


def test_ping(client):
    with _ws(client) as ws:
        first = ws.receive_json()
        ws.send_json({"op": "ping"})
        pong = ws.receive_json()
        assert pong["v"] == 1
        assert pong["tick"] == first["tick"]
        assert "clock" in pong


def test_release_watching_ticks(client):
    with _ws(client) as ws:
        ws.receive_json()
        ws.send_json({"op": "clock", "speed": 20})
        ws.receive_json()
        ws.send_json({"op": "release"})
        snap = ws.receive_json()
        assert snap["clock"]["mode"] == "watching"
        assert snap["control_id"] is None
        assert snap["pending_possess"] is False
        time.sleep(0.25)
        session = next(iter(SESSIONS.values()))
        assert session.world.tick_index >= 1
        assert session.clock_mode() == "watching"


def test_possess_after_death(client):
    with _ws(client) as ws:
        snap = ws.receive_json()
        session = next(iter(SESSIONS.values()))
        player = session.world.registry.get_member("survivors", snap["control_id"])
        other_id = next(
            s.id for s in session.world.survivors() if s.id != player.id
        )
        player.health = 1
        player.meat = 0
        player.water = 0
        player.fiber = 0
        died_name = player.name
        ws.send_json({"op": "act", "action": "produce"})
        after = ws.receive_json()
        assert after["pending_possess"] is True
        assert after["clock"]["mode"] == "awaiting_possess"
        assert after["control_id"] is None
        assert after["died_as_name"] == died_name
        ws.send_json({"op": "possess", "id": other_id})
        possessed = ws.receive_json()
        assert possessed["control_id"] == other_id
        assert possessed["spectate_id"] == other_id
        assert possessed["pending_possess"] is False
        assert possessed["died_as_name"] is None
        assert possessed["clock"]["mode"] == "awaiting_player"


def test_disconnect_cleanup(client):
    with _ws(client) as ws:
        ws.receive_json()
        assert session_count() == 1
    assert session_count() == 0


def test_step_disabled_while_awaiting_player(client):
    with _ws(client) as ws:
        snap = ws.receive_json()
        ws.send_json({"op": "clock", "mode": "step"})
        err = ws.receive_json()
        assert err["error"] == "invalid_command"
        ws.send_json({"op": "ping"})
        later = ws.receive_json()
        assert later["tick"] == snap["tick"]


def test_act_produce_advances(client):
    with _ws(client) as ws:
        ws.receive_json()
        ws.send_json({"op": "act", "action": "produce"})
        snap = ws.receive_json()
        assert snap["tick"] == 1
        assert snap["clock"]["mode"] == "awaiting_player"
        player = next(row for row in snap["survivors"] if row["is_player"])
        assert player["action"] == "produce"
        assert player["last_target"] is None
