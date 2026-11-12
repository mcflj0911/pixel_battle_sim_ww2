"""Headless check for the castle war. No window opens: SDL is pointed at its dummy video and audio drivers.

    python check.py                       # runs seeds 1 and 2 and prints each one
    python check.py --seeds 1,5,9         # other seeds
    python check.py --frame castle.png    # also save a frame of the first battle as a PNG
    python check.py --frame f.png --cam 3300 --phase 0.0   # ...with the camera at world x 3300, at night

It checks that a broken scenario is rejected with a readable message. Each seed runs the battle for CHECK_SECONDS of
battle time, since a battle has no end. It checks the castle war's rules: both sides muster the same number of
troops, the troops are still fighting at the end, and a gate sallies out at least once
across the seeds. It also times frames as the window does. Exits with status 1 if any check fails."""
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

import config as C  # noqa: E402
import heroes  # noqa: E402
from battle import Battle  # noqa: E402
from main import sim_frame  # noqa: E402
from render import Renderer  # noqa: E402
from scenario import ScenarioError, load, validate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIO = os.path.join(HERE, "scenarios", "camp_war.json")
CHECK_SECONDS = 600.0                      # battle seconds each seed runs for
FRAMES = 300                               # 10 seconds of window time at 30 fps


def check_validation():
    """A broken scenario must give a readable error, not a crash."""
    try:
        validate({"name": "x", "map": {"width": 10, "height": 10},
                  "sides": {"a": {"name": "A", "color": [1, 2, 3], "goal": [1, 1]}},
                  "unit_types": {}, "groups": [{"side": "b", "unit_type": "t", "count": 1, "area": [0, 0, 1, 1]}]})
    except ScenarioError as err:
        print(f"validation: rejected a bad scenario as expected ({err})")
        return True
    print("validation: a bad scenario was accepted")
    return False


def check_rules(battle, scenario, start):
    """Returns a list of problems with the castle war's rules; empty means they hold."""
    problems = []
    fired = [eid for _, eid in battle.fire_log]
    if "muster" not in fired:
        problems.append("the muster never fired")
    for side in scenario["sides"]:
        if battle.started[side] <= start[side]:
            problems.append(f"{side} never mustered troops")
        if battle.active(side) == 0:
            problems.append(f"{side} has no troops left fighting at the end")
    problems += check_heroes(battle, scenario)
    stranded = [u for u in battle.units if u.stats["speed"] == 0 and u.perch is None and u.stats["sprite"] != "hmg_nest"]
    if stranded:
        problems.append(f"{len(stranded)} archers on the walls are not standing on a wall or tower")
    # both sides spawn together: each shared wave event must spawn for every side in one go
    for eid in ("muster", "siege_catapults", "siege_trebuchets"):
        spawned = {a["side"] for ev in scenario["events"] if ev["id"] == eid for a in ev["actions"]
                   if a["type"] == "spawn"}
        if spawned != set(scenario["sides"]):
            problems.append(f"event {eid} does not spawn for every side at once")
    return problems


def check_heroes(battle, scenario):
    """Four heroes a side; each skill list is two passive and two active; a fallen hero returns after its respawn
    time; and every hero's active skills were used."""
    problems = []
    for sid in scenario["sides"]:
        names = [n for n, r in battle.heroes.items() if r["side"] == sid and r["unit"].stats["speed"] > 0]
        kings = [n for n, r in battle.heroes.items() if r["side"] == sid and r["unit"].stats["speed"] == 0]
        if len(names) != 4:
            problems.append(f"{sid} has {len(names)} field heroes, expected 4")
        if len(kings) != 1 or battle.heroes[kings[0]]["unit"].perch != "ally_keep" and sid == "allies":
            problems.append(f"{sid} should have one king standing on its keep")
    fell = {}
    for t, name, what in battle.hero_log:
        if what == "fall":
            fell[name] = t
        elif name in fell:
            want = battle.heroes[name]["unit"].stats["respawn"]
            if abs((t - fell.pop(name)) - want) > 1.01:
                problems.append(f"{name} did not return {want:.0f} s after falling")
    for name, rec in battle.heroes.items():
        if rec["unit"].state == "dead" and rec["status"] != "fallen":
            problems.append(f"{name} is dead but not marked fallen")
    check_heroes.seen = getattr(check_heroes, "seen", set()) | set(battle.casts)
    check_heroes.returns = getattr(check_heroes, "returns", 0) + sum(1 for _, _, w in battle.hero_log if w == "return")
    return problems


