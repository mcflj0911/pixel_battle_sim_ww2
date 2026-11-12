"""Drawing the sea lane: the beach and the water along the bottom of the map, the shoreline surf, ships (bobbing on the
swell, leaving wakes, burning, sinking), the wreckage that floats afterwards, and the splashes shots make in the water.
SeaRender is a mixin for Renderer; it reads the weather mix from self.wxv (set by WeatherRender) so a storm roughens the
water."""
import math
import random

import pygame

import config as C

SHALLOW, MID, DEEP = (96, 180, 184), (48, 120, 170), (22, 62, 118)
SAND_DRY, SAND_WET = (216, 198, 144), (172, 152, 106)
DRAUGHT = {"longship": 3, "galley": 4, "catapult_ship": 5, "landing_boat": 2, "destroyer": 5, "submarine": 11, "carrier": 5, "dreadnought": 6}   # sprite rows below the waterline


def _lerp3(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def _px(surf, color, x, y, w=1, h=1):
    surf.fill(color, pygame.Rect(x, y, w, h))


class SeaRender:
    def _sea_init(self):
        self.shore = self.sc["map"].get("shore")
        self.sinks = []                                 # ships going down: dicts of x, y, side, kind, facing, born
        self.flotsam = []                               # wreckage floating where a ship sank
        self._ship_ids = set()                          # uids of the ships in the battle (shots that hit one do not splash)
        self._wl = {}                                   # cached translucent water strips laid over a hull's waterline
        self._sink_bubble = 0.0
        if self.shore is None:
            return
        rng = random.Random(77)
        self._sea_y0 = self._screen_low_y(self.shore)
        self._beach_y0 = self._screen_low_y(self.shore - C.BEACH_WIDTH)
        self._make_beach(rng)
        self._make_sea()
        rows = C.LOW_H - self._sea_y0
        self._waves = []
        for r in range(1, rows, 3):                     # whitecaps: more of them, and longer, the nearer the viewer
            for _ in range(2 + r // 10):
                self._waves.append((r, rng.uniform(0, C.LOW_W + 60), rng.randint(3, 8 + r // 5), rng.uniform(0.6, 1.4),
                                    rng.uniform(0, 6.28)))
        self._fore = [(rng.uniform(0, C.LOW_W + 80), rng.randint(0, 12), rng.randint(10, 26), rng.uniform(0.8, 1.6))
                      for _ in range(16)]

    def _screen_low_y(self, y):
        """Where map y lands on the low-res screen (with no camera shake)."""
        z = self.depth(y)
        return round((C.GROUND_Y + (z - 0.5) * C.LANE_SPREAD) / C.PIXEL)

    # ------------------------------------------------------------------ static art
    def _make_beach(self, rng):
        h = self._sea_y0 - self._beach_y0 + 2
        surf = pygame.Surface((C.LOW_W, h), pygame.SRCALPHA)
        for y in range(h):
            k = (y / max(1, h - 1)) ** 1.3
            pygame.draw.line(surf, _lerp3(SAND_DRY, SAND_WET, k), (0, y), (C.LOW_W, y))
        for _ in range(520):                            # grains, shells and pebbles
            x, y = rng.randrange(C.LOW_W), rng.randrange(h)
            c = surf.get_at((x, y))
            surf.set_at((x, y), _lerp3(tuple(c)[:3], rng.choice(((255, 244, 214), (140, 122, 84), (200, 190, 176))), 0.5))
        for _ in range(60):                             # a few darker, weedy patches in the wet sand
            x, y = rng.randrange(C.LOW_W), rng.randrange(h // 2, h)
            pygame.draw.line(surf, (110, 120, 80), (x, y), (x + rng.randint(2, 5), y))
        for x in range(C.LOW_W):                        # a ragged edge where the grass gives way to sand
            cut = rng.choice((0, 0, 1, 1, 2))
            if cut:
                surf.fill((0, 0, 0, 0), pygame.Rect(x, 0, 1, cut))
        self.beach = surf

    def _make_sea(self):
        h = C.LOW_H - self._sea_y0 + 8
        surf = pygame.Surface((C.LOW_W, h))
        for y in range(h):
            k = y / max(1, h - 1)
            c = _lerp3(SHALLOW, MID, k / 0.35) if k < 0.35 else _lerp3(MID, DEEP, (k - 0.35) / 0.65)
            pygame.draw.line(surf, c, (0, y), (C.LOW_W, y))
            if y % 7 == 3:                              # faint bands of lighter and darker water
                pygame.draw.line(surf, _lerp3(c, (255, 255, 255), 0.07), (0, y), (C.LOW_W, y))
        self.sea_img = surf

    # ------------------------------------------------------------------ the beach and the water
    def _draw_shore(self, low):
        if self.shore is None:
            return
        t = self.now
        w = self.wxv
        amp = 1.0 + 2.0 * w["storm"]
        off = int(self.cam_x / C.PIXEL) % C.LOW_W
        top0 = self._low(0, self.shore - C.BEACH_WIDTH)[1]
        sy = self._low(0, self.shore)[1]
        low.blit(self.beach, (-off, top0))
        low.blit(self.beach, (C.LOW_W - off, top0))
        low.blit(self.sea_img, (0, sy))
        low.fill(self.sea_img.get_at((0, 0)), pygame.Rect(0, sy - 1, C.LOW_W, 2))
        rows = C.LOW_H - sy
        drift = 2.0 + abs(w["wind"]) * 6.0
        for r, x0, ln, spd, ph in self._waves:
            if r >= rows:
                continue
            y = sy + r + round(math.sin(t * 1.3 + ph) * amp * 0.7)
            x = (x0 - off + t * drift * spd) % (C.LOW_W + 60) - 30
            k = min(1.0, r / 55.0)
            pygame.draw.line(low, _lerp3((176, 226, 232), (92, 150, 196), k), (x, y), (x + ln, y))
            pygame.draw.line(low, _lerp3((70, 140, 170), (24, 66, 120), k), (x + 1, y + 1), (x + ln - 1, y + 1))
        day = self.day * (1.0 - 0.8 * w["cloud"])
        glint = (255, 252, 226) if self.day > 0.3 else (186, 202, 240)
        if day > 0.1 or self.night > 0.5:                # sparkles on the water, new ones each third of a second
            bucket = int(t * 3)
            for i in range(26):
                gx = (i * 977 + bucket * 131) % C.LOW_W
                gy = sy + 2 + (i * 53 + bucket * 17) % max(1, rows - 3)
                _px(low, glint, gx, gy)
        self._draw_surf(low, sy, t, amp)
        self._draw_flotsam(low)

    def _draw_surf(self, low, sy, t, amp):
        """The foam line where the water meets the sand: a swell that runs in and drains away, broken into dashes."""
        swell = (math.sin(t * 0.8) + 1) / 2
        for x in range(0, C.LOW_W, 4):
            wx = x * C.PIXEL + self.cam_x
            phase = wx * 0.035 + t * 1.3
            ey = sy + round(1.3 * amp * math.sin(phase)) - round(swell * (1 + amp * 0.5))
            if (x // 4 + int(t * 3)) % 5:
                _px(low, (244, 250, 252), x, ey, 4, 1)
            _px(low, (150, 206, 214), x, ey + 1, 4, 1)
            if swell > 0.5:                              # the wet sand darkens where the swell reaches
                _px(low, (150, 132, 92), x, ey - 1, 4, 1)

    def _draw_sea_foreground(self, low):
        """The nearest water, drawn over everything: long whitecaps that slide past quickly."""
        if self.shore is None:
            return
        off = self.cam_x / C.PIXEL * (1.5 if self.parallax else 1.0)
        for x0, r, ln, spd in self._fore:
            x = (x0 - off + self.now * 6 * spd) % (C.LOW_W + 80) - 40
            y = C.LOW_H - 4 - r
            pygame.draw.line(low, (150, 206, 222), (x, y), (x + ln, y))
            pygame.draw.line(low, (30, 78, 130), (x + 2, y + 1), (x + ln - 2, y + 1))

    def _draw_flotsam(self, low):
        now = self.now
        self.flotsam = [f for f in self.flotsam if now - f["born"] < 16.0]
        wind = self.wxv["wind"]
        for f in self.flotsam:
            x = f["x"] + wind * 4 * (now - f["born"]) + f["dx"] * (now - f["born"])
            if not self._seen(x):
                continue
            sx, sy, _ = self._low(x, f["y"])
            bob = round(math.sin(now * 1.5 + f["ph"]))
            _px(low, (96, 66, 38), sx, sy + bob, f["len"], 1)
            _px(low, (150, 112, 66), sx, sy + bob - 1, f["len"] - 1, 1)

    # ------------------------------------------------------------------ ships
    def _wl_strip(self, w, h):
        key = (w, h)
        s = self._wl.get(key)
        if s is None:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            for y in range(h):
                inset = min(3, y)
                s.fill((34 + y * 4, 92 + y * 4, 150 + y * 3, 70 + min(60, y * 15)), pygame.Rect(inset, y, max(1, w - 2 * inset), 1))
            self._wl[key] = s
        return s

    def _draw_ship(self, battle, u):
        low = self.low
        st = battle.sc["unit_types"][u.kind]
        color = battle.sc["sides"][u.side]["color"]
        now = self.now
        spr = st["sprite"]
        x, gy, sc = self._low(u.x, u.y)
        f = u.facing
        storm = self.wxv["storm"]
        moving = bool(u.nav and u.nav.get("moving"))
        bob = round(math.sin(now * 1.7 + u.uid * 1.3) * (0.7 + 1.5 * storm))
        a = self.anim.get(u.uid)
        pose = int(now * 5) % 3 if moving else 0
        if spr == "carrier":                             # aircraft parked on the deck: the hangar's share still aboard
            pose = max(0, min(3, st.get("hangar", 4) - len(u.nav.get("wing", ())) if u.nav else 0))
        elif spr in ("catapult_ship", "dreadnought"):    # the catapult's arm: flung on a shot, winding back as it reloads
            total = max(1, round(st["cooldown"] * C.SIM_RATE))
            if a is not None and a[0] == "fire" and now - a[1] < 0.55:
                pose = 1 + min(4, int(5 * (now - a[1]) / 0.55))
            else:
                pose = 5 - min(5, int((1 - min(1.0, u.cooldown / total)) * 6))
        sprite = self._sprite(spr, color, False, "fighting", 2 if u.flash else 0, sc, f < 0, pose, False, 0)
        sw, sh = sprite.get_size()
        dr = round(DRAUGHT.get(spr, 4) * sc)
        wl = gy + bob                                    # the waterline
        top = wl - sh + dr
        px = x - sw // 2
        dx = 0
        if a is not None and a[0] in ("shoot", "swing") and now - a[1] < 0.25:
            dx = -f * round(math.sin(math.pi * (now - a[1]) / 0.25))
        pygame.draw.ellipse(low, (20, 52, 96), pygame.Rect(x - int(sw * 0.42), wl - 1, int(sw * 0.84), max(3, round(4 * sc))))
        if moving:
            self._wake(low, x, wl, f, sw, sc)
        low.blit(sprite, (px + dx, top))
        low.blit(self._wl_strip(sw, max(3, dr + 2)), (px, wl - 2))
        for i in range(0, sw, 4):                        # foam lapping the hull
            if (i // 4 + int(now * 5)) % 3:
                _px(low, (236, 246, 250), px + i + (1 if f < 0 else 0), wl - 1, 2, 1)
        if self.night > 0.2:
            self.lights.append((x - f * sw // 3, top + sh // 2 - 2, 9, "torch"))
        if u.burn > 0:                                   # fire on the deck
            for k in range(3):
                fx = px + int(sw * (0.3 + 0.2 * k))
                fl = int(now * 12 + k) % 2
                _px(low, (255, 150, 40), fx, top + sh // 3 - fl, 2, 3)
                _px(low, (255, 228, 120), fx, top + sh // 3 + 1 - fl, 1, 1)
                _px(low, (70, 66, 62), fx + 1, top + sh // 3 - 4 - int(now * 8 + k) % 3, 1, 2)
        if u.hp < st["hp"] * 0.7:
            frac = max(0.0, u.hp / st["hp"])
            bw = max(8, sw // 2)
            pygame.draw.rect(low, (40, 10, 10), pygame.Rect(x - bw // 2, top - 3, bw, 1))
            pygame.draw.rect(low, (120, 230, 90), pygame.Rect(x - bw // 2, top - 3, round(bw * frac), 1))

    def _wake(self, low, x, wl, f, sw, sc):
        """White water at the bow and a widening trail of foam behind the stern."""
        _px(low, (244, 250, 255), x + f * (sw // 2 - 3), wl - 1, 3, 1)
        _px(low, (200, 230, 240), x + f * (sw // 2 - 1), wl, 3, 1)
        for i in range(1, 9):
            k = i / 9
            col = _lerp3((236, 246, 250), (60, 124, 172), k)
            bx = x - f * (sw // 2 + i * 2)
            _px(low, col, bx, wl - (i % 2), 2, 1)
            if i > 3:
                _px(low, col, bx, wl + 1 + (i % 2), 2, 1)

    def _draw_sink(self, low, s):
        """A ship going down: tilting and settling into the water until only the top of the mast shows."""
        now = self.now
        k = min(1.0, (now - s["born"]) / 3.2)
        st = self._unit_types[s["kind"]]
        x, gy, sc = self._low(s["x"], s["y"])
        spr = st["sprite"]
        f = s["facing"]
        sprite = self._sprite(spr, self._sides[s["side"]]["color"], False, "fighting", 0, sc, f < 0, 0, False, 0)
        sw, sh = sprite.get_size()
        dr = round(DRAUGHT.get(spr, 4) * sc)
        wl = gy + round(math.sin(now * 2 + s["x"]) * 1.2)
        rot = pygame.transform.rotate(sprite, -f * 20 * k)
        rw, rh = rot.get_size()
        top = wl - rh + dr + int(k * (sh + 2))
        low.set_clip(pygame.Rect(0, 0, C.LOW_W, wl + 1))
        low.blit(rot, (x - rw // 2, top))
        low.set_clip(None)
        r = int(sw * (0.3 + 0.5 * k))
        pygame.draw.ellipse(low, (226, 240, 248), pygame.Rect(x - r, wl - 1, 2 * r, 3), 1)        # a ring of foam
        if k < 0.85 and int(now * 9) % 2:
            _px(low, (240, 248, 252), x + int(math.sin(now * 5) * sw * 0.3), wl - 2, 2, 1)

    # ------------------------------------------------------------------ what shots do at sea
    def _sea_impact(self, rec):
        """A shot that comes down at sea: a hit on a ship throws wood and smoke, a miss throws up water. Returns True
        when the shot has been dealt with here."""
        if self.shore is None or rec["y1"] < self.shore:
            return False
        x, y = rec["x1"], rec["y1"]
        if rec.get("target") in self._ship_ids:
            self._burst("debris", x, y, 1)
            if rec["kind"] == "stone":
                self._burst("smoke", x, y, 1)
                self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.4, "size": 20, "col": (210, 190, 150)})
            if rec.get("ammo") == "fire":
                self._burst("fire", x, y, 1)
            if self.audio:
                self.audio.sfx("crash" if rec["kind"] == "stone" else "arrow_hit", x)
            return True
        self._splash(x, y, rec["kind"] == "stone")
        return True

    def _splash(self, x, y, big=False):
        self._burst("splash", x, y, 2 if big else 1)
        self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.6 if big else 0.4, "size": 24 if big else 11,
                           "col": (226, 242, 250)})
        if self.audio:
            self.audio.sfx("splash", x)

    def _ship_fx(self, battle, fx):
        """Effects that belong to the sea: a ship sinking, marines landing."""
        kind, x, y = fx[0], fx[1], fx[2]
        if kind == "sink":
            self.sinks.append({"x": x, "y": y, "side": fx[3], "kind": fx[4], "facing": fx[5], "born": self.now})
            self._splash(x, y, True)
            if self.audio:
                self.audio.sfx("crash", x)
        elif kind == "landing":
            self._burst("dust", x, y - 8, 3)
            self._splash(x, y + 12, True)
            if self.audio:
                self.audio.sfx("horn", x)

    def _sea_update(self, dt):
        """Sinking ships leave bubbles while they go down, then wreckage."""
        now = self.now
        self._sink_bubble -= dt
        for s in self.sinks[:]:
            if now - s["born"] >= 3.2:
                self.sinks.remove(s)
                for _ in range(6):
                    self.flotsam.append({"x": s["x"] + self.rng.uniform(-22, 22), "y": s["y"] + self.rng.uniform(-6, 6),
                                         "born": now, "dx": self.rng.uniform(-3, 3), "len": self.rng.randint(3, 6),
                                         "ph": self.rng.uniform(0, 6)})
            elif self._sink_bubble <= 0 and self._seen(s["x"]):
                self._burst("splash", s["x"] + self.rng.uniform(-12, 12), s["y"], 1)
        if self._sink_bubble <= 0:
            self._sink_bubble = 0.25
