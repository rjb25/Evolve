from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Event:
    event_id: int
    tick: int
    kind: str
    actor: int | None = None
    target: int | None = None
    name: str | None = None
    give: str | None = None
    get: str | None = None
    accepted: bool | None = None

    def as_dict(self) -> dict:
        data = {
            "event_id": self.event_id,
            "tick": self.tick,
            "kind": self.kind,
        }
        if self.actor is not None:
            data["actor"] = self.actor
        if self.target is not None:
            data["target"] = self.target
        if self.name is not None:
            data["name"] = self.name
        if self.give is not None:
            data["give"] = self.give
        if self.get is not None:
            data["get"] = self.get
        if self.accepted is not None:
            data["accepted"] = self.accepted
        return data
