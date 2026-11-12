"""Aircraft that are shot down: the burning, spinning fall, the crash, and the wreckage left on the ground (a mixin for
Renderer). The engine decides where the aircraft comes down and what it hurts (extras.py, `_crash_tick`); this draws it."""
import math

import pygame

import config as C


def _px(surf, color, x, y, w=1, h=1):
    surf.fill(color, pygame.Rect(x, y, w, h))


def crash_radius(hp):
    """The blast radius of a crash: the same rule the engine uses."""
    return C.CRASH_RADIUS_BASE + min(28.0, hp / 18.0)


class CrashRender:
    FALL_SECONDS = 0.9

    def _draw_plunges(self, low):
        """A flyer shot down falls toward its crash site, nose down, spinning, trailing flame and a thick black smoke."""
        for p in self.plunges:
            if not self._seen(min(p["x"], p["tx"]), max(p["x"], p["tx"])):
                continue
            k = min(1.0, (self.now - p["born"]) / self.FALL_SECONDS)
            right = p["tx"] >= p["x"]
            ang = (-1 if right else 1) * (12 + 70 * k * k) + math.sin(self.now * 18 + p["born"] * 7) * 6
            for i in range(9, 0, -1):                                   # the trail: smoke far back, fire close behind
                kk = k - 0.045 * i
                if kk < 0:
                    continue
                px, py = self._fall_pos(p, kk)
                if i <= 3:
                    pygame.draw.circle(low, (255, 200 - 40 * i, 50), (px, py), 2)
                else:
                    g = max(30, 110 - 8 * i)
                    pygame.draw.circle(low, (g, g, g + 2), (px, py), 1 + i // 3)
            x, y = self._fall_pos(p, k)
            gx, gy, sc = self._low(p["x"] + (p["tx"] - p["x"]) * k, p["y"] + (p["ty"] - p["y"]) * k)
            s = self._sprite(self._unit_types[p["kind"]]["sprite"], self._sides[p["side"]]["color"], False, "dead", 0, sc,
                             not right, 0, False, 0)
            s = pygame.transform.rotate(s, ang)
            low.blit(s, (x - s.get_width() // 2, y - s.get_height() // 2))
            _px(low, (255, 226, 130), x - 1, y - 1, 2, 2)                                # the engine burning
            pygame.draw.ellipse(low, (30, 46, 26), pygame.Rect(gx - 3, gy - 1, 7, 2))      # its shadow rushing up
            if self.night > 0.15:
                self.lights.append((x, y, 14, "torch"))

    def _fall_pos(self, p, k):
        """Screen position of a falling flyer a share k of the way down: it slides toward the crash site while its height
        drops away quadratically."""
        e = k * k * 0.5 + k * 0.5
        wx = p["x"] + (p["tx"] - p["x"]) * e
        wy = p["y"] + (p["ty"] - p["y"]) * e
        _, y, _ = self._low(wx, wy, p["h"] * (1 - k * k))
        x, _, _ = self._low(wx, wy, 0)
        return x, y

    def _crash_land(self, p):
        """The flyer hits the ground: a fireball and a column of smoke, a crater, flames on the grass, a shock ring the size
        of the blast, and a wreck that stays. In the sea there is only a great splash."""
        x, y = p["tx"], p["ty"]
        hp = self._unit_types[p["kind"]]["hp"]
        r = crash_radius(hp)
        seen = self._seen(x - r, x + r)
        if self.shore is not None and y >= self.shore:                         # into the sea
            if seen:
                self._sparks(x, y, (214, 236, 250), 16, 24, (50, 130), 0.9)
                self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.8, "size": r, "col": (214, 236, 250)})
                if self.audio:
                    self.audio.sfx("fall", x)
            return
        self.craters.append((x, y, max(5.0, r * 0.3)))
        del self.craters[:-C.MAX_CRATERS]
        self.flames += [(x + self.rng.uniform(-r * 0.4, r * 0.4), y + self.rng.uniform(-r * 0.15, r * 0.15),
                         self.now + self.rng.uniform(5, 9)) for _ in range(3)]
        self.wrecks.append({"x": x, "y": y, "kind": p["kind"], "side": p["side"], "born": self.now,
                            "tilt": self.rng.choice((-1, 1)) * self.rng.uniform(8, 24), "flip": p["tx"] < p["x"],
                            "seed": self.rng.randrange(1000), "cache": {}})
        del self.wrecks[:-C.MAX_WRECKS]
        if seen:
            self._burst("fire", x, y, 5)
            self._burst("smoke", x, y, 5)
            self._burst("debris", x, y, 6)
            self._burst("dust", x, y, 3)
            self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.7, "size": r, "col": (255, 170, 70)})
            self.rings.append({"x": x, "y": y, "born": self.now + 0.1, "life": 0.5, "size": r * 0.6, "col": (255, 232, 160)})
            self.shake = max(self.shake, 4.0 + r / 12)
            if self.audio:
                self.audio.sfx("crash", x)
                self.audio.sfx("boulder", x)

    def _wreck_surface(self, w, sc):
        key = round(sc * 10)
        s = w["cache"].get(key)
        if s is None:
            spr = self._sprite(self._unit_types[w["kind"]]["sprite"], self._sides[w["side"]]["color"], False, "dead", 0, sc,
                               w["flip"], 0, False, 0).copy()
            spr.fill((84, 80, 78), special_flags=pygame.BLEND_RGB_MULT)            # charred
            spr.fill((26, 22, 20), special_flags=pygame.BLEND_RGB_ADD)
            s = pygame.transform.rotate(spr, w["tilt"])
            w["cache"][key] = s
        return s

    def _draw_wreck(self, w):
        """What is left of the aircraft: a charred, tilted hulk with scattered pieces. It burns for the first half minute and
        smokes for a while after, then fades away."""
        age = self.now - w["born"]
        left = C.WRECK_SECONDS - age
        if left <= 0:
            return
        low = self.low
        x, gy, sc = self._low(w["x"], w["y"])
        s = self._wreck_surface(w, sc)
        if left < 10:
            s = s.copy()
            s.set_alpha(int(255 * left / 10))
        pygame.draw.ellipse(low, (26, 36, 22), pygame.Rect(x - s.get_width() // 2, gy - 2, s.get_width(), 4))
        low.blit(s, (x - s.get_width() // 2, gy - s.get_height() + 3))
        seed = w["seed"]
        for i in range(6):                                                      # torn-off pieces strewn about
            dx = (seed * (i + 3)) % 31 - 15
            dy = (seed * (i + 5)) % 7 - 3
            _px(low, (70, 66, 64) if i % 2 else (112, 90, 70), x + dx, gy + dy, 2 if i % 3 == 0 else 1, 1)
        fire = age < 28
        for i in range(3 if fire else 0):                                       # flames licking the hulk
            fx = x - 5 + i * 5 + (seed + i) % 3
            fh = 2 + int((math.sin(self.now * 11 + i * 2 + seed) + 1.2) * 2) * (1.0 - age / 28.0)
            pygame.draw.line(low, (255, 130, 40), (fx, gy - 2), (fx, gy - 3 - int(fh)))
            _px(low, (255, 226, 130), fx, gy - 3 - int(fh))
            if self.night > 0.15:
                self.lights.append((fx, gy - 4, 12, "torch"))
        if age < 55:                                                            # a column of smoke
            density = 1.0 if fire else 0.5
            for i in range(5):
                off = (self.now * 9 + i * 8 + seed) % 40
                sx = x + int(math.sin(off * 0.2 + i) * 2) + off // 14
                g = int(70 + off * 2.2)
                r = 1 + int(off // 12)
                if density < 1.0 and i % 2:
                    continue
                pygame.draw.circle(low, (min(200, g), min(200, g), min(204, g + 3)), (sx, gy - 5 - int(off)), r)