def check_king(scenario):
    """A siege at the west castle: a king on his keep must call on his skills (and shoot) when foes press the walls."""
    battle = Battle(scenario, seed=scenario["seed"])
    king = next(r["unit"] for r in battle.heroes.values() if r["side"] == "allies" and r["unit"].stats["speed"] == 0)
    for _ in range(6):                      # the garrison is bigger now: keep a stream of foes at the walls
        battle.spawn("axis", "rifleman", 14, [300, 280, 60, 150])
        battle.run_for(battle.time + 10)
        used = [s for s in king.stats["skills"] if battle.casts.get(s)]
        if used or king.kills:
            break
    if not used and king.kills == 0:
        print("PROBLEM: the king on his keep neither shot nor used a skill with foes at the walls")
        return False
    print(f"general: used {used or 'no skills'}, {king.kills} kills from the command post")
    return True


def drill_heroes(scenario):
    """Puts a crowd of foes beside every field hero, again and again, so skills the long march kept from firing get used."""
    b = Battle(scenario, seed=7)
    b.run_for(2)
    for _ in range(10):
        for r in list(b.heroes.values()):
            u = r["unit"]
            if u.state != "fighting" or u.stats["speed"] == 0:
                continue
            foe = next(sid for sid in scenario["sides"] if sid != r["side"])
            b.spawn(foe, "rifleman", 10, [u.x + 50, u.y - 25, 40, 50])
            b.spawn(foe, "tank", 1, [u.x + 70, u.y - 25, 40, 50])
        b.run_for(b.time + 12)
        check_heroes.seen |= set(b.casts)


def check_walls(scenario):
    """The armies fight in the open field now, so the wall archers are tested separately: three foes are put beside
    the west castle and its archers must shoot at them from the walls."""
    battle = Battle(scenario, seed=scenario["seed"])
    battle.spawn("axis", "rifleman", 3, [300, 290, 40, 40])
    battle.run_for(15)
    if battle.elevated_shots == 0:
        print("PROBLEM: the archers on the walls never shot at foes beside the camp")
        return False
    print(f"walls: the garrison loosed {battle.elevated_shots} shots from the walls at foes beside the camp")
    return True


def check_crash(scenario):
    """A shot-down aircraft falls to a crash site and hurts the men beneath it."""
    b = Battle(scenario, seed=1)
    b.run_for(1)
    fighter = next((k for k, v in scenario["unit_types"].items() if v.get("flying") and not v.get("naval")), None)
    if fighter is None:
        return True
    b.spawn("axis", fighter, 1, [900, 300, 20, 20])
    plane = next((u for u in b.units if u.stats.get("flying") and u.side == "axis" and u.state == "fighting"), None)
    if plane is None:
        print("PROBLEM: crash drill could not field an aircraft")
        return False
    tx = plane.x + 70 * (1 if plane.rout_dx >= 0 else -1)
    b.spawn("allies", "rifleman", 6, [tx - 6, plane.y - 6, 12, 12]) if "rifleman" in scenario["unit_types"] else None
    victims = [u for u in b.units if u.side == "allies" and not u.stats.get("flying")][-6:]
    before = sum(u.hp for u in victims)
    b._hurt(plane, 99999)
    if not b.crashes:
        print("PROBLEM: a shot-down aircraft planned no crash")
        return False
    b.run_for(b.time + 3)
    if b.extra_stats.get("crashes", 0) < 1:
        print("PROBLEM: the crash never landed")
        return False
    print(f"crash: {b.extra_stats['crashes']} landed, {b.extra_stats.get('crash_hits', 0)} hurt (hp {before:.0f} -> {sum(u.hp for u in victims):.0f})")
    return True


