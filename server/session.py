from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from engine.survivor import ActError, Command
from engine.world import World
from server.protocol import (
    MAX_MESSAGE_BYTES,
    ActCommand,
    ClockCommand,
    ClockState,
    ClientCommand,
    PossessCommand,
    ProtocolError,
    ResetCommand,
    Snapshot,
    SpectateCommand,
    error_frame,
    parse_message,
    validate_act,
)

ALLOWED_WS_ORIGINS = {
    "https://roleplaycardgame.com",
    "http://127.0.0.1:8765",
    "http://localhost:8765",
}
MAX_SESSIONS = 50
MAX_MSG_PER_SEC = 20
DEFAULT_TIMEOUT_MS = 15000
DEFAULT_SPEED = 1.0
HEARTBEAT_S = 1.0

log = logging.getLogger("evolvevisualizer.session")


class Session:
    def __init__(
        self,
        ws: WebSocket,
        seed: int | None = None,
        spectate_only: bool = False,
    ):
        self.sid = uuid.uuid4().hex
        self.ws = ws
        self.world = World(population=10, seed=seed, spectate_only=spectate_only)
        self.lock = asyncio.Lock()
        self.speed = DEFAULT_SPEED
        self.timeout_ms = DEFAULT_TIMEOUT_MS
        self._paused = False
        self._timeout_deadline: float | None = None
        self._frozen_remaining_ms: int | None = None
        self._wake = asyncio.Event()
        self._clock_task: asyncio.Task | None = None
        self._msg_times: deque[float] = deque()
        self._closed = False

    def clock_mode(self) -> str:
        world_mode = self.world._clock_mode()
        if world_mode == "extinct":
            return "extinct"
        if self._paused:
            return "pause"
        return world_mode

    def _timeout_remaining_ms(self) -> int:
        if self.timeout_ms == 0:
            return 0
        if self._paused:
            if self._frozen_remaining_ms is not None:
                return max(0, int(self._frozen_remaining_ms))
            return self.timeout_ms
        if self.world._clock_mode() != "awaiting_player" or self._timeout_deadline is None:
            return self.timeout_ms
        remaining = int(round((self._timeout_deadline - time.monotonic()) * 1000))
        return max(0, remaining)

    def build_snapshot(self) -> dict:
        snap = self.world.snapshot()
        snap["clock"] = ClockState(
            mode=self.clock_mode(),
            speed=self.speed,
            timeout_ms=self.timeout_ms,
            timeout_remaining_ms=self._timeout_remaining_ms(),
        ).model_dump()
        out = Snapshot.model_validate(snap)
        dumped = out.model_dump()
        dumped["events"] = [ev.model_dump(exclude_none=True) for ev in out.events]
        return dumped

    def _arm_timeout(self) -> None:
        if self.timeout_ms == 0:
            self._timeout_deadline = None
            self._frozen_remaining_ms = None
            return
        if self._paused:
            self._frozen_remaining_ms = self.timeout_ms
            self._timeout_deadline = None
            return
        self._timeout_deadline = time.monotonic() + self.timeout_ms / 1000.0
        self._frozen_remaining_ms = None

    def _after_tick(self) -> None:
        if self.world._clock_mode() == "awaiting_player":
            self._arm_timeout()
        else:
            self._timeout_deadline = None

    def _pause(self) -> None:
        if self._paused:
            return
        remaining = self._timeout_remaining_ms()
        self._paused = True
        self._frozen_remaining_ms = remaining
        self._timeout_deadline = None

    def _play(self) -> None:
        if not self._paused:
            return
        remaining = self._frozen_remaining_ms
        self._paused = False
        self._frozen_remaining_ms = None
        if self.world._clock_mode() == "awaiting_player" and self.timeout_ms != 0:
            if remaining is None:
                remaining = self.timeout_ms
            self._timeout_deadline = time.monotonic() + remaining / 1000.0
        else:
            self._timeout_deadline = None

    def _rate_ok(self) -> bool:
        now = time.monotonic()
        self._msg_times.append(now)
        cutoff = now - 1.0
        while self._msg_times and self._msg_times[0] < cutoff:
            self._msg_times.popleft()
        return len(self._msg_times) <= MAX_MSG_PER_SEC

    def _next_delay(self) -> float | None:
        mode = self.clock_mode()
        if mode == "watching":
            return 1.0 / self.speed
        if mode == "awaiting_player" and self.timeout_ms != 0:
            return max(0.0, min(HEARTBEAT_S, self._timeout_remaining_ms() / 1000.0))
        return HEARTBEAT_S

    async def _send_json(self, data: dict) -> None:
        await self.ws.send_json(data)

    async def _send_snapshot(self) -> None:
        await self._send_json(self.build_snapshot())

    async def _send_error(self, error: str, detail: str = "") -> None:
        await self._send_json(error_frame(error, detail))

    async def _on_timer(self) -> None:
        mode = self.clock_mode()
        if mode == "watching":
            self.world.tick(None)
            self._after_tick()
            await self._send_snapshot()
            return
        if mode == "awaiting_player":
            if self.timeout_ms != 0 and self._timeout_remaining_ms() <= 0:
                self.world.tick(None)
                self._after_tick()
            await self._send_snapshot()
            return
        await self._send_snapshot()

    async def _clock_loop(self) -> None:
        try:
            while not self._closed:
                self._wake.clear()
                async with self.lock:
                    delay = self._next_delay()
                try:
                    if delay is None:
                        await self._wake.wait()
                        continue
                    await asyncio.wait_for(self._wake.wait(), timeout=delay)
                    continue
                except asyncio.TimeoutError:
                    pass
                async with self.lock:
                    if not self._closed:
                        await self._on_timer()
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            return

    async def _step(self) -> None:
        world_mode = self.world._clock_mode()
        if world_mode in ("awaiting_player", "awaiting_possess", "extinct"):
            await self._send_error("invalid_command", "step disabled")
            return
        self.world.tick(None)
        self._after_tick()
        self._pause()
        await self._send_snapshot()

    async def _handle_act(self, cmd: ActCommand) -> None:
        try:
            validate_act(
                cmd,
                clock_mode=self.clock_mode(),
                actor_id=self.world.control_id,
            )
            self.world.tick(Command(action=cmd.action, target_id=cmd.target_id))
        except ProtocolError as exc:
            await self._send_error(exc.error, exc.detail)
            return
        except ActError as exc:
            await self._send_error(exc.code, exc.detail)
            return
        self._after_tick()
        await self._send_snapshot()

    async def _handle_possess(self, cmd: PossessCommand) -> None:
        try:
            self.world.possess(cmd.id)
        except ActError as exc:
            await self._send_error(exc.code, exc.detail)
            return
        if self.world._clock_mode() == "awaiting_player":
            self._arm_timeout()
        await self._send_snapshot()

    async def _handle_release(self) -> None:
        if self.world.control_id is not None or self.world.pending_possess:
            self.world.release()
            self._timeout_deadline = None
        await self._send_snapshot()

    async def _handle_spectate(self, cmd: SpectateCommand) -> None:
        try:
            self.world.spectate(cmd.id)
        except ActError as exc:
            await self._send_error(exc.code, exc.detail)
            return
        await self._send_snapshot()

    async def _handle_clock(self, cmd: ClockCommand) -> None:
        if cmd.speed is not None:
            self.speed = cmd.speed
        if cmd.timeout_ms is not None:
            self.timeout_ms = cmd.timeout_ms
            if self.world._clock_mode() == "awaiting_player":
                if self._paused:
                    self._frozen_remaining_ms = self.timeout_ms
                else:
                    self._arm_timeout()
        if cmd.mode == "pause":
            self._pause()
        elif cmd.mode == "play":
            self._play()
        elif cmd.mode == "step":
            await self._step()
            return
        await self._send_snapshot()

    async def _handle_reset(self, cmd: ResetCommand) -> None:
        self.world.reset(seed=cmd.seed)
        self._paused = False
        self._frozen_remaining_ms = None
        self._arm_timeout()
        await self._send_snapshot()

    async def _handle(self, cmd: ClientCommand) -> None:
        if isinstance(cmd, ActCommand):
            await self._handle_act(cmd)
        elif isinstance(cmd, PossessCommand):
            await self._handle_possess(cmd)
        elif isinstance(cmd, SpectateCommand):
            await self._handle_spectate(cmd)
        elif isinstance(cmd, ClockCommand):
            await self._handle_clock(cmd)
        elif isinstance(cmd, ResetCommand):
            await self._handle_reset(cmd)
        elif cmd.op == "release":
            await self._handle_release()
        else:
            await self._send_snapshot()

    async def _on_message(self, raw: str) -> None:
        if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
            await self._send_error("message_too_large", "max 8 KiB")
            return
        if not self._rate_ok():
            await self._send_error("rate_limited", "max 20 messages per second")
            return
        try:
            cmd = parse_message(raw)
        except ProtocolError as exc:
            await self._send_error(exc.error, exc.detail)
            return
        async with self.lock:
            await self._handle(cmd)
        self._wake.set()

    async def run(self) -> None:
        await self.ws.accept()
        self._arm_timeout()
        self._clock_task = asyncio.create_task(self._clock_loop())
        log.info("session start sid=%s seed=%s", self.sid, self.world.seed)
        try:
            await self._send_snapshot()
            while True:
                raw = await self.ws.receive_text()
                await self._on_message(raw)
        except WebSocketDisconnect:
            pass

    async def shutdown(self) -> None:
        self._closed = True
        self._wake.set()
        task = self._clock_task
        self._clock_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        log.info("session stop sid=%s", self.sid)


SESSIONS: dict[str, Session] = {}
_SESSIONS_LOCK = asyncio.Lock()


def session_count() -> int:
    return len(SESSIONS)


def parse_ws_query(ws: WebSocket) -> tuple[int | None, bool]:
    seed_raw = ws.query_params.get("seed")
    seed = None
    if seed_raw not in (None, ""):
        try:
            seed = int(seed_raw)
        except (TypeError, ValueError):
            seed = None
    spectate_only = ws.query_params.get("spectate") == "1"
    return seed, spectate_only


async def run_session(ws: WebSocket) -> None:
    seed, spectate_only = parse_ws_query(ws)
    session = Session(ws, seed=seed, spectate_only=spectate_only)
    async with _SESSIONS_LOCK:
        if len(SESSIONS) >= MAX_SESSIONS:
            await ws.close(code=1013)
            return
        SESSIONS[session.sid] = session
    try:
        await session.run()
    finally:
        await session.shutdown()
        SESSIONS.pop(session.sid, None)
