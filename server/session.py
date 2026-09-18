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
EMPTY_GRACE_S = 60.0

log = logging.getLogger("evolvevisualizer.session")


class Lobby:
    def __init__(
        self,
        lobby_id: str,
        seed: int | None = None,
        spectate_only: bool = False,
    ):
        self.id = lobby_id
        self.world = World(population=10, seed=seed, spectate_only=spectate_only)
        self.lock = asyncio.Lock()
        self.clients: dict[str, Session] = {}
        self.host_sid: str | None = None
        self.speed = DEFAULT_SPEED
        self._paused = False
        self._wake = asyncio.Event()
        self._clock_task: asyncio.Task | None = None
        self._closed = False
        self._empty_since: float | None = None

    def claimed(self) -> set[int]:
        return {c.seat_id for c in self.clients.values() if c.seat_id is not None}

    def living_seats(self) -> list[Session]:
        living = {s.id for s in self.world.survivors() if s.alive()}
        return [
            c
            for c in self.clients.values()
            if c.seat_id is not None and c.seat_id in living
        ]

    def host(self) -> Session | None:
        if self.host_sid is None:
            return None
        return self.clients.get(self.host_sid)

    def sync_host_control(self) -> None:
        host = self.host()
        if host is None:
            return
        self.world.control_id = host.seat_id
        self.world.pending_possess = host.pending_possess
        self.world.died_as_name = host.died_as_name
        if host.spectate_id is not None:
            self.world.spectate_id = host.spectate_id

    def summary(self) -> dict:
        world = self.world
        alive = len(world.survivors())
        humans = len(self.living_seats())
        open_seats = len(world.unclaimed_living(self.claimed()))
        host = self.host()
        host_name = None
        if host and host.seat_id is not None:
            member = world.registry.get_member("survivors", host.seat_id)
            if member is not None:
                host_name = member.name
        elif world.survivors():
            host_name = world.survivors()[0].name
        extinct = alive == 0
        return {
            "id": self.id,
            "tick": world.tick_index,
            "alive": alive,
            "humans": humans,
            "open_seats": open_seats,
            "seed": world.seed,
            "host_name": host_name,
            "joinable": open_seats > 0 and not extinct,
        }

    def clock_mode_for(self, session: Session) -> str:
        if not self.world.survivors():
            return "extinct"
        if session.pending_possess:
            return "awaiting_possess"
        if self._paused:
            return "pause"
        if self.living_seats():
            return "awaiting_player"
        return "watching"

    async def broadcast(self) -> None:
        for client in list(self.clients.values()):
            if client._closed:
                continue
            try:
                await client._send_snapshot()
            except Exception:
                client._closed = True

    async def maybe_tick(self) -> bool:
        seats = self.living_seats()
        if not seats:
            return False
        commands: dict[int, Command] = {}
        for client in seats:
            if client.submitted is not None:
                commands[client.seat_id] = client.submitted
            elif client._timed_out():
                commands[client.seat_id] = Command(action="produce")
            else:
                return False
        for client in seats:
            client.submitted = None
        humans = self.claimed()
        snap = self.world.tick(commands, human_ids=humans)
        dead = set(snap.pop("_dead_humans", []))
        names = {
            ev.actor: ev.name
            for ev in self.world.events
            if ev.kind == "death" and ev.actor in dead
        }
        for client in list(self.clients.values()):
            if client.seat_id in dead:
                client.pending_possess = True
                client.died_as_name = names.get(client.seat_id)
                client.seat_id = None
                client.submitted = None
        for client in seats:
            if client.seat_id is not None:
                client._arm_timeout()
        self.sync_host_control()
        await self.broadcast()
        return True

    async def npc_tick(self) -> None:
        if self.living_seats():
            return
        self.world.tick(None, human_ids=self.claimed())
        self.sync_host_control()
        await self.broadcast()

    def pick_seat(self, *, host: bool, spectate_only: bool) -> int | None:
        if spectate_only:
            return None
        claimed = self.claimed()
        if host and self.world.registry.get_member("survivors", 1) is not None:
            if 1 not in claimed:
                return 1
        free = self.world.unclaimed_living(claimed)
        if not free:
            return None
        return self.world.rng.choice(free).id

    async def attach(self, session: Session, spectate_only: bool) -> str | None:
        host = not self.clients
        seat = self.pick_seat(host=host, spectate_only=spectate_only)
        if not spectate_only and seat is None:
            return "lobby full"
        session.lobby = self
        session.seat_id = seat
        session.spectate_id = seat if seat is not None else 1
        session.pending_possess = False
        self.clients[session.sid] = session
        if host:
            self.host_sid = session.sid
            if spectate_only:
                self.world.control_id = None
                self.world.spectate_only = True
                self.world.spectate_id = 1
                self.world.pending_possess = False
            else:
                self.world.control_id = seat
                self.world.spectate_id = seat
                self.world.spectate_only = False
        self._empty_since = None
        if self._clock_task is None:
            self._clock_task = asyncio.create_task(self._clock_loop())
        return None

    async def detach(self, session: Session) -> None:
        self.clients.pop(session.sid, None)
        self.commands_drop(session)
        if self.host_sid == session.sid:
            self.host_sid = next(iter(self.clients), None)
        self.sync_host_control()
        if not self.clients:
            self._empty_since = time.monotonic()
        else:
            await self.broadcast()
            self._wake.set()

    def commands_drop(self, session: Session) -> None:
        session.submitted = None

    async def _clock_loop(self) -> None:
        try:
            while not self._closed:
                self._wake.clear()
                async with self.lock:
                    delay = self._next_delay()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=delay)
                    continue
                except asyncio.TimeoutError:
                    pass
                drop = False
                async with self.lock:
                    if self._closed:
                        return
                    if self._empty_since is not None:
                        if time.monotonic() - self._empty_since >= EMPTY_GRACE_S:
                            self._closed = True
                            drop = True
                        else:
                            continue
                if drop:
                    async with _SESSIONS_LOCK:
                        if LOBBIES.get(self.id) is self:
                            LOBBIES.pop(self.id, None)
                    return
                async with self.lock:
                    if self._closed:
                        return
                    if self._empty_since is not None:
                        continue
                    mode = "watching"
                    if self.living_seats():
                        mode = "awaiting_player"
                    if not self.world.survivors():
                        mode = "extinct"
                    if self._paused and mode != "extinct":
                        await self.broadcast()
                        continue
                    if mode == "watching":
                        await self.npc_tick()
                    elif mode == "awaiting_player":
                        ticked = await self.maybe_tick()
                        if not ticked:
                            await self.broadcast()
                    else:
                        await self.broadcast()
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            return

    def _next_delay(self) -> float:
        if self._empty_since is not None:
            remaining = EMPTY_GRACE_S - (time.monotonic() - self._empty_since)
            return max(0.05, remaining)
        if self._paused:
            return HEARTBEAT_S
        if not self.living_seats() and self.world.survivors():
            return max(0.05, 1.0 / self.speed)
        soonest = HEARTBEAT_S
        for client in self.living_seats():
            if client.submitted is not None:
                continue
            if client.timeout_ms == 0:
                continue
            rem = client._timeout_remaining_ms() / 1000.0
            if rem <= 0:
                soonest = min(soonest, 0.05)
            else:
                soonest = min(soonest, rem)
        return max(0.05, soonest)

    async def shutdown(self) -> None:
        self._closed = True
        self._wake.set()
        task = self._clock_task
        self._clock_task = None
        current = asyncio.current_task()
        if task is None or task is current:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class Session:
    def __init__(self, ws: WebSocket):
        self.sid = uuid.uuid4().hex
        self.ws = ws
        self.lobby: Lobby | None = None
        self.seat_id: int | None = None
        self.spectate_id: int | None = None
        self.pending_possess = False
        self.died_as_name: str | None = None
        self.timeout_ms = DEFAULT_TIMEOUT_MS
        self._timeout_deadline: float | None = None
        self._frozen_remaining_ms: int | None = None
        self._msg_times: deque[float] = deque()
        self._closed = False
        self.submitted: Command | None = None

    @property
    def world(self) -> World:
        assert self.lobby is not None
        return self.lobby.world

    @property
    def lock(self) -> asyncio.Lock:
        assert self.lobby is not None
        return self.lobby.lock

    def clock_mode(self) -> str:
        assert self.lobby is not None
        return self.lobby.clock_mode_for(self)

    def _is_host(self) -> bool:
        return self.lobby is not None and self.lobby.host_sid == self.sid

    def _timed_out(self) -> bool:
        if self.timeout_ms == 0:
            return False
        if self.lobby and self.lobby._paused:
            return False
        return self._timeout_remaining_ms() <= 0

    def _timeout_remaining_ms(self) -> int:
        if self.timeout_ms == 0:
            return 0
        if self.lobby and self.lobby._paused:
            if self._frozen_remaining_ms is not None:
                return max(0, int(self._frozen_remaining_ms))
            return self.timeout_ms
        if self.clock_mode() != "awaiting_player" or self._timeout_deadline is None:
            return self.timeout_ms
        remaining = int(round((self._timeout_deadline - time.monotonic()) * 1000))
        return max(0, remaining)

    def waiting_ids(self) -> list[int]:
        assert self.lobby is not None
        waiting = []
        for client in self.lobby.living_seats():
            if client.submitted is None and not client._timed_out():
                waiting.append(client.seat_id)
        return sorted(x for x in waiting if x is not None)

    def build_snapshot(self) -> dict:
        assert self.lobby is not None
        humans = self.lobby.claimed()
        snap = self.world.snapshot(viewer_id=self.seat_id, human_ids=humans)
        snap["control_id"] = self.seat_id
        snap["spectate_id"] = self.spectate_id
        snap["pending_possess"] = self.pending_possess
        snap["died_as_name"] = self.died_as_name
        snap["humans"] = sorted(humans)
        snap["host"] = self._is_host()
        snap["waiting"] = self.waiting_ids()
        snap["lobby_id"] = self.lobby.id
        snap["clock"] = ClockState(
            mode=self.clock_mode(),
            speed=self.lobby.speed,
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
        if self.lobby and self.lobby._paused:
            self._frozen_remaining_ms = self.timeout_ms
            self._timeout_deadline = None
            return
        self._timeout_deadline = time.monotonic() + self.timeout_ms / 1000.0
        self._frozen_remaining_ms = None

    def _pause(self) -> None:
        assert self.lobby is not None
        if self.lobby._paused:
            return
        for client in self.lobby.clients.values():
            client._frozen_remaining_ms = client._timeout_remaining_ms()
            client._timeout_deadline = None
        self.lobby._paused = True

    def _play(self) -> None:
        assert self.lobby is not None
        if not self.lobby._paused:
            return
        self.lobby._paused = False
        now = time.monotonic()
        for client in self.lobby.clients.values():
            remaining = client._frozen_remaining_ms
            client._frozen_remaining_ms = None
            if client.clock_mode() == "awaiting_player" and client.timeout_ms != 0:
                if remaining is None:
                    remaining = client.timeout_ms
                client._timeout_deadline = now + remaining / 1000.0
            else:
                client._timeout_deadline = None

    def _rate_ok(self) -> bool:
        now = time.monotonic()
        self._msg_times.append(now)
        cutoff = now - 1.0
        while self._msg_times and self._msg_times[0] < cutoff:
            self._msg_times.popleft()
        return len(self._msg_times) <= MAX_MSG_PER_SEC

    async def _send_json(self, data: dict) -> None:
        await self.ws.send_json(data)

    async def _send_snapshot(self) -> None:
        await self._send_json(self.build_snapshot())

    async def _send_error(self, error: str, detail: str = "") -> None:
        await self._send_json(error_frame(error, detail))

    async def _step(self) -> None:
        assert self.lobby is not None
        if self.lobby.living_seats() or self.pending_possess or not self.world.survivors():
            await self._send_error("invalid_command", "step disabled")
            return
        await self.lobby.npc_tick()
        self._pause()

    async def _handle_act(self, cmd: ActCommand) -> None:
        assert self.lobby is not None
        try:
            validate_act(
                cmd,
                clock_mode=self.clock_mode(),
                actor_id=self.seat_id,
            )
            if self.seat_id is None:
                raise ProtocolError("invalid_command", "no seated player")
            command = Command(action=cmd.action, target_id=cmd.target_id)
            self.world.validate_player_command(command, actor_id=self.seat_id)
        except ProtocolError as exc:
            await self._send_error(exc.error, exc.detail)
            return
        except ActError as exc:
            await self._send_error(exc.code, exc.detail)
            return
        self.submitted = command
        await self.lobby.maybe_tick()
        if self.submitted is not None:
            await self.lobby.broadcast()

    async def _handle_possess(self, cmd: PossessCommand) -> None:
        assert self.lobby is not None
        claimed = self.lobby.claimed()
        if self.seat_id is not None:
            claimed.discard(self.seat_id)
        target = self.world.registry.get_member("survivors", cmd.id)
        if target is None or not target.alive():
            await self._send_error("unknown_target", f"id {cmd.id} is not living")
            return
        if cmd.id in claimed:
            await self._send_error("unknown_target", f"id {cmd.id} is already seated")
            return
        self.seat_id = cmd.id
        self.spectate_id = cmd.id
        self.pending_possess = False
        self.died_as_name = None
        self.world._emit(kind="possess", actor=cmd.id)
        self.lobby.sync_host_control()
        self._arm_timeout()
        await self.lobby.broadcast()

    async def _handle_release(self) -> None:
        assert self.lobby is not None
        if self.seat_id is not None or self.pending_possess:
            self.world._emit(kind="release")
        self.seat_id = None
        self.pending_possess = False
        self.submitted = None
        self.died_as_name = None
        self._timeout_deadline = None
        self.lobby.sync_host_control()
        await self.lobby.broadcast()

    async def _handle_spectate(self, cmd: SpectateCommand) -> None:
        target = self.world.registry.get_member("survivors", cmd.id)
        if target is None or not target.alive():
            await self._send_error("unknown_target", f"id {cmd.id} is not living")
            return
        self.spectate_id = cmd.id
        if self._is_host():
            self.world.spectate_id = cmd.id
        await self.lobby.broadcast()

    async def _handle_clock(self, cmd: ClockCommand) -> None:
        assert self.lobby is not None
        if not self._is_host():
            await self._send_error("invalid_command", "host only")
            return
        if cmd.speed is not None:
            self.lobby.speed = cmd.speed
        if cmd.timeout_ms is not None:
            self.timeout_ms = cmd.timeout_ms
            for client in self.lobby.clients.values():
                client.timeout_ms = cmd.timeout_ms
                if client.clock_mode() == "awaiting_player":
                    if self.lobby._paused:
                        client._frozen_remaining_ms = client.timeout_ms
                    else:
                        client._arm_timeout()
        if cmd.mode == "pause":
            self._pause()
        elif cmd.mode == "play":
            self._play()
        elif cmd.mode == "step":
            await self._step()
            return
        await self.lobby.broadcast()

    async def _handle_reset(self, cmd: ResetCommand) -> None:
        assert self.lobby is not None
        if not self._is_host():
            await self._send_error("invalid_command", "host only")
            return
        self.world.reset(seed=cmd.seed)
        seated = [c for c in self.lobby.clients.values() if not c._closed]
        claimed: set[int] = set()
        host = self.lobby.host()
        if host is not None:
            host.seat_id = 1
            host.spectate_id = 1
            host.pending_possess = False
            host.died_as_name = None
            host.submitted = None
            claimed.add(1)
        for client in seated:
            if client is host:
                continue
            free = self.world.unclaimed_living(claimed)
            if not free:
                client.seat_id = None
                continue
            pick = self.world.rng.choice(free).id
            client.seat_id = pick
            client.spectate_id = pick
            claimed.add(pick)
            client.pending_possess = False
            client.died_as_name = None
            client.submitted = None
        self.lobby._paused = False
        self.lobby.sync_host_control()
        for client in seated:
            client._arm_timeout()
        await self.lobby.broadcast()

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
        async with self.lock:
            oversize = len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES
            allowed = self._rate_ok()
            if not allowed:
                await self._send_error("rate_limited", "max 20 messages per second")
                return
            if oversize:
                await self._send_error("message_too_large", "max 8 KiB")
                return
            try:
                parsed = parse_message(raw)
            except ProtocolError as exc:
                await self._send_error(exc.error, exc.detail)
                return
            await self._handle(parsed)
        if self.lobby is not None:
            self.lobby._wake.set()

    async def run(self) -> None:
        await self.ws.accept()
        self._arm_timeout()
        log.info("session start sid=%s lobby=%s", self.sid, self.lobby.id if self.lobby else None)
        try:
            async with self.lock:
                await self._send_snapshot()
            while True:
                raw = await self.ws.receive_text()
                await self._on_message(raw)
        except WebSocketDisconnect:
            pass

    async def shutdown(self) -> None:
        self._closed = True
        log.info("session stop sid=%s", self.sid)


SESSIONS: dict[str, Session] = {}
LOBBIES: dict[str, Lobby] = {}
_SESSIONS_LOCK = asyncio.Lock()


def session_count() -> int:
    return len(SESSIONS)


def list_lobbies() -> list[dict]:
    rows = []
    for lobby in LOBBIES.values():
        if not lobby.clients:
            continue
        if lobby.id.startswith("sf-"):
            continue
        rows.append(lobby.summary())
    rows.sort(key=lambda row: row["tick"], reverse=True)
    return rows


async def create_lobby(seed: int | None = None) -> Lobby:
    async with _SESSIONS_LOCK:
        if len(LOBBIES) >= MAX_SESSIONS:
            raise ActError("unavailable", "max lobbies")
        lobby_id = uuid.uuid4().hex[:8]
        while lobby_id in LOBBIES:
            lobby_id = uuid.uuid4().hex[:8]
        lobby = Lobby(lobby_id, seed=seed, spectate_only=False)
        lobby._empty_since = time.monotonic()
        lobby._clock_task = asyncio.create_task(lobby._clock_loop())
        LOBBIES[lobby_id] = lobby
        return lobby


def parse_ws_query(ws: WebSocket) -> tuple[int | None, bool, str | None]:
    seed_raw = ws.query_params.get("seed")
    seed = None
    if seed_raw not in (None, ""):
        try:
            seed = int(seed_raw)
        except (TypeError, ValueError):
            seed = None
    spectate_only = ws.query_params.get("spectate") == "1"
    lobby_id = ws.query_params.get("lobby") or None
    return seed, spectate_only, lobby_id


async def reject_websocket(ws: WebSocket, code: int) -> None:
    await ws.accept()
    await ws.close(code=code)


async def snapshot_by_sid(sid: str | None) -> dict | None:
    if not sid:
        return None
    async with _SESSIONS_LOCK:
        sess = SESSIONS.get(sid)
    if sess is None:
        return None
    async with sess.lock:
        return sess.build_snapshot()


async def run_session(ws: WebSocket) -> None:
    seed, spectate_only, lobby_id = parse_ws_query(ws)
    session = Session(ws)
    async with _SESSIONS_LOCK:
        if lobby_id:
            lobby = LOBBIES.get(lobby_id)
            if lobby is None or lobby._closed:
                if len(LOBBIES) >= MAX_SESSIONS:
                    await reject_websocket(ws, 1013)
                    return
                lobby = Lobby(lobby_id, seed=seed, spectate_only=spectate_only)
                LOBBIES[lobby_id] = lobby
        else:
            if len(LOBBIES) >= MAX_SESSIONS:
                await reject_websocket(ws, 1013)
                return
            lobby_id = uuid.uuid4().hex[:8]
            while lobby_id in LOBBIES:
                lobby_id = uuid.uuid4().hex[:8]
            lobby = Lobby(lobby_id, seed=seed, spectate_only=spectate_only)
            LOBBIES[lobby_id] = lobby
        SESSIONS[session.sid] = session
    async with lobby.lock:
        err = await lobby.attach(session, spectate_only)
    if err:
        async with _SESSIONS_LOCK:
            SESSIONS.pop(session.sid, None)
        await reject_websocket(ws, 1013)
        return
    try:
        await session.run()
    finally:
        await session.shutdown()
        async with lobby.lock:
            await lobby.detach(session)
        async with _SESSIONS_LOCK:
            SESSIONS.pop(session.sid, None)
