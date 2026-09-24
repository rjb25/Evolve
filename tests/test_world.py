import pytest

from engine.survivor import ActError, Command
from engine.world import World


def _goods(world):
    return [
        (s.id, s.health, s.meat, s.water, s.fiber) for s in world.survivors()
    ]


def test_registry_choice_returns_last_if_cum_completes():
    world = World(population=1, seed=0, spectate_only=True)

    class _HighRng:
        def random(self):
            return 0.99

    world.registry.rng = _HighRng()
    assert world.registry.choice(["a", "b", "c"], [0.1, 0.1, 0.1]) == "c"


def test_first_id_is_one():
    world = World(population=10, seed=0)
    ids = [s.id for s in world.survivors()]
    assert ids == list(range(1, 11))


def test_tick_zero_is_post_spawn_pre_live():
    world = World(population=3, seed=0)
    assert world.tick_index == 0
    for s in world.survivors():
        assert s.health == 20
        assert (s.meat, s.water, s.fiber) == (20, 20, 20)
        assert s.action == "none"
        assert s.last_target is None


def test_default_control_id_is_first_spawn():
    world = World(population=3, seed=0)
    assert world.control_id == 1
    assert world.spectate_id == 1
    assert world.pending_possess is False


def test_spectate_only_has_no_player():
    world = World(population=3, seed=0, spectate_only=True)
    assert world.control_id is None
    assert world.pending_possess is False
    assert world.spectate_id == 1


def test_self_deal_rejected_without_mutating():
    world = World(population=2, seed=0, control_id=1)
    actor = world.survivors()[0]
    actor.relations = [actor.id]
    before_goods = _goods(world)
    before_tick = world.tick_index
    with pytest.raises(ActError) as raised:
        world.tick(Command(action="deal", target_id=actor.id))
    assert raised.value.code == "invalid_command"
    assert world.tick_index == before_tick
    assert _goods(world) == before_goods


def test_player_advertise_without_target_advances():
    world = World(population=2, seed=0, control_id=1)
    actor = world.survivors()[0]
    world.tick(Command(action="deal"))
    assert world.tick_index == 1
    assert actor.action == "deal"
    assert len(actor.deals) == 1


def test_player_deal_unknown_target_does_not_advance():
    world = World(population=2, seed=0, control_id=1)
    before_goods = _goods(world)
    with pytest.raises(ActError) as raised:
        world.tick(Command(action="deal", target_id=99))
    assert raised.value.code == "unknown_target"
    assert world.tick_index == 0
    assert _goods(world) == before_goods


def test_player_deal_not_in_relations_does_not_advance():
    world = World(population=2, seed=0, control_id=1)
    other = world.survivors()[1]
    before_goods = _goods(world)
    with pytest.raises(ActError) as raised:
        world.tick(Command(action="deal", target_id=other.id))
    assert raised.value.code == "unknown_target"
    assert world.tick_index == 0
    assert _goods(world) == before_goods


def test_seated_player_tick_none_is_produce():
    world = World(population=1, seed=0, control_id=1)
    s = world.survivors()[0]
    specialty = s.produce
    before = getattr(s, specialty)
    world.tick(None)
    assert world.tick_index == 1
    assert s.action == "produce"
    assert getattr(s, specialty) == before - 1 + 20


def test_npc_deal_empty_relations_advertises():
    world = World(population=2, seed=0, spectate_only=True)
    for s in world.survivors():
        s.weights = [0.0, 1.0, 0.0]
        s.relations = []
    world.tick()
    assert world.tick_index == 1
    for s in world.survivors():
        assert s.action == "deal"
        assert len(s.deals) == 1


def test_npc_relate_when_fully_tied_does_not_raise():
    world = World(population=3, seed=0, spectate_only=True)
    people = world.survivors()
    for s in people:
        s.weights = [0.0, 0.0, 1.0]
        s.relations = [o.id for o in people if o.id != s.id]
    world.tick()
    assert world.tick_index == 1
    for s in world.survivors():
        assert s.action == "relate"


