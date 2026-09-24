import pytest

from engine.survivor import ActError, Command, MAX_DEALS
from engine.world import World


def _pair(world=None):
    world = world or World(population=2, seed=0, control_id=1)
    a, b = world.survivors()
    return world, a, b


def test_live_fed_clamps_to_nineteen():
    world = World(population=1, seed=0, spectate_only=True)
    s = world.survivors()[0]
    s.health, s.meat, s.water, s.fiber = 20, 20, 20, 20
    s.live()
    assert (s.meat, s.water, s.fiber) == (19, 19, 19)
    assert s.health == 20


def test_live_starve_clamps_zero_not_negative():
    world = World(population=1, seed=0, spectate_only=True)
    s = world.survivors()[0]
    s.health, s.meat, s.water, s.fiber = 20, 0, 5, 5
    s.live()
    assert s.meat == 0
    assert s.water == 4
    assert s.fiber == 4
    assert s.health == 16


def test_live_zero_stock_tick_still_starves():
    world = World(population=1, seed=0, spectate_only=True)
    s = world.survivors()[0]
    s.health, s.meat, s.water, s.fiber = 20, 0, 0, 0
    s.live()
    assert (s.meat, s.water, s.fiber) == (0, 0, 0)
    assert s.health == 16


def test_live_heal_when_fed_and_hurt():
    world = World(population=1, seed=0, spectate_only=True)
    s = world.survivors()[0]
    s.health, s.meat, s.water, s.fiber = 16, 5, 5, 5
    s.live()
    assert s.health == 18
    assert (s.meat, s.water, s.fiber) == (4, 4, 4)


def test_produce_plus_twenty():
    world = World(population=1, seed=0, spectate_only=True)
    s = world.survivors()[0]
    s.produce = "fiber"
    s.fiber = 20
    s.act(world, Command(action="produce"))
    assert s.fiber == 40
    assert s.action == "produce"
    assert s.last_target is None


def test_decide_accept_fiber_meat_fixture():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 8, 10
    assert player.excess() == "fiber"
    assert player.need() == "meat"
    assert friend.decide(player.excess(), player.need(), player) is True
    assert friend.meat > friend.fiber - 1


def test_decide_reject_fiber_meat_fixture():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 2, 10
    assert friend.decide(player.excess(), player.need(), player) is False
    assert not (friend.meat > friend.fiber - 1)


def test_advertise_then_relation_fulfills():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 8, 10
    player.relations = [friend.id]
    friend.relations = [player.id]
    player.act(world, Command(action="deal"))
    assert len(player.deals) == 1
    offer = player.deals[0]
    assert offer.give == "fiber"
    assert offer.get == "meat"
    friend.act(world, Command(action="deal", target_id=player.id, offer_id=offer.id))
    assert player.meat == 14
    assert player.fiber == 3
    assert friend.meat == -1
    assert friend.fiber == 13
    assert player.deals == []
    assert friend.last_target == player.id
    assert friend.action == "deal"


def test_sixth_advertise_drops_oldest():
    world, player, friend = _pair()
    player.act(world, Command(action="deal"))
    first_id = player.deals[0].id
    for _ in range(MAX_DEALS):
        player.act(world, Command(action="deal"))
    assert len(player.deals) == MAX_DEALS
    assert first_id not in [offer.id for offer in player.deals]
    unlists = [e for e in world.events if e.kind == "unlist"]
    assert unlists
    assert unlists[0].offer_id == first_id


def test_unrelated_fulfill_rejected_listing_remains():
    world, player, stranger = _pair()
    player.act(world, Command(action="deal"))
    assert player.deals
    with pytest.raises(ActError) as raised:
        stranger.act(world, Command(action="deal", target_id=player.id))
    assert raised.value.code == "unknown_target"
    assert len(player.deals) == 1


def test_advertise_without_relations_then_relate_fulfill():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 8, 10
    player.act(world, Command(action="deal"))
    assert len(player.deals) == 1
    player.act(world, Command(action="relate", target_id=friend.id))
    friend.act(world, Command(action="deal", target_id=player.id))
    assert player.deals == []
    assert player.meat == 14
    assert friend.fiber == 13


def test_self_fulfill_rejected():
    world, player, _friend = _pair()
    player.act(world, Command(action="deal"))
    with pytest.raises(ActError) as raised:
        player.act(world, Command(action="deal", target_id=player.id))
    assert raised.value.code == "invalid_command"
    assert len(player.deals) == 1


def test_deal_not_clamped():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 8, 10
    player.relations = [friend.id]
    friend.relations = [player.id]
    player.act(world, Command(action="deal"))
    friend.act(world, Command(action="deal", target_id=player.id))
    assert friend.meat == -1


def test_npc_prefers_fulfill_over_advertise():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 8, 10
    player.relations = [friend.id]
    friend.relations = [player.id]
    player.act(world, Command(action="deal"))
    friend.weights = [0.0, 1.0, 0.0]
    friend.act(world, None)
    assert player.deals == []
    assert friend.deals == []
    assert friend.last_target == player.id


def test_npc_decide_false_leaves_listing_and_advertises():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 2, 10
    player.relations = [friend.id]
    friend.relations = [player.id]
    player.act(world, Command(action="deal"))
    listed = player.deals[0].id
    friend.weights = [0.0, 1.0, 0.0]
    friend.act(world, None)
    assert [offer.id for offer in player.deals] == [listed]
    assert len(friend.deals) == 1


def test_listing_survives_produce():
    world, player, _friend = _pair()
    player.act(world, Command(action="deal"))
    offer_id = player.deals[0].id
    for _ in range(3):
        player.act(world, Command(action="produce"))
    assert [offer.id for offer in player.deals] == [offer_id]


def test_reset_clears_deals():
    world, player, _friend = _pair()
    player.act(world, Command(action="deal"))
    world.reset(seed=1, population=2)
    for s in world.survivors():
        assert s.deals == []


def test_two_identical_slots_fulfill_twice():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 8, 10
    player.relations = [friend.id]
    friend.relations = [player.id]
    player.act(world, Command(action="deal"))
    player.act(world, Command(action="deal"))
    assert len(player.deals) == 2
    friend.act(world, Command(action="deal", target_id=player.id))
    assert len(player.deals) == 1
    friend.act(world, Command(action="deal", target_id=player.id))
    assert player.deals == []


def test_relate_bidirectional():
    world, a, b = _pair()
    a.act(world, Command(action="relate", target_id=b.id))
    assert b.id in a.relations
    assert a.id in b.relations
    assert a.last_target == b.id
    assert a.action == "relate"


def test_produce_clears_last_target():
    world, a, b = _pair()
    a.last_target = b.id
    a.act(world, Command(action="produce"))
    assert a.last_target is None
