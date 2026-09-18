import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.session import LOBBIES, SESSIONS, session_count

ORIGIN = {"Origin": "http://127.0.0.1:8765"}


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    SESSIONS.clear()
    LOBBIES.clear()


def _ws(client, path="/Evolution/ws"):
    return client.websocket_connect(path, headers=ORIGIN)


def test_lobbies_empty(client):
    response = client.get("/Evolution/api/lobbies")
    assert response.status_code == 200
    assert response.json() == {"lobbies": []}


def test_create_lobby_requires_origin(client):
    assert client.post("/Evolution/api/lobbies", json={}).status_code == 403
    ok = client.post(
        "/Evolution/api/lobbies",
        json={},
        headers={"Origin": "https://roleplaycardgame.com"},
    )
    assert ok.status_code == 200


def test_create_lobby_and_list(client):
    created = client.post("/Evolution/api/lobbies", json={"seed": 9}, headers=ORIGIN)
    assert created.status_code == 200
    lobby_id = created.json()["id"]
    with _ws(client, f"/Evolution/ws?lobby={lobby_id}") as ws:
        snap = ws.receive_json()
        assert snap["lobby_id"] == lobby_id
        assert snap["control_id"] == 1
        assert snap["host"] is True
        listed = client.get("/Evolution/api/lobbies").json()["lobbies"]
        assert any(row["id"] == lobby_id and row["joinable"] for row in listed)


def test_two_players_barrier(client):
    with _ws(client) as host:
        first = host.receive_json()
        lobby_id = first["lobby_id"]
        host_id = first["control_id"]
        with _ws(client, f"/Evolution/ws?lobby={lobby_id}") as guest:
            joined = guest.receive_json()
            guest_id = joined["control_id"]
            assert guest_id != host_id
            assert sorted(joined["humans"]) == sorted([host_id, guest_id])
            host.send_json({"op": "act", "action": "produce"})
            waiting = host.receive_json()
            assert waiting["tick"] == 0
            assert host_id not in waiting["waiting"]
            assert guest_id in waiting["waiting"]
            guest.send_json({"op": "act", "action": "produce"})

            def _until_tick(sock, start):
                snap = start
                for _ in range(8):
                    if snap.get("tick") == 1:
                        return snap
                    snap = sock.receive_json()
                return snap

            host_done = _until_tick(host, waiting)
            guest_done = _until_tick(guest, joined)
            assert host_done["tick"] == 1
            assert guest_done["tick"] == 1


def test_join_unknown_lobby_1013(client):
    from starlette.websockets import WebSocketDisconnect

    with client.websocket_connect(
        "/Evolution/ws?lobby=nopexxxx", headers=ORIGIN
    ) as ws:
        with pytest.raises(WebSocketDisconnect) as raised:
            ws.receive_json()
        assert raised.value.code == 1013


def test_guest_clock_rejected(client):
    with _ws(client) as host:
        first = host.receive_json()
        with _ws(client, f"/Evolution/ws?lobby={first['lobby_id']}") as guest:
            guest.receive_json()
            guest.send_json({"op": "clock", "mode": "pause"})
            err = guest.receive_json()
            assert err["error"] == "invalid_command"
            assert err["detail"] == "host only"
            host.send_json({"op": "ping"})
            later = host.receive_json()
            assert later["clock"]["mode"] == "awaiting_player"
            assert later["tick"] == 0


def test_reconnect_same_lobby(client):
    with _ws(client) as host:
        first = host.receive_json()
        lobby_id = first["lobby_id"]
        host.send_json({"op": "act", "action": "produce"})
        after = host.receive_json()
        assert after["tick"] == 1
    with _ws(client, f"/Evolution/ws?lobby={lobby_id}") as again:
        snap = again.receive_json()
        assert snap["v"] == 1
        assert snap["lobby_id"] == lobby_id
        assert snap["control_id"] is not None


def test_session_count_two_sockets_one_lobby(client):
    with _ws(client) as host:
        first = host.receive_json()
        with _ws(client, f"/Evolution/ws?lobby={first['lobby_id']}") as guest:
            guest.receive_json()
            assert session_count() == 2
            listed = client.get("/Evolution/api/lobbies").json()["lobbies"]
            assert len(listed) == 1
            assert listed[0]["humans"] == 2
