from __future__ import annotations

from dataclasses import dataclass

from engine.dna import make_word


@dataclass
class Command:
    action: str
    target_id: int | None = None


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
                if not self.relations:
                    return
                target_id = world.rng.choice(self.relations)
                self._apply_deal(world, target_id)
            elif action == "relate":
                if not target or target.id in self.relations:
                    return
                self._apply_relate(world, target)
            return

        if command.action not in self.options or (
            command.action in ("deal", "relate")
            and (command.target_id is None or command.target_id == self.id)
        ):
            raise ActError("invalid_command", "player command failed backstop")
        self.action = command.action
        if command.action == "produce":
            self.last_target = None
            setattr(self, self.produce, getattr(self, self.produce) + 20)
            world._emit(kind="produce", actor=self.id)
            return
        if command.action == "deal":
            self._apply_deal(world, command.target_id)
        else:
            friend = world.registry.get_member("survivors", command.target_id)
            self._apply_relate(world, friend)

    def _apply_deal(self, world, target_id: int) -> None:
        self.last_target = target_id
        friend = world.registry.get_member("survivors", target_id)
        if friend:
            giving = self.excess()
            getting = self.need()
            decision = friend.decide(giving, getting, self)
            if decision:
                setattr(self, getting, getattr(self, getting) + 10)
                setattr(friend, giving, getattr(friend, giving) + 10)
                setattr(self, giving, getattr(self, giving) - 9)
                setattr(friend, getting, getattr(friend, getting) - 9)
            world._emit(
                kind="deal",
                actor=self.id,
                target=target_id,
                give=giving,
                get=getting,
                accepted=bool(decision),
            )
        else:
            if world.registry.get_members("survivors"):
                if target_id in self.relations:
                    self.relations.remove(target_id)

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