def check_big(scenario):
    """The big weapons: an MLRS pod's salvo and a V-2 launcher's single rocket hurt a crowd; a carrier flies off aircraft;
    a dreadnought's broadside falls on several marks at once."""
    ok = True
    # a rocket pod and a V-2 launcher, each shooting at a crowd in range
    for side, foe, kind, key, x in (("allies", "axis", "mlrs_pod", "missiles", 2700), ("axis", "allies", "v2_launcher", "v2", 3000)):
        b = Battle(scenario, seed=1)
        b.run_for(1)
        b.spawn(side, kind, 1, [x, 330, 20, 20])
        first = len(b.units)
        b.spawn(foe, "sentry", 14, [x + 300, 320, 50, 50])
        crowd = b.units[first:]
        hp0 = sum(u.hp for u in crowd)
        b.run_for(b.time + 45)
        if b.extra_stats.get(key, 0) < 1:
            print(f"PROBLEM: the {kind} never fired")
            ok = False
        elif sum(u.hp for u in crowd if u.state == "fighting") >= hp0:
            print(f"PROBLEM: the {kind} did no harm")
            ok = False
        else:
            print(f"{kind}: {b.extra_stats.get(key, 0)} rockets, crowd hp {hp0:.0f} -> {sum(max(0, u.hp) for u in crowd):.0f}")
    b = Battle(scenario, seed=1)
    b.run_for(1)
    b.spawn("allies", "carrier", 1, [900, b.shore + 60, 40, 30])
    b.run_for(b.time + 60)
    if b.extra_stats.get("sorties", 0) < 2:
        print("PROBLEM: the carrier flew off no aircraft")
        ok = False
    else:
        print(f"carrier: {b.extra_stats['sorties']} sorties flown")
    b = Battle(scenario, seed=1)
    b.run_for(1)
    b.spawn("axis", "dreadnought", 1, [1800, b.shore + 60, 40, 30])
    ship = next(u for u in b.units if u.kind == "dreadnought")
    b.spawn("allies", "rifleman", 12, [ship.x - 150, b.shore - 70, 120, 40])
    b.run_for(b.time + 40)
    if not b.extra_stats.get("broadsides"):
        print("PROBLEM: the dreadnought never fired a broadside")
        ok = False
    else:
        print(f"dreadnought: {b.extra_stats['broadsides']} broadsides")
    return ok


def check_land(scenario):
    """Rivers and bridges: a river stops men but not at a bridge; a bridge that falls closes the river and engineers rebuild
    it; with no bridge left they float a pontoon, which a single shell destroys."""
    ok = True
    b = Battle(scenario, seed=1)
    b.run_for(1)
    bridges = [t for t in b.terrain if t.get("style") == "bridge" and t["river"] == "west_river"]
    if not bridges or not b._blocked(2200, 250, 3) or b._blocked(2200, 360, 3):
        print("PROBLEM: a river should block the way except at its bridge")
        return False
    road = next(t for t in bridges if t["rect"][1] < 360 < t["rect"][1] + t["rect"][3])
    b._break_bridge(road)
    if not b._blocked(road["rect"][0] + 30, 360, 3):
        print("PROBLEM: a bridge that fell did not close the river")
        ok = False
    b.spawn("allies", "engineer", 2, [2050, 340, 40, 40])
    b.run_for(b.time + 45)
    if not b.extra_stats.get("repaired") or b._blocked(road["rect"][0] + 30, 360, 3):
        print("PROBLEM: engineers did not rebuild the fallen bridge")
        ok = False
    b = Battle(scenario, seed=2)
    b.run_for(1)
    for t in [t for t in b.terrain if t.get("style") == "bridge" and t["river"] == "west_river"]:
        b._break_bridge(t)
    b.broken_bridges.clear()
    b.spawn("allies", "engineer", 2, [2090, 330, 30, 60])
    b.spawn("allies", "rifleman", 6, [2080, 330, 30, 60])
    b.run_for(b.time + 60)
    pont = next((t for t in b.terrain if t.get("pontoon")), None)
    if pont is None:
        print("PROBLEM: engineers did not float a pontoon across a river with no bridge")
        return False
    b._hit_structures_near(pont["rect"][0] + 20, pont["rect"][1] + 20, 5, 60)
    if pont in b.terrain:
        print("PROBLEM: a shell did not destroy the pontoon")
        ok = False
    if ok:
        print("land: a river blocks, a bridge falls and is rebuilt, a pontoon is floated and one shell sinks it")
    return ok


