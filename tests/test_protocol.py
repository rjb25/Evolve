import json

import pytest

from engine.world import World
from server.protocol import (
    MAX_MESSAGE_BYTES,
    SPEED_MAX,
    SPEED_MIN,
    ActCommand,
    ClockCommand,
    ProtocolError,
    Snapshot,
    error_frame,
    parse_message,
    validate_act,
)


def test_parse_produce():
    cmd = parse_message({"op": "act", "action": "produce"})
    assert isinstance(cmd, ActCommand)
    assert cmd.action == "produce"
    assert cmd.target_id is None


def test_parse_deal_requires_target():
    cmd = parse_message({"op": "act", "action": "deal", "target_id": 7})
    assert cmd.target_id == 7
    with pytest.raises(ProtocolError) as raised:
        parse_message({"op": "act", "action": "deal"})
    assert raised.value.error == "invalid_command"


def test_parse_relate_requires_target():
    with pytest.raises(ProtocolError) as raised:
        parse_message({"op": "act", "action": "relate"})
    assert raised.value.error == "invalid_command"


def test_parse_invalid_action():
    with pytest.raises(ProtocolError) as raised:
        parse_message({"op": "act", "action": "skip"})
    assert raised.value.error == "invalid_command"


def test_unknown_op():
    with pytest.raises(ProtocolError) as raised:
        parse_message({"op": "explode"})
    assert raised.value.error == "invalid_command"
    assert "unknown op" in raised.value.detail


def test_missing_op():
    with pytest.raises(ProtocolError) as raised:
        parse_message({"action": "produce"})
    assert raised.value.error == "invalid_command"


def test_possess_requires_id():
    with pytest.raises(ProtocolError):
        parse_message({"op": "possess"})
    with pytest.raises(ProtocolError):
        parse_message({"op": "possess", "id": None})
    cmd = parse_message({"op": "possess", "id": 8})
    assert cmd.id == 8


def test_spectate_requires_id():
    with pytest.raises(ProtocolError):
        parse_message({"op": "spectate"})
    cmd = parse_message({"op": "spectate", "id": 3})
    assert cmd.id == 3


def test_release_ping_reset():
    assert parse_message({"op": "release"}).op == "release"
    assert parse_message({"op": "ping"}).op == "ping"
    reset = parse_message({"op": "reset", "seed": 42})
    assert reset.seed == 42


def test_clock_speed_clamped():
    high = parse_message({"op": "clock", "speed": 100})
    assert isinstance(high, ClockCommand)
    assert high.speed == SPEED_MAX
    low = parse_message({"op": "clock", "speed": 0.01})
    assert low.speed == SPEED_MIN
    mid = parse_message({"op": "clock", "speed": 2.0, "mode": "play"})
    assert mid.speed == 2.0
    assert mid.mode == "play"


def test_clock_timeout_zero_ok_negative_rejected():
    cmd = parse_message({"op": "clock", "timeout_ms": 0})
    assert cmd.timeout_ms == 0
    with pytest.raises(ProtocolError):
        parse_message({"op": "clock", "timeout_ms": -1})


def test_clock_invalid_mode():
    with pytest.raises(ProtocolError):
        parse_message({"op": "clock", "mode": "watching"})


def test_invalid_json_and_non_object():
    with pytest.raises(ProtocolError) as raised:
        parse_message("{not json")
    assert raised.value.error == "invalid_json"
    with pytest.raises(ProtocolError) as raised:
        parse_message("[1, 2]")
    assert raised.value.error == "invalid_command"


def test_message_too_large():
    payload = json.dumps({"op": "ping", "pad": "x" * (MAX_MESSAGE_BYTES)})
    assert len(payload.encode("utf-8")) > MAX_MESSAGE_BYTES
    with pytest.raises(ProtocolError) as raised:
        parse_message(payload)
    assert raised.value.error == "message_too_large"


def test_validate_act_rejects_self_target():
    cmd = parse_message({"op": "act", "action": "deal", "target_id": 1})
    with pytest.raises(ProtocolError) as raised:
        validate_act(cmd, clock_mode="awaiting_player", actor_id=1)
    assert raised.value.error == "invalid_command"
    validate_act(cmd, clock_mode="awaiting_player", actor_id=2)


def test_validate_act_requires_awaiting_player():
    cmd = parse_message({"op": "act", "action": "produce"})
    with pytest.raises(ProtocolError) as raised:
        validate_act(cmd, clock_mode="watching", actor_id=1)
    assert raised.value.detail == "not awaiting player"
    with pytest.raises(ProtocolError):
        validate_act(cmd, clock_mode="pause", actor_id=1)
    validate_act(cmd, clock_mode="awaiting_player", actor_id=1)


def test_error_frame_shape():
    frame = error_frame("unknown_target", "id 99 is not living")
    assert frame == {
        "v": 1,
        "error": "unknown_target",
        "detail": "id 99 is not living",
    }


def test_snapshot_model_matches_world():
    world = World(population=3, seed=0, control_id=1)
    snap = world.snapshot()
    snap["clock"] = {
        "mode": "awaiting_player",
        "speed": 1.0,
        "timeout_ms": 15000,
        "timeout_remaining_ms": 15000,
    }
    parsed = Snapshot.model_validate(snap)
    assert parsed.v == 1
    assert parsed.tick == 0
    assert parsed.seed == 0
    assert parsed.control_id == 1
    assert parsed.population == 3
    assert parsed.events == []
    assert parsed.survivors[0].last_target is None
    dumped = parsed.model_dump()
    json.dumps(dumped)