def test_death_drops_publisher_deals():
    world = World(population=2, seed=0, spectate_only=True)
    a, b = world.survivors()
    a.act(world, Command(action="deal"))
    assert a.deals
    a.health = 0
    world.tick()
    living_ids = [s.id for s in world.survivors()]
    assert a.id not in living_ids
    assert all(s.id != a.id for s in world.survivors())


def test_death_sweep_prunes_relations_and_last_target():
    world = World(population=2, seed=0, spectate_only=True)
    a, b = world.survivors()
    a.relations = [b.id]
    b.relations = [a.id]
    a.last_target = b.id
    b.health = 0
    world.tick()
    living_ids = [s.id for s in world.survivors()]
    assert b.id not in living_ids
    assert a.relations == []
    assert a.last_target is None
    kinds = [e.kind for e in world.events]
    assert "death" in kinds


def test_successor_tie_break_highest_health_then_lowest_id():
    world = World(population=3, seed=0)
    people = world.survivors()
    assert [s.health for s in people] == [20, 20, 20]
    assert world.pick_successor() == 1
    people[0].health = 19
    assert world.pick_successor() == 2
    people[1].health = 10
    people[2].health = 15
    assert world.pick_successor() == 1
    people[0].health = 5
    people[2].health = 15
    people[1].health = 15
    assert world.pick_successor() == 2


def test_possess_and_release():
    world = World(population=3, seed=0, control_id=1)
    world.release()
    assert world.control_id is None
    assert world.pending_possess is False
    world.possess(2)
    assert world.control_id == 2
    assert world.spectate_id == 2
    assert world.pending_possess is False
    assert world.died_as_name is None


def test_player_death_sets_pending_possess():
    world = World(population=2, seed=0, control_id=1)
    player = world.survivors()[0]
    player.health = 0
    world.tick()
    assert world.control_id is None
    assert world.pending_possess is True
    assert world.died_as_name == player.name


def test_reset_respawns():
    world = World(population=2, seed=0, spectate_only=True)
    world.tick()
    world.reset(seed=1, population=4)
    assert world.tick_index == 0
    assert len(world.survivors()) == 4
    assert any(e.kind == "reset" for e in world.events)
    assert world.control_id is None
    assert world.spectate_only is True


def test_reset_after_extinction_reseats_player():
    world = World(population=1, seed=0, control_id=1)
    world.survivors()[0].health = 0
    world.tick()
    assert world.survivors() == []
    assert world.control_id is None
    assert world.pending_possess is False
    world.reset(seed=0)
    assert world.spectate_only is False
    assert world.control_id == 1
    assert world.snapshot()["clock"]["mode"] == "awaiting_player"
    assert len(world.survivors()) == 10


def test_reset_event_ids_continue():
    world = World(population=1, seed=0, control_id=1)
    world.tick(Command(action="produce"))
    assert world.events[-1].event_id == 1
    world.reset(seed=1)
    events = world.snapshot()["events"]
    assert [e["kind"] for e in events] == ["reset"]
    assert events[0]["event_id"] == 2


def test_two_human_commands_one_tick():
    world = World(population=3, seed=0, control_id=1)
    a, b, c = world.survivors()
    a.produce = "fiber"
    b.produce = "meat"
    world.tick(
        {
            1: Command(action="produce"),
            2: Command(action="produce"),
        },
        human_ids={1, 2},
    )
    assert world.tick_index == 1
    assert a.action == "produce"
    assert b.action == "produce"
    assert c.action != "none"
    snap = world.snapshot(viewer_id=2, human_ids={1, 2})
    assert snap["control_id"] == 2
    assert snap["humans"] == [1, 2]
    assert [row["id"] for row in snap["survivors"] if row["is_player"]] == [1, 2]


def test_possess_rejects_claimed():
    world = World(population=3, seed=0, control_id=1)
    with pytest.raises(ActError) as raised:
        world.possess(2, claimed={2})
    assert raised.value.code == "unknown_target"
    assert world.control_id == 1
    assert world.pick_successor(claimed={1}) == 2
