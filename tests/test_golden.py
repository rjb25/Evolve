from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from engine.world import World

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO_ROOT / "engine"
PREREFACTOR = REPO_ROOT / "tests" / "golden" / "prerefactor"
HARNESS = REPO_ROOT / "tests" / "golden" / "prerefactor_run.py"


def _run_frozen(*extra_args: str) -> dict:
    env = {**os.environ, "PYTHONPATH": str(PREREFACTOR)}
    proc = subprocess.run(
        [sys.executable, str(HARNESS), *extra_args],
        env=env,
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def _engine_bag(world: World) -> dict:
    names = {s.id: s.name for s in world.survivors()}
    bag = {}
    for s in world.survivors():
        rel = sorted(names[rid] for rid in s.relations if rid in names)
        bag[s.name] = [
            s.health,
            s.meat,
            s.water,
            s.fiber,
            s.produce,
            rel,
            s.action,
        ]
    return bag


def test_nostarve_bag_matches_frozen_copies():
    frozen = _run_frozen()
    world = World(seed=0, spectate_only=True)
    engine_bags = []
    for _ in range(frozen["ticks"]):
        world.tick()
        engine_bags.append(_engine_bag(world))
    assert engine_bags == frozen["bags"]
    assert frozen["ticks"] <= 50


def test_always_produce_three_tick_bag_pins_random_target_draw():
    frozen = _run_frozen("--always-produce")
    assert frozen["ticks"] == 3
    world = World(seed=0, spectate_only=True)
    for s in world.survivors():
        s.weights = [1.0, 0.0, 0.0]
    engine_bags = []
    for _ in range(3):
        world.tick()
        engine_bags.append(_engine_bag(world))
    assert engine_bags == frozen["bags"]
    version, internal, gauss = world.rng.getstate()
    assert [version, list(internal), gauss] == frozen["rng_state"]


def test_two_seeded_worlds_match_after_fifty_npc_ticks():
    a = World(seed=0, spectate_only=True)
    b = World(seed=0, spectate_only=True)
    snap_a = snap_b = None
    for _ in range(50):
        snap_a = a.tick()
        snap_b = b.tick()
    assert snap_a == snap_b
    for s in a.survivors():
        assert s.meat >= 0
        assert s.water >= 0
        assert s.fiber >= 0


def test_engine_has_no_process_random():
    forbidden = re.compile(r"\brandom\.(choice|random|seed)\s*\(")
    hits = []
    for path in sorted(ENGINE_DIR.rglob("*.py")):
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if forbidden.search(line):
                hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}:{line}")
    assert hits == []
