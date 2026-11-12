"""Flying units. Two kinds a side: an air-to-ground bomber (the wyvern rider, who drops pots of burning pitch on men
below) and an air-to-air interceptor (the hawk rider, who hunts the enemy's flyers and ignores everything on the
ground). Flyers ignore walls, moats, trenches and spikes, and cannot be reached by melee men, siege engines or
splash: only archers (and the king and the ranged heroes) can shoot them down, with some of the arrows missing.

A flyer steers rather than walks: each tick it turns part of the way toward where it wants to go and flies on at a
steady speed, so it sweeps in a curve, makes bombing runs past its target and circles back, and a pair of hawks
wheel round each other in a dogfight. AirUnits is a mixin for Battle."""
import math

import config as C


class AirUnits:
    def _army_center(self, side):
        """The middle of a side's marching ground army (cached for the tick), or None if it has none."""
        c = self._centers.get(side, False)
        if c is False:
            men = [u for u in self._side_units.get(side, ()) if u.stats["speed"] > 0 and not u.stats.get("siege")]
            if len(men) >= 3:
                c = (sorted(u.x for u in men)[len(men) // 2], sorted(u.y for u in men)[len(men) // 2])
            else:
                c = None
            self._centers[side] = c
        return c

    def _air_goal(self, u):
        """Where a flyer with no target heads: a bomber toward the enemy army, an interceptor with its own bombers
        (or its own army). When it arrives it circles."""
        side, role = u.side, u.stats.get("air_role")
        point = None
        if role == "ground":
            for e in self.enemies[side]:
                point = self._army_center(e) or point
            if point is None:
                point = tuple(self.sc["sides"][side]["goal"])
        else:
            mates = [v for v in self._air_units.get(side, ()) if v.stats.get("air_role") == "ground"]
            if mates:
                point = (sum(v.x for v in mates) / len(mates), sum(v.y for v in mates) / len(mates))
            else:
                point = self._army_center(side) or self.home[side]
        dx, dy = point[0] - u.x, point[1] - u.y
        d = math.hypot(dx, dy)
        if d < 90:                                   # arrived: circle over the spot
            return -u.rout_dy, u.rout_dx
        return dx / d, dy / d

    def _fight_air(self, u):
        s = u.stats
        if u.buffs and self._buff(u, "stun"):
            return
        if self._harsh(s) and self.rng.random() < 0.1:
            u.state = "fled"                             # the weather is too bad to fly: it returns to base
            self.extra_stats["grounded"] += 1
            return
        if u.cooldown > 0:
            u.cooldown -= 1
        if s.get("cargo"):
            self._cargo_step(u)
            return
        if s.get("carpet"):
            self._carpet_step(u)
            return
        u.retarget -= 1
        t = u.target
        if t is None or not self._valid_target(u, t) or u.retarget <= 0:
            t = self._nearest_enemy(u, s["sight"])
            u.target = t
            u.retarget = max(1, round(C.RETARGET_SECONDS * C.SIM_RATE))
        hx, hy = u.rout_dx, u.rout_dy                # the heading: a unit vector, kept in the routing slots
        if t is not None:
            dx, dy = t.x - u.x, t.y - u.y
            d = math.hypot(dx, dy) or 1.0
            if d <= s["reach"] and u.cooldown == 0:
                self._attack(u, t)
                u.cooldown = max(1, round(s["cooldown"] * C.SIM_RATE))
            if s.get("air_role") == "ground" and u.cooldown > 0 and d < s["reach"] * 2.5:
                want = (hx, hy)                      # a bomber flies on through its run, then turns back
            else:
                want = (dx / d, dy / d)
        else:
            want = self._air_goal(u)
        nx, ny = hx + (want[0] - hx) * C.AIR_TURN, hy + (want[1] - hy) * C.AIR_TURN
        n = math.hypot(nx, ny) or 1.0
        self._fly(u, nx / n, ny / n)

    def _fly(self, u, nx, ny):
        dist = u.stats["speed"] / C.SIM_RATE * self.wx_fly
        if u.buffs:
            dist *= (1 + self._buff(u, "haste")) * max(0.2, 1 - self._buff(u, "slow"))
        x, y = u.x + nx * dist + self.wx["wind"] * 9 / C.SIM_RATE, u.y + ny * dist     # the wind carries it
        margin = 8
        if x < margin or x > self.W - margin:
            nx, x = -nx, min(max(x, margin), self.W - margin)    # turn back at the edge of the map
        if y < margin or y > self.H - margin:
            ny, y = -ny, min(max(y, margin), self.H - margin)
        u.x, u.y = x, y
        u.rout_dx, u.rout_dy = nx, ny
        if abs(nx) > 0.2:
            u.facing = 1 if nx > 0 else -1

    def _bomb(self, u, t):
        """A bomber lets a pot of burning pitch fall on the man below."""
        self.air_stats["bombs"] += 1
        self._launch(u, "stone", C.AIR_BOMB_FLIGHT, target=t, struct=None, x1=t.x, y1=t.y)
