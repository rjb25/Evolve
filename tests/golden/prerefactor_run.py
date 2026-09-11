"""Subprocess harness for frozen pre-extract copies. Do not import engine."""
import json
import random
import sys

random.seed(0)

from survivor import Survivor  # noqa: E402
from tools import tools  # noqa: E402


def min_goods(survivor):
    return min(survivor.meat, survivor.water, survivor.fiber)


def relation_names(survivor):
    names = []
    for rid in survivor.relations:
        other = tools.get_member("peasants", rid)
        if other:
            names.append(other.name)
    return sorted(names)


def bag():
    out = {}
    for peasant in tools.get_members("peasants"):
        out[peasant.name] = [
            peasant.health,
            peasant.meat,
            peasant.water,
            peasant.fiber,
            peasant.produce,
            relation_names(peasant),
            peasant.action,
        ]
    return out


def main():
    always_produce = "--always-produce" in sys.argv
    for _ in range(10):
        peasant = Survivor()
        tools.add_member("peasants", peasant)
    if always_produce:
        for peasant in tools.get_members("peasants"):
            peasant.weights = [1.0, 0.0, 0.0]
        max_ticks = 3
    else:
        max_ticks = 50

    bags = []
    ticks_done = 0
    for _ in range(max_ticks):
        members = tools.get_members("peasants")
        if not always_produce and any(min_goods(s) <= 0 for s in members):
            break
        for peasant in members:
            if peasant.health > 0:
                peasant.live()
                peasant.act()
        for peasant in list(tools.get_members("peasants")):
            if not peasant.alive():
                tools.del_member("peasants", peasant)
        ticks_done += 1
        bags.append(bag())
    payload = {"ticks": ticks_done, "bags": bags}
    if always_produce:
        version, internal, gauss = random.getstate()
        payload["rng_state"] = [version, list(internal), gauss]
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