def check_frames(scenario, view, surface):
    """Runs frames as the window does (the same frame function, at 4x speed, the fast case) and times each one: the
    simulation plus drawing. At 30 fps a frame has 1/30 s. This is timed headless, so it leaves out the display's
    own flip and vsync. Returns True if the 95th-percentile frame fits in 1/30 s."""
    battle = Battle(scenario, seed=scenario["seed"])
    dt = 1.0 / C.FPS
    acc, last_draw, times = 0.0, 0.0, []
    for _ in range(FRAMES):
        t0 = time.perf_counter()
        acc = sim_frame(battle, acc, dt * C.SIM_RATE * C.SPEEDS[2], last_draw)
        t1 = time.perf_counter()
        view.draw(surface, battle, "4x", False)
        last_draw = time.perf_counter() - t1
        times.append(time.perf_counter() - t0)
    times.sort()
    p95 = times[int(len(times) * 0.95)]
    mean = sum(times) / len(times)
    print(f"frames at 4x: {len(times)} frames, mean {mean * 1000:.1f} ms, 95th percentile {p95 * 1000:.1f} ms, "
          f"worst {times[-1] * 1000:.1f} ms (budget {dt * 1000:.1f} ms at {C.FPS} fps, headless)")
    ok = p95 <= dt
    if not ok:
        print("PROBLEM: frames are slower than the 30 fps budget")
    return ok


