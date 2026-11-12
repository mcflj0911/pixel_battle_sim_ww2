"""The battle engine: a top-down simulation with no pygame in it, so it can run headless.

Units walk on a flow field per side (so they go around walls and funnel through a breach), attack whatever enemy
is within reach, lose morale when they are hurt or when friends die near them, and run when morale breaks.
Archers and siege engines loose projectiles: the damage lands when the projectile does, and a projectile whose
target has already died (or whose shooter is gone) does nothing. Named heroes never rout, rally the men near them,
and are recorded (with their kills). Events are read straight from the scenario dict. A battle has no end: it runs
for as long as the program does, with troops mustering and sallying out as the scenario's events say."""
import itertools
import math
import random
import time

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

import config as C
import scenery
from heroes import HeroSkills
from air import AirUnits
from extras import FieldExtras
from naval import NavalUnits
from weather import Weather


_SHOT_IDS = itertools.count(1)           # every shot gets a number that is unique across battles


def rect_contains(rect, x, y):
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


class Unit:
    __slots__ = ("uid", "side", "kind", "stats", "name", "x", "y", "hp", "morale", "cooldown", "target", "retarget",
                 "state", "rout_dx", "rout_dy", "rout_time", "flash", "kills", "facing", "perch", "height", "lane",
                 "formation", "burn", "cover", "hidden", "ambush", "bonus_until", "buffs", "cds", "nav")

    def __init__(self, uid, side, kind, stats, name, x, y):
        self.uid = uid
        self.side = side
        self.kind = kind
        self.stats = stats
        self.name = name                 # set for named heroes, otherwise None
        self.x = x
        self.y = y
        self.hp = stats["hp"]
        self.morale = 100.0
        self.cooldown = 0
        self.target = None
        self.retarget = 0
        self.state = "fighting"          # fighting | routing | dead | fled
        self.rout_dx = 0.0
        self.rout_dy = 0.0
        self.rout_time = 0.0
        self.flash = 0                   # frames of white flash after being hit (drawn by the renderer)
        self.kills = 0
        self.facing = 1                  # 1 = faces right, -1 = faces left (set from the last move)
        self.perch = None                # id of the wall or tower a garrison stands on (None for everyone else)
        self.height = 0.0                # how high its feet are above the ground: the top of its perch
        self.lane = 0                    # which of the four gate lanes (config LANES_Y) this unit keeps to
        self.formation = None            # "testudo" (shields locked overhead), "spear" (lances levelled) or None
        self.burn = 0                    # ticks left alight from a flaming arrow
        self.cover = False               # standing in a trench or an old crater: arrows hit less
        self.hidden = False              # lying in wait behind a tree or bush: foes cannot see or target it
        self.ambush = None               # the ambush squad (a dict) this unit belongs to, if any
        self.bonus_until = 0.0           # battle time until which it strikes harder (after springing an ambush)
        self.buffs = None                # {name: (until, strength)}: auras, hero skills, stuns and slows
        self.cds = None                  # a hero's skill cooldowns: {skill id: battle time it is ready}
        self.nav = None                  # a ship's sailing record (lane, patrol leg, landing-boat state)

    @property
    def hero(self):
        return self.stats.get("hero", False)


