"""Field extras for the WW2 battle: the things that are not a plain "unit hits unit".

  medics        heal the wounded friends around them
  engineers     blow breaches in walls with satchel charges and clear minefields
  minefields    terrain of style "mines": hidden mines that blast whatever steps on them (vehicles worst)
  barbed wire   terrain of style "wire": slows men on foot; tanks and engineers cut through it
  smoke         a mortar's smoke shell leaves a cloud that hides whoever stands in it from distant eyes
  supply        a transport plane drops a crate on its own army; whoever walks to it is healed and steadied
  paratroopers  a transport plane drops a stick of them behind the enemy; they float down helpless, then fight
  searchlights  `searchlights` in the scenario: enemy aircraft caught in a beam cannot dodge ground fire
  carpet bombs  a heavy bomber flies a long run over the enemy army, shedding bombs as it goes
  veterancy     a unit that kills enough rises in rank and hits harder
  weather       bombers and transports will not fly in bad weather, fighters not in a storm

Everything is driven by unit-type flags and terrain styles in the scenario file (see the README). Extras is a mixin for
Battle."""
import math
import random

import config as C


def rank_of(kills):
    """Veteran rank 0..3 for a unit with this many kills."""
    r = 0
    for n in C.VET_KILLS:
        if kills >= n:
            r += 1
    return r


