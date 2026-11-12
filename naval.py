"""Ships. The bottom of the map is a sea (map "shore": every y from there down is water), with a beach above it.
Land troops cannot enter the water and ships cannot leave it. Four kinds of ship sail it:

  longship       a raider with a dragon prow that rams other ships
  galley         archers on a broad deck: shoots ships, and men on the beach and the field's southern edge
  catapult ship  a barge that throws stones at ships and the shore, with splash
  landing boat   carries a boatload of marines (a ground unit), rows to the enemy's beach, puts them ashore, and goes
                 back for more

Ships steer like flyers rather than walk: each tick they turn part of the way toward where they want to go (slowly: a
ship cannot spin on the spot), so they sweep in curves, circle their prey and keep station at the range of their
weapons. With nothing to fight they patrol the sea from their own end to the enemy's and back. Land archers, siege
engines, heroes and flyers that carry fire can all attack ships; melee troops cannot reach them.
NavalUnits is a mixin for Battle."""
import math

import numpy as np

import config as C


class NavalUnits:
    def _sea_lane_range(self):
        return self.shore + C.SHIP_LANE_MARGIN, self.H - C.SHIP_LANE_MARGIN

    def _naval_init(self, u):
        lo, hi = self._sea_lane_range()
        u.y = min(max(u.y, lo), hi)
        gx = self.sc["sides"][u.side]["goal"][0]
        u.rout_dx, u.rout_dy = (1.0 if gx > u.x else -1.0), 0.0
        u.nav = {"lane": self.rng.uniform(lo, hi), "leg": 0, "mode": "sail", "spot": None, "ready": 0.0,
                 "load": int(u.stats.get("carry", 0)), "moving": False}

    # ------------------------------------------------------------------ finding something to fight
    def _sea_nearest(self, u, radius):
        """The nearest enemy ship within radius of u, as (ship, distance), or (None, None)."""
        best, bd = None, None
        for sid in self.enemies[u.side]:
            tree = self._sea_trees.get(sid)
            if tree is None:
                continue
            d, i = tree.query((u.x, u.y), k=1, distance_upper_bound=radius)
            if np.isfinite(d) and (bd is None or d < bd):
                best, bd = self._sea_units[sid][int(i)], d
        return best, bd

    def _naval_target(self, u):
        """A ship picks the nearest enemy ship; a ship with a ranged weapon also picks men on the shore within its reach,
        but prefers a ship."""
        s = u.stats
        ship, sd = self._sea_nearest(u, s["sight"] * self.wx_sight)
        if s.get("asw"):                                  # a destroyer hunts submarines first, then aircraft
            for sid in self.enemies[u.side]:
                for v in self._subs.get(sid, ()):
                    if math.hypot(v.x - u.x, v.y - u.y) <= s["reach"]:
                        return v
        if s.get("aa"):
            for sid in self.enemies[u.side]:
                tree = self._air_trees.get(sid)
                if tree is not None:
                    d, i = tree.query((u.x, u.y), k=1, distance_upper_bound=s["reach"] * 0.8)
                    if d != float("inf"):
                        return self._air_units[sid][int(i)]
        if s.get("naval_role") in ("ram", "sub"):
            return ship
        if s.get("naval_role") == "transport":
            return None
        land, ld = None, None
        for sid in self.enemies[u.side]:
            tree = self._side_trees.get(sid)
            if tree is None:
                continue
            d, i = tree.query((u.x, u.y), k=1, distance_upper_bound=s["reach"])
            if np.isfinite(d) and (ld is None or d < ld):
                land, ld = self._side_units[sid][int(i)], d
        if ship is not None and (land is None or sd * 0.7 <= ld):
            return ship
        return land if land is not None else ship

    # ------------------------------------------------------------------ the fight
    def _fight_naval(self, u):
        s, nav = u.stats, u.nav
        if u.buffs and self._buff(u, "stun"):
            return
        if u.cooldown > 0:
            u.cooldown -= 1
        u.retarget -= 1
        role = s.get("naval_role")
        t = u.target
        if role != "transport" and (t is None or not self._valid_target(u, t) or u.retarget <= 0):
            t = self._naval_target(u)
            u.target = t
            u.retarget = max(1, round(C.RETARGET_SECONDS * C.SIM_RATE))
        move = True
        if role == "carrier":
            self._carrier_deck(u)
        if role == "transport":
            want, move = self._transport_step(u)
        elif t is not None:
            dx, dy = t.x - u.x, t.y - u.y
            d = math.hypot(dx, dy) or 1.0
            if d <= s["reach"] and u.cooldown == 0:
                if s.get("volley_targets"):
                    self._naval_volley(u, t)
                else:
                    self._attack(u, t)
                self.naval_stats["shots"] += 1
                u.cooldown = max(1, round(s["cooldown"] * C.SIM_RATE))
            ranged = s["reach"] >= 60
            if role == "carrier":
                want = self._carrier_station(u)                 # a carrier keeps to its own waters and lets its wing fight
            elif ranged and d <= s["reach"] * 0.82:
                want, move = (u.rout_dx, u.rout_dy), False          # in range: it holds its station and shoots
            else:
                want = (dx / d, dy / d)
        else:
            want = self._carrier_station(u) if role == "carrier" else self._sea_patrol(u)
        hx, hy = u.rout_dx, u.rout_dy
        nx, ny = hx + (want[0] - hx) * C.NAVAL_TURN, hy + (want[1] - hy) * C.NAVAL_TURN
        n = math.hypot(nx, ny) or 1.0
        self._sail(u, nx / n, ny / n, move)
        self._sea_separate(u)

    def _naval_volley(self, u, first):
        """A dreadnought's broadside: its guns each pick their own mark, so one salvo falls on up to `volley_targets`
        different enemies in reach (land troops, ships, and aircraft too if it has flak), the chosen target first."""
        s = u.stats
        marks = [first]
        pool = [v for v in self._neighbours(u.x, u.y, s["reach"])
                if v is not first and v.state == "fighting" and v.side in self.enemies[u.side]
                and (s.get("aa") or not v.stats.get("flying"))]
        self.rng.shuffle(pool)
        marks += pool[:int(s["volley_targets"]) - 1]
        for v in marks:
            self._attack(u, v)
        self.extra_stats["broadsides"] = self.extra_stats.get("broadsides", 0) + 1

    def _carrier_deck(self, u):
        """A carrier keeps a wing of aircraft (`hangar`): every `sortie_every` seconds it flies off up to `sortie` more to
        replace those lost, alternating bombers and fighters. They are ordinary aircraft: they bomb or strafe whatever is
        in reach (men, ships, guns) and fight other aircraft; the carrier's own deck guns shoot at the foe near it."""
        s, nav = u.stats, u.nav
        wing = nav.setdefault("wing", [])
        if self.time < nav.get("next_sortie", 0.0):
            return
        nav["next_sortie"] = self.time + s.get("sortie_every", 14.0)
        alive = {v.uid for v in self.units if v.state == "fighting" and v.stats.get("flying") and v.side == u.side}
        wing[:] = [w for w in wing if w in alive]
        kinds = s.get("wing", ["dive_bomber"])
        for _ in range(min(int(s.get("sortie", 2)), int(s.get("hangar", 4)) - len(wing))):
            kind = kinds[nav.get("flown", 0) % len(kinds)]
            nav["flown"] = nav.get("flown", 0) + 1
            before = len(self.units)
            self.spawn(u.side, kind, 1, [u.x - 12, u.y - 6, 24, 12])
            for v in self.units[before:]:
                wing.append(v.uid)
                self.extra_stats["sorties"] = self.extra_stats.get("sorties", 0) + 1

    def _carrier_station(self, u):
        """Steam slowly back and forth over its own third of the sea, far from the enemy's guns."""
        nav = u.nav
        e = next(iter(self.enemies[u.side]))
        ogx = self.sc["sides"][u.side]["goal"][0]
        dirx = 1.0 if self.sc["sides"][e]["goal"][0] > ogx else -1.0
        tx = ogx + dirx * (1700 if nav["leg"] == 0 else 500)
        if abs(u.x - tx) < 120:
            nav["leg"] = 1 - nav["leg"]
        return self._toward(u, tx, nav["lane"])

    def _sea_patrol(self, u):
        """With nothing to fight: sail toward the enemy's end of the sea along the ship's own lane, then back."""
        nav = u.nav
        e = next(iter(self.enemies[u.side]))
        egx = self.sc["sides"][e]["goal"][0]
        ogx = self.sc["sides"][u.side]["goal"][0]
        dirx = 1.0 if egx > ogx else -1.0
        tx = egx - dirx * 260 if nav["leg"] == 0 else ogx + dirx * 260
        if abs(u.x - tx) < 160:
            nav["leg"] = 1 - nav["leg"]
        return self._toward(u, tx, nav["lane"])

    @staticmethod
    def _toward(u, tx, ty):
        dx, dy = tx - u.x, ty - u.y
        d = math.hypot(dx, dy) or 1.0
        return dx / d, dy / d

    # ------------------------------------------------------------------ landing boats
    def _transport_step(self, u):
        """A landing boat: sail to the enemy's beach, put the marines ashore, sail home, reload, and go again.
        Returns (where to steer, whether to move)."""
        nav, s = u.nav, u.stats
        e = next(iter(self.enemies[u.side]))
        egx = self.sc["sides"][e]["goal"][0]
        ogx = self.sc["sides"][u.side]["goal"][0]
        dirx = 1.0 if egx > ogx else -1.0
        beach = self.shore + 12
        if nav["mode"] == "sail":
            if nav["spot"] is None:
                nav["spot"] = egx - dirx * self.rng.uniform(260, 640)
            tx = nav["spot"]
            ty = beach if abs(u.x - tx) < 220 else nav["lane"]
            if math.hypot(u.x - tx, u.y - beach) < 26 and nav["load"] > 0:
                self._land_marines(u)
                nav["mode"], nav["spot"] = "return", None
            return self._toward(u, tx, ty), True
        if nav["mode"] == "return":
            hx = ogx + dirx * 300
            if abs(u.x - hx) < 70:
                nav["mode"], nav["ready"] = "wait", self.time + C.LANDING_RELOAD
            return self._toward(u, hx, nav["lane"]), True
        if self.time >= nav["ready"]:                                  # reloaded: marines aboard again
            nav["mode"], nav["load"] = "sail", int(s.get("carry", 6))
        return (u.rout_dx, u.rout_dy), False

    def _land_marines(self, u):
        n = u.nav["load"]
        u.nav["load"] = 0
        x = u.x
        self.spawn(u.side, "marine", n, [x - 26, self.shore - 40, 52, 22])
        self.naval_stats["landings"] += 1
        self.naval_stats["marines"] += n
        self._fx("landing", x, self.shore)
        self.say(f"{self.sc['sides'][u.side]['name']} marines storm the beach.")

    # ------------------------------------------------------------------ movement
    def _sail(self, u, nx, ny, move=True):
        lo, hi = self._sea_lane_range()
        u.nav["moving"] = bool(move)
        if move:
            dist = u.stats["speed"] / C.SIM_RATE * self.wx_sail
            if u.buffs:
                dist *= (1 + self._buff(u, "haste")) * max(0.2, 1 - self._buff(u, "slow"))
            x, y = u.x + nx * dist, u.y + ny * dist
            margin = 10
            if x < margin or x > self.W - margin:
                nx, x = -nx, min(max(x, margin), self.W - margin)
            if y < lo - 8 or y > hi + 8:
                ny, y = -ny, min(max(y, lo - 8), hi + 8)
            u.x, u.y = x, max(y, self.shore + 8)                    # a ship never runs up onto the sand
        u.rout_dx, u.rout_dy = nx, ny
        if abs(nx) > 0.3:
            u.facing = 1 if nx > 0 else -1

    def _sea_separate(self, u):
        """Ships push each other apart (they are big)."""
        sep = C.NAVAL_SEPARATION
        for v in self._sea:
            if v is u or v.state != "fighting":
                continue
            dx, dy = u.x - v.x, (u.y - v.y) * 1.6
            d = math.hypot(dx, dy)
            if d >= sep:
                continue
            if d < 1e-6:
                dx, dy, d = self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), 1.0
            push = (sep - d) * 0.25
            u.x += dx / d * push
            u.y += dy / d * push / 1.6
        u.y = max(u.y, self.shore + 8)