def main():
    seeds = [1, 2]
    frame_path = None
    args = sys.argv[1:]
    if "--seeds" in args:
        seeds = [int(s) for s in args[args.index("--seeds") + 1].split(",")]
    if "--frame" in args:
        frame_path = args[args.index("--frame") + 1]
    cam = float(args[args.index("--cam") + 1]) if "--cam" in args else None      # frame the camera here (world x)
    phase = float(args[args.index("--phase") + 1]) if "--phase" in args else None   # time of day: 0.5 noon, 0.0 night

    ok = check_validation()
    scenario = load(SCENARIO)
    pygame.init()
    surface = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
    view = Renderer(scenario)
    gate_sallies = 0
    ambushes = [0]
    sea = {"shots": 0, "sunk": 0, "landings": 0, "marines": 0, "strikes": 0, "changes": 0}
    air = {"bombs": 0, "dogfights": 0, "air_losses": 0, "bolts": 0, "swoops": 0}
    extras = {}

    for i, seed in enumerate(seeds):
        battle = Battle(scenario, seed=seed)
        start = dict(battle.started)
        fielded, real_spawn = set(), battle.spawn

        def spawn(side, kind, *args, **kw):               # note every unit type each side actually fields
            fielded.add((side, battle.sc["variants"].get((side, kind), kind)))
            return real_spawn(side, kind, *args, **kw)
        battle.spawn = spawn
        t0 = time.time()
        battle.run_for(CHECK_SECONDS)
        elapsed = time.time() - t0
        print(f"seed {seed}: ran {battle.time:.1f} battle seconds ({battle.tick_count} ticks, {elapsed:.1f} s wall)")
        for sid, sd in scenario["sides"].items():
            print(f"  {sd['name']}: mustered {battle.started[sid]}, lost {battle.lost[sid]}, "
                  f"routed away {battle.fled[sid]}, fighting now {battle.active(sid)}")
        sallies = [eid for _, eid in battle.fire_log if eid.startswith(("open_", "sally_"))]
        gate_sallies += len(sallies)
        print(f"  gate sallies: {len(sallies)}, siege hits on structures: {battle.structure_hits}")
        print(f"  ambushes: {battle.ambushes_planned} planned, {battle.ambushes_sprung} sprung")
        ambushes[0] += battle.ambushes_sprung
        for k, v in battle.air_stats.items():
            air[k] += v
        for k, v in battle.extra_stats.items():
            extras[k] = extras.get(k, 0) + v
        for k, v in battle.naval_stats.items():
            sea[k] += v
        sea["strikes"] += battle.wx_stats["strikes"]
        sea["changes"] += battle.wx_stats["changes"]
        made = fielded
        for need in (("allies", "gi_rifleman"), ("axis", "grenadier"), ("allies", "halftrack"), ("axis", "armored_halftrack")):
            if need not in made:
                print(f"  PROBLEM: {need[0]} never fielded a {need[1]}")
                ok = False
        problems = check_rules(battle, scenario, start)
        for p in problems:
            print(f"  PROBLEM: {p}")
        ok = ok and not problems
        if i == 0:
            if cam is not None:
                view.look_at(cam)
            if phase is not None:
                view.set_phase(phase)
            view.draw(surface, battle, "1x", False)
            for ph in (0.72, 0.9, 0.05):                 # dusk, night, dawn: torches and glows must all be cached
                view.set_phase(ph)
                view.draw(surface, battle, "1x", False)
            if phase is not None:
                view.set_phase(phase)
            if frame_path:
                pygame.image.save(surface, frame_path)
                print(f"  frame saved to {frame_path}")

    all_active = {sid for sd in scenario["unit_types"].values() if sd["speed"] > 0 for sid in sd["skills"]
                  if not heroes.SKILLS[sid]["passive"]}          # the kings are tested on their own (check_king)
    never = sorted(all_active - check_heroes.seen)
    if never:                                              # the armies meet late on a wide field: drill the rest
        drill_heroes(scenario)
        never = sorted(all_active - check_heroes.seen)
    if never:
        print("PROBLEM: these hero skills were never cast:", ", ".join(never))
        ok = False
    if check_heroes.returns == 0:
        print("PROBLEM: no fallen hero ever returned to the field")
        ok = False
    print(f"heroes: {len(all_active)} active skills cast, {check_heroes.returns} returns after falling")
    print(f"air: {air['bombs']} bombs, {air['dogfights']} dogfights, {air['bolts']} bolts, "
          f"{air['swoops']} harpy swoops, {air['air_losses']} losses")
    if air["bombs"] == 0 or air["dogfights"] == 0 or air["air_losses"] == 0 or air["bolts"] == 0 or air["swoops"] == 0:
        print("PROBLEM: the flyers never bombed, never fought each other, or never fell")
        ok = False
    print(f"sea: {sea['shots']} ship shots, {sea['sunk']} ships sunk, {sea['landings']} landings ({sea['marines']} marines); "
          f"weather: {sea['changes']} changes, {sea['strikes']} lightning strikes")
    if sea["shots"] == 0 or sea["landings"] == 0 or sea["changes"] == 0:
        print("PROBLEM: the ships never fought or landed, or the weather never changed")
        ok = False
    print("extras: " + ", ".join(f"{k} {round(v)}" for k, v in extras.items()))
    for need in ("healed", "promotions", "mines", "crates", "carpet", "smoke", "paratroopers", "missiles", "v2"):
        if not extras.get(need):
            print(f"PROBLEM: the field extras never produced any '{need}'")
            ok = False
    if ambushes[0] == 0:
        print("PROBLEM: no ambush was sprung in any battle")
        ok = False
    if gate_sallies == 0:
        print("PROBLEM: no gate sallied out in any battle")
        ok = False
    ok = check_walls(scenario) and ok
    ok = check_king(scenario) and ok
    ok = check_land(scenario) and ok
    ok = check_crash(scenario) and ok
    ok = check_big(scenario) and ok
    ok = check_frames(scenario, view, surface) and ok
    pygame.quit()
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
