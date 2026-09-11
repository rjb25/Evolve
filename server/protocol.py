from __future__ import annotations

import json
from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

MAX_MESSAGE_BYTES = 8 * 1024
SPEED_MIN = 0.5
SPEED_MAX = 20.0
MIN_TIMEOUT_MS = 250
OPS = frozenset({"act", "possess", "release", "spectate", "clock", "reset", "ping"})


class ProtocolError(ValueError):
    def __init__(self, error: str, detail: str = ""):
        self.error = error
        self.detail = detail
        super().__init__(detail)


class ActCommand(BaseModel):
    op: Literal["act"]
    action: Literal["produce", "deal", "relate"]
    target_id: int | None = None

    @model_validator(mode="after")
    def deal_relate_need_target(self) -> ActCommand:
        if self.action in ("deal", "relate") and self.target_id is None:
            raise ValueError("deal/relate need a living non-self target")
        return self


class PossessCommand(BaseModel):
    op: Literal["possess"]
    id: int


class ReleaseCommand(BaseModel):
    op: Literal["release"]


class SpectateCommand(BaseModel):
    op: Literal["spectate"]
    id: int


class ClockCommand(BaseModel):
    op: Literal["clock"]
    mode: Literal["play", "pause", "step"] | None = None
    speed: float | None = None
    timeout_ms: int | None = None

    @field_validator("speed")
    @classmethod
    def clamp_speed(cls, value: float | None) -> float | None:
        if value is None:
            return value
        return max(SPEED_MIN, min(SPEED_MAX, value))

    @field_validator("timeout_ms")
    @classmethod
    def timeout_non_negative(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value < 0:
            raise ValueError("timeout_ms must be >= 0")
        if value == 0:
            return 0
        return max(MIN_TIMEOUT_MS, value)


class ResetCommand(BaseModel):
    op: Literal["reset"]
    seed: int | None = None


class PingCommand(BaseModel):
    op: Literal["ping"]


ClientCommand = Annotated[
    Union[
        ActCommand,
        PossessCommand,
        ReleaseCommand,
        SpectateCommand,
        ClockCommand,
        ResetCommand,
        PingCommand,
    ],
    Field(discriminator="op"),
]

COMMAND_ADAPTER: TypeAdapter[ClientCommand] = TypeAdapter(ClientCommand)


class ClockState(BaseModel):
    mode: Literal["pause", "awaiting_player", "awaiting_possess", "watching", "extinct"]
    speed: float
    timeout_ms: int
    timeout_remaining_ms: int


class SurvivorRow(BaseModel):
    id: int
    name: str
    health: int
    meat: int
    water: int
    fiber: int
    produce: str
    action: str
    last_target: int | None
    relations: list[int]
    is_player: bool
    alive: bool


class EventRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    event_id: int
    tick: int
    kind: str
    actor: int | None = None
    target: int | None = None
    name: str | None = None
    give: str | None = None
    get: str | None = None
    accepted: bool | None = None


class DealPreview(BaseModel):
    excess: str | None = None
    need: str | None = None
    accept_if: str


class Snapshot(BaseModel):
    v: Literal[1] = 1
    tick: int
    seed: int | None = None
    clock: ClockState
    control_id: int | None
    spectate_id: int | None
    pending_possess: bool
    died_as_name: str | None
    population: int
    survivors: list[SurvivorRow]
    events: list[EventRecord]
    deal_preview: DealPreview


def error_frame(error: str, detail: str = "") -> dict:
    return {"v": 1, "error": error, "detail": detail}


def validate_act(
    cmd: ActCommand, *, clock_mode: str, actor_id: int | None
) -> None:
    if clock_mode != "awaiting_player":
        raise ProtocolError("invalid_command", "not awaiting player")
    if cmd.action in ("deal", "relate"):
        if cmd.target_id is None or (
            actor_id is not None and cmd.target_id == actor_id
        ):
            raise ProtocolError(
                "invalid_command",
                "deal/relate need a living non-self target",
            )


def _validation_detail(exc: ValidationError) -> str:
    err = exc.errors()[0]
    loc = ".".join(str(part) for part in err.get("loc", ()) if part != "op")
    msg = err.get("msg", "invalid command")
    if loc:
        return f"{loc}: {msg}"
    return msg


def parse_message(raw: str | bytes | dict) -> ClientCommand:
    if isinstance(raw, (str, bytes)):
        if isinstance(raw, bytes):
            if len(raw) > MAX_MESSAGE_BYTES:
                raise ProtocolError("message_too_large", "max 8 KiB")
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ProtocolError("invalid_json", "malformed JSON") from exc
        if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ProtocolError("message_too_large", "max 8 KiB")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProtocolError("invalid_json", "malformed JSON") from exc
    else:
        data = raw
    if not isinstance(data, dict):
        raise ProtocolError("invalid_command", "message must be an object")
    op = data.get("op")
    if op is None:
        raise ProtocolError("invalid_command", "missing op")
    if op not in OPS:
        raise ProtocolError("invalid_command", f"unknown op {op!r}")
    try:
        return COMMAND_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise ProtocolError("invalid_command", _validation_detail(exc)) from exc