class Battle(HeroSkills, AirUnits, NavalUnits, Weather, FieldExtras):
    def __init__(self, scenario, seed=None):
        self.sc = scenario
        self.W = scenario["map"]["width"]
        self.H = scenario["map"]["height"]
        self.rng = random.Random(scenario["seed"] if seed is None else seed)
        self.time = 0.0
        self.tick_count = 0
        self.units = []
        self.next_uid = 1
        self.terrain = [dict(t) for t in scenario["terrain"]]
        self.walls = []                  # rects of solid terrain, rebuilt when terrain changes
        self.log = []                    # (time, text) pairs, newest last
        self.fired = set()               # ids of one-off events that have fired
        self.last_fired = {}             # event id -> battle time it last fired (repeating events use this)
        self.fire_count = {}             # event id -> how many times it has fired
        self._cur_event = None
        self.fire_log = []               # (time, event id) for every firing, in order
        self.objectives_done = {oid: False for oid in (o["id"] for o in scenario["objectives"])}
        self.started = {s: 0 for s in scenario["sides"]}
        self.lost = {s: 0 for s in scenario["sides"]}
        self.fled = {s: 0 for s in scenario["sides"]}
        self.enemies = {}
        for sid, sd in scenario["sides"].items():
            self.enemies[sid] = set(sd["enemies"]) if sd["enemies"] is not None else set(scenario["sides"]) - {sid}
        self.heroes = {}                 # name -> record of each named hero, shown in the HUD
        self.inspiring = []              # living heroes this tick (they rally the men near them)
        self.flow = {}
        self.flow_dirty = True
        self._flow_time = -1e9
        self._gen = None                 # the tick in progress, if it has been split across frames
        self.structure_hits = 0          # siege stones that hit a wall, gate, tower or palisade
        self.elevated_shots = 0          # shots loosed from the top of a wall or tower (the defenders' shots)
        self.projectiles = []            # arrows and stones in the air: their damage lands when they arrive
        self.pending = []                # delayed waves of hero strikes: {at, args}
        self.hero_log = []               # (time, hero name, 'fall' | 'return'), for the headless check
        self.casts = {}                  # skill id -> how many times it has been cast
        self.air_stats = {"bombs": 0, "dogfights": 0, "air_losses": 0, "bolts": 0, "swoops": 0}
        self._centers = {}
        self._air_units = {}
        self.shore = scenario["map"].get("shore")        # y where the sea begins (None: no sea)
        self._sea, self._sea_units, self._sea_trees = [], {}, {}
        self.naval_stats = {"shots": 0, "sunk": 0, "landings": 0, "marines": 0}
        self._weather_init()
        self._shot_ids = _SHOT_IDS
        self.shots = []                  # the same shots for the renderer to draw (it does not change the battle)
        self.fx = []                     # (kind, x, y) effects that happened this tick, for the renderer
        self.grid = {}
        self.lane_cursor = {s: 0 for s in scenario["sides"]}   # next lane to hand out, per side
        self.pits = [tuple(c) for c in scenario.get("craters", [])]   # old shell holes: permanent, and cover
        # props a squad can hide behind (the renderer draws the same props: both ask scenery.place)
        self.cover_props = [(p["x"], p["y"], scenery.CONCEALING[p["kind"]])
                            for p in scenery.place(scenario, C.DOODADS) if p["kind"] in scenery.CONCEALING]
        self.squads = {sid: [] for sid in scenario["sides"]}      # ambush squads in progress, per side
        self._next_plan = {sid: C.AMBUSH_EVERY for sid in scenario["sides"]}
        self.ambushes_planned = 0
        self.ambushes_sprung = 0
        self._refresh_walls()
        self._extras_init()
        for g in scenario["groups"]:
            self.spawn(g["side"], g["unit_type"], g["count"], g["area"], g.get("name"))
        # where each side started: a shaken side's troops fall back toward it
        self.home = {}
        for sid, sd in scenario["sides"].items():
            pts = [(u.x, u.y) for u in self.units if u.side == sid]
            self.home[sid] = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts \
                else tuple(sd["goal"])
        self._run_events()

    # ------------------------------------------------------------------ public helpers
    def active(self, side):
        return sum(1 for u in self.units if u.side == side and u.state == "fighting")

    def run_for(self, seconds):
        """Run whole ticks until the battle has run for `seconds` of battle time (the headless check uses this)."""
        while self.time < seconds:
            self.tick()

    def say(self, text):
        self.log.append((round(self.time, 1), text))
        del self.log[:-200]

    # ------------------------------------------------------------------ setup
    def spawn(self, side, kind, count, area, name=None, respawn=False):
        kind = self.sc["variants"].get((side, kind), kind)         # each side fields its own version of a unit
        stats = self.sc["unit_types"][kind]
        if name is not None and count != 1:
            raise ValueError(f"a named unit ({name}) must have count 1")
        made = 0
        for _ in range(count):
            if (stats.get("flying") or stats.get("naval")) and sum(1 for v in self.units if v.side == side and v.kind == kind
                                           and v.state == "fighting") >= stats["max_alive"]:
                break                                    # a side keeps only so many of each flyer in the air
            if (stats.get("flying") or stats.get("naval")) and self._harsh(stats):
                self.extra_stats["grounded"] += 1
                break                                    # the weather keeps its aircraft on the ground
            made += 1
            x, y = self._free_spot(area, garrison=stats["speed"] == 0)
            u = Unit(self.next_uid, side, kind, stats, name, x, y)
            if stats.get("flying"):
                u.height = stats["altitude"]
                gx = self.sc["sides"][side]["goal"][0]
                u.rout_dx, u.rout_dy = (1.0 if gx > x else -1.0), 0.0       # the heading it starts on
            if stats.get("cargo"):
                u.nav = {"dropped": False}
            if stats.get("paratrooper"):
                u.height, u.nav = C.CHUTE_HEIGHT, {"chute": True}      # he floats down before he can fight
            if stats.get("naval"):
                self._naval_init(u)
            if stats.get("tower"):
                u.nav = {"men": stats["garrison"]}
            if stats["speed"] == 0:
                u.perch, u.height = self._perch_at(x, y)
            else:
                u.lane = self.lane_cursor[side] % len(C.LANES_Y)     # a batch spreads across all four lanes
                self.lane_cursor[side] += 1
            self.units.append(u)
            self.next_uid += 1
            if stats.get("hero"):
                u.cds = {sid: self.time + self.rng.uniform(4, 12) for sid in stats.get("skills", ())}
            if name is not None:
                kills = self.heroes[name]["kills"] if name in self.heroes else 0
                self.heroes[name] = {"name": name, "side": side, "status": "alive", "kills": kills, "fell_at": None,
                                     "unit": u, "area": area, "respawn_at": None}
                u.kills = kills
                if respawn:
                    self._fx("respawn", x, y, u.uid)
        if not respawn:
            self.started[side] += made

    def _free_spot(self, area, garrison=False):
        """A spot inside area. A garrison unit (speed 0: an archer on a wall or tower) may stand inside solid
        terrain, since that is where it is put; everyone else is placed on free ground."""
        ax, ay, aw, ah = area
        x = y = 0.0
        if garrison:
            return self.rng.uniform(ax, ax + aw), self.rng.uniform(ay, ay + ah)
        for _ in range(40):
            x = self.rng.uniform(ax, ax + aw)
            y = self.rng.uniform(ay, ay + ah)
            if not self._blocked(x, y, C.UNIT_RADIUS):
                break
        return x, y

    def _perch_at(self, x, y):
        """The block a garrison stands on: the tallest wall or tower containing its spot. Returns (id, height), or
        (None, 0.0) if the spot is on no block."""
        best = None
        for t in self.terrain:
            if t["hidden"] or t.get("style") not in ("wall", "tower", "keep") or (not t["solid"] and t.get("style") != "keep"):
                continue
            if rect_contains(t["rect"], x, y) and (best is None or t["height"] > best["height"]):
                best = t
        return (None, 0.0) if best is None else (best["id"], best["height"])

    def _refresh_walls(self):
        self.walls = [t["rect"] for t in self.terrain if t["solid"] and not t["hidden"]]
        self.spikes = [t["rect"] for t in self.terrain if t.get("style") == "spikes" and not t["hidden"]]
        self.trenches = [t["rect"] for t in self.terrain if t.get("style") == "trench" and not t["hidden"]]
        self.wires = [t for t in self.terrain if t.get("style") == "wire" and not t["hidden"]]
        self.hills = [(t["rect"][0], t["rect"][1], t["rect"][2], t["rect"][3]) for t in self.terrain
                      if t.get("style") == "hill" and not t["hidden"]]
        self.pontoons = [t for t in self.terrain if t.get("pontoon") and not t["hidden"]]
        self._wall_grid = {}                      # solid blocks by 64 px cell, so a move only tests the blocks beside it
        for rect in self.walls:
            rx, ry, rw, rh = rect
            for gx in range(int((rx - 16) // 64), int((rx + rw + 16) // 64) + 1):
                for gy in range(int((ry - 16) // 64), int((ry + rh + 16) // 64) + 1):
                    self._wall_grid.setdefault((gx, gy), []).append(rect)
        self.flow_dirty = True

    # ------------------------------------------------------------------ one tick
    def tick(self):
        """Run one whole tick now (the headless check uses this)."""
        while not self.step(float("inf")):
            pass

    @property
    def mid_tick(self):
        return self._gen is not None

    def step(self, budget):
        """Do up to `budget` seconds of work on the current tick. A tick is split into slices, so a big battle
        never holds up the window for long. Returns True when a whole tick has finished."""
        if self._gen is None:
            self._gen = self._tick_steps()
        t0 = time.perf_counter()
        while True:
            try:
                next(self._gen)
            except StopIteration:
                self._gen = None
                return True
            if time.perf_counter() - t0 >= budget:
                return False

    def _tick_steps(self):
        """One tick, as a generator: it yields between slices of units so the caller can check its frame budget."""
        self.tick_count += 1
        self.time += 1.0 / C.SIM_RATE
        # the flow field is rebuilt when terrain or goals change, but at most every FLOW_REBUILD_SECONDS
        if self.flow_dirty and self.time - self._flow_time >= C.FLOW_REBUILD_SECONDS:
            self._rebuild_flow()
            self._flow_time = self.time
        self._respawns()
        self._weather_tick()
        self.inspiring = [u for u in self.units if u.hero and u.state == "fighting"]
        self._build_index()
        self.hero_tick()
        self._ambush_tick()
        self._extras_tick()
        yield
        for i, u in enumerate(list(self.units)):
            if u.state == "fighting":
                self._fight(u)
                u.cover = u.height == 0 and self._in_cover(u.x, u.y)
                if u.burn:
                    self._burn(u)
                self._spikes_hurt(u)
                self._extras_unit(u)
            elif u.state == "routing":
                self._rout(u)
            if u.flash:
                u.flash -= 1
            if i % C.UNITS_PER_SLICE == 0:
                yield
        self._land_projectiles()
        self._settle()
        self._run_events()
        self._update_objectives()

    def _in_cover(self, x, y):
        """True inside a trench or an old crater."""
        for rx, ry, rw, rh in self.trenches:
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return True
        for cx, cy, r in self.pits:
            if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
                return True
        return False

    def _cover_point(self, u):
        """The nearest trench or crater within COVER_SEEK of u, as a point to walk to, or None."""
        best, best_d = None, C.COVER_SEEK
        for rx, ry, rw, rh in self.trenches:
            px, py = min(max(u.x, rx + 2), rx + rw - 2), min(max(u.y, ry + 2), ry + rh - 2)
            d = math.hypot(px - u.x, py - u.y)
            if d < best_d:
                best, best_d = (px, py), d
        for cx, cy, r in self.pits:
            d = math.hypot(cx - u.x, cy - u.y) - r * 0.5
            if d < best_d:
                best, best_d = (cx, cy), d
        return best

    def _burn(self, u):
        """A man alight from a flaming arrow takes fire damage each tick until it burns out."""
        u.burn -= 1
        if (self.wx["rain"] > 0.3 and self.rng.random() < self.wx["rain"]) or u.stats.get("naval"):
            u.burn = max(0, u.burn - 1)                       # rain and sea water douse a fire
        self._hurt(u, C.BURN_DPS / C.SIM_RATE)
        if u.state == "fighting" and u.burn % 2 == 0:
            self._fx("fire", u.x, u.y)

    def _spikes_hurt(self, u):
        """A man on the ground in a field of spikes is wounded each tick. Cavalry, with their horses, take double."""
        if u.state != "fighting" or u.height > 0 or not self.spikes:
            return                       # a man who burned to death this tick is not hurt again
        for x, y, w, h in self.spikes:
            if x <= u.x < x + w and y <= u.y < y + h:
                self._hurt(u, C.SPIKE_DPS * (2 if u.stats.get("mounted") else 1) / C.SIM_RATE)
                return

    def _rout_threshold(self, u):
        """Morale below this breaks a unit. A unit with rout_after cannot break until that event has fired."""
        after = u.stats.get("rout_after")
        if after is not None and after not in self.fired:
            return -1e9
        return u.stats.get("rout_at", C.ROUT_MORALE)

    def _settle(self):
        for u in self.units:
            if u.state == "fighting" and not u.hero and u.morale < self._rout_threshold(u):
                self._start_rout(u)
        self.units = [u for u in self.units if u.state in ("fighting", "routing")]

    # ------------------------------------------------------------------ fighting
    def _fight(self, u):
        s = u.stats
        if s.get("flying"):
            self._fight_air(u)
            return
        if s.get("naval"):
            self._fight_naval(u)
            return
        if u.nav is not None and u.nav.get("chute"):
            self._descend(u)                           # a paratrooper is helpless until his feet touch the ground
            return
        if u.ambush is not None:
            self._ambusher(u)
            return
        if u.buffs:
            if self._buff(u, "stun"):
                self._separate(u)                      # a stunned man stands dazed
                return
            if u.cooldown > 0 and self.rng.random() < self._buff(u, "work"):
                u.cooldown -= 1                        # a witch's siegecraft: the engine reloads faster
            if u.cds is not None and self._buff(u, "charge"):
                self._charge_hits(u)
        reach = s["reach"] * (1 + self._buff(u, "reach")) if u.buffs else s["reach"]
        if u.cooldown > 0:
            u.cooldown -= 1
        u.retarget -= 1
        t = u.target
        if t is None or not self._valid_target(u, t) or u.retarget <= 0:
            t = self._nearest_enemy(u, s["sight"], focus=True)
            u.target = t
            u.retarget = max(1, round(C.RETARGET_SECONDS * C.SIM_RATE))
            u.formation = self._pick_formation(u, t)     # re-chosen with each new target, not every tick
        if t is None and (s.get("siege") or s.get("struct_only") or s.get("sapper")):
            # no man in sight: a siege engine batters the nearest enemy wall, gate, tower or palisade in reach
            wall = self._structure_in_reach(u, reach)
            if wall is not None:
                if u.cooldown == 0:
                    if s.get("sapper"):
                        self._sap(u, wall)
                    else:
                        self._hit_structure(u, wall)
                    u.cooldown = max(1, round(s["cooldown"] * C.SIM_RATE * (4 if s.get("sapper") else 1)))
                self._separate(u)
                return
        if t is None:
            if u.morale < 100:
                u.morale = min(100.0, u.morale + C.MORALE_REGEN + self._inspiration(u))
            if s.get("sapper") and self._engineer_work(u):
                self._separate(u)
                return
            self._flow_step(u)
        elif self._withdrawing(u):
            self._march_home(u)
        else:
            d = math.hypot(t.x - u.x, t.y - u.y)
            if self._kite(u, t, d):
                pass
            elif d <= reach:
                u.facing = 1 if t.x >= u.x else -1
                if u.cooldown == 0:
                    self._attack(u, t)
                    u.cooldown = max(1, round(s["cooldown"] * C.SIM_RATE))
                elif s["reach"] >= 60 and s["speed"] > 0 and not u.cover and not s.get("siege") and not s.get("air_only"):
                    spot = self._cover_point(u)            # an archer between shots drops into a trench or crater
                    if spot is not None:
                        self._step_toward(u, spot[0], spot[1])
            elif s.get("air_only"):
                self._flow_step(u)                       # a ballista marches with the army: it does not chase a flyer
            elif self._clear(u.x, u.y, t.x, t.y):
                if s.get("mounted") and u.formation != "spear" and d > 50 and not t.stats.get("mounted"):
                    self._step_toward(u, t.x - t.facing * 40, t.y)    # cavalry ride round to hit the foe from behind
                else:
                    self._step_toward(u, t.x, t.y)
            else:
                self._flow_step(u)
        self._separate(u)

    def _lane_pull(self, u, ty):
        """A unit's aim is drawn toward its own lane. On the open field the four lanes are spread across the whole
        battlefield, so an army advances in four columns; they narrow to the gate lanes near a castle gate."""
        w = 0.0                                          # how close to a gate: 1 at the gate, 0 beyond LANE_BLEND
        for x0, x1 in C.LANE_GATE_X:
            w = max(w, 1.0 - max(x0 - u.x, 0.0, u.x - x1) / C.LANE_BLEND)
        lane = C.FIELD_LANES_Y[u.lane] * (1 - w) + C.LANES_Y[u.lane] * w
        pull = C.FIELD_LANE_PULL * (1 - w) + C.LANE_PULL * w
        return ty + (lane - ty) * pull

    def _kite(self, u, t, d):
        """An archer does not stand in a foe's face: when a foe is closer than KITE_DISTANCE of its reach it steps
        back instead of shooting this tick. Returns True when it stepped back."""
        s = u.stats
        if s.get("siege") or s.get("tower") or s.get("air_only") or s["speed"] == 0 or s["reach"] < 60 or d < 1e-6 or d >= C.KITE_DISTANCE * s["reach"]:
            return False                 # a garrison stands on its wall: it cannot step back, so it keeps shooting
        self._move(u, -(t.x - u.x) / d, -(t.y - u.y) / d, s["speed"] / C.SIM_RATE)
        return True

    def _pick_formation(self, u, t):
        """How a unit forms up, given the foe it is after. Cavalry with friends beside them and a foot foe in front
        level their spears. Foot men facing a volley of arrows with no foe in their face lock their shields (testudo)."""
        s = u.stats
        if t is None or u.hero:
            return None
        if s.get("mounted"):
            if t.stats.get("mounted") or t.stats["reach"] >= 60:
                return None
            friends = 0
            for v in self._neighbours(u.x, u.y, C.FORMATION_RADIUS):
                if v is not u and v.side == u.side and v.stats.get("mounted"):
                    friends += 1
                    if friends >= 2:
                        return "spear"
            return None
        if s["reach"] >= 60 or s.get("siege") or s["speed"] == 0:
            return None
        arrows = 0
        for v in self._neighbours(u.x, u.y, C.FORMATION_RADIUS):
            if v.side not in self.enemies[u.side]:
                continue
            if v.stats["reach"] < 60:
                if (v.x - u.x) ** 2 + (v.y - u.y) ** 2 < 40 ** 2:
                    return None                       # a foe is in its face: it keeps its spears up
            elif not v.stats.get("siege"):
                arrows += 1
        return "testudo" if arrows >= C.TESTUDO_ARCHERS else None

    # ------------------------------------------------------------------ ambushes
    def _ambush_tick(self):
        """Runs each side's ambush squads and, now and then, plans a new one."""
        for side in self.sc["sides"]:
            for sq in list(self.squads[side]):
                self._run_squad(side, sq)
            if self.time >= self._next_plan[side] and len(self.squads[side]) < 2:
                self._next_plan[side] = self.time + C.AMBUSH_EVERY
                self._plan_ambush(side)

    def _plan_ambush(self, side):
        """Looks at where the enemy army is heading and sends a squad to lie in wait behind a tree, bush, rock, haystack
        or wagon on its path, out of its sight."""
        enemy = [v for e in self.enemies[side] for v in self._side_units.get(e, ())
                 if v.stats["speed"] > 0 and not v.stats.get("siege")]
        if len(enemy) < 8:
            return
        hx = self.home[side][0]
        van = sorted(enemy, key=lambda v: abs(v.x - hx))[:max(8, len(enemy) // 4)]      # the enemy's leading quarter
        ex = sorted(v.x for v in van)[len(van) // 2]
        ey = sorted(v.y for v in van)[len(van) // 2]
        ahead = 1 if hx > ex else -1                           # the enemy marches toward our side
        px, py = ex + ahead * 350, ey
        used = {sq["prop"] for sqs in self.squads.values() for sq in sqs}
        best = None
        for p in self.cover_props:
            if p in used or math.hypot(p[0] - ex, p[1] - ey) < 280:      # too close and they would be seen early
                continue
            d = math.hypot(p[0] - px, p[1] - py)
            if d <= 160 and (best is None or d < best[0]):
                best = (d, p)
        if best is None:
            return
        prop = best[1]
        mates = [u for u in self._side_units[side]
                 if u.target is None and u.ambush is None and u.stats["speed"] > 0 and not u.hero
                 and not u.stats.get("siege") and not u.stats.get("mounted") and not u.stats.get("air_only")
                 and math.hypot(u.x - prop[0], u.y - prop[1]) < 650]
        if len(mates) < C.AMBUSH_MIN:
            return
        mates.sort(key=lambda u: (u.x - prop[0]) ** 2 + (u.y - prop[1]) ** 2)
        chosen = mates[:C.AMBUSH_SIZE]
        sq = {"prop": prop, "state": "moving", "born": self.time, "spots": {}, "spring": False}
        for i, u in enumerate(chosen):
            ang = 2 * math.pi * i / len(chosen)
            sq["spots"][u.uid] = (prop[0] + math.cos(ang) * prop[2], prop[1] + math.sin(ang) * prop[2] * 0.6)
            u.ambush = sq
        self.squads[side].append(sq)
        self.ambushes_planned += 1

    def _run_squad(self, side, sq):
        members = [u for u in self.units if u.side == side and u.ambush is sq and u.state == "fighting"]
        if len(members) < 2 or self.time - sq["born"] > C.AMBUSH_PATIENCE:
            self._end_squad(side, sq, members, sprung=False)
            return
        foe_near = any(self._nearest_enemy(u, C.AMBUSH_TRIGGER) is not None for u in members[:3])
        if sq["state"] == "moving":
            if foe_near:                                        # found before they were in place: the plan fails
                self._end_squad(side, sq, members, sprung=False)
                return
            arrived = sum(1 for u in members
                          if math.hypot(u.x - sq["spots"][u.uid][0], u.y - sq["spots"][u.uid][1]) < 5)
            if arrived >= 0.7 * len(members) or self.time - sq["born"] > 20:
                sq["state"] = "hiding"
                for u in members:
                    u.hidden = True
        elif foe_near or sq["spring"]:
            self._end_squad(side, sq, members, sprung=True)

    def _end_squad(self, side, sq, members, sprung):
        self.squads[side].remove(sq)
        for u in members:
            u.hidden, u.ambush = False, None
            if sprung:
                u.bonus_until = self.time + C.AMBUSH_BONUS_SECONDS
                self._fx("dust", u.x, u.y)
        for u in self.units:                                    # any who died or routed with the flag still set
            if u.ambush is sq:
                u.ambush = None
        if sprung:
            self.ambushes_sprung += 1
            self._fx("horn", sq["prop"][0], sq["prop"][1])
            for v in self._neighbours(sq["prop"][0], sq["prop"][1], 90):
                if v.side in self.enemies[side] and v.state == "fighting":
                    v.morale -= C.AMBUSH_SHOCK
            self.say(f"{self.sc['sides'][side]['name']} springs an ambush from cover!")

    def _ambusher(self, u):
        """A man in an ambush squad walks to his hiding place and then waits there, unseen and still."""
        sq = u.ambush
        if sq["state"] == "moving":
            spot = sq["spots"].get(u.uid)
            if spot is not None and math.hypot(spot[0] - u.x, spot[1] - u.y) > 3:
                self._step_toward(u, spot[0], spot[1])

    def _withdrawing(self, u):
        """A melee unit that is badly shaken and outnumbered nearby falls back toward its side's start, rather than
        charging on into the enemy."""
        s = u.stats
        if u.hero:                                   # a badly wounded hero pulls back to his side's lines to recover
            return u.hp < C.HERO_RETREAT * s["hp"] and s["reach"] < 60 and bool(self._foes_near(u.side, u.x, u.y, 90))
        if s["reach"] >= 60 or s.get("siege") or u.morale >= C.WITHDRAW_MORALE:
            return False
        friends = foes = 0
        for v in self._neighbours(u.x, u.y, C.WITHDRAW_RADIUS):
            if v is u:
                continue
            if v.side == u.side:
                friends += 1
            elif v.side in self.enemies[u.side]:
                foes += 1
        return foes > friends

    def _march_home(self, u):
        hx, hy = self.home[u.side]
        self._step_toward(u, hx, hy)

    def _inspiration(self, u):
        """Morale regained per tick from friendly heroes close by."""
        bonus = 0.0
        for h in self.inspiring:
            if h.side == u.side and (h.x - u.x) ** 2 + (h.y - u.y) ** 2 <= C.INSPIRE_RADIUS ** 2:
                bonus += C.INSPIRE_REGEN
        return bonus

    def _attack(self, u, t):
        """Melee hits at once. Archers and siege engines loose a projectile instead: it lands after its flight time,
        and only then does it hurt the target (if the target is still there)."""
        s = u.stats
        d = math.hypot(t.x - u.x, t.y - u.y)
        if s.get("air_role") == "ground" or (s.get("multirole") and not t.stats.get("flying")):
            if s.get("swoop") or s.get("multirole"):      # a strafing run: a burst of tracers rakes the target
                ts = t.stats
                sdmg = s["attack"] * self.rng.uniform(*C.DAMAGE_SPREAD)
                sdmg *= 1 - ts["defence"] / (ts["defence"] + C.DEFENCE_K)
                self.air_stats["swoops"] += 1
                self._tracers(u, t, 6)
                if self._hurt(t, max(0.5, sdmg)):
                    self._credit(u)
                return
            self._bomb(u, t)
            return
        if s.get("air_only"):                            # a ballista looses a heavy bolt, true to its mark
            self.air_stats["bolts"] += 1
            self._launch(u, "arrow", self._shot_flight(d, "arrow"), target=t, struct=None, x1=t.x, y1=t.y, bolt=True)
            return
        if s.get("tower"):                                # archers inside loose a volley from the top and the slits
            men = u.nav["men"]
            for i in range(1 + (men >= 3) + (men >= 5)):
                kind = "fire" if s.get("fire") and self.rng.random() < self.wx_fire else "arrow"
                self._launch(u, kind, self._shot_flight(d, "arrow"), target=t, struct=None,
                             x1=t.x + self.rng.uniform(-6, 6), y1=t.y + self.rng.uniform(-4, 4), mult=men / max(1, s["garrison"]) + 0.3)
            return
        if s.get("torpedo"):                              # a submarine fires a torpedo along the water
            self._launch(u, "stone", self._shot_flight(d, "stone"), target=t, struct=None, x1=t.x, y1=t.y)
            return
        if s.get("salvo") or s.get("v2"):                 # a rocket launcher unit: a salvo, or one big V-2
            self._rocket_fire(u, t)
            return
        if s.get("naval") and t.stats.get("flying"):      # a ship's guns throw flak at aircraft
            self._launch(u, "arrow", self._shot_flight(d, "arrow"), target=t, struct=None, x1=t.x, y1=t.y)
            return
        if s.get("siege") or s.get("bombard"):
            self._launch(u, "stone", self._shot_flight(d, "stone"), target=t, struct=None, x1=t.x, y1=t.y)
            return
        if s["reach"] >= 60 and not s.get("flying"):      # (aircraft fall through to the dogfight below)
            if s.get("volley"):
                packed = [v for v in self._neighbours(t.x, t.y, C.SHOWER_RADIUS)
                          if v.side in self.enemies[u.side]]
                if len(packed) >= C.SHOWER_MIN:
                    self._launch(u, "shower", self._shot_flight(d, "arrow"), target=t, struct=None, x1=t.x, y1=t.y,
                                 splash=C.SHOWER_RADIUS)
                    return
            kind = "fire" if (s.get("fire") or self._perk(u, "ignite")) and self.rng.random() < self.wx_fire else "arrow"
            self._launch(u, kind, self._shot_flight(d, "arrow"), target=t, struct=None, x1=t.x, y1=t.y)
            return
        ts = t.stats
        dmg = s["attack"] * self.rng.uniform(*C.DAMAGE_SPREAD)
        dmg *= 1 - ts["defence"] / (ts["defence"] + C.DEFENCE_K)
        if u.buffs:
            dmg *= 1 + self._buff(u, "fury")
        if s.get("hero"):
            dmg *= self._crit(u)
        if u.formation == "spear" and not ts.get("mounted"):
            dmg *= C.SPEAR_BONUS
        if s.get("anti_mounted") and (ts.get("mounted") or ts.get("vehicle")):
            dmg *= C.ANTI_MOUNTED_BONUS         # a bazooka rocket stops a vehicle
        dmg *= self._vet(u)
        if s.get("berserk"):
            dmg *= 1.0 + (1.0 - max(0.05, u.hp / s["hp"])) * C.BERSERK_SCALE  # the lower his hp, the wilder he swings
        if (u.x - t.x) * t.facing < -6:
            dmg *= C.FLANK_BONUS                               # struck from behind: the foe is facing away
        if u.bonus_until > self.time:
            dmg *= C.AMBUSH_BONUS
        dmg = max(0.5, dmg)
        if t.stats.get("flying"):
            self.air_stats["dogfights"] += 1
        if self._hurt(t, dmg):
            self._credit(u)
        t.flash = 2
        if s.get("flying"):                                # aircraft are not melee: a burst of machine-gun tracers
            self._tracers(u, t, 5)
        else:
            self._fx("blood", t.x, t.y)
            self._fx("clash", t.x, t.y)
            self._fx("swing", u.x, u.y, u.uid, t.x)
        if s.get("hero") or t.stats.get("hero"):
            steal = self._perk(u, "lifesteal")
            if steal is not None:
                self._heal(u, dmg * steal["v"])
            thorn = self._perk(t, "thorns")
            if thorn is not None and u.state == "fighting":
                if self._hurt(u, dmg * thorn["v"]):
                    self._credit(t)
                self._fx("clash", u.x, u.y)

    def _shot_flight(self, d, kind):
        """Battle seconds a shot of distance d stays in the air: a longer shot flies longer."""
        speed, (lo, hi) = (C.ARROW_SPEED, C.ARROW_FLIGHT_RANGE) if kind == "arrow" else (C.STONE_SPEED, C.STONE_FLIGHT_RANGE)
        return max(lo, min(hi, d / speed))

    def _tracers(self, u, t, rounds):
        """A burst of machine-gun tracers from an aircraft to its target (the damage is dealt by the caller): a visual
        record only, flying straight from the plane's height to the target's."""
        self.shots.append({"uid": next(_SHOT_IDS), "kind": "arrow", "ammo": "arrow", "src": u.stats["sprite"],
                           "flight": 0.5, "bolt": False, "drop": False, "tracer": rounds,
                           "x0": u.x, "y0": u.y, "x1": t.x, "y1": t.y,
                           "shooter": u.uid, "target": t.uid, "land": "none", "crater": 0, "angle": 0.0,
                           "h0": u.height, "h1": t.height})
        del self.shots[:-150]

    def _launch(self, u, kind, flight, target, struct, x1, y1, splash=None, mult=1.0, slow=0.0, bolt=False):
        """Sends a projectile from u. The visual record goes to the renderer straight away; the damage waits in
        self.projectiles until the flight time has passed. A shower (splash given) falls on everyone round x1, y1."""
        ammo = "fire" if kind == "stone" and self.rng.random() < u.stats.get("fire_ammo", 0) * self.wx_fire else kind
        if kind == "stone" and u.stats.get("smoke_ammo") and self.rng.random() < u.stats["smoke_ammo"]:
            ammo = "smoke"                               # a smoke shell: no damage, a cloud instead
        if kind == "arrow" and u.stats.get("bolt"):
            ammo = u.stats["bolt"]                       # a hero's magic bolt ("holy", "hex")
        flight *= u.stats.get("flight_k", 1.0)
        crit = self._crit(u) if u.stats.get("hero") else 1.0
        power = mult * crit * ((1 + self._buff(u, "fury")) if u.buffs else 1.0) * self._vet(u)
        mx = u.x
        if u.stats.get("naval"):                         # a ship fires from its guns, toward the target's side
            mx += (18 if u.stats.get("bombard") else 10) * (1 if x1 >= u.x else -1)
        self.shots.append({"uid": next(_SHOT_IDS), "kind": kind, "ammo": ammo, "src": u.stats["sprite"],
                           "flight": flight, "bolt": bolt or crit > 1.0, "drop": bool(u.stats.get("flying")),
                           "x0": mx, "y0": u.y, "x1": x1, "y1": y1,
                           "shooter": u.uid, "target": None if target is None else target.uid,
                           "land": "dust" if kind == "stone" else "none",
                           "crater": 7 if kind == "stone" and not (self.shore is not None and y1 >= self.shore) else 0,
                           "angle": u.stats["angle"], "h0": u.height + u.stats.get("shoot_height", 0.0),
                           "torpedo": bool(u.stats.get("torpedo")), "round": u.stats.get("round", ""),
                           "h1": 0.0 if target is None else target.height})
        if u.height > 0:
            self.elevated_shots += 1
        del self.shots[:-150]
        self.projectiles.append({"kind": kind, "shooter": u.uid, "target": None if target is None else target.uid,
                                 "struct": struct, "x1": x1, "y1": y1,
                                 "dmg": u.stats["attack"] * power * (C.AMBUSH_BONUS if u.bonus_until > self.time else 1.0),
                                 "slow": slow,
                                 "splash": u.stats.get("splash", 0.0) if splash is None else splash,
                                 "ammo": ammo, "arrive": self.time + flight})

    def _land_projectiles(self):
        """Lands every projectile whose flight is over. A projectile whose target has died, or whose shooter has
        gone, is dropped without effect."""
        if not self.projectiles:
            return
        by_uid = {u.uid: u for u in self.units if u.state in ("fighting", "routing")}
        still_flying = []
        for p in self.projectiles:
            if p["arrive"] > self.time:
                still_flying.append(p)
                continue
            shooter = by_uid.get(p["shooter"])
            if p.get("area"):
                self._land_area(p, shooter)              # a hero's strike lands even if the hero has since fallen
                continue
            if shooter is None:
                continue                 # the shooter is dead or gone: the shot fizzles
            if p.get("ammo") == "smoke":
                self._add_smoke(p["x1"], p["y1"])
                continue
            if p["struct"] is not None:
                t = next((x for x in self.terrain if x["id"] == p["struct"] and not x["hidden"]), None)
                if t is not None:
                    self._damage_structure(t, p["dmg"])
                continue
            if p["splash"]:
                self._hit_structures_near(p["x1"], p["y1"], p["splash"], p["dmg"] * 0.8)
            target = by_uid.get(p["target"])
            if target is None:
                continue                 # the target has died or gone: the shot fizzles
            self._hit_unit(shooter, target, p["dmg"], p["kind"])
            if p.get("slow") and target.state == "fighting":
                self._give(target, "slow", p["slow"], 5.0)
            if p["splash"]:
                self._splash(shooter, target, p["splash"], p["dmg"])
            if p.get("ammo") == "fire":                  # a pot of burning pitch: everyone near the landing is alight
                for v in self._neighbours(target.x, target.y, max(p["splash"], 14)):
                    if v.state == "fighting" and v.side in self.enemies[shooter.side]:
                        v.burn = int(C.BURN_SECONDS * C.SIM_RATE)
        self.projectiles = still_flying

    def _hit_unit(self, shooter, target, base, kind):
        ts = target.stats
        if kind == "fire":
            target.burn = int(C.BURN_SECONDS * C.SIM_RATE)     # a flaming arrow sets its target alight
        if target.stats.get("flying") and kind != "stone" and not (shooter is not None and shooter.stats.get("air_only")) \
                and target.uid not in self.lit:
            base *= C.AIR_DODGE                                # a flyer is hard to hit (unless a searchlight has it)
        if shooter is not None and shooter.stats.get("anti_mounted") and (ts.get("mounted") or ts.get("vehicle")):
            base *= C.ANTI_MOUNTED_BONUS
        if kind != "stone":
            base *= self.wx_arrow                              # wet bowstrings and wind
            if target.stats.get("naval"):
                base *= C.NAVAL_ARROW                          # planks and shields turn arrows
        if target.formation == "testudo" and kind != "stone" and not (shooter is not None and shooter.stats.get("pierce_shield")):
            base *= C.TESTUDO_RANGED  # a pavise bolt punches straight through locked shields                           # locked shields turn aside arrows and showers
        if target.cover and kind != "stone":
            base *= C.COVER_SHOT                               # a trench or a crater shelters a man from arrows
        dmg = base * self.rng.uniform(*C.DAMAGE_SPREAD) * (1 - ts["defence"] / (ts["defence"] + C.DEFENCE_K))
        target.flash = 2
        self._fx("dust" if kind == "stone" else "blood", target.x, target.y)
        if shooter is not None and shooter.stats.get("hero"):
            steal = self._perk(shooter, "lifesteal")
            if steal is not None:
                self._heal(shooter, dmg * steal["v"])
        if self._hurt(target, max(0.5, dmg)) and shooter is not None:
            self._credit(shooter)

    def _splash(self, shooter, target, radius, base):
        """A catapult or trebuchet stone also hits the men round where it lands."""
        for v in self._neighbours(target.x, target.y, radius):
            if v is target or v.state != "fighting" or shooter is None or v.side == shooter.side:
                continue
            if v.side not in self.enemies[shooter.side]:
                continue
            if math.hypot(v.x - target.x, v.y - target.y) > radius:
                continue
            vd = v.stats["defence"]
            sdmg = base * 0.5 * self.rng.uniform(*C.DAMAGE_SPREAD) * (1 - vd / (vd + C.DEFENCE_K))
            if self._hurt(v, max(0.5, sdmg)):
                shooter.kills += 1

    def _structure_in_reach(self, u, reach):
        """The nearest standing enemy structure (a wall, gate, tower or palisade) within reach of u, or None."""
        best, best_d = None, reach
        for t in self.terrain:
            if t["hidden"] or not t["solid"] or t.get("hp") is None or t.get("owner") not in self.enemies[u.side]:
                continue
            x, y, w, h = t["rect"]
            d = math.hypot(min(max(u.x, x), x + w) - u.x, min(max(u.y, y), y + h) - u.y)
            if d < best_d:
                best, best_d = t, d
        for t in self.terrain:                              # a bridge foes are crossing (and none of ours): bring it down
            if t.get("style") != "bridge" or t["hidden"]:
                continue
            x, y, w, h = t["rect"]
            d = math.hypot(min(max(u.x, x), x + w) - u.x, min(max(u.y, y), y + h) - u.y)
            if d >= best_d:
                continue
            near = self._neighbours(x + w / 2, y + h / 2, 60)
            if any(v.side in self.enemies[u.side] for v in near) and not any(v.side == u.side for v in near):
                best, best_d = t, d
        return best

    def _hit_structure(self, u, t):
        """A siege engine looses a stone at a structure. The stone hits when it lands."""
        x, y, w, h = t["rect"]
        cx, cy = x + w / 2, y + h / 2
        s_angle = u.stats["angle"]
        ammo = "fire" if self.rng.random() < u.stats.get("fire_ammo", 0) else "stone"
        flight = self._shot_flight(math.hypot(cx - u.x, cy - u.y), "stone")
        self.shots.append({"uid": next(_SHOT_IDS), "kind": "stone", "ammo": ammo, "src": u.stats["sprite"],
                           "flight": flight,
                           "x0": u.x, "y0": u.y, "x1": cx, "y1": cy,
                           "shooter": u.uid, "target": None, "land": "dust", "crater": 6, "angle": s_angle,
                           "h0": u.height, "h1": 0.0})
        if u.height > 0:
            self.elevated_shots += 1
        del self.shots[:-150]
        self.projectiles.append({"kind": "stone", "shooter": u.uid, "target": None, "struct": t["id"],
                                 "x1": cx, "y1": cy, "dmg": u.stats["attack"], "splash": 0.0,
                                 "ammo": ammo, "arrive": self.time + flight})

    def _damage_structure(self, t, base):
        """A stone hits a structure. When its hit points run out it is breached: it is removed."""
        dmg = base * self.rng.uniform(*C.DAMAGE_SPREAD)
        self.structure_hits += 1
        x, y, w, h = t["rect"]
        cx, cy = x + w / 2, y + h / 2
        t["hp"] -= dmg
        if t["hp"] > 0:
            return
        if t.get("style") == "bridge":
            self._break_bridge(t)
            return
        self.terrain = [q for q in self.terrain if q is not t]
        self._refresh_walls()
        for g in self.units:                 # the men standing on top of a breached block fall with it
            if g.perch == t["id"] and g.state == "fighting":
                self._hurt(g, 1e9)
        self._fx("breach", cx, cy)
        self.say(f"The {t.get('name') or t['id']} is breached!")

    def _fx(self, kind, x, y, *extra):
        self.fx.append((kind, x, y) + extra)
        del self.fx[:-200]

    def drain_fx(self):
        """The effects since the last call (the renderer uses these for blood, dust and breaches)."""
        out, self.fx = self.fx, []
        return out

    def _hurt(self, u, dmg):
        """Apply damage. Returns True if the unit died."""
        if u.state == "dead":
            return False                 # already down (a second arrow in flight, a burst landing on a corpse)
        if u.buffs:
            dmg *= (1 + self._buff(u, "vuln")) * (1 - min(0.85, self._buff(u, "guard")))
        u.hp -= dmg
        u.morale -= dmg * C.MORALE_PER_DAMAGE
        if u.nav is not None and u.stats.get("tower"):
            u.nav["men"] = max(0, math.ceil(u.stats["garrison"] * max(0.0, u.hp) / u.stats["hp"]))   # men fall with the tower
        if u.hidden and u.ambush is not None:
            u.ambush["spring"] = True                          # a hidden man who is hurt gives the squad away
        if u.stats.get("immortal") and u.hp < 1:
            u.hp = 1.0                   # a hero the story has survive the battle cannot fall in play
        if u.hp > 0:
            return False
        u.state = "dead"
        self.lost[u.side] += 1
        self._fx("blood", u.x, u.y)
        if u.stats.get("tower"):                                  # the tower collapses and the survivors tumble out
            self._fx("collapse", u.x, u.y)
            out = max(1, round(u.stats["garrison"] * 0.6))
            self.spawn(u.side, "machine_gunner", out, [u.x - 16, u.y - 8, 32, 16])
            self.say(f"A {u.stats['name'].lower()} falls.")
        if u.stats.get("naval"):
            self.naval_stats["sunk"] += 1
            self._fx("sink", u.x, u.y, u.side, u.kind, u.facing)      # the ship goes down
        elif u.stats.get("flying"):
            self.air_stats["air_losses"] += 1
            tx, ty = self._plan_crash(u)
            self._fx("plunge", u.x, u.y, u.height, u.side, u.kind, tx, ty)      # the aircraft falls from the sky
        else:
            self._fx("corpse", u.x, u.y, u.side, u.kind, u.height)
        if u.name is not None:
            rec = self.heroes[u.name]
            rec["status"] = "fallen"
            rec["fell_at"] = round(self.time, 1)
            rec["respawn_at"] = self.time + u.stats.get("respawn", C.HERO_RESPAWN)
            self.hero_log.append((self.time, u.name, "fall"))
            self._fx("hero_fall", u.x, u.y, u.uid)
            self.say(f"{u.name} falls.")
        self._death_shock(u)
        return True

    def _death_shock(self, dead):
        for v in self._neighbours(dead.x, dead.y, C.MORALE_RADIUS):
            if v is dead or v.state != "fighting":
                continue
            if math.hypot(v.x - dead.x, v.y - dead.y) > C.MORALE_RADIUS:
                continue
            if v.side == dead.side:
                v.morale -= C.MORALE_ALLY_DEATH
            elif dead.side in self.enemies[v.side]:
                v.morale = min(100.0, v.morale + C.MORALE_ENEMY_DEATH)

    def _start_rout(self, u):
        u.state = "routing"
        u.target = None
        u.formation = None
        u.hidden, u.ambush = False, None
        foe = self._nearest_enemy(u, 250)
        if foe is not None:
            dx, dy = u.x - foe.x, u.y - foe.y
        else:
            gx, gy = self.sc["sides"][u.side]["goal"]
            dx, dy = u.x - gx, u.y - gy
        d = math.hypot(dx, dy) or 1.0
        u.rout_dx, u.rout_dy = dx / d, dy / d

    def _rout(self, u):
        u.rout_time += 1.0 / C.SIM_RATE
        speed = u.stats["speed"] * C.ROUT_SPEED / C.SIM_RATE
        self._move(u, u.rout_dx, u.rout_dy, speed)
        off_map = u.x <= 0 or u.y <= 0 or u.x >= self.W or u.y >= self.H
        if off_map or u.rout_time >= C.ROUT_LIMIT:
            u.state = "fled"
            self.fled[u.side] += 1

    # ------------------------------------------------------------------ movement
    def _step_toward(self, u, tx, ty):
        dx, dy = tx - u.x, ty - u.y
        d = math.hypot(dx, dy)
        if d > 1e-6:
            self._move(u, dx / d, dy / d, u.stats["speed"] / C.SIM_RATE)

    def _flow_step(self, u):
        field = self.flow.get(u.side)
        if field is None:
            return
        gx, gy = self.sc["sides"][u.side]["goal"]
        if math.hypot(gx - u.x, gy - u.y) < 14:
            return
        cols = self._cols
        cx = min(max(int(u.x // C.FLOW_CELL), 0), cols - 1)
        cy = min(max(int(u.y // C.FLOW_CELL), 0), self._rows - 1)
        here = field[cy * cols + cx]
        best, best_d = None, here
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = cx + dx, cy + dy
                if (dx == 0 and dy == 0) or not (0 <= nx < cols and 0 <= ny < self._rows):
                    continue
                nd = field[ny * cols + nx]
                if nd < best_d:
                    best, best_d = (nx, ny), nd
        if best is not None:
            tx = (best[0] + 0.5) * C.FLOW_CELL
            ty = self._lane_pull(u, (best[1] + 0.5) * C.FLOW_CELL)
            self._step_toward(u, tx, ty)

    def _move(self, u, ux, uy, dist):
        dist *= self.wx_walk                              # mud and snow
        if u.buffs:
            dist *= (1 + self._buff(u, "haste")) * max(0.2, 1 - self._buff(u, "slow"))
        while dist > 24:                                  # a charge covers ground in short hops so it cannot skip a wall
            self._move1(u, ux, uy, 24)
            dist -= 24
        self._move1(u, ux, uy, dist)

    def _move1(self, u, ux, uy, dist):
        r = C.UNIT_RADIUS
        if u.formation == "testudo":
            dist *= C.TESTUDO_SPEED                             # a locked shield wall moves slowly
        if u.cover:
            dist *= C.TRENCH_SPEED * (0.7 if u.stats.get("mounted") else 1.0)   # climbing through a trench is slow
        ox, oy = u.x, u.y
        nx = min(max(u.x + ux * dist, r), self.W - r)
        ny = min(max(u.y + uy * dist, r), self.H - r)
        if self.shore is not None:
            ny = min(ny, self.shore - r - 2)                   # the water's edge: men on foot stop at the sand
        if not self._blocked(nx, ny, r):
            u.x, u.y = nx, ny
        elif not self._blocked(nx, u.y, r):
            u.x = nx                     # blocked diagonally: slide along the wall on the free axis
        elif not self._blocked(u.x, ny, r):
            u.y = ny
        if u.x - ox > 0.05:
            u.facing = 1
        elif ox - u.x > 0.05:
            u.facing = -1

    def _separate(self, u):
        sep = C.SEPARATION
        for v in self._neighbours(u.x, u.y, sep):
            if v is u or v.state != "fighting":
                continue
            dx, dy = u.x - v.x, u.y - v.y
            d = math.hypot(dx, dy)
            if d >= sep:
                continue
            if d < 1e-6:
                dx, dy, d = self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), 1.0
            push = (sep - d) * 0.3
            nx, ny = u.x + dx / d * push, u.y + dy / d * push
            r = C.UNIT_RADIUS
            if self.shore is not None:
                ny = min(ny, self.shore - r - 2)
            if r <= nx <= self.W - r and r <= ny <= self.H - r and not self._blocked(nx, ny, r):
                u.x, u.y = nx, ny

    def _blocked(self, x, y, r):
        for rx, ry, rw, rh in self._wall_grid.get((int(x // 64), int(y // 64)), ()):
            if rx - r < x < rx + rw + r and ry - r < y < ry + rh + r:
                return True
        return False

    def _clear(self, x0, y0, x1, y1):
        """True when the straight line between two points does not cross solid terrain."""
        steps = max(2, int(math.hypot(x1 - x0, y1 - y0) // 8))
        for i in range(1, steps + 1):
            t = i / steps
            if self._blocked(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 0):
                return False
        return True

    # ------------------------------------------------------------------ spatial grid and flow field
    def _build_index(self):
        """KD-trees over the fighting units, rebuilt each tick: one for everyone (crowding, morale), and one per
        side (finding the nearest enemy). Positions can be a fraction of a step stale; that is fine here."""
        self._all = [u for u in self.units if u.state == "fighting" and not u.stats.get("flying")
                     and not u.stats.get("naval")]
        self._sea = [u for u in self.units if u.state == "fighting" and u.stats.get("naval")]
        self._air = [u for u in self.units if u.state == "fighting" and u.stats.get("flying")]
        self._centers = {}
        self._routers = [u for u in self.units if u.state == "routing"]
        self._tree_all = cKDTree(np.array([(u.x, u.y) for u in self._all])) if self._all else None
        self._side_units = {sid: [] for sid in self.sc["sides"]}
        for u in self._all:
            if not u.hidden:                             # a man in hiding cannot be seen, so he cannot be targeted
                self._side_units[u.side].append(u)
        self._side_trees = {sid: cKDTree(np.array([(u.x, u.y) for u in us]))
                            for sid, us in self._side_units.items() if us}
        self._air_units = {sid: [] for sid in self.sc["sides"]}
        for u in self._air:
            self._air_units[u.side].append(u)
        self._air_trees = {sid: cKDTree(np.array([(u.x, u.y) for u in us]))
                           for sid, us in self._air_units.items() if us}
        self._sea_units = {sid: [] for sid in self.sc["sides"]}
        self._subs = {sid: [] for sid in self.sc["sides"]}          # submarines: only destroyers can find them
        for u in self._sea:
            (self._subs if u.stats.get("submerged") else self._sea_units)[u.side].append(u)
        self._sea_trees = {sid: cKDTree(np.array([(u.x, u.y) for u in us]))
                           for sid, us in self._sea_units.items() if us}

    def _neighbours(self, x, y, radius):
        if self._tree_all is None:
            return []
        return [self._all[i] for i in self._tree_all.query_ball_point((x, y), radius)]

    def _valid_target(self, u, t):
        if t.state == "fighting":
            return True
        return t.state == "routing" and bool(u.stats.get("hunts_routers"))

    def _nearest_enemy(self, u, radius, focus=False):
        """The enemy to attack. Plain: the nearest. With focus: among the nearest few, the one that is nearest and most
        hurt (so a unit finishes off a wounded man rather than spreading its blows). Used for fleeing too (no focus)."""
        if u.stats.get("struct_only"):
            return None                    # a battering ram ignores enemies
        radius *= self.wx_sight           # fog, rain and snow shorten how far men see
        best, best_key = None, None
        role = u.stats.get("air_role")
        multi = bool(u.stats.get("multirole"))             # a heavy fighter hunts flyers and ground targets alike
        air_only = (role == "air" and not multi) or u.stats.get("air_only")
        for sid in (() if air_only else self.enemies[u.side]):               # an interceptor or ballista looks only at flyers
            tree = self._side_trees.get(sid)
            if tree is None:
                continue
            n = len(self._side_units[sid])
            ds, idx = tree.query((u.x, u.y), k=min(C.FOCUS_NEIGHBOURS if focus else 1, n),
                                 distance_upper_bound=radius)
            for d, i in zip(np.atleast_1d(ds), np.atleast_1d(idx)):
                if not np.isfinite(d) or i >= n:
                    continue
                v = self._side_units[sid][int(i)]
                if v.state != "fighting":
                    continue
                key = d * (0.5 + v.hp / v.stats["hp"]) if focus else d
                if best_key is None or key < best_key:
                    best, best_key = v, key
        if air_only or multi or (role is None and u.stats["reach"] >= 60 and not u.stats.get("siege")):
            # flyers are shot at by archers and fought by interceptors; a bomber never looks up
            reach = radius if role == "air" else min(radius, u.stats["reach"])
            for sid in self.enemies[u.side]:
                tree = self._air_trees.get(sid)
                if tree is None:
                    continue
                d, i = tree.query((u.x, u.y), k=1, distance_upper_bound=reach)
                if np.isfinite(d) and (best_key is None or d < (best_key if not focus else math.hypot(
                        best.x - u.x, best.y - u.y))):
                    v = self._air_units[sid][int(i)]
                    best, best_key = v, d
        if self._sea and not air_only and not u.stats.get("naval") and (
                role == "ground" or u.stats["reach"] >= 60 or u.stats.get("siege")):
            # ships are shot at from the beach, by siege engines and by heroes, and bombed from the air
            v, d = self._sea_nearest(u, radius if role == "ground" else min(radius, u.stats["reach"]))
            if v is not None and (best_key is None or d < best_key):
                best, best_key = v, d
        if best is not None and self.smokes and not best.stats.get("flying") and self._smoked(best, u):
            best = None                                 # a man in a smoke cloud cannot be seen from afar
        if u.stats.get("hunts_routers"):                # Huorns also run down routing Orcs
            for v in self._routers:
                if v.side in self.enemies[u.side]:
                    d = math.hypot(v.x - u.x, v.y - u.y)
                    if d <= radius and (best_key is None or d < best_key):
                        best, best_key = v, d
        return best

    def _rebuild_flow(self):
        """For each side, a Dijkstra distance field to its goal. Solid cells are passable at a high cost,
        so units push up against walls and only go round them when that is shorter."""
        cell = C.FLOW_CELL
        cols = math.ceil(self.W / cell)
        rows = math.ceil(self.H / cell)
        self._cols, self._rows = cols, rows
        xs = (np.arange(cols) + 0.5) * cell
        ys = (np.arange(rows) + 0.5) * cell
        X, Y = np.meshgrid(xs, ys)
        mask = np.zeros((rows, cols), dtype=bool)
        for rx, ry, rw, rh in self.walls:               # same rule as rect_contains, for every cell at once
            mask |= (X >= rx) & (X < rx + rw) & (Y >= ry) & (Y < ry + rh)
        if self.shore is not None:                       # the sea is no place to walk: the flow field steers round it
            mask |= Y >= self.shore - 6
        solid = mask.ravel().tolist()
        # the grid as a sparse graph: an edge into a cell costs the step plus WALL_COST if the cell is solid.
        # SciPy's Dijkstra then runs the search in compiled code (it was ~0.2 s in pure Python).
        n = cols * rows
        solid_arr = np.asarray(solid, dtype=float)
        idx = np.arange(n)
        cx, cy = idx % cols, idx // cols
        srcs, dsts, ws = [], [], []
        for dx, dy, step in ((-1, -1, 1.414), (0, -1, 1.0), (1, -1, 1.414), (-1, 0, 1.0),
                             (1, 0, 1.0), (-1, 1, 1.414), (0, 1, 1.0), (1, 1, 1.414)):
            nx, ny = cx + dx, cy + dy
            ok = (nx >= 0) & (nx < cols) & (ny >= 0) & (ny < rows)
            dst = (ny * cols + nx)[ok]
            srcs.append(idx[ok])
            dsts.append(dst)
            ws.append(step + C.WALL_COST * solid_arr[dst])
        graph = csr_matrix((np.concatenate(ws), (np.concatenate(srcs), np.concatenate(dsts))), shape=(n, n))
        self.flow = {}
        for sid, sd in self.sc["sides"].items():
            gx = min(max(int(sd["goal"][0] // cell), 0), cols - 1)
            gy = min(max(int(sd["goal"][1] // cell), 0), rows - 1)
            dist = dijkstra(graph, directed=True, indices=gy * cols + gx)
            self.flow[sid] = dist.tolist()
        self.flow_dirty = False

    # ------------------------------------------------------------------ scenario events and objectives
    def _holds(self, c):
        k = c["type"]
        if k == "time":
            return self.time >= c["at"]
        if k == "all":
            return all(self._holds(x) for x in c["conditions"])
        if k == "any":
            return any(self._holds(x) for x in c["conditions"])
        if k == "not":
            return not self._holds(c["condition"])
        if k == "event_fired":
            return c["event"] in self.fired
        if k == "wave":
            # true once for every `every` firings of another event (every 5th muster wave): it holds while that event has
            # fired more such multiples than the event being tested has
            return self.fire_count.get(c["event"], 0) // c["every"] > self.fire_count.get(self._cur_event, 0)
        if k == "after":
            t0 = self.last_fired.get(c["event"])
            return t0 is not None and self.time - t0 >= c["seconds"]
        if k == "terrain_hidden":
            return any(t["id"] == c["id"] and t["hidden"] for t in self.terrain)
        if k == "side_below":
            return sum(1 for u in self.units if u.side == c["side"]) < c["count"]
        if k == "side_eliminated":
            # routing units still count as present until they have run away or been caught
            present = sum(1 for u in self.units if u.side == c["side"] and u.state in ("fighting", "routing"))
            return present == 0 and not self._reinforcements_pending(c["side"])
        if k == "side_reaches":
            return any(u.side == c["side"] and u.state == "fighting" and rect_contains(c["area"], u.x, u.y)
                       for u in self.units)
        if k == "units_in_area":
            n = sum(1 for u in self.units if u.side == c["side"] and u.state == "fighting"
                    and rect_contains(c["area"], u.x, u.y))
            return n >= c["count"]
        return False

    def _reinforcements_pending(self, side):
        for ev in self.sc["events"]:
            if ev.get("repeat") or ev["id"] in self.fired:
                continue
            if any(a["type"] == "spawn" and a["side"] == side for a in ev["actions"]):
                return True
        return False

    def _run_events(self):
        """Fire each event whose trigger holds. A one-off event fires once; a repeating one fires again when its
        cooldown (seconds) has passed and its trigger still holds."""
        for ev in self.sc["events"]:
            eid = ev["id"]
            if ev.get("repeat"):
                last = self.last_fired.get(eid)
                if last is not None and self.time - last < ev.get("cooldown", 0.0):
                    continue
            elif eid in self.fired:
                continue
            self._cur_event = eid
            if not self._holds(ev["trigger"]):
                continue
            self.fired.add(eid)
            self.fire_count[eid] = self.fire_count.get(eid, 0) + 1
            self.last_fired[eid] = self.time
            self.fire_log.append((round(self.time, 1), eid))
            for a in ev["actions"]:
                self._do(a)

    def _do(self, a):
        if a["type"] == "spawn":
            self.spawn(a["side"], a["unit_type"], a["count"], a["area"], a.get("name"))
        elif a["type"] == "remove_terrain":
            self.terrain = [t for t in self.terrain if t["id"] != a["id"]]
            self._refresh_walls()
        elif a["type"] in ("show_terrain", "hide_terrain"):
            for t in self.terrain:
                if t["id"] == a["id"]:
                    t["hidden"] = a["type"] == "hide_terrain"
                    if t.get("style") == "gate":
                        self._fx("gate", t["rect"][0] + t["rect"][2] / 2, t["rect"][1] + t["rect"][3] / 2)
            self._refresh_walls()
        elif a["type"] == "set_goal":
            self.sc["sides"][a["side"]]["goal"] = list(a["point"])
            self.flow_dirty = True
        elif a["type"] == "message":
            self.say(a["text"])
        elif a["type"] == "barrage":
            self._barrage(a)

    def _update_objectives(self):
        for o in self.sc["objectives"]:
            if not self.objectives_done[o["id"]] and self._holds(o["when"]):
                self.objectives_done[o["id"]] = True
                self.say(f"Objective complete: {o['text']}")

