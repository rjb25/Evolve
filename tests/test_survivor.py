from engine.survivor import Command
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


def test_deal_accept_moves_plus_ten_minus_nine():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 8, 10
    player.relations = [friend.id]
    friend.relations = [player.id]
    player.act(world, Command(action="deal", target_id=friend.id))
    assert player.meat == 14
    assert player.fiber == 3
    assert friend.meat == -1
    assert friend.fiber == 13
    assert player.last_target == friend.id
    assert player.action == "deal"


def test_deal_reject_no_goods_move_sets_last_target():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 2, 10
    player.relations = [friend.id]
    friend.relations = [player.id]
    player.act(world, Command(action="deal", target_id=friend.id))
    assert (player.fiber, player.meat, player.water) == (12, 4, 10)
    assert (friend.fiber, friend.meat, friend.water) == (3, 2, 10)
    assert player.last_target == friend.id
    assert player.action == "deal"


def test_deal_not_clamped():
    world, player, friend = _pair()
    player.fiber, player.meat, player.water = 12, 4, 10
    friend.fiber, friend.meat, friend.water = 3, 8, 10
    player.relations = [friend.id]
    friend.relations = [player.id]
    player.act(world, Command(action="deal", target_id=friend.id))
    assert friend.meat == -1


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
