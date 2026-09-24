from __future__ import annotations

from dataclasses import dataclass

from engine.dna import make_word


MAX_DEALS = 5


@dataclass
class Command:
    action: str
    target_id: int | None = None
    offer_id: int | None = None


@dataclass
class Offer:
    id: int
    give: str
    get: str
    posted_tick: int

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "give": self.give,
            "get": self.get,
            "posted_tick": self.posted_tick,
        }


class ActError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(detail)


class Survivor:
    def __init__(self, world, **kwargs):
        self.action = "none"
        self.health = 20
        self.meat = 20
        self.water = 20
        self.fiber = 20
        self.isplayer = 0
        self.trade = ["meat", "water", "fiber"]
        self.produce = world.rng.choice(["meat", "water", "fiber"])
        self.options = ["produce", "deal", "relate"]
        self.weights = world.registry.make_weights(len(self.options))
        self.relations = []
        self.last_target = None
        self.deals: list[Offer] = []
        self._next_offer_id = 1
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, "name"):
            self.name = make_word(6, world.rng)
        self.id = world.registry.unique_id()

    def __str__(self):
        out_string = (
            str(self.id)
            + " "
            + self.name
            + " Health:"
            + str(self.health)
            + " Goods: m"
            + str(self.meat)
            + " w"
            + str(self.water)
            + " f"
            + str(self.fiber)
            + " Do:"
            + self.action
        )
        if self.isplayer:
            out_string = out_string + " ME"
        return out_string

    def alive(self):
        return self.health > 0

    def act(self, world, command: Command | None = None) -> None:
        if command is None:
            action = world.registry.choice(self.options, self.weights)
            self.action = action
            target = self.random_target(world)
            if action == "produce":
                self.last_target = None
                setattr(self, self.produce, getattr(self, self.produce) + 20)
            elif action == "deal":
                self._npc_deal(world)
            elif action == "relate":
                if not target or target.id in self.relations:
                    return
                self._apply_relate(world, target)
            return

        if command.action not in self.options:
            raise ActError("invalid_command", "player command failed backstop")
        if command.action == "relate" and (
            command.target_id is None or command.target_id == self.id
        ):
            raise ActError("invalid_command", "player command failed backstop")
        if command.action == "deal" and command.target_id == self.id:
            raise ActError("invalid_command", "player command failed backstop")
        self.action = command.action
        if command.action == "produce":
            self.last_target = None
            setattr(self, self.produce, getattr(self, self.produce) + 20)
            world._emit(kind="produce", actor=self.id)
            return
        if command.action == "deal":
            if command.target_id is None:
                self._advertise(world)
            else:
                self._player_fulfill(world, command.target_id, command.offer_id)
        else:
            friend = world.registry.get_member("survivors", command.target_id)
            self._apply_relate(world, friend)

    def _advertise(self, world) -> None:
        self.last_target = None
        if len(self.deals) >= MAX_DEALS:
            dropped = self.deals.pop(0)
            world._emit(
                kind="unlist",
                actor=self.id,
                give=dropped.give,
                get=dropped.get,
                offer_id=dropped.id,
            )
        offer = Offer(
            id=self._next_offer_id,
            give=self.excess(),
            get=self.need(),
            posted_tick=world.tick_index,
        )
        self._next_offer_id += 1
        self.deals.append(offer)
        world._emit(
            kind="list",
            actor=self.id,
            give=offer.give,
            get=offer.get,
            offer_id=offer.id,
        )

    def _find_offer(self, publisher, offer_id: int | None) -> Offer | None:
        if not publisher.deals:
            return None
        if offer_id is None:
            return publisher.deals[0]
        for offer in publisher.deals:
            if offer.id == offer_id:
                return offer
        return None

    def _best_fulfillable(self, world) -> tuple | None:
        living = {s.id: s for s in world.survivors() if s.alive()}
        best = None
        for rid in self.relations:
            publisher = living.get(rid)
            if publisher is None:
                continue
            for offer in publisher.deals:
                if not self.decide(offer.give, offer.get, publisher):
                    continue
                key = (publisher.id, offer.id)
                if best is None or key < best[0]:
                    best = (key, publisher, offer)
        if best is None:
            return None
        return best[1], best[2]

    def _npc_deal(self, world) -> None:
        picked = self._best_fulfillable(world)
        if picked is None:
            self._advertise(world)
            return
        self._fulfill(world, picked[0], picked[1])

    def _player_fulfill(self, world, target_id: int, offer_id: int | None) -> None:
        publisher = world.registry.get_member("survivors", target_id)
        if publisher is None or not publisher.alive():
            raise ActError("unknown_target", f"id {target_id} is not living")
        if target_id not in self.relations:
            raise ActError("unknown_target", "not in relations")
        offer = self._find_offer(publisher, offer_id)
        if offer is None:
            raise ActError("unknown_target", "no matching offer")
        self._fulfill(world, publisher, offer)

    def _fulfill(self, world, publisher, offer: Offer) -> None:
        self.last_target = publisher.id
        setattr(publisher, offer.get, getattr(publisher, offer.get) + 10)
        setattr(publisher, offer.give, getattr(publisher, offer.give) - 9)
        setattr(self, offer.give, getattr(self, offer.give) + 10)
        setattr(self, offer.get, getattr(self, offer.get) - 9)
        publisher.deals = [row for row in publisher.deals if row.id != offer.id]
        world._emit(
            kind="deal",
            actor=publisher.id,
            target=self.id,
            give=offer.give,
            get=offer.get,
            accepted=True,
            offer_id=offer.id,
        )

    def _apply_relate(self, world, friend) -> None:
        self.last_target = friend.id
        if friend.id not in self.relations:
            self.relations.append(friend.id)
            friend.relations.append(self.id)
            world._emit(kind="relate", actor=self.id, target=friend.id)

    def decide(self, receive, give, friend):
        giving = getattr(self, give)
        receiving = getattr(self, receive)
        return giving > receiving - 1

    def excess(self):
        best = -1000000
        best_option = ""
        for option in self.trade:
            stock = getattr(self, option)
            if stock > best:
                best = getattr(self, option)
                best_option = option
        return best_option

    def need(self):
        best = 10000000
        best_option = ""
        for option in self.trade:
            stock = getattr(self, option)
            if stock < best:
                best = getattr(self, option)
                best_option = option
        return best_option

    def live(self) -> None:
        fed = min(self.meat, self.water, self.fiber) > 0
        self.meat = max(0, self.meat - 1)
        self.water = max(0, self.water - 1)
        self.fiber = max(0, self.fiber - 1)
        if fed:
            if self.health < 20:
                self.health += 2
        else:
            self.health -= 4

    def random_target(self, world):
        state = world.registry.get_members("survivors")
        valid = False
        target = 0
        while not valid:
            if len(state) < 2:
                return False
            else:
                target = world.rng.choice(state)
                if target.id != self.id:
                    return target