class FieldExtras:
    def _extras_init(self):
        self.smokes = []                 # clouds: {x, y, r, born, until}
        self.crates = []                 # supply crates: {x, y, side, born, land_at, until}
        self.lit = set()                 # uids of aircraft caught in a searchlight beam this tick
        self.searchlights = [dict(s) for s in self.sc.get("searchlights", [])]
        self.extra_stats = {"mines": 0, "defused": 0, "healed": 0.0, "crates": 0, "paratroopers": 0, "smoke": 0,
                            "promotions": 0, "grounded": 0, "breaches": 0, "wire_cut": 0, "carpet": 0}
        self.minefields = []
        self.crashes = []                # stricken aircraft on their way down: {x, y, r, dmg, at}
        self.broken_bridges = []         # bridges that have fallen: {bridge, progress}, waiting for engineers
        self.pontoon_wip = {}            # river block id -> engineer-seconds spent floating a pontoon there
        self.pontoon_count = 0
        rng = random.Random(self.sc["seed"] * 31 + 7)        # its own dice: laying mines does not disturb the fighting
        for t in self.terrain:
            if t.get("style") == "mines":
                x, y, w, h = t["rect"]
                n = max(4, int(w * h / C.MINE_SPACING ** 2))
                self.minefields.append({"t": t, "owner": t.get("owner"),
                                        "mines": [[rng.uniform(x, x + w), rng.uniform(y, y + h)] for _ in range(n)]})

    # ------------------------------------------------------------------ each tick
    def _extras_tick(self):
        now = self.time
        if self.smokes:
            self.smokes = [s for s in self.smokes if s["until"] > now]
        if self.crates:
            self.crates = [c for c in self.crates if c["until"] > now]
            self._crate_tick()
        self._lit_tick()
        self._medic_tick()
        if self.crashes:
            self._crash_tick()

    def _medic_tick(self):
        for u in self._all:
            h = u.stats.get("heal")
            if not h or u.state != "fighting":
                continue
            r = u.stats.get("heal_radius", 60)
            hurt = [v for v in self._neighbours(u.x, u.y, r)
                    if v is not u and v.side == u.side and v.hp < v.stats["hp"] - 0.5]
            if not hurt:
                continue
            hurt.sort(key=lambda v: v.hp / v.stats["hp"])
            for v in hurt[:3]:
                amount = h / C.SIM_RATE
                self._heal(v, amount)
                self.extra_stats["healed"] += amount
            if self.tick_count % 4 == 0:
                self._fx("heal", hurt[0].x, hurt[0].y)

    def _lit_tick(self):
        self.lit = set()
        for sl in self.searchlights:
            r = sl.get("range", C.SEARCH_RANGE)
            for e in self.enemies[sl["side"]]:
                for a in self._air_units.get(e, ()):
                    if (a.x - sl["x"]) ** 2 + (a.y - sl["y"]) ** 2 < r * r:
                        self.lit.add(a.uid)

    def _crate_tick(self):
        for c in list(self.crates):
            if self.time < c["land_at"]:
                continue
            for v in self._neighbours(c["x"], c["y"], 17):
                if v.side == c["side"] and v.state == "fighting" and not v.stats.get("flying"):
                    self._heal(v, v.stats["hp"] * C.CRATE_HEAL)
                    v.morale = min(100.0, v.morale + C.CRATE_MORALE)
                    v.burn = 0
                    self.crates.remove(c)
                    self.extra_stats["crates"] += 1
                    self._fx("supply", c["x"], c["y"])
                    break

    # ------------------------------------------------------------------ hazards a unit walks into
    def _extras_unit(self, u):
        s = u.stats
        if u.state != "fighting" or s.get("flying") or s.get("naval") or s["speed"] <= 0:
            return
        x, y = u.x, u.y
        sapper = s.get("sapper")
        for mf in self.minefields:
            if mf["t"]["hidden"] or not mf["mines"]:
                continue
            rx, ry, rw, rh = mf["t"]["rect"]
            if not (rx - 18 <= x < rx + rw + 18 and ry - 18 <= y < ry + rh + 18):
                continue
            own = mf["owner"] == u.side
            keep = []
            for m in mf["mines"]:
                d2 = (m[0] - x) ** 2 + (m[1] - y) ** 2
                if sapper and not own and d2 < C.MINE_DEFUSE ** 2:
                    self.extra_stats["defused"] += 1
                    self._fx("defuse", m[0], m[1])
                    continue
                if not own and d2 < C.MINE_TRIGGER ** 2 and u.height == 0:
                    dmg = C.MINE_DAMAGE * (C.MINE_VEHICLE if s.get("vehicle") else 1.0)
                    self.extra_stats["mines"] += 1
                    self._fx("mine", m[0], m[1])
                    self._hurt(u, dmg)
                    if u.state != "fighting":
                        continue
                    continue
                keep.append(m)
            mf["mines"] = keep
        for hx, hy, hw, hh in self.hills:                       # a hill: harder to hit, longer sight, slow to climb
            if hx <= x < hx + hw and hy <= y < hy + hh:
                ex, ey = (x - hx - hw / 2) / (hw / 2), (y - hy - hh / 2) / (hh / 2)
                if ex * ex + ey * ey <= 1.0:
                    self._give(u, "guard", C.HILL_GUARD, 1.0)
                    self._give(u, "reach", C.HILL_REACH, 1.0)
                    self._give(u, "slow", C.HILL_SLOW, 1.0)
                    break
        for t in self.pontoons:                                  # a pontoon sags under whatever crosses it
            px, py, pw, ph = t["rect"]
            if px <= x < px + pw and py <= y < py + ph:
                t["hp"] -= C.VEHICLE_ON_PONTOON if s.get("vehicle") else C.FOOT_ON_PONTOON
                if t["hp"] <= 0:
                    self._break_bridge(t)
                break
        for t in self.wires:
            wx, wy, ww, wh = t["rect"]
            if wx <= x < wx + ww and wy <= y < wy + wh:
                if s.get("vehicle") or sapper:
                    t["hp"] = (t["hp"] if t["hp"] is not None else 60.0) - (5.0 if s.get("vehicle") else 12.0)
                    if t["hp"] <= 0:
                        self.terrain = [q for q in self.terrain if q is not t]
                        self._refresh_walls()
                        self.extra_stats["wire_cut"] += 1
                        self._fx("wire_cut", wx + ww / 2, wy + wh / 2)
                else:
                    self._give(u, "slow", C.WIRE_SLOW, 0.8)
                break

    # ------------------------------------------------------------------ engineers
    def _sap(self, u, wall):
        """An engineer plants a satchel charge on the wall: a breaching blow, and a bruise for the man who set it."""
        self.extra_stats["breaches"] += 1
        self._damage_structure(wall, u.stats.get("charge", 80.0) * self._vet(u))
        x, y, w, h = wall["rect"]
        self._fx("blast", min(max(u.x, x), x + w), min(max(u.y, y), y + h))
        self._hurt(u, 10.0)

    # ------------------------------------------------------------------ smoke
    def _add_smoke(self, x, y):
        self.smokes.append({"x": x, "y": y, "r": C.SMOKE_RADIUS, "born": self.time, "until": self.time + C.SMOKE_SECONDS})
        self.extra_stats["smoke"] += 1

    def _smoked(self, v, u):
        """True when v stands in a smoke cloud and u is too far off to see through it."""
        for s in self.smokes:
            if (v.x - s["x"]) ** 2 + (v.y - s["y"]) ** 2 < s["r"] ** 2 and \
                    (v.x - u.x) ** 2 + (v.y - u.y) ** 2 > (s["r"] * 0.9) ** 2:
                return True
        return False

    # ------------------------------------------------------------------ veterancy
    def _vet(self, u):
        m = 1.0
        for n, b in zip(C.VET_KILLS, C.VET_DAMAGE):
            if u.kills >= n:
                m = b
        return m

    def _promote(self, u):
        if u.kills in C.VET_KILLS and not u.hero:
            self._heal(u, u.stats["hp"] * C.VET_HEAL)
            u.morale = 100.0
            self.extra_stats["promotions"] += 1
            self._fx("rank", u.x, u.y, u.uid)

    # ------------------------------------------------------------------ paratroopers
    def _descend(self, u):
        u.height = max(0.0, u.height - C.CHUTE_SPEED / C.SIM_RATE)
        if u.height <= 0:
            u.nav = None
            self._fx("dust", u.x, u.y)

    # ------------------------------------------------------------------ weather
    def _harsh(self, s):
        w = self.wx
        if s.get("fair_weather"):
            return w["rain"] > 0.9 or w["storm"] > 0.15 or w["fog"] > 0.6
        if s.get("storm_grounded"):
            return w["storm"] > 0.4
        return False

    # ------------------------------------------------------------------ transports and heavy bombers
    def _cargo_step(self, u):
        """A transport plane: fly to where it is needed (its own army for a supply crate, the enemy's for paratroopers),
        drop its load, fly on and leave the map."""
        s, nav = u.stats, u.nav
        side = u.side
        e = next(iter(self.enemies[side]))
        lo, hi = 40.0, self.shore - 30 if self.shore else self.H - 40.0
        if not nav["dropped"]:
            if s["cargo"] == "crate":
                dest = self._group_near(side, self.home[side][0], 1400) or self._army_center(side) or self.home[side]
            else:                                                  # over the enemy troops nearest our own camp
                dest = self._front(e, self.home[side][0]) or self._army_center(e) or self.home[e]
            tx, ty = dest
            ty = min(max(ty, lo), hi)
            dx = tx - u.x
            if abs(dx) < 30:
                self._cargo_drop(u)
                nav["dropped"] = True
            want = (1.0 if dx >= 0 else -1.0, max(-0.6, min(0.6, (ty - u.y) / 160.0)))
        else:
            want = (1.0 if u.rout_dx >= 0 else -1.0, 0.0)
        n = math.hypot(*want) or 1.0
        hx, hy = u.rout_dx, u.rout_dy
        nx, ny = hx + (want[0] / n - hx) * C.AIR_TURN, hy + (want[1] / n - hy) * C.AIR_TURN
        m = math.hypot(nx, ny) or 1.0
        self._fly(u, nx / m, ny / m)
        if nav["dropped"] and (u.x < 14 or u.x > self.W - 14):
            u.state = "fled"                                   # it has flown off the map

    def _group_near(self, side, x, radius):
        """The middle of a side's men within `radius` of world x (None if fewer than three)."""
        near = [v for v in self._side_units.get(side, ()) if abs(v.x - x) < radius]
        if len(near) < 3:
            return None
        return (sum(v.x for v in near) / len(near), sum(v.y for v in near) / len(near))

    def _front(self, side, x):
        """The middle of the ten men of `side` nearest world x: the leading edge of that army as seen from there."""
        us = sorted(self._side_units.get(side, ()), key=lambda v: abs(v.x - x))[:10]
        if len(us) < 3:
            return None
        return (sum(v.x for v in us) / len(us), sum(v.y for v in us) / len(us))

    def _cargo_drop(self, u):
        s = u.stats
        if s["cargo"] == "crate":
            self.crates.append({"x": u.x, "y": u.y, "side": u.side, "born": self.time,
                                "land_at": self.time + C.CRATE_FALL, "until": self.time + C.CRATE_LIFE})
            self._fx("drop", u.x, u.y)
            self.say(f"{self.sc['sides'][u.side]['name']} drop supplies.")
        else:
            n = int(s.get("cargo_n", 8))
            self.spawn(u.side, s.get("cargo_unit", "paratrooper"), n, [u.x - 44, max(40.0, u.y - 14), 88, 28])
            self.extra_stats["paratroopers"] += n
            self._fx("drop", u.x, u.y)
            self.say(f"{self.sc['sides'][u.side]['name']} paratroopers jump behind the lines.")

    def _carpet_step(self, u):
        """A heavy bomber flies straight along the front, steering across toward the enemy army, and drops a bomb on
        anything beneath it every time its bomb bay is ready."""
        s = u.stats
        e = next(iter(self.enemies[u.side]))
        c = self._army_center(e)
        want_y = 0.0
        if c is not None:
            want_y = max(-0.5, min(0.5, (c[1] - u.y) / 150.0))
        hx = 1.0 if u.rout_dx >= 0 else -1.0
        n = math.hypot(hx, want_y)
        self._fly(u, hx / n, want_y / n)
        if u.cooldown == 0:
            for v in self._neighbours(u.x, u.y, 48):
                if v.side in self.enemies[u.side] and v.state == "fighting":
                    self._bomb(u, v)
                    self.extra_stats["carpet"] += 1
                    u.cooldown = max(1, round(s["cooldown"] * C.SIM_RATE))
                    break

    # ------------------------------------------------------------------ barrages
    def _barrage(self, a):
        """The `barrage` event action. Missiles: a salvo of small rockets leaves the side's castle one after another and
        comes down all over the target area (each covers a small circle, together a wide one). V-2: a single huge rocket
        climbs out of the castle and drops on the middle of the target area (one big blast)."""
        side, name = a["side"], self.sc["sides"][a["side"]]["name"]
        x0, y0 = self.home[side]
        ax, ay, aw, ah = a["area"]
        if a["style"] == "v2":
            self.pending.append({"at": self.time + 1.0, "barrage": True, "args": {
                "side": side, "style": "v2", "x0": x0, "y0": y0, "x1": ax + aw / 2, "y1": ay + ah / 2,
                "r": a["radius"] * C.V2_RADIUS_K, "dmg": a["damage"], "flight": C.V2_FLIGHT}})
            self.say(a["text"] or f"{name} launch a V-2!")
        else:
            for i in range(a["count"]):
                self.pending.append({"at": self.time + C.MISSILE_DELAY * i, "barrage": True, "args": {
                    "side": side, "style": "missiles", "x0": x0 + self.rng.uniform(-30, 30), "y0": y0 + self.rng.uniform(-20, 20),
                    "x1": self.rng.uniform(ax, ax + aw), "y1": self.rng.uniform(ay, ay + ah), "r": a["radius"],
                    "dmg": a["damage"], "flight": C.MISSILE_FLIGHT + self.rng.uniform(-0.2, 0.2)}})
            self.say(a["text"] or f"{name} fire a missile barrage!")
        self.extra_stats["barrages"] = self.extra_stats.get("barrages", 0) + 1

    def _launch_barrage(self, side, style, x0, y0, x1, y1, r, dmg, flight, shooter=-1):
        v2 = style == "v2"
        ammo = "v2" if v2 else "missile"
        self.shots.append({"uid": next(self._shot_ids), "kind": "stone", "ammo": ammo, "src": "barrage", "x0": x0, "y0": y0,
                           "x1": x1, "y1": y1, "shooter": shooter, "target": None, "land": "dust", "crater": 30 if v2 else 8,
                           "angle": C.V2_ANGLE if v2 else C.MISSILE_ANGLE, "h0": 26.0, "h1": 0.0, "flight": flight,
                           "area": True, "big": v2, "r": r, "bolt": False, "drop": False, "maxpeak": 380 if v2 else 240})
        del self.shots[:-150]
        self.projectiles.append({"kind": "area", "shooter": shooter, "target": None, "struct": None, "x1": x1, "y1": y1,
                                 "dmg": dmg, "splash": r, "ammo": ammo, "burn": v2, "side": side, "area": True,
                                 "arrive": self.time + flight})
        if v2:
            self.extra_stats["v2"] = self.extra_stats.get("v2", 0) + 1
        else:
            self.extra_stats["missiles"] = self.extra_stats.get("missiles", 0) + 1

    def _rocket_fire(self, u, t):
        """A launcher unit's attack. The MLRS pod ("salvo": n) looses n small rockets that scatter over a patch round the
        target; the V-2 launcher ("v2": true) sends one huge rocket that climbs out of sight and drops on the target. Both
        reuse the castle barrage's rounds, so the art and the blast match."""
        s = u.stats
        power = self._vet(u)
        if s.get("v2"):
            self._launch_barrage(u.side, "v2", u.x, u.y - 4, t.x, t.y, s["splash"], s["attack"] * power, C.V2_FLIGHT, u.uid)
            self.say(f"{self.sc['sides'][u.side]['name']} launch a V-2!") if self.rng.random() < 0.3 else None
            return
        spread = s.get("spread", 26.0)
        for i in range(int(s.get("salvo", 8))):
            ang, rad = self.rng.uniform(0, 6.2832), spread * math.sqrt(self.rng.random())
            self._launch_barrage(u.side, "missiles", u.x + self.rng.uniform(-6, 6), u.y - 2,
                                 t.x + math.cos(ang) * rad, t.y + math.sin(ang) * rad * 0.6, s["splash"], s["attack"] * power,
                                 C.MISSILE_FLIGHT * 0.7 + 0.1 * i + self.rng.uniform(-0.1, 0.1), u.uid)

    # ------------------------------------------------------------------ bridges, pontoons and the engineers who mend them
    def _hit_structures_near(self, x, y, r, dmg):
        """Shells and bombs that land on a bridge or a house hurt it (without counting as a siege hit)."""
        for t in list(self.terrain):
            if t.get("style") not in ("bridge", "house") or t["hidden"]:
                continue
            rx, ry, rw, rh = t["rect"]
            if rx - r <= x <= rx + rw + r and ry - r <= y <= ry + rh + r:
                self._damage_structure(t, dmg)
                self.structure_hits -= 1

    def _break_bridge(self, t):
        """A bridge or pontoon falls into the river: its water comes back and anyone on it drowns. A real bridge is kept
        in `broken_bridges` so engineers can rebuild it; a pontoon is simply gone."""
        self.terrain = [q for q in self.terrain if q is not t]
        for q in self.terrain:
            if q["id"] in t["span"]:
                q["hidden"] = False
        self._refresh_walls()
        x, y, w, h = t["rect"]
        for u in list(self._all):
            if u.state == "fighting" and x - 2 <= u.x <= x + w + 2 and y - 2 <= u.y <= y + h + 2:
                self._hurt(u, 1e9)                           # into the water
        self._fx("bridge", x + w / 2, y + h / 2)
        if not t.get("pontoon"):
            self.broken_bridges.append({"bridge": t, "progress": 0.0})
        self.extra_stats["bridges_down"] = self.extra_stats.get("bridges_down", 0) + 1
        self.say(f"{t['name'][0].upper() + t['name'][1:]} is destroyed!")

    def _repair_bridge(self, rec):
        t = rec["bridge"]
        self.broken_bridges.remove(rec)
        for q in self.terrain:
            if q["id"] in t["span"]:
                q["hidden"] = True
        t["hp"] = t["max_hp"] * 0.7
        self.terrain.append(t)
        self._refresh_walls()
        self._fx("bridge_up", t["rect"][0] + t["rect"][2] / 2, t["rect"][1] + t["rect"][3] / 2)
        self.extra_stats["repaired"] = self.extra_stats.get("repaired", 0) + 1
        self.say(f"Engineers rebuild {t['name']}.")

    def _build_pontoon(self, seg):
        """Two blocks of river are floated over with pontoons: a crossing with very few hit points."""
        river = [q for q in self.terrain if q.get("river") == seg["river"] and q["style"] == "river"]
        river.sort(key=lambda q: q["rect"][1])
        i = river.index(seg)
        other = river[i + 1] if i + 1 < len(river) else river[i - 1]
        if other["hidden"]:
            return
        pair = [seg, other]
        x0 = min(q["rect"][0] for q in pair)
        x1 = max(q["rect"][0] + q["rect"][2] for q in pair)
        y0 = min(q["rect"][1] for q in pair)
        y1 = max(q["rect"][1] + q["rect"][3] for q in pair)
        self.pontoon_count += 1
        pid = f"pontoon_{self.pontoon_count}"
        for q in pair:
            q["hidden"] = True
            q["gap_of"] = pid
        self.terrain.append({"id": pid, "rect": [x0 - 6, y0, x1 - x0 + 12, y1 - y0], "color": (96, 104, 84), "solid": False,
                             "label": None, "hidden": False, "height": 1.0, "style": "bridge", "owner": None, "roof": None,
                             "name": "a pontoon bridge", "hp": C.PONTOON_HP, "max_hp": C.PONTOON_HP, "river": seg["river"],
                             "span": [q["id"] for q in pair], "pontoon": True})
        self._refresh_walls()
        self._fx("bridge_up", (x0 + x1) / 2, (y0 + y1) / 2)
        self.extra_stats["pontoons"] = self.extra_stats.get("pontoons", 0) + 1
        self.say("Engineers float a pontoon bridge across the river.")

    def _engineer_work(self, u):
        """An engineer with no foe in sight: mend the nearest broken bridge, or, held up at a river with friends behind
        him and no bridge near, float a pontoon across. True while he is busy at it."""
        dt = 1.0 / C.SIM_RATE * self._vet(u)
        best = None
        for rec in self.broken_bridges:
            x, y, w, h = rec["bridge"]["rect"]
            bank = x - 10 if u.x < x + w / 2 else x + w + 10
            d = math.hypot(bank - u.x, y + h / 2 - u.y)
            if d < C.ENGINEER_RANGE and (best is None or d < best[0]):
                best = (d, rec, bank, y + h / 2)
        if best is not None:
            d, rec, bx, by = best
            if d > 20:
                self._step_toward(u, bx, by)
            else:
                rec["progress"] += dt
                if self.tick_count % 4 == 0:
                    self._fx("dust", u.x + u.facing * 6, u.y)
                if rec["progress"] >= C.REPAIR_SECONDS:
                    self._repair_bridge(rec)
            return True
        gx = self.sc["sides"][u.side]["goal"][0]
        seg = None
        for q in self.terrain:
            if q.get("style") != "river" or q["hidden"]:
                continue
            rx, ry, rw, rh = q["rect"]
            if abs(u.x - (rx + rw / 2)) < rw / 2 + 24 and ry - 12 <= u.y <= ry + rh + 12 and (rx + rw / 2 - u.x) * (gx - u.x) > 0:
                seg = q
                break
        if seg is None:
            return False
        for b in self.terrain:                                # a bridge close by: no need
            if b.get("style") == "bridge" and b.get("river") == seg["river"] and not b["hidden"] and abs(b["rect"][1] + b["rect"][3] / 2 - u.y) < 130:
                return False
        if sum(1 for v in self._neighbours(u.x, u.y, 150) if v.side == u.side and not v.stats.get("sapper")) < 2:
            return False
        wip = self.pontoon_wip.get(seg["id"], 0.0) + dt
        self.pontoon_wip[seg["id"]] = wip
        if self.tick_count % 4 == 0:
            self._fx("dust", u.x + u.facing * 6, u.y)
        if wip >= C.PONTOON_SECONDS:
            self.pontoon_wip.pop(seg["id"], None)
            self._build_pontoon(seg)
        return True

    # ------------------------------------------------------------------ aircraft crashes
    def _plan_crash(self, u):
        """A shot-down aircraft keeps going the way it was heading and hits the ground a moment later. Returns where."""
        s = u.stats
        hx = 1.0 if u.rout_dx >= 0 else -1.0
        tx = min(max(u.x + hx * C.CRASH_DRIFT, 10.0), self.W - 10.0)
        ty = min(max(u.y + u.rout_dy * C.CRASH_DRIFT * 0.5, 10.0), self.H - 10.0)
        hp = s["hp"]
        self.crashes.append({"x": tx, "y": ty, "r": C.CRASH_RADIUS_BASE + min(28.0, hp / 18.0),
                             "dmg": min(C.CRASH_DMG_MAX, max(30.0, hp * C.CRASH_DMG_K)), "at": self.time + C.CRASH_FALL})
        return tx, ty

    def _crash_tick(self):
        """Crashes that have reached the ground: the wreck hurts whoever is under it, friend or foe, sets the nearest men
        alight, and damages bridges and houses; one that falls on a ship damages it."""
        due = [c for c in self.crashes if c["at"] <= self.time]
        if not due:
            return
        self.crashes = [c for c in self.crashes if c["at"] > self.time]
        for c in due:
            x, y, r, dmg = c["x"], c["y"], c["r"], c["dmg"]
            self.extra_stats["crashes"] = self.extra_stats.get("crashes", 0) + 1
            if self.shore is not None and y >= self.shore:
                victims = [v for v in self._sea if math.hypot(v.x - x, v.y - y) < r]
            else:
                victims = [v for v in self._neighbours(x, y, r) if v.state == "fighting" and not v.stats.get("flying")]
                self._hit_structures_near(x, y, r, dmg * 1.5)
            for v in victims:
                d = math.hypot(v.x - x, v.y - y)
                before = v.state
                self._hurt(v, dmg * (1.0 - 0.6 * d / r))
                self.extra_stats["crash_hits"] = self.extra_stats.get("crash_hits", 0) + 1
                if v.state == "fighting" and d < r * 0.5 and not v.stats.get("naval"):
                    v.burn = int(C.BURN_SECONDS * C.SIM_RATE)               # caught in the fireball
