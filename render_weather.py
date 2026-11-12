"""Drawing the weather the engine runs (weather.py): the sky greys and darkens, cloud decks drift on the wind, rain
streaks across the screen and splashes on the ground, snow drifts down and settles on the field, fog fills the air
and softens the distance, and lightning splits the sky and flashes the whole scene, with the thunder arriving after it.
WeatherRender is a mixin for Renderer. self.wxv holds the weather mix the engine reports, copied each frame."""
import math
import random

import pygame

import config as C

NAMES = {"clear": "Clear skies", "cloudy": "Overcast", "rain": "Rain", "storm": "Thunderstorm", "fog": "Fog",
         "snow": "Snow"}


def _px(surf, color, x, y, w=1, h=1):
    surf.fill(color, pygame.Rect(x, y, w, h))


class WeatherRender:
    def _wx_init(self):
        self.wxv = {"cloud": 0.0, "rain": 0.0, "storm": 0.0, "fog": 0.0, "snow": 0.0, "wind": 0.0}
        self._wx_kind = None
        self.snow_cover = 0.0                      # how much snow lies on the ground (builds in snow, melts after)
        self.flash = 0.0                           # the sky's lightning flash (1 at the strike, fading fast)
        self.bolts = []                            # lightning bolts: dicts of pts and born
        self.thunder_q = []                        # (real time due, world x): thunder still on its way
        self.drops, self.flakes, self.drips = [], [], []
        self.cloud_x = 0.0                         # how far the clouds have drifted (they go with the wind)
        self.next_sheet = 6.0
        self._wxrng = random.Random(5)
        self._make_weather_art()

    # ------------------------------------------------------------------ static art
    def _make_weather_art(self):
        rng = random.Random(31)
        horizon = round(C.SKY_HORIZON / C.PIXEL)

        def deck(col, alpha_lo, alpha_hi):
            s = pygame.Surface((C.LOW_W, horizon + 14), pygame.SRCALPHA)
            for _ in range(90):
                x, y = rng.uniform(0, C.LOW_W), rng.uniform(-6, horizon - 28)
                w, h = rng.uniform(44, 150), rng.uniform(14, 36)
                c = col + (rng.randint(alpha_lo, alpha_hi),)
                for wrap in (-C.LOW_W, 0, C.LOW_W):
                    pygame.draw.ellipse(s, c, pygame.Rect(int(x + wrap), int(y), int(w), int(h)))
            return s

        self.deck_light = deck((178, 182, 192), 70, 130)
        self.deck_dark = deck((58, 64, 82), 90, 160)
        fw = pygame.Surface((C.LOW_W, C.LOW_H), pygame.SRCALPHA)       # a wall of haze, thickest at the horizon
        for y in range(C.LOW_H):
            a = 90 + 120 * (y / horizon) if y < horizon else max(50, 200 - 150 * (y - horizon) / (C.LOW_H - horizon))
            pygame.draw.line(fw, (198, 204, 212, int(min(220, a))), (0, y), (C.LOW_W, y))
        self.fog_wall = fw
        self.fog_puffs = pygame.Surface((C.LOW_W * 2, 90), pygame.SRCALPHA)
        for _ in range(46):
            x, y, w, h = rng.uniform(0, C.LOW_W * 2), rng.uniform(0, 60), rng.uniform(60, 190), rng.uniform(14, 34)
            for wrap in (-C.LOW_W * 2, 0, C.LOW_W * 2):
                pygame.draw.ellipse(self.fog_puffs, (214, 220, 226, rng.randint(26, 58)),
                                    pygame.Rect(int(x + wrap), int(y), int(w), int(h)))
        h = C.LOW_H - horizon
        self.snow_tex = pygame.Surface((C.LOW_W, h), pygame.SRCALPHA)
        for _ in range(220):
            x, y = rng.uniform(0, C.LOW_W), rng.uniform(0, h)
            w, hh = rng.uniform(14, 60), rng.uniform(3, 10)
            for wrap in (-C.LOW_W, 0):
                pygame.draw.ellipse(self.snow_tex, (236, 242, 250, 255), pygame.Rect(int(x + wrap), int(y), int(w), int(hh)))
        for _ in range(900):
            self.snow_tex.set_at((rng.randrange(C.LOW_W), rng.randrange(h)), (250, 252, 255, 255))

    # ------------------------------------------------------------------ per frame
    def _wx_update(self, battle):
        w = battle.wx
        for k in self.wxv:
            self.wxv[k] = w[k]
        now, dt = self.now, self._dt
        if self._wx_kind is None:
            self._wx_kind = battle.wx_kind
        elif battle.wx_kind != self._wx_kind:
            self._wx_kind = battle.wx_kind
            self.notify(NAMES[battle.wx_kind])
        self.cloud_x += (1.4 + abs(w["wind"]) * 10.0) * dt
        if w["snow"] > 0.35:
            self.snow_cover = min(1.0, self.snow_cover + dt * w["snow"] / 25)
        else:
            self.snow_cover = max(0.0, self.snow_cover - dt / 45)
        self.flash = max(0.0, self.flash - dt * 3.5)
        if w["storm"] > 0.5 and now > self.next_sheet:       # distant sheet lightning in the clouds
            self.flash = max(self.flash, 0.5)
            self.next_sheet = now + self._wxrng.uniform(4, 11)
            self.thunder_q.append((now + self._wxrng.uniform(0.6, 2.2), self.cam_x + C.SCREEN_W / 2 + self._wxrng.uniform(-900, 900)))
        due = [q for q in self.thunder_q if q[0] <= now]
        if due:
            self.thunder_q = [q for q in self.thunder_q if q[0] > now]
            if self.audio:
                for _, x in due:
                    self.audio.sfx("thunder", x)
        self.bolts = [b for b in self.bolts if now - b["born"] < 0.4]
        self._wx_particles(dt, w)
        if self.audio:
            self.audio.set_ambience(rain=w["rain"], wind=abs(w["wind"]), storm=w["storm"], snow=w["snow"],
                                    surf=0.5 if self.shore is not None else 0.0)

    def _wx_particles(self, dt, w):
        horizon = round(C.SKY_HORIZON / C.PIXEL)
        rain_n = int(w["rain"] * 300)
        first = not self.drops
        while len(self.drops) < rain_n:
            near = self._wxrng.random() < 0.4
            self.drops.append([self._wxrng.uniform(-30, C.LOW_W + 60),
                               self._wxrng.uniform(0, C.LOW_H) if first else self._wxrng.uniform(-30, 0),
                               self._wxrng.uniform(300, 400) if near else self._wxrng.uniform(220, 300),
                               self._wxrng.randint(3, 5) if near else self._wxrng.randint(2, 3), near,
                               self._wxrng.uniform(horizon + 6, C.LOW_H)])
        del self.drops[rain_n:]
        vx = w["wind"] * 70
        for d in self.drops:
            d[0] += vx * dt
            d[1] += d[2] * dt
            if d[1] >= d[5]:                                  # it lands: a little splash, then it falls again
                if d[1] > horizon + 20 and len(self.drips) < 90 and self._wxrng.random() < 0.5:
                    self.drips.append((d[0], d[1], self.now))
                d[0] = self._wxrng.uniform(-30, C.LOW_W + 60)
                d[1] = self._wxrng.uniform(-30, 0)
                d[5] = self._wxrng.uniform(horizon + 6, C.LOW_H)
        self.drips = [p for p in self.drips if self.now - p[2] < 0.2]
        snow_n = int(w["snow"] * 240)
        first = not self.flakes
        while len(self.flakes) < snow_n:
            self.flakes.append([self._wxrng.uniform(-20, C.LOW_W + 40),
                                self._wxrng.uniform(0, C.LOW_H) if first else self._wxrng.uniform(-20, 0),
                                self._wxrng.uniform(16, 40), self._wxrng.uniform(0, 6.28), self._wxrng.choice((1, 1, 2))])
        del self.flakes[snow_n:]
        for f in self.flakes:
            f[0] += (w["wind"] * 35 + math.sin(self.now * 1.3 + f[3]) * 10) * dt
            f[1] += f[2] * dt
            if f[1] > C.LOW_H:
                f[0] = self._wxrng.uniform(-20, C.LOW_W + 40)
                f[1] = self._wxrng.uniform(-20, 0)

    def _lightning_fx(self, battle, x, y):
        """A bolt strikes at (x, y): the sky flashes, a jagged bolt runs down to the spot, and thunder follows."""
        sx, sy, _ = self._low(x, y)
        pts = [(sx + self._wxrng.uniform(-40, 40), -2.0)]
        steps = 9
        for i in range(1, steps + 1):
            k = i / steps
            jag = (1 - k) * 12
            pts.append((pts[0][0] + (sx - pts[0][0]) * k + self._wxrng.uniform(-jag, jag), sy * k))
        pts[-1] = (sx, sy)
        branch = []
        j = self._wxrng.randint(3, 6)
        bx, by = pts[j]
        for i in range(1, 4):
            branch.append((bx + i * 5 * self._wxrng.choice((-1, 1)) + self._wxrng.uniform(-3, 3), by + i * 6))
        self.bolts.append({"pts": pts, "branch": [pts[j]] + branch, "born": self.now})
        self.flash = 1.0
        self._burst("fire", x, y, 2)
        self._burst("debris", x, y, 1)
        self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.5, "size": 40, "col": (200, 220, 255)})
        if self._seen(x):
            self.shake = max(self.shake, 4.0)
        delay = 0.15 + min(1.8, abs(x - (self.cam_x + C.SCREEN_W / 2)) / 700)
        self.thunder_q.append((self.now + delay, x))
        if self.audio:
            self.audio.sfx("crack", x)

    # ------------------------------------------------------------------ drawing
    def _wx_sky_colors(self, top, bot):
        """The sky's gradient, greyed and darkened by cloud and storm."""
        w = self.wxv
        oc, storm = w["cloud"], w["storm"]
        if oc > 0.01:
            lum = 0.3 + 0.7 * self.day
            g_top = tuple(int(c * lum * (1 - 0.45 * storm)) for c in (122, 130, 144))
            g_bot = tuple(int(c * lum * (1 - 0.40 * storm)) for c in (172, 174, 180))
            top = tuple(int(a + (b - a) * oc * 0.9) for a, b in zip(top, g_top))
            bot = tuple(int(a + (b - a) * oc * 0.85) for a, b in zip(bot, g_bot))
        return top, bot

    def _wx_sky(self, low):
        w = self.wxv
        oc, storm = w["cloud"], w["storm"]
        if oc <= 0.03:
            return
        off = int(self.cloud_x * 1.6) % C.LOW_W
        for deck, a in ((self.deck_light, oc * (1 - storm)), (self.deck_dark, oc * storm)):
            if a > 0.02:
                deck.set_alpha(int(255 * min(1.0, a)))
                low.blit(deck, (-off, 0))
                low.blit(deck, (C.LOW_W - off, 0))

    def _wx_snow_ground(self, low):
        """Snow lying on the field: laid over the grass, below the horizon."""
        if self.snow_cover < 0.03:
            return
        horizon = round(C.SKY_HORIZON / C.PIXEL)
        self.snow_tex.set_alpha(int(235 * min(1.0, self.snow_cover)))
        off = int(self.cam_x / C.PIXEL) % C.LOW_W
        low.blit(self.snow_tex, (-off, horizon))
        low.blit(self.snow_tex, (C.LOW_W - off, horizon))

    def _draw_weather_fog(self, low):
        fog = self.wxv["fog"]
        if fog <= 0.02:
            return
        self.fog_wall.set_alpha(int(255 * min(1.0, fog * 0.9)))
        low.blit(self.fog_wall, (0, 0))
        horizon = round(C.SKY_HORIZON / C.PIXEL)
        self.fog_puffs.set_alpha(int(255 * min(1.0, fog)))
        for k, (rate, y) in enumerate(((0.5, horizon - 18), (1.1, horizon + 26))):   # banks of mist drifting at two depths
            off = int(self.cam_x / C.PIXEL * rate + self.cloud_x * (1.5 + k)) % (C.LOW_W * 2)
            low.blit(self.fog_puffs, (-off, y))
            low.blit(self.fog_puffs, (C.LOW_W * 2 - off, y))

    def _draw_weather_front(self, low):
        """Rain, snow and lightning: laid over the finished scene."""
        w = self.wxv
        lum = 0.45 + 0.55 * self.day
        if self.drops:
            far = (int(150 * lum), int(170 * lum), int(204 * lum))
            near = (int(196 * lum), int(214 * lum), int(240 * lum))
            vx = w["wind"] * 70
            for d in self.drops:
                pygame.draw.line(low, near if d[4] else far, (int(d[0]), int(d[1])),
                                 (int(d[0] - vx * 0.03), int(d[1] - d[3])))
            ripple = (int(190 * lum), int(210 * lum), int(232 * lum))
            for x, y, born in self.drips:
                k = (self.now - born) / 0.2
                _px(low, ripple, int(x) - 1 - int(k * 2), int(y), 3 + int(k * 4), 1)
        if self.flakes:
            col = (int(244 * lum), int(248 * lum), int(255 * lum))
            for f in self.flakes:
                _px(low, col, int(f[0]), int(f[1]), f[4], f[4])
        if self.flash > 0.02:
            v = int(105 * self.flash)
            low.fill((v, v, min(255, v + 12)), special_flags=pygame.BLEND_RGB_ADD)
        for b in self.bolts:
            age = (self.now - b["born"]) / 0.4
            if age > 0.5 and int(self.now * 40) % 2:
                continue
            for pts, core in ((b["pts"], 2), (b["branch"], 1)):
                pygame.draw.lines(low, (150, 176, 255), False, pts, core + 2)
                pygame.draw.lines(low, (255, 255, 255), False, pts, core)
