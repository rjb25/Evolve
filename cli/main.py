from __future__ import annotations

import argparse
import cProfile
import pstats
import time

from engine.survivor import ActError, Command
from engine.world import World


def parse_command(raw: str, options: list[str] | None = None) -> Command:
    if options is None:
        options = ["produce", "deal", "relate"]
    parts = raw.split()
    try:
        actionindex = int(parts[0])
        action = options[actionindex]
    except (ValueError, TypeError, IndexError):
        action = options[0]
    target_id = None
    offer_id = None
    if len(parts) > 1:
        try:
            target_id = int(parts[1])
        except (ValueError, TypeError):
            target_id = None
    if len(parts) > 2:
        try:
            offer_id = int(parts[2])
        except (ValueError, TypeError):
            offer_id = None
    return Command(action=action, target_id=target_id, offer_id=offer_id)


def print_roster(world: World) -> None:
    for survivor in world.survivors():
        line = str(survivor)
        if survivor.id == world.control_id:
            if not line.endswith(" ME"):
                line = line + " ME"
        print(line)


def _handle_possess_prompt(world: World) -> bool:
    print(f"You died as {world.died_as_name}. Possess or Auto.")
    try:
        raw = input("possess id (or auto): ")
    except EOFError:
        return False
    token = raw.strip().lower()
    if token in ("auto", "", "a"):
        successor = world.pick_successor()
        if successor is None:
            print("Extinction. New run.")
            return False
        world.possess(successor)
    else:
        try:
            world.possess(int(token))
        except (ValueError, ActError) as err:
            detail = err.detail if isinstance(err, ActError) else str(err)
            print(detail)
            return True
    return True


def interactive(seed: int | None = None) -> None:
    world = World(seed=seed)
    print("control id is 1 (first spawned survivor)")
    print_roster(world)
    while True:
        if not world.survivors():
            print("Extinction. New run.")
            return
        if world.pending_possess:
            if not _handle_possess_prompt(world):
                return
            print_roster(world)
            continue
        try:
            raw = input("Survivor action? (number) ")
        except EOFError:
            return
        if raw.strip().lower() in ("q", "quit"):
            return
        cmd = parse_command(raw)
        try:
            world.tick(cmd)
        except ActError as err:
            print(err.detail)
            continue
        print_roster(world)


def profile_run(n: int, seed: int | None = None) -> None:
    world = World(seed=seed, spectate_only=True)
    t0 = time.perf_counter()
    with cProfile.Profile() as profile:
        for _ in range(n):
            world.tick()
    elapsed = time.perf_counter() - t0
    living = len(world.survivors())
    print(f"ticks={n} living={living} elapsed={elapsed:.4f}s")
    results = pstats.Stats(profile)
    results.dump_stats("results.prof")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evolution simulation CLI")
    parser.add_argument("--profile", type=int, default=None, metavar="N")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)
    if args.profile is not None:
        profile_run(args.profile, args.seed)
    else:
        interactive(args.seed)


if __name__ == "__main__":
    main()
