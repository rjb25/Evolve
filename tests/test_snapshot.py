import json

from engine.survivor import Command
from engine.world import World


def test_tick_zero_snapshot_shape():
    world = World(population=10, seed=0, control_id=1)
    snap = world.snapshot()
    assert snap["v"] == 1
    assert snap["tick"] == 0
    assert snap["seed"] == 0
    assert snap["control_id"] == 1
    assert snap["pending_possess"] is False
    assert snap["died_as_name"] is None
    assert snap["population"] == 10
    assert snap["events"] == []
    assert len(snap["survivors"]) == 10
    for row in snap["survivors"]:
        assert row["health"] == 20
        assert row["meat"] == 20
        assert row["water"] == 20
        assert row["fiber"] == 20
        assert row["action"] == "none"
        assert row["last_target"] is None
        assert row["relations"] == []
        assert row["deals"] == []
        assert row["alive"] is True
    assert snap["survivors"][0]["is_player"] is True
    assert snap["survivors"][1]["is_player"] is False
    json.dumps(snap)


def test_last_target_null_when_unset():
    world = World(population=2, seed=0, control_id=1)
    snap = world.snapshot()
    assert snap["survivors"][0]["last_target"] is None
    encoded = json.loads(json.dumps(snap))
    assert encoded["survivors"][0]["last_target"] is None


def test_last_target_set_on_fulfill():
    world = World(population=2, seed=0, control_id=1)
    a, b = world.survivors()
    a.fiber, a.meat, a.water = 12, 4, 10
    b.fiber, b.meat, b.water = 3, 8, 10
    a.relations = [b.id]
    b.relations = [a.id]
    a.act(world, Command(action="deal"))
    b.act(world, Command(action="deal", target_id=a.id))
    snap = world.snapshot()
    friend = next(row for row in snap["survivors"] if row["id"] == b.id)
    assert friend["last_target"] == a.id
    deals = [e for e in snap["events"] if e["kind"] == "deal"]
    assert deals
    assert deals[-1]["accepted"] is True
    assert deals[-1]["offer_id"] == 1


def test_event_ring_and_player_produce():
    world = World(population=1, seed=0, control_id=1)
    snap = world.tick(Command(action="produce"))
    assert snap["tick"] == 1
    assert len(snap["events"]) == 1
    event = snap["events"][0]
    assert event["event_id"] == 1
    assert event["tick"] == 0
    assert event["kind"] == "produce"
    assert event["actor"] == 1
    assert snap["tick"] == event["tick"] + 1


def test_npc_produce_is_not_emitted():
    world = World(population=2, seed=0, spectate_only=True)
    for s in world.survivors():
        s.weights = [1.0, 0.0, 0.0]
    snap = world.tick()
    assert all(e["kind"] != "produce" for e in snap["events"])


def test_relate_and_death_events():
    world = World(population=2, seed=0, control_id=1)
    a, b = world.survivors()
    world.tick(Command(action="relate", target_id=b.id))
    kinds = [e.kind for e in world.events]
    assert "relate" in kinds
    b.health = 0
    world.tick(Command(action="produce"))
    kinds = [e.kind for e in world.events]
    assert "death" in kinds
    assert b.id not in [s.id for s in world.survivors()]


def test_event_ring_caps_at_200():
    world = World(population=1, seed=0, control_id=1)
    s = world.survivors()[0]
    for _ in range(210):
        s.meat = s.water = s.fiber = 20
        s.health = 20
        world.tick(Command(action="produce"))
    snap = world.snapshot()
    assert len(snap["events"]) == 200
    assert snap["events"][0]["event_id"] == 11
    assert snap["events"][-1]["event_id"] == 210


def test_snapshot_json_able_after_npc_ticks():
    world = World(population=10, seed=0, spectate_only=True)
    for _ in range(5):
        snap = world.tick()
    json.dumps(snap)
