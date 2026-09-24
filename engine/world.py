from __future__ import annotations

import random

from engine.dna import Dna
from engine.events import Event
from engine.registry import Registry
from engine.survivor import ActError, Command, Survivor

EVENT_RING = 200


class World:
    def __init__(self, population=10, seed=None, control_id=1, spectate_only=False):
        self.seed = seed
        self.population_cap = population
        self.spectate_only = spectate_only
        self.rng = random.Random(seed)
        self.registry = Registry(rng=self.rng)
        self.dna = Dna(rng=self.rng)
        self.tick_index = 0
        self.control_id: int | None
        self.pending_possess: bool = False
        self.died_as_name: str | None = None
        self.spectate_id: int | None
        self.events: list[Event] = []
        self._next_event_id = 1
        self._spawn_initial(population)
        if spectate_only:
            self.control_id = None
            self.pending_possess = False
            self.spectate_id = 1
        else:
            self.control_id = control_id if control_id is not None else 1
            self.spectate_id = self.control_id

    def _spawn_initial(self, population: int) -> None:
        # Spawn RNG: Dna is already constructed (26 laws + 10 rules).
        # Per survivor: specialty, make_weights(3), make_word(6), unique_id.
        # Per-tick NPC RNG: (1) choice(options, weights) (2) always random_target()
        # even on produce/deal. Deal no longer draws rng.choice(relations).
        for _ in range(population):
            survivor = Survivor(self)
            self.registry.add_member("survivors", survivor)

    def survivors(self) -> list[Survivor]:
        return self.registry.get_members("survivors")

    def _emit(self, kind: str, **kwargs) -> None:
        event = Event(
            event_id=self._next_event_id,
            tick=self.tick_index,
            kind=kind,
            **kwargs,
        )
        self._next_event_id += 1
        self.events.append(event)
        if len(self.events) > EVENT_RING:
            self.events = self.events[-EVENT_RING:]

    def living_human_ids(self, human_ids: set[int] | None = None) -> list[int]:
        humans = self._human_set(human_ids)
        return [
            s.id
            for s in self.survivors()
            if s.alive() and s.id in humans
        ]

    def _human_set(self, human_ids: set[int] | None = None) -> set[int]:
        if human_ids is not None:
            return set(human_ids)
        if self.control_id is not None:
            return {self.control_id}
        return set()

    def _clock_mode(self, human_ids: set[int] | None = None) -> str:
        if not self.survivors():
            return "extinct"
        if self.pending_possess:
            return "awaiting_possess"
        if self.living_human_ids(human_ids):
            return "awaiting_player"
        return "watching"

    def validate_player_command(
        self, cmd: Command, actor_id: int | None = None
    ) -> None:
        aid = self.control_id if actor_id is None else actor_id
        actor = self.registry.get_member("survivors", aid)
        if actor is None:
            raise ActError("invalid_command", "no seated player")
        if cmd.action not in actor.options:
            raise ActError("invalid_command", "action not in options")
        if cmd.action == "relate":
            if cmd.target_id is None or cmd.target_id == actor.id:
                raise ActError(
                    "invalid_command",
                    "deal/relate need a living non-self target",
                )
            target = self.registry.get_member("survivors", cmd.target_id)
            if target is None or not target.alive():
                raise ActError("unknown_target", f"id {cmd.target_id} is not living")
            if cmd.target_id in actor.relations:
                raise ActError("invalid_command", "already related")
            return
        if cmd.action == "deal":
            if cmd.target_id is None:
                return
            if cmd.target_id == actor.id:
                raise ActError(
                    "invalid_command",
                    "deal/relate need a living non-self target",
                )
            target = self.registry.get_member("survivors", cmd.target_id)
            if target is None or not target.alive():
                raise ActError("unknown_target", f"id {cmd.target_id} is not living")
            if cmd.target_id not in actor.relations:
                raise ActError("unknown_target", "not in relations")
            if cmd.offer_id is None:
                if not target.deals:
                    raise ActError("unknown_target", "no matching offer")
            elif not any(offer.id == cmd.offer_id for offer in target.deals):
                raise ActError("unknown_target", "no matching offer")

    def tick(
        self,
        player_command: Command | dict | None = None,
        human_ids: set[int] | None = None,
    ) -> dict:
        if isinstance(player_command, dict):
            commands = dict(player_command)
            for actor_id, cmd in commands.items():
                self.validate_player_command(cmd, actor_id=actor_id)
        else:
            commands = {}
            if self.control_id is not None:
                cmd = (
                    player_command
                    if player_command is not None
                    else Command(action="produce")
                )
                self.validate_player_command(cmd, actor_id=self.control_id)
                commands[self.control_id] = cmd
        humans = self._human_set(human_ids) | set(commands)
        living = [s for s in self.survivors() if s.health > 0]
        for s in living:
            s.live()
            if s.id in commands:
                s.act(self, commands[s.id])
            else:
                s.act(self, None)
        dead_ids: list[int] = []
        dead_humans: list[int] = []
        for s in list(self.survivors()):
            if not s.alive():
                dead_ids.append(s.id)
                self._emit(kind="death", actor=s.id, name=s.name)
                if s.id in humans:
                    dead_humans.append(s.id)
                if s.id == self.control_id:
                    self.died_as_name = s.name
                    self.control_id = None
                    self.pending_possess = True
                self.registry.del_member("survivors", s)
        if dead_ids:
            dead = set(dead_ids)
            for s in self.survivors():
                s.relations = [rid for rid in s.relations if rid not in dead]
                if s.last_target in dead:
                    s.last_target = None
        if not self.survivors():
            self.pending_possess = False
            self.control_id = None
        self.tick_index += 1
        remaining_humans = humans - set(dead_humans)
        snap = self.snapshot(human_ids=remaining_humans)
        snap["_dead_humans"] = dead_humans
        return snap

    def pick_successor(self, claimed: set[int] | None = None) -> int | None:
        blocked = set(claimed or ())
        living = [
            s for s in self.survivors() if s.alive() and s.id not in blocked
        ]
        if not living:
            return None
        return max(living, key=lambda s: (s.health, -s.id)).id

    def unclaimed_living(self, claimed: set[int] | None = None) -> list:
        blocked = set(claimed or ())
        return [s for s in self.survivors() if s.alive() and s.id not in blocked]

    def possess(self, survivor_id: int, claimed: set[int] | None = None) -> None:
        target = self.registry.get_member("survivors", survivor_id)
        if target is None or not target.alive():
            raise ActError("unknown_target", f"id {survivor_id} is not living")
        blocked = set(claimed or ())
        if survivor_id in blocked:
            raise ActError("unknown_target", f"id {survivor_id} is already seated")
        self.control_id = survivor_id
        self.spectate_id = survivor_id
        self.pending_possess = False
        self.died_as_name = None
        self._emit(kind="possess", actor=survivor_id)

    def release(self) -> None:
        self.control_id = None
        self.pending_possess = False
        self._emit(kind="release")

    def spectate(self, survivor_id: int) -> None:
        target = self.registry.get_member("survivors", survivor_id)
        if target is None or not target.alive():
            raise ActError("unknown_target", f"id {survivor_id} is not living")
        self.spectate_id = survivor_id

    def reset(self, seed: int | None = None, population: int = 10) -> None:
        next_event_id = self._next_event_id
        spectate_only = self.spectate_only
        self.__init__(
            population=population,
            seed=seed,
            control_id=1,
            spectate_only=spectate_only,
        )
        self._next_event_id = next_event_id
        self._emit(kind="reset")

    def snapshot(
        self,
        viewer_id: int | None = None,
        human_ids: set[int] | None = None,
    ) -> dict:
        humans = self._human_set(human_ids)
        viewer = self.control_id if viewer_id is None else viewer_id
        survivors = []
        for s in self.survivors():
            survivors.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "health": s.health,
                    "meat": s.meat,
                    "water": s.water,
                    "fiber": s.fiber,
                    "produce": s.produce,
                    "action": s.action,
                    "last_target": s.last_target,
                    "relations": list(s.relations),
                    "deals": [offer.as_dict() for offer in s.deals],
                    "is_player": s.id in humans,
                    "alive": s.alive(),
                }
            )
        actor = None
        if viewer is not None:
            actor = self.registry.get_member("survivors", viewer)
        if actor is None and self.spectate_id is not None:
            actor = self.registry.get_member("survivors", self.spectate_id)
        deal_preview = {
            "excess": actor.excess() if actor else None,
            "need": actor.need() if actor else None,
            "accept_if": "counterpart[need] > counterpart[excess] - 1",
        }
        return {
            "v": 1,
            "tick": self.tick_index,
            "seed": self.seed,
            "clock": {"mode": self._clock_mode(humans)},
            "control_id": self.control_id if viewer_id is None else viewer_id,
            "spectate_id": self.spectate_id,
            "pending_possess": self.pending_possess,
            "died_as_name": self.died_as_name,
            "population": len(survivors),
            "survivors": survivors,
            "events": [e.as_dict() for e in self.events],
            "deal_preview": deal_preview,
            "humans": sorted(humans),
        }
