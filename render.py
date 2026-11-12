"""The 2.5D view: the battlefield is seen side-on and scrolls past a camera. The map's depth (sim y) becomes a depth
lane: the far edge is small and high on screen, the near edge is large and low. The camera follows the fighting on
its own (a slow, cinematic drift) and the left and right arrow keys pan it by hand. The scenery behind and in front
of the battle scrolls at different speeds for depth. A day and night cycle tints the whole scene; at night the men
carry torches and the towers, walls and camps glow.

The simulation is flat (top-down); this module only places it on screen. Everything is drawn at low resolution
and scaled up for the pixel-art look. Walls, towers and gates are drawn as blocks with a top and a front face,
and everything is drawn in order of depth so that a wall hides the units standing behind it. Archers standing
on walls and towers are drawn just after the wall they stand on. There is no HUD unless H is pressed."""
import bisect
import math
import random
import time

import pygame

import config as C
import doodads
import heroes
import sprites
from extras import rank_of
from render_camp import CampRender
from render_crash import CrashRender
from render_land import LandRender
from render_rounds import RoundRender
from render_sea import SeaRender
from render_weather import WeatherRender

GOLD = (236, 196, 84)
INK = (26, 20, 16)
SKIN = (226, 190, 150)

# sky colours before the night tint is laid over the scene (so they are brighter than they end up)
DAY_TOP, DAY_BOT = (58, 92, 140), (196, 176, 136)
DUSK_TOP, DUSK_BOT = (84, 80, 140), (244, 150, 96)
NIGHT_TOP, NIGHT_BOT = (40, 56, 110), (100, 116, 156)
DAY_TINT, DUSK_TINT, NIGHT_TINT = (255, 255, 255), (255, 190, 150), (62, 80, 150)


def shade(color, k):
    return tuple(max(0, min(255, int(c * k))) for c in color)


def lerp3(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def smooth(lo, hi, x):
    t = max(0.0, min(1.0, (x - lo) / (hi - lo)))
    return t * t * (3 - 2 * t)


def _px(surf, color, x, y, w=1, h=1):
    surf.fill(color, pygame.Rect(x, y, w, h))


GOLD_L = (236, 196, 84)


class Renderer(CampRender, SeaRender, WeatherRender, RoundRender, LandRender, CrashRender):
    def __init__(self, scenario):
        self.sc = scenario
        self.W = scenario["map"]["width"]
        self.H = scenario["map"]["height"]
        self.low = pygame.Surface((C.LOW_W, C.LOW_H))
        self.sprites = {}
        self.prop_sprites = {}
        self.t = 0
        self.font = pygame.font.Font(None, 24)
        self.small = pygame.font.Font(None, 20)
        self.mid = pygame.font.Font(None, 40)
        self.rng = random.Random(7)
        # camera
        self.cam_x = max(0.0, self.W / 2 - C.SCREEN_W / 2)
        self.pan_dir = 0                              # -1 / 0 / 1: set each frame by the arrow keys
        self.cinematic = True                         # follow the fighting when no key has been pressed lately
        self._manual_until = 0.0
        self._cam_goal = self.W / 2                   # where the fighting is now (rescanned a few times a second)
        self._cam_aim = self.W / 2                    # ...and the same, smoothed: what the camera actually chases
        self._cam_scan = -1e9
        self._cam_v = 0.0                             # camera velocity (px/s): the camera has momentum
        self._pan_v = 0.0                             # velocity from the arrow keys, eased in and out
        self.speed = 1                                # battle speed multiplier (set by main): paces the shots in flight
        self.audio = None                             # a sound.Audio, set by main; None = silent
        self.plunges = []                             # flyers shot down, falling out of the sky
        self.wrecks = []                              # crashed aircraft lying on the ground
        self._unit_types = scenario['unit_types']
        self.styles = {sd['color']: sd.get('style', '') for sd in scenario['sides'].values()}   # a side's colour -> its look
        sprites.register_sides(self.styles)                 # the WW2 art picks each side's uniforms and markings by it
        self._sides = scenario['sides']
        self.king = {}                                # uid -> the king's pacing on his keep: mode, timer, spot
        self.anim = {}                                # uid -> (kind, real time, extra): a swing, a shot or a siege throw
        self.cast = {}                                # uid -> (real time, colour) of a hero's latest skill
        self.floaters = []                            # floating text: skill names, falls and returns
        self.pillars = []                             # columns of light where a hero returns or holy fire falls
        self.shake = 0.0                              # camera shake, in screen pixels (decays quickly)
        self.shake_dx = self.shake_dy = 0.0
        self.flames = []                              # pitch fires left burning where fire ammo landed: (x, y, until)
        self.rings = []                               # expanding shock rings: dicts of x, y, born, life, size
        # light
        self.clock = C.START_PHASE * C.DAY_SECONDS
        self.phase, self.day, self.dusk, self.night = C.START_PHASE, 1.0, 0.0, 0.0
        self.tint = DAY_TINT
        self.lights = []                              # (x, y, glow radius, kind) collected while drawing, lit at night
        # interface
        self.show_hud = False
        self.parallax = True                          # X: background layers scroll at their own speeds (off: flat)
        self.letterbox = True
        self.toast = ("", 0.0)
        # shots, particles, bodies
        self.shot_live = {}               # uid -> (shot record, real time it was let fly)
        self._max_shot = 0                # the newest shot uid seen so far (uids only grow)
        self._last_pos = {}               # uid -> where a unit was last frame (to tell when it is walking)
        self._ip = {}                     # uid -> [from x, from y, to x, to y, start time, duration]: the glide between ticks
        self._tc, self._tc_t, self._tick_dt = 0, None, 0.5   # last tick count seen, when, and the real seconds a tick takes
        self._walk_until = {}             # uid -> real time until which its legs keep stepping
        self.corpses = []                 # fallen units: where they lie, what they look like, when they fell
        self.craters = []                 # (x, y, radius) in world units: the craters stone shots dig
        self.particles = []               # dust, blood and sparks: world x, y, height h, velocities, life (seconds)
        self.now = time.perf_counter()
        self._last_real = self.now
        self._dt = 1 / C.FPS
        # static art, made once
        self.sky_clouds = self._make_clouds()
        self.ground = self._make_ground()
        self.far_hills = self._make_hills(seed=3, base=C.SKY_HORIZON - 40, amp=34, step=18, f=0.12)
        self.near_hills = self._make_hills(seed=8, base=C.SKY_HORIZON - 12, amp=16, step=12, f=0.25)
        self.fog = self._make_fog()
        self.vignette = self._make_vignette()
        self.sun_img, self.moon_img = self._make_orbs()
        self.glows = {(r, lv): self._make_glow(r, k) for r in (6, 7, 8, 9, 11, 12, 14, 22)
                      for lv, k in enumerate((0.2, 0.36, 0.55))}
        scenery = random.Random(21)
        self.stars = [(scenery.randrange(0, C.LOW_W), scenery.randrange(2, 132), scenery.uniform(0.4, 1.0))
                      for _ in range(150)]
        # trees on the far hills: they scroll more than the hills behind them and less than the ground
        span = self.W * 0.45 + C.SCREEN_W + 80
        self.mid_trees = [(scenery.uniform(-40, span), scenery.uniform(5, 11), scenery.uniform(346, 362))
                          for _ in range(int(150 * span / C.SCREEN_W))]
        # grass tufts across the bottom of the screen: the nearest layer, so it scrolls the most
        span = self.W * 1.5 + C.SCREEN_W
        self.tufts = [(scenery.uniform(0, span), scenery.uniform(650, 718), scenery.uniform(0.8, 1.4))
                      for _ in range(int(90 * span / C.SCREEN_W))]
        self.props = doodads.place(scenario, C.DOODADS)
        self.prop_x = [p["x"] for p in self.props]
        for kind in doodads.KINDS:                               # build every doodad now, not mid-battle
            for var in range(3):
                self._prop_sprite(kind, var, False, 1.0)
        gates = sorted(t["rect"] for t in scenario["terrain"] if t.get("style") == "gate")
        self.road = None
        if len(gates) >= 2:                                      # a worn dirt road from gate to gate
            g0, g1 = gates[0], gates[-1]
            self.road = (g0[0] + g0[2], g1[0], g0[1] + g0[3] / 2)
        self._wx_init()
        self._sea_init()

    # ------------------------------------------------------------------ interface hooks used by main.py
    def look_at(self, x):
        self.cam_x = max(0.0, min(self.W - C.SCREEN_W, x - C.SCREEN_W / 2))
        self._manual_until = time.perf_counter() + 1e6

    def set_phase(self, phase):
        self.clock = phase * C.DAY_SECONDS

    def notify(self, text):
        self.toast = (text, time.perf_counter() + 1.6)

    # ------------------------------------------------------------------ projection
    def depth(self, y):
        """Sim y (0 = far edge, H = near edge) to a depth lane z in 0..1."""
        return C.VIEW_FAR + C.VIEW_PER_Y * y

    def project(self, x, y, h=0.0):
        """World point (x, y) at height h (full-resolution pixels) -> screen (sx, sy, scale)."""
        z = self.depth(y)
        sc = 0.75 + 0.5 * z
        sx = x - self.cam_x + self.shake_dx
        sy = C.GROUND_Y + (z - 0.5) * C.LANE_SPREAD - h * sc + self.shake_dy
        return sx, sy, sc

    def _low(self, x, y, h=0.0):
        sx, sy, sc = self.project(x, y, h)
        return round(sx / C.PIXEL), round(sy / C.PIXEL), sc

    def _seen(self, x0, x1=None, margin=80):
        """True when the world span x0..x1 overlaps the screen."""
        x1 = x0 if x1 is None else x1
        return x1 >= self.cam_x - margin and x0 <= self.cam_x + C.SCREEN_W + margin

    # ------------------------------------------------------------------ static art (made once)
    def _make_clouds(self):
        surf = pygame.Surface((C.LOW_W, C.SKY_HORIZON // C.PIXEL), pygame.SRCALPHA)
        rng = random.Random(5)
        for _ in range(9):
            cx, cy = rng.uniform(0, C.LOW_W), rng.uniform(16, surf.get_height() * 0.55)
            w = rng.uniform(40, 96)
            for wrap in (-C.LOW_W, 0, C.LOW_W):                # drawn again either side so the layer wraps cleanly
                for _ in range(5):
                    ox, oy = rng.uniform(-w * 0.4, w * 0.4), rng.uniform(-3, 3)
                    rw, rh = int(w * rng.uniform(0.3, 0.5)), int(rng.uniform(5, 9))
                    pygame.draw.ellipse(surf, (222, 218, 206, 230),
                                        pygame.Rect(int(cx + wrap + ox - rw / 2), int(cy + oy - rh / 2), rw, rh))
                pygame.draw.ellipse(surf, (178, 174, 170, 200), pygame.Rect(int(cx + wrap - w / 2), int(cy + 2), int(w), 4))
        return surf

    def _make_hills(self, seed, base, amp, step, f):
        """A ridge line of hills spanning the scrolled width, drawn as a silhouette."""
        rng = random.Random(seed)
        pts = []
        for x in range(-80, int(self.W * f) + C.SCREEN_W + 160, step):
            pts.append((x, base - amp * (0.5 + 0.5 * math.sin(x * 0.011 + rng.uniform(0, 6))) * rng.uniform(0.6, 1.0)))
        return pts

    def _make_vignette(self):
        surf = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        for i in range(0, 120, 4):
            alpha = int(110 * (i / 120) ** 2)
            pygame.draw.ellipse(surf, (0, 0, 0, alpha),
                                pygame.Rect(-i * 3, -i * 2, C.SCREEN_W + i * 6, C.SCREEN_H + i * 4), 4)
        return surf

    def _make_fog(self):
        """A band of haze along the horizon, strongest on the line itself."""
        surf = pygame.Surface((C.LOW_W, 20), pygame.SRCALPHA)
        for r in range(20):
            alpha = int(120 * max(0.0, 1 - abs(r - 9) / 10) ** 1.5)
            pygame.draw.line(surf, (214, 206, 186, alpha), (0, r), (C.LOW_W, r))
        return surf

    def _make_orbs(self):
        sun = pygame.Surface((40, 40), pygame.SRCALPHA)
        for r, a in ((19, 26), (15, 50), (11, 110)):
            pygame.draw.circle(sun, (255, 236, 170, a), (20, 20), r)
        pygame.draw.circle(sun, (255, 250, 220), (20, 20), 8)
        moon = pygame.Surface((36, 36), pygame.SRCALPHA)
        for r, a in ((17, 24), (13, 44)):
            pygame.draw.circle(moon, (200, 214, 255, a), (18, 18), r)
        pygame.draw.circle(moon, (232, 236, 246), (18, 18), 8)
        for x, y, r in ((15, 15, 2), (21, 19, 2), (17, 22, 1)):
            pygame.draw.circle(moon, (192, 198, 214), (x, y), r)
        return sun, moon

    def _make_glow(self, r, k):
        """A soft orange glow for lighting at night: laid on with additive blending, so it brightens what is under it."""
        s = pygame.Surface((r * 2, r * 2))
        for rr in range(r, 0, -1):
            i = k * (1 - rr / r) ** 1.6 * 1.1
            pygame.draw.circle(s, (min(255, int(255 * i)), min(255, int(150 * i)), min(255, int(60 * i))), (r, r), rr)
        return s

    def _make_ground(self):
        """The grass below the horizon: depth bands, nearer bands brighter, with mown patches and blades. It is one
        screen wide and wraps, so the camera can scroll it for ever."""
        horizon = round(C.SKY_HORIZON / C.PIXEL)
        h = C.LOW_H - horizon
        surf = pygame.Surface((C.LOW_W, h))
        for y in range(h):
            k = 0.7 + 0.45 * y / max(1, h)
            pygame.draw.line(surf, shade((84, 116, 64), k), (0, y), (C.LOW_W, y))
        rng = random.Random(44)
        for _ in range(70):
            px, py = rng.uniform(0, C.LOW_W), rng.uniform(0, h)
            w, hh = int(rng.uniform(20, 70)), int(rng.uniform(4, 10))
            col = shade((84, 116, 64), rng.uniform(0.82, 0.94) * (1.0 if rng.random() < 0.7 else 1.12))
            for wrap in (0, -C.LOW_W):
                pygame.draw.ellipse(surf, col, pygame.Rect(int(px + wrap), int(py), w, hh))
        for _ in range(1800):
            px, py = rng.randrange(C.LOW_W), rng.randrange(h)
            k = (0.7 + 0.45 * py / max(1, h)) * rng.choice((0.8, 1.2, 1.3))
            _px(surf, shade((84, 116, 64), k), px, py)
        for z in (0.10, 0.26, 0.42, 0.58, 0.74, 0.90):
            y = round((C.GROUND_Y + (z - 0.5) * C.LANE_SPREAD) / C.PIXEL)
            if y > horizon:
                pygame.draw.line(surf, shade((84, 116, 64), 0.84), (0, y - horizon), (C.LOW_W, y - horizon))
        return surf

    # ------------------------------------------------------------------ sprites (cached, scaled with depth)
    def _sprite(self, kind, color, hero, state, flash, sc, flip=False, frame=0, wounded=False, variant=0):
        """A unit's sprite at this depth scale, facing left if flip, on walk frame `frame`. Built once per distinct
        look, so the frame never flips, rotates or scales a sprite."""
        bucket = round(sc * 10)
        key = (kind, color, hero, state, flash, bucket, flip, frame, wounded, variant)
        if key not in self.sprites:
            base_key = (kind, color, hero, state, flash, frame, wounded, variant)
            if base_key not in self.sprites:
                white = flash > 0
                style = self.styles.get(color, "")
                routing = state == "routing"
                if kind in ("wyvern", "hawk"):
                    s = getattr(sprites, kind)(color, white, frame)
                elif kind in sprites.HEROES:
                    s = sprites.HEROES[kind](color, variant, white, frame)         # variant = the hero's style
                elif kind == "rider":
                    s = sprites.rider(color, hero, white, frame, variant)
                elif kind == "huorn":
                    s = sprites.huorn(white)
                elif kind in sprites.SIEGE_KINDS:
                    s = getattr(sprites, kind)(color, white, frame, style=style)   # frame = the throwing pose
                elif kind in sprites.EXTRA_KINDS:
                    s = getattr(sprites, kind)(color, white, frame)  # longbow, halberdier … harpy, ships
                else:
                    s = sprites.foot(color, archer=(kind == "archer"), hero=hero, white=white, frame=frame,
                                     wounded=wounded, routing=routing, variant=variant)
                s = sprites.dress(s, kind, style)
                if not white:
                    s = sprites.restyle(s, kind, style)
                if state == "dead":                     # a body lies on its side
                    s = pygame.transform.rotate(s, -90)
                if state in ("routing", "dead"):
                    s.fill((150, 140, 140, 255), special_flags=pygame.BLEND_RGBA_MULT)
                self.sprites[base_key] = s
            s = self.sprites[base_key]
            if flip:
                s = pygame.transform.flip(s, True, False)
            w, h = max(1, round(s.get_width() * bucket / 10)), max(1, round(s.get_height() * bucket / 10))
            self.sprites[key] = pygame.transform.scale(s, (w, h))
        return self.sprites[key]

    def _prop_sprite(self, kind, var, flip, sc):
        bucket = round(sc * 10)
        key = (kind, var, flip, bucket)
        if key not in self.prop_sprites:
            base = (kind, var)
            if base not in self.prop_sprites:
                self.prop_sprites[base] = doodads.build(kind, var)
            s = self.prop_sprites[base]
            if flip:
                s = pygame.transform.flip(s, True, False)
            w, h = max(1, round(s.get_width() * bucket / 10)), max(1, round(s.get_height() * bucket / 10))
            self.prop_sprites[key] = pygame.transform.scale(s, (w, h))
        return self.prop_sprites[key]

    # ------------------------------------------------------------------ light, sky and background
    def _update_light(self, dt):
        self.clock += dt
        self.phase = (self.clock / C.DAY_SECONDS) % 1.0
        sun = math.sin(2 * math.pi * (self.phase - 0.25))
        self.day = smooth(-0.12, 0.30, sun)
        self.dusk = max(0.0, 1 - abs(sun) / 0.28)
        self.night = 1.0 - self.day
        tint = lerp3(NIGHT_TINT, DAY_TINT, self.day)
        self.tint = lerp3(tint, DUSK_TINT, self.dusk * 0.55)

    def _draw_sky(self, low):
        key = (round(self.day * 40), round(self.dusk * 40), round(self.wxv['cloud'] * 20), round(self.wxv['storm'] * 20))        # the gradient only changes slowly: redraw it rarely
        if key != getattr(self, "_sky_key", None):
            self._sky_key = key
            top = lerp3(NIGHT_TOP, DAY_TOP, self.day)
            bot = lerp3(NIGHT_BOT, DAY_BOT, self.day)
            if self.dusk:
                top = lerp3(top, DUSK_TOP, self.dusk * 0.8)
                bot = lerp3(bot, DUSK_BOT, self.dusk * 0.9)
            top, bot = self._wx_sky_colors(top, bot)
            horizon = C.SKY_HORIZON // C.PIXEL
            self._sky_surf = pygame.Surface((C.LOW_W, horizon + 1))
            for y in range(horizon + 1):
                pygame.draw.line(self._sky_surf, lerp3(top, bot, y / max(1, horizon)), (0, y), (C.LOW_W, y))
        low.blit(self._sky_surf, (0, 0))
        horizon = C.SKY_HORIZON // C.PIXEL
        u = (self.phase - 0.25) / 0.5                       # the sun's journey: 0 at sunrise, 1 at sunset
        if 0.0 <= u <= 1.0:
            sx = int(C.LOW_W * (0.06 + 0.88 * u))
            sy = int(horizon - 8 - 130 * math.sin(math.pi * u))
            if self.wxv['cloud'] < 0.9:
                self.sun_img.set_alpha(int(255 * (1 - self.wxv['cloud'])))
                low.blit(self.sun_img, (sx - 20, sy - 20))
        off = int((self.clock * 1.4 + self.cam_x * (0.03 if self.parallax else 0.0)) % C.LOW_W)
        low.blit(self.sky_clouds, (-off, 0))
        low.blit(self.sky_clouds, (C.LOW_W - off, 0))
        self._wx_sky(low)

    def _draw_background(self, low):
        self._draw_sky(low)
        for pts, f, col in ((self.far_hills, 0.12, (96, 110, 136)), (self.near_hills, 0.25, (70, 92, 74))):
            dx = -self.cam_x * (f if self.parallax else 0.0)       # without parallax the backdrop stands still
            poly = [(round((x + dx) / C.PIXEL), round(y / C.PIXEL)) for x, y in pts]
            poly = [p for p in poly if -30 <= p[0] <= C.LOW_W + 30]
            if len(poly) < 2:
                continue
            poly += [(poly[-1][0], C.LOW_H), (poly[0][0], C.LOW_H)]
            pygame.draw.polygon(low, col, poly)
        horizon = round(C.SKY_HORIZON / C.PIXEL)
        off = int(self.cam_x / C.PIXEL) % C.LOW_W
        low.blit(self.ground, (-off, horizon))
        low.blit(self.ground, (C.LOW_W - off, horizon))
        self._wx_snow_ground(low)
        low.blit(self.fog, (0, horizon - 10))

    def _draw_night_sky(self, low):
        """Stars and the moon, drawn over the dark scene (they are not dimmed by the night tint)."""
        if self.night < 0.2:
            return
        for i, (x, y, b) in enumerate(self.stars):
            tw = 0.55 if (i + int(self.now * 2)) % 9 == 0 else 1.0
            v = int(235 * b * tw * smooth(0.2, 0.8, self.night) * (1 - 0.95 * self.wxv['cloud']))
            _px(low, (v, v, min(255, v + 18)), x, y)
        m = (self.phase - 0.75) % 1.0 / 0.5                  # the moon's journey across the night
        if 0.0 <= m <= 1.0 and math.sin(math.pi * m) > 0.1:
            mx = int(C.LOW_W * (0.1 + 0.8 * m))
            my = int(138 - 100 * math.sin(math.pi * m))
            low.blit(self.moon_img, (mx - 18, my - 18))

    def _grade(self, low):
        """The colour of the hour: everything is multiplied by the tint of the day, dusk or night."""
        if self.tint != DAY_TINT:
            low.fill(self.tint, special_flags=pygame.BLEND_RGB_MULT)

    def _draw_lights(self, low):
        """Torches, braziers and windows: a bright flame and a glow added over the dark scene."""
        if self.night < 0.2:
            return
        lv = 0 if self.night < 0.45 else (1 if self.night < 0.8 else 2)
        flick = int(self.now * 9)
        for i, (x, y, r, kind) in enumerate(self.lights[:700]):
            g = self.glows.get((r, lv))
            if g is None:                                   # a radius nobody asked for before: build it once
                g = self.glows[(r, lv)] = self._make_glow(r, (0.2, 0.36, 0.55)[lv])
            low.blit(g, (x - r, y - r), special_flags=pygame.BLEND_RGB_ADD)
            if kind == "window":
                _px(low, (255, 214, 110), x - 1, y - 1, 2, 3)
            else:
                f = (flick + i) % 3
                _px(low, (255, 120, 30), x, y - f // 2 - 1, 1, 2)
                _px(low, (255, 224, 120), x, y - 1, 1, 1)

    # ------------------------------------------------------------------ ground-level terrain
    def _draw_road(self, low):
        if self.road is None:
            return
        x0, x1, y = self.road
        if not self._seen(x0, x1):
            return
        half = 26
        pts = [self._low(x0, y - half)[:2], self._low(x1, y - half)[:2], self._low(x1, y + half)[:2],
               self._low(x0, y + half)[:2]]
        pygame.draw.polygon(low, (134, 114, 82), pts)
        pygame.draw.line(low, (112, 94, 66), pts[0], pts[1])
        pygame.draw.line(low, (112, 94, 66), pts[3], pts[2])
        for rut in (-9, 9):                                       # two wheel ruts
            a, b = self._low(x0, y + rut)[:2], self._low(x1, y + rut)[:2]
            pygame.draw.line(low, (116, 98, 70), a, b)

    def _draw_flat_terrain(self, low, battle):
        """Ground-level things: water runs away from the viewer; trenches and spike fields are drawn flat; the rest of
        the flat ground is drawn as patches."""
        for t in battle.terrain:
            # moats are solid (no one walks in them) but are water, drawn flat; other solid things are blocks
            if t["hidden"] or (t["solid"] and t.get("style") not in ("moat", "river")) or t.get("style") == "keep":
                continue
            x, y, w, h = t["rect"]
            if not self._seen(x, x + w):
                continue
            style = t.get("style")
            if style == "water":
                self._stream_band(low, self._low(x, y)[:2], self._low(x + w, y + h)[:2], battle.time)
            elif style == "river":
                self._river_seg(low, t)
            elif style == "bridge":
                self._bridge(low, t, battle)
            elif style == "hill":
                self._flat_cached(low, t, self._hill)
            elif style in ("spikes", "wire"):
                self._flat_cached(low, t, self._spikes)
            elif style == "trench":
                self._flat_cached(low, t, self._trench)
            else:
                pts = [self._low(x, y)[:2], self._low(x + w, y)[:2], self._low(x + w, y + h)[:2], self._low(x, y + h)[:2]]
                pygame.draw.polygon(low, t["color"], pts)
                if style == "moat":                 # light glints drifting along the water
                    self._shimmer(low, pts, battle.time)
                elif style == "mines":              # a minefield: churned earth, and the mines half buried in it
                    self._draw_mine_dots(low, battle, t)

    def _flat_cached(self, low, t, draw):
        """Draws a static ground feature (wire belt, trench) once onto its own small surface and then just blits it,
        shifted by the camera: the projection is a plain slide in x, so the picture never changes."""
        cache = self.__dict__.setdefault("_flat_cache", {})
        key = id(t)
        ent = cache.get(key)
        if ent is None or ent[2] is not t:
            sv = (self.cam_x, self.shake_dx, self.shake_dy)
            self.cam_x, self.shake_dx, self.shake_dy = 0.0, 0.0, 0.0
            x, y, w, h = t["rect"]
            pts = [self._low(x + dx, y + dy, hh)[:2] for dx in (0, w) for dy in (0, h) for hh in (0, max(8, t.get("height", 8)))]
            ox, oy = min(p[0] for p in pts) - 6, min(p[1] for p in pts) - 6
            sw, sh = max(p[0] for p in pts) + 6 - ox, max(p[1] for p in pts) + 6 - oy
            if sw > 2400 or sh > 400:
                ent = (None, None, t)
            else:
                surf = pygame.Surface((sw, sh))
                surf.fill((255, 0, 255))
                surf.set_colorkey((255, 0, 255))
                self.shake_dx, self.shake_dy = -ox * C.PIXEL, -oy * C.PIXEL
                draw(surf, t)
                ent = (surf, (ox, oy), t)
            self.cam_x, self.shake_dx, self.shake_dy = sv
            cache[key] = ent
        if ent[0] is None:
            draw(low, t)
            return
        ox, oy = ent[1]
        low.blit(ent[0], (ox + round((-self.cam_x + self.shake_dx) / C.PIXEL), oy + round(self.shake_dy / C.PIXEL)))

    def _trench(self, low, t):
        """A trench: a dark floor with duckboards, the far wall lit above it, a berm of spoil with sandbags in front."""
        x, y, w, h = t["rect"]
        a, b = self._low(x, y)[:2], self._low(x + w, y)[:2]
        c, d = self._low(x + w, y + h)[:2], self._low(x, y + h)[:2]
        pygame.draw.polygon(low, (46, 34, 24), [a, b, c, d])                                  # the floor
        for wx in range(int(x) + 6, int(x + w) - 2, 12):                                      # duckboards
            p, q = self._low(wx, y + 2)[:2], self._low(wx, y + h - 2)[:2]
            pygame.draw.line(low, (86, 62, 38), p, q)
        pygame.draw.polygon(low, (112, 86, 58), [a, b, (b[0], b[1] + 2), (a[0], a[1] + 2)])  # the far wall's lit face
        pygame.draw.polygon(low, (128, 100, 68), [d, c, (c[0], c[1] + 3), (d[0], d[1] + 3)])  # the berm of spoil
        pygame.draw.line(low, (156, 126, 88), d, c)
        if max(w, h) >= 40:                                                                  # sandbags along the berm
            for wx in range(int(x) + 3, int(x + w) - 3, 9):
                sx, sy, _ = self._low(wx, y + h)
                pygame.draw.rect(low, (176, 158, 112), pygame.Rect(sx, sy + 1, 4, 2))
                pygame.draw.rect(low, (128, 112, 78), pygame.Rect(sx, sy + 2, 4, 1))
            for wy in range(int(y) + 4, int(y + h) - 3, 9) if w < h else ():                # (a long, upright trench)
                sx, sy, _ = self._low(x + w, wy)
                pygame.draw.rect(low, (176, 158, 112), pygame.Rect(sx, sy, 2, 3))

    def _shimmer(self, low, pts, t):
        """A few short glints on the muddy water of an anti-tank ditch, sliding along it as time passes."""
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        for i in range(max(1, (x1 - x0 + y1 - y0) // 14)):
            gx = x0 + (i * 37 + t * 9) % max(1, x1 - x0)
            gy = y0 + (i * 53) % max(1, y1 - y0)
            pygame.draw.line(low, (150, 128, 90), (int(gx), int(gy)), (int(gx) + 3, int(gy)))

    def _stream_band(self, low, a, b, t):
        pygame.draw.polygon(low, (52, 92, 150), [(a[0] - 4, a[1]), (a[0] + 4, a[1]), (b[0] + 4, b[1]), (b[0] - 4, b[1])])
        for i in range(0, max(1, b[1] - a[1]), 3):           # ripples drift toward the viewer
            yy = a[1] + i
            shift = int((t * 4 + i) % 6) - 3
            pygame.draw.line(low, (88, 136, 190), (a[0] - 3 + shift, yy), (a[0] + 3 + shift, yy))

    # ------------------------------------------------------------------ blocks (walls, towers, gates, keeps)
    def _emblem(self, low, x, y, pattern):
        """A side's emblem: its pixel pattern ('#' = a gold pixel), drawn with its top left at (x, y)."""
        for r, row in enumerate(pattern):
            for c, ch in enumerate(row):
                if ch == "#":
                    _px(low, GOLD, x + c, y + r)

    def _banner(self, low, x, y, height, color, emblem=None):
        """A pole with a swallowtail flag in the side's colour and its emblem, standing on top of a block."""
        top = y - height
        pygame.draw.line(low, (60, 46, 30), (x, y), (x, top))
        sway = int(math.sin(self.now * 3 + x * 0.3) * 1.2)          # the flag stirs in the wind
        flag = [(x, top), (x + 9, top + sway), (x + 9, top + 8 + sway), (x, top + 8)]
        pygame.draw.polygon(low, color, flag)
        pygame.draw.polygon(low, shade(color, 0.55), flag, 1)
        if emblem:
            self._emblem(low, x + 1, top + 1, emblem)

    def _hang(self, low, cx, top_y, color, emblem):
        """A sign board on two posts in front of a wall, painted in the side's colour with its emblem."""
        pygame.draw.line(low, (60, 46, 30), (cx - 4, top_y), (cx - 4, top_y + 11))
        pygame.draw.line(low, (60, 46, 30), (cx + 4, top_y), (cx + 4, top_y + 11))
        pygame.draw.rect(low, color, pygame.Rect(cx - 5, top_y, 11, 9))
        pygame.draw.rect(low, shade(color, 0.5), pygame.Rect(cx - 5, top_y, 11, 9), 1)
        if emblem:
            self._emblem(low, cx - 3, top_y + 2, emblem)

    # ------------------------------------------------------------------ units
    BUFF_ICONS = {"guard": (110, 150, 255), "fury": (255, 214, 90), "haste": (236, 236, 240), "slow": (110, 200, 255),
                  "vuln": (255, 96, 72)}

    def _king_walk(self, u, facing):
        """The king's idle life, drawn only (he stays where the engine put him): he strolls to a new spot on the keep
        roof, stands a while, and now and then cheers. He cheers at once when he calls a command. Returns the offset
        from his post, what he is doing, and the way he faces."""
        k = self.king.get(u.uid)
        now = self.now
        if k is None:
            k = self.king[u.uid] = {"mode": "idle", "until": now + self.rng.uniform(1, 4), "ox": 0.0, "oy": 0.0,
                                    "tx": 0.0, "ty": 0.0, "f": facing}
        cast = self.cast.get(u.uid)
        if cast is not None and now - cast[0] < 1.4 and k["mode"] != "cheer":
            k["mode"], k["until"] = "cheer", now + 1.6
        if k["mode"] == "walk":
            dx, dy = k["tx"] - k["ox"], k["ty"] - k["oy"]
            d = math.hypot(dx, dy)
            step = 9.0 * self._dt
            if d <= step:
                k["mode"], k["until"] = "idle", now + self.rng.uniform(1.5, 4)
            else:
                k["ox"] += dx / d * step
                k["oy"] += dy / d * step
                k["f"] = 1 if dx > 0 else -1
        elif now >= k["until"]:
            if k["mode"] == "idle" and self.rng.random() < 0.55:
                k["mode"] = "walk"
                k["tx"], k["ty"] = self.rng.uniform(-24, 24), self.rng.uniform(-30, 30)
            elif k["mode"] == "idle":
                k["mode"], k["until"] = "cheer", now + 1.6
                self._sparks(u.x + k["ox"], u.y + k["oy"], (255, 214, 90), 10, 14, (40, 90), 0.8)
            else:
                k["mode"], k["until"] = "idle", now + self.rng.uniform(1.5, 4)
        return k["ox"], k["oy"], k["mode"] if k["mode"] != "idle" else "idle", k["f"]

    def _draw_flyer(self, battle, u):
        """A wyvern or hawk rider at its altitude: wings beating, bobbing on the air, a shadow far below on the
        ground, lunging forward as it strikes."""
        low = self.low
        sc_unit = battle.sc["unit_types"][u.kind]
        color = battle.sc["sides"][u.side]["color"]
        now = self.now
        x, gy, sc = self._low(u.x, u.y)
        alt = u.height + 3 * math.sin(now * 2.6 + u.uid)
        _, y, _ = self._low(u.x, u.y, alt)
        f = u.facing
        frame = (0, 1, 2, 1)[int(now * 8 + u.uid) % 4]
        sprite = self._sprite(sc_unit["sprite"], color, False, u.state, 2 if u.flash else 0, sc, f < 0, frame, False, 0)
        sw, sh = sprite.get_size()
        dx = 0
        a = self.anim.get(u.uid)
        if a is not None and a[0] in ("swing", "shoot") and now - a[1] < 0.3:
            dx = f * round(3 * math.sin(math.pi * (now - a[1]) / 0.3))
        shade_w = max(4, round(sw * 0.6 * (1 - min(0.5, alt / 220))))
        pygame.draw.ellipse(low, (30, 46, 26), pygame.Rect(x - shade_w // 2, gy - 1, shade_w, max(2, round(3 * sc))))
        low.blit(sprite, (x - sw // 2 + dx, y - sh // 2))
        if self.night > 0.2:
            self.lights.append((x - f * 3, y + 2, 7, "torch"))
        if u.burn > 0:
            _px(low, (255, 150, 40), x - 2, y - sh // 2 - 1 - int(now * 12) % 2, 2, 3)
        if u.hp < sc_unit["hp"] * 0.6:
            frac = max(0.0, u.hp / sc_unit["hp"])
            pygame.draw.rect(low, (40, 10, 10), pygame.Rect(x - 5, y - sh // 2 - 4, 10, 1))
            pygame.draw.rect(low, (120, 230, 90), pygame.Rect(x - 5, y - sh // 2 - 4, round(10 * frac), 1))

    def _draw_unit(self, battle, u):
        if u.stats.get("naval"):
            self._draw_ship(battle, u)
            return
        if u.stats.get("flying"):
            self._draw_flyer(battle, u)
            return
        low = self.low
        sc_unit = battle.sc["unit_types"][u.kind]
        color = battle.sc["sides"][u.side]["color"]
        now = self.now
        spr = sc_unit["sprite"]
        siege = spr in ("catapult", "trebuchet", "ballista", "mangonel", "mlrs", "v2_launcher")
        ox = oy = 0.0
        king_mode = None
        f = u.facing
        if spr == "king":                            # the king paces his keep roof and cheers now and then
            ox, oy, king_mode, f = self._king_walk(u, f)
        x, gy, sc = self._low(u.x + ox, u.y + oy)    # the ground under the unit: its shadow goes here
        _, y, _ = self._low(u.x + ox, u.y + oy, u.height)   # its feet, raised onto the top of the keep, wall or tower
        flash = 2 if u.flash else 0
        moving = king_mode == "walk" if king_mode else self._moving(u)
        frame = int(now * 6) % 2 if moving else 0                   # legs step while it walks
        if king_mode == "cheer":
            frame = 2
        wounded = u.hp < 0.5 * sc_unit["hp"]
        if u.flash and (u.stats["speed"] > 0 or spr == "king"):
            x -= f                                   # a struck unit is knocked back a pixel
        # ---- action: lunge on a melee blow, recoil on a shot, a hop while marching, a slow breath when still
        dx = dy = 0
        swing = None
        a = self.anim.get(u.uid)
        if a is not None and not siege:
            age = now - a[1]
            if a[0] == "swing" and age < 0.3:
                swing = age / 0.3
                dx = f * round((3 if u.hero else 2) * math.sin(math.pi * swing))
            elif a[0] == "shoot" and age < 0.25:
                dx = -f * round(math.sin(math.pi * age / 0.25))
        if king_mode == "cheer":
            dy = -(int(now * 7) % 2) * 2             # hops for joy
        elif not siege and u.state == "fighting":
            if moving:
                dy = -frame
            elif int(now * 1.6 + u.uid * 0.37) % 4 == 0:
                dy = -1
        pose = frame
        if siege:                                    # the throwing arm: flung on a shot, winding back while it reloads
            total = max(1, round(sc_unit["cooldown"] * C.SIM_RATE))
            dur = {"catapult": 0.5, "ballista": 0.3, "mangonel": 0.55}.get(spr, 0.8)
            if a is not None and a[0] == "fire" and now - a[1] < dur:
                pose = 1 + min(4, int(5 * (now - a[1]) / dur))
            else:
                pose = 5 - min(5, int((1 - min(1.0, u.cooldown / total)) * 6))
        if spr == "tank_destroyer":                  # the gun slides back on a shot and creeps forward again
            pose = 0
            if a is not None and a[0] == "fire" and now - a[1] < 0.6:
                pose = 1 + min(3, int(4 * (now - a[1]) / 0.6))
        if spr == "siege_tower":                     # the archers inside: how many levels are manned, and a bow drawn
            firing = a is not None and a[0] in ("shoot", "fire") and now - a[1] < 0.35
            pose = 2 * min(3, math.ceil((u.nav["men"] if u.nav else 0) / 2)) + (1 if firing else 0)
        variant = sc_unit.get("style", 0) if spr in sprites.HEROES else u.uid % 3
        sprite = self._sprite(spr, color, u.hero, u.state, flash, sc, f < 0, pose, wounded, variant)
        sw, sh = sprite.get_size()
        shadow_w = max(4, round(10 * sc)) if spr not in sprites.HEROES else max(6, round(sw * 0.75))
        if spr in sprites.SIEGE_KINDS:
            shadow_w = max(8, round(sw * 0.8))
        top = y - sh + 1 + dy
        px = x - sw // 2 + dx
        if u.cover and u.height == 0:                # standing in a trench or a crater: sunk to the chest
            sink = max(2, round(4 * sc))
            low.blit(sprite, (px, top + sink), area=pygame.Rect(0, 0, sw, sh - sink))
            top += sink
        else:
            pygame.draw.ellipse(low, (34, 52, 30), pygame.Rect(x - shadow_w // 2, gy - 1, shadow_w, max(2, round(3 * sc))))
            if u.hero:
                pygame.draw.ellipse(low, GOLD, pygame.Rect(x - shadow_w, gy - 2, shadow_w * 2, max(3, round(3 * sc))), 1)
            low.blit(sprite, (px, top))
        cast = self.cast.get(u.uid)
        if cast is not None and now - cast[0] < 0.8:             # a hero's skill: a pulsing ring and a spark overhead
            k = (now - cast[0]) / 0.8
            rw = shadow_w + round(10 * k * sc)
            pygame.draw.ellipse(low, cast[1], pygame.Rect(x - rw, gy - 2 - round(2 * k), rw * 2, max(3, round(rw * 0.45))), 1)
            _px(low, cast[1], x - 2 + round(4 * math.sin(now * 20)), top - 2 - round(3 * k))
            _px(low, (255, 255, 255), x + 2 - round(4 * math.sin(now * 17)), top - 3 - round(2 * k))
        if swing is not None and 0.1 < swing < 0.85:             # the blade's slash: a bright arc in front of the man
            ang = math.radians(-100 + 150 * swing)
            reach = 7 if u.hero else 5
            col = (255, 236, 170) if u.hero else (236, 236, 244)
            for k in range(3 if u.hero else 2):
                ar = ang - math.radians(14 * k)
                _px(low, col if k == 0 else shade(col, 0.7), x + f * round(3 + reach * math.cos(ar)),
                    top + sh // 3 + round(reach * math.sin(ar)))
        if u.buffs and u.state == "fighting":                    # marks of a skill on him: shield, fury, haste, slow, curse
            t_now = battle.time
            n = 0
            for name, (until, _v) in u.buffs.items():
                if until - t_now > 1.2 and name in self.BUFF_ICONS:
                    _px(low, self.BUFF_ICONS[name], x - 3 + n * 3, top - 4, 2, 2)
                    n += 1
                elif name == "stun" and until > t_now:           # stars circling a dazed head
                    for k in range(3):
                        ang = now * 7 + k * 2.1
                        _px(low, (255, 240, 120), x + round(4 * math.cos(ang)), top - 2 + round(1.5 * math.sin(ang)))
                elif name == "charge" and until > t_now:         # speed lines behind a charging hero
                    for k in range(1, 4):
                        _px(low, (255, 240, 190), x - f * (sw // 2 + 2 * k), top + sh // 2 + k - 2, 3, 1)
        if siege:                                                # two men working each siege engine
            self._crew(low, x, gy, color, pose, min(sw // 2 + 2, 17))
        if u.formation == "testudo":                             # dug in: a sandbag parapet in front, heads down
            for k in range(3):
                pygame.draw.ellipse(low, (176, 158, 112), pygame.Rect(x + f * (3 + 4 * k) - 3, top + sh - 7, 6, 4))
                _px(low, (206, 190, 142), x + f * (3 + 4 * k) - 2, top + sh - 7, 3, 1)
            _px(low, shade(color, 0.9), x - 4, top - 1, 9, 1)     # a helmet band in the side's colour
        if u.formation == "spear":                               # a vehicle charge: dust behind, a tracer streaking ahead
            for k in range(1, 5):
                _px(low, (196, 180, 140), x - f * (6 + 4 * k), top + sh - 2 - k % 2, 3, 1)
            pygame.draw.line(low, (255, 226, 140), (x + f * 6, top + 5), (x + f * 22, top + 3))
            _px(low, (255, 255, 236), x + f * 22, top + 3)
        if u.burn > 0:                                           # flames licking off a man alight
            flick = int(now * 12) % 2
            _px(low, (255, 150, 40), x - 2, top - 1 - flick, 2, 3)
            _px(low, (255, 230, 120), x + 1, top - 2 - flick, 1, 2)
            if self.night > 0.2:
                self.lights.append((x, top, 8, "torch"))
        if u.state == "routing" and u.uid % 3 == 0:            # a routing man carries a wounded comrade on his back
            _px(low, (236, 226, 210), x - 4, top + 3, 7, 2)
            _px(low, (170, 30, 30), x - 1, top + 4, 2, 1)
        if u.hero and spr != "commander":                      # a banner pole over each hero
            pygame.draw.line(low, (90, 70, 40), (x, top), (x, top - 5))
            pygame.draw.rect(low, color, pygame.Rect(x, top - 5, 4, 3))
            pygame.draw.rect(low, GOLD, pygame.Rect(x, top - 5, 4, 3), 1)
        if self.night > 0.2 and u.state != "dead":             # at night every man carries a torch
            if siege:
                self.lights.append((x + 8, top + 2, 14, "torch"))
            else:
                tx, ty = x - f * 5, top + round(sh * 0.4)
                pygame.draw.line(low, (96, 64, 36), (tx, ty), (tx, ty + 3))
                self.lights.append((tx, ty - 1, 8 if sc_unit["speed"] > 0 else 6, "torch"))
        if u.nav is not None and u.nav.get("chute"):              # a paratrooper under his canopy
            sway = round(math.sin(now * 2 + u.uid) * 2)
            pygame.draw.ellipse(low, (236, 236, 226), pygame.Rect(x - 9 + sway, top - 15, 18, 9))
            pygame.draw.ellipse(low, color, pygame.Rect(x - 3 + sway, top - 15, 6, 9))
            pygame.draw.line(low, (200, 200, 190), (x - 9 + sway, top - 11), (x, top + 1))
            pygame.draw.line(low, (200, 200, 190), (x + 8 + sway, top - 11), (x, top + 1))
        rank = rank_of(u.kills) if not u.hero else 0
        if rank and u.state == "fighting":                        # a veteran wears chevrons over his head
            for k in range(rank):
                yy = top - 4 - 2 * k
                pygame.draw.line(low, (240, 200, 70), (x - 2, yy), (x, yy + 1))
                pygame.draw.line(low, (240, 200, 70), (x, yy + 1), (x + 2, yy))
        if u.hp < sc_unit["hp"] * 0.6 and not u.hero:
            frac = max(0.0, u.hp / sc_unit["hp"])
            pygame.draw.rect(low, (40, 10, 10), pygame.Rect(x - 4, top - 3, 8, 1))
            pygame.draw.rect(low, (120, 230, 90), pygame.Rect(x - 4, top - 3, round(8 * frac), 1))

    def _glide(self, battle):
        """The simulation ticks only a couple of times a second, so units would hop from spot to spot. Instead each
        unit is drawn gliding in a straight line from where it was drawn to where the engine now has it, taking one
        tick's real time to get there. Sets every unit's x, y to the drawn spot and returns the true ones so
        _unglide can put them back after the frame is drawn."""
        now = self.now
        tc = battle.tick_count
        if tc != self._tc:
            if self._tc_t is not None and tc > self._tc:
                per = (now - self._tc_t) / (tc - self._tc)       # several ticks in one frame (fast speeds): share the gap
                if 0.01 < per < 1.5:
                    self._tick_dt += (per - self._tick_dt) * 0.25
            self._tc, self._tc_t = tc, now
        dur = max(0.03, min(1.0, self._tick_dt))
        saved = []
        for u in battle.units:
            ax, ay = u.x, u.y
            rec = self._ip.get(u.uid)
            if u.state not in ("fighting", "routing") or u.hidden:
                self._ip.pop(u.uid, None)
                continue
            if rec is None:
                self._ip[u.uid] = rec = [ax, ay, ax, ay, now, dur]
            elif ax != rec[2] or ay != rec[3]:                   # the engine moved it: glide on from where it is drawn
                k = min(1.0, (now - rec[4]) / rec[5])
                cx, cy = rec[0] + (rec[2] - rec[0]) * k, rec[1] + (rec[3] - rec[1]) * k
                if math.hypot(ax - cx, ay - cy) > 90:           # a jump (a respawn, a spawn): do not glide across the map
                    cx, cy = ax, ay
                rec[:] = [cx, cy, ax, ay, now, dur]
            k = min(1.0, (now - rec[4]) / rec[5])
            u.x, u.y = rec[0] + (rec[2] - rec[0]) * k, rec[1] + (rec[3] - rec[1]) * k
            saved.append((u, ax, ay))
        return saved

    @staticmethod
    def _unglide(saved):
        for u, x, y in saved:
            u.x, u.y = x, y

    def _moving(self, u):
        """True while a unit has walked in the last half second, so its legs keep stepping."""
        last = self._last_pos.get(u.uid)
        self._last_pos[u.uid] = (u.x, u.y)
        if last is not None and math.hypot(u.x - last[0], u.y - last[1]) > 0.01:
            self._walk_until[u.uid] = self.now + 0.5
        return self._walk_until.get(u.uid, 0.0) > self.now

    def _crew(self, low, x, gy, color, pose=0, half=11):
        """Two small men working a siege engine, one either side of it. They lean in to wind the arm back and step
        away as it is flung."""
        flung = pose >= 3
        wind = int(self.now * 3) % 2
        for side, dx in ((-1, -half), (1, half)):
            lean = -side * (1 if (not flung and pose < 5) else 0) * wind
            bx = x + dx + lean
            step = 1 if flung else 0
            _px(low, shade(color, 0.7), bx - 1, gy - 6 + step, 3, 5 - step)      # tunic
            _px(low, SKIN, bx - 1, gy - 8 + step, 3, 2)                          # head
            _px(low, INK, bx - 2, gy - 9 + step, 5, 1)
            if not flung and pose < 5:                                           # an arm on the windlass
                _px(low, SKIN, bx - side * 2, gy - 5 - wind, 1, 2)

    def _add_corpse(self, battle, fx):
        """A unit has died: its body lies where it fell, and fades out over time."""
        _, x, y, side, kind, height = fx
        self.corpses.append({"x": x, "y": y, "h": height, "sprite": battle.sc["unit_types"][kind]["sprite"],
                             "color": battle.sc["sides"][side]["color"], "born": self.now,
                             "style": battle.sc["unit_types"][kind].get("style", 0)})
        del self.corpses[:-160]

    def _draw_corpse(self, c):
        life = 1 - (self.now - c["born"]) / C.CORPSE_SECONDS
        if life <= 0:
            return
        x, gy, sc = self._low(c["x"], c["y"])
        _, y, _ = self._low(c["x"], c["y"], c["h"])
        s = self._sprite(c["sprite"], c["color"], False, "dead", 0, sc, variant=c.get("style", 0)).copy()
        s.set_alpha(int(255 * life))
        self.low.blit(s, (x - s.get_width() // 2, y - s.get_height() + 2))

    def _draw_prop(self, p):
        x, gy, sc = self._low(p["x"], p["y"])
        s = self._prop_sprite(p["kind"], p["var"], p["flip"], sc)
        self.low.blit(s, (x - s.get_width() // 2, gy - s.get_height() + 1))
        if p["kind"] in doodads.GLOWING and self.night > 0.2:
            self.lights.append((x, gy - s.get_height() // 2, 22 if p["kind"] == "campfire" else 14, "torch"))

    # ------------------------------------------------------------------ effects: shots, craters, particles
    def _update_effects(self, battle):
        """Moves the visual effects on by real time. Arrows and stones are timed in real seconds, so they fly smoothly
        whatever the battle's speed; the battle's own clock only ticks a few times a second."""
        now = time.perf_counter()
        dt = min(0.1, now - self._last_real)
        self._last_real = now
        self._dt = dt
        self.now = now
        self._update_light(dt)
        self._ship_ids = {u.uid for u in getattr(battle, '_sea', ())}
        self._wx_update(battle)
        self._sea_update(dt)
        self.corpses = [c for c in self.corpses if now - c["born"] < C.CORPSE_SECONDS]
        alive = {u.uid for u in battle.units if u.state in ("fighting", "routing")}
        for rec in battle.shots:
            if rec["uid"] > self._max_shot:               # a shot we have not seen yet
                self._max_shot = rec["uid"]
                if rec["shooter"] in alive or rec.get("src") == "barrage":
                    if rec.get("src") in self.SHIP_SRC:       # shot from a deck: it leaves from above the water
                        rec["h0"] = max(rec["h0"], 16.0 if rec["kind"] == "stone" else 22.0)
                        self._muzzle(rec)
                    self.shot_live[rec["uid"]] = (rec, now, self._flight(rec))
                    self._shot_sound(rec)
                    self._shooter_anim(rec, now)
        for uid, (rec, start, flight) in list(self.shot_live.items()):
            if (rec["shooter"] not in alive and not rec.get("area")) or \
                    (rec["target"] is not None and rec["target"] not in alive):
                del self.shot_live[uid]                  # the shooter or the target is gone: the shot fizzles
                continue
            if now - start >= flight:
                del self.shot_live[uid]
                if rec["crater"] and not (self.shore is not None and rec["y1"] >= self.shore):
                    self.craters.append((rec["x1"], rec["y1"], rec["crater"]))
                    del self.craters[:-C.MAX_CRATERS]
                self._land(rec)
        for fx in battle.drain_fx():
            kind, x, y = fx[0], fx[1], fx[2]
            if kind == "swing":
                self.anim[fx[3]] = ("swing", now, fx[4])
                continue
            if kind == "plunge":
                self.plunges.append({"x": x, "y": y, "h": fx[3], "side": fx[4], "kind": fx[5], "born": now,
                                     "tx": fx[6] if len(fx) > 6 else x, "ty": fx[7] if len(fx) > 7 else y})
                if self.audio:
                    self.audio.sfx("fall", x)
                continue
            if kind == "collapse":                             # a siege tower falls apart
                if self._seen(x):
                    self._burst("dust", x, y, 4)
                    self._burst("debris", x, y, 4)
                    self._burst("smoke", x, y, 2)
                    self.rings.append({"x": x, "y": y, "born": now, "life": 0.6, "size": 40, "col": (200, 184, 150)})
                    self.shake = max(self.shake, 6.0)
                if self.audio:
                    self.audio.sfx("crash", x)
                continue
            if kind in ("sink", "landing"):
                self._ship_fx(battle, fx)
                continue
            if kind == "lightning":
                self._lightning_fx(battle, x, y)
                continue
            if kind in self.EXTRA_FX:
                self._extra_fx(battle, fx)
                continue
            if kind in ("skill", "respawn", "hero_fall"):
                self._hero_fx(battle, fx)
                continue
            self._fx_sound(kind, x)
            if kind == "corpse":
                self._add_corpse(battle, fx)
                continue
            if kind in ("clash", "horn", "gate"):
                continue                                   # heard, not drawn
            if not self._seen(x):                          # effects off screen are not worth drawing
                continue
            if kind == "breach":
                self._burst("dust", x, y, 4)
                self.craters.append((x, y, 18))
                del self.craters[:-C.MAX_CRATERS]
            else:
                self._burst(kind, x, y, 1)
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vh"] -= 260 * dt                       # gravity
            p["h"] = max(0.0, p["h"] + p["vh"] * dt)
            if p["h"] == 0.0:
                p["vh"] = -p["vh"] * 0.3              # a bounce
            p["life"] -= dt
        self.particles = [p for p in self.particles if p["life"] > 0][-C.MAX_PARTICLES:]
        for pl in [p for p in self.plunges if now - p["born"] >= self.FALL_SECONDS]:      # a shot-down flyer hits the ground
            self.plunges.remove(pl)
            self._crash_land(pl)
        self.wrecks = [w for w in self.wrecks if now - w["born"] < C.WRECK_SECONDS]
        self.flames = [f for f in self.flames if f[2] > now]
        self.floaters = [f for f in self.floaters if now - f["born"] < f["life"]]
        self.pillars = [p for p in self.pillars if now - p["born"] < p["life"]]
        if len(self.anim) > 400:                                  # forget the animation of units long gone
            self.anim = {k: v for k, v in self.anim.items() if now - v[1] < 2.0}
        self.shake = max(0.0, self.shake - 22 * dt)
        self.shake_dx = self.rng.uniform(-1, 1) * self.shake
        self.shake_dy = self.rng.uniform(-1, 1) * self.shake
        self.rings = [r for r in self.rings if now - r["born"] < r["life"]]

    def _flight(self, rec):
        """Real seconds a shot stays in the air: its battle flight time at the current speed, but never so short that
        it cannot be seen. At 1x an arrow flies for its full half second."""
        sim = rec.get("flight", 1.0)
        floor = C.STONE_MIN_FLIGHT if rec["kind"] == "stone" else C.ARROW_MIN_FLIGHT
        return max(floor, sim / max(1, self.speed))

    def _shot_sound(self, rec):
        if self.audio is None:
            return
        if rec.get("drop"):
            self.audio.sfx("whistle", rec["x0"])
        elif rec.get("src") == "hero":
            self.audio.sfx("volley" if rec["kind"] == "shower" else "zap", rec["x0"])
        elif rec.get("tracer"):
            self.audio.sfx("volley", rec["x0"])
        elif rec.get("ammo") in ("holy", "hex"):
            self.audio.sfx("zap", rec["x0"])
        elif rec.get("src") == "barrage":
            self.audio.sfx("whistle" if rec["ammo"] == "missile" else "trebuchet", rec["x0"])
        elif rec.get("round") in ("rocket", "rocket_salvo"):
            self.audio.sfx("whistle", rec["x0"])
        elif rec.get("round") in ("ap", "heavy", "naval_heavy"):
            self.audio.sfx("trebuchet", rec["x0"])
        elif rec.get("src") in ("ballista", "mangonel"):
            self.audio.sfx("catapult", rec["x0"])
        elif rec["kind"] == "stone":
            self.audio.sfx("trebuchet" if rec.get("src") == "trebuchet" else "catapult", rec["x0"])
        elif rec["kind"] == "shower":
            self.audio.sfx("volley", rec["x0"])
        elif rec["kind"] == "fire":
            self.audio.sfx("fire_arrow", rec["x0"])
        else:
            self.audio.sfx("bow", rec["x0"])

    def _fx_sound(self, kind, x):
        if self.audio is None:
            return
        name = {"clash": "clash", "blood": "hit", "corpse": "fall", "breach": "crash", "horn": "horn",
                "gate": "gate", "dust": "thud", "mine": "boulder", "blast": "boulder"}.get(kind)
        if name:
            self.audio.sfx(name, x)

    def _land(self, rec):
        """What a shot does where it comes down: a stone throws up a column of dust and a shock ring (burning pitch
        bursts into flame and leaves a fire), an arrow a puff, a shower a patter of puffs."""
        if self._sea_impact(rec):
            return
        x, y = rec["x1"], rec["y1"]
        ammo = rec.get("ammo", rec["kind"])
        if ammo == "smoke":                                      # a smoke shell: a pop and a billow, no damage
            self._burst("smoke", x, y, 3)
            self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.4, "size": 18, "col": (214, 214, 220)})
            if self.audio:
                self.audio.sfx("thud", x)
            return
        if ammo in ("missile", "v2"):
            self._barrage_land(rec, ammo == "v2")
            return
        rd = rec.get("round")
        if rd == "flak":                                         # a burst of black smoke in the sky, nothing on the ground
            if rec.get("h1", 0) > 8:
                self._sparks(x, y, (255, 200, 90), 5, 14, (20, 50), 0.4)
                return
        if rd == "ap" and rec["kind"] == "stone":                # an armour-piercing round: a spark and a short flat puff
            self._sparks(x, y, (255, 226, 150), 8, 20, (30, 80), 0.5)
            self._burst("dust", x, y, 1)
            if self.audio:
                self.audio.sfx("arrow_hit", x)
            return
        if rd == "heavy" and self._seen(x):                      # a howitzer shell: a deep thump
            self.shake = max(self.shake, 5.0)
        if rec.get("tracer"):                                    # tracers: sparks on the ground, nothing in the air
            if rec["h1"] < 8:
                self._sparks(x, y, (255, 210, 120), 4, 12, (20, 60), 0.4)
            return
        if ammo in ("holy", "hex") and rec["kind"] == "arrow":
            col = (255, 232, 150) if ammo == "holy" else (255, 96, 72)
            self._sparks(x, y, col, 8, 22, (30, 90), 0.7)
            if self.audio:
                self.audio.sfx("arrow_hit", x)
            return
        if rec["kind"] == "stone":
            big = rec.get("big", False)
            if ammo == "holy":
                self._sparks(x, y, (255, 232, 150), 18, 30, (60, 150), 0.9)
                self._sparks(x, y, (255, 255, 230), 8, 14, (80, 170), 0.6)
                self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.6, "size": rec.get("r", 50), "col": (255, 236, 160)})
                self.pillars.append({"x": x, "y": y, "born": self.now, "life": 0.7, "col": (255, 236, 160), "h": 70})
                if self.audio:
                    self.audio.sfx("holy", x)
                return
            if ammo == "fire" and big:
                self._burst("fire", x, y, 6)
                self._burst("smoke", x, y, 4)
                self._burst("debris", x, y, 2)
                self.flames += [(x + self.rng.uniform(-14, 14), y + self.rng.uniform(-8, 8), self.now + 7.0) for _ in range(4)]
                self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.7, "size": 52, "col": (255, 150, 60)})
                self.rings.append({"x": x, "y": y, "born": self.now + 0.1, "life": 0.6, "size": 34, "col": (255, 220, 120)})
                if self._seen(x):
                    self.shake = max(self.shake, 7.0)
                if self.audio:
                    self.audio.sfx("boulder", x)
                return
            if ammo == "fire":
                self._burst("fire", x, y, 3)
                self._burst("smoke", x, y, 2)
                self.flames.append((x, y, self.now + 6.0))
                self.flames.append((x + self.rng.uniform(-9, 9), y + self.rng.uniform(-5, 5), self.now + 4.0))
                self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.5, "size": 26, "col": (255, 170, 70)})
                if self.audio:
                    self.audio.sfx("pitch", x)
            else:
                self._burst("dust", x, y, 3)
                self._burst("debris", x, y, 1)
                if rec.get("src") in ("trebuchet",) and self._seen(x):
                    self.shake = max(self.shake, 3.0)
                self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.45, "size": 22, "col": (200, 184, 150)})
                if self.audio:
                    self.audio.sfx("boulder", x)
        elif rec["kind"] == "fire":
            self._burst("fire", x, y, 1)
            if self.audio:
                self.audio.sfx("arrow_hit", x)
        elif rec["kind"] == "shower":
            self._burst("dust", x, y, 1)
            if self.audio:
                self.audio.sfx("rain", x)
        else:
            self._burst("tick", x, y, 1)
            if self.audio:
                self.audio.sfx("arrow_hit", x)

    def _shooter_anim(self, rec, now):
        """The archer draws and looses, the siege engine throws and kicks up dust."""
        uid = rec["shooter"]
        if rec.get("src") == "barrage" and rec["shooter"] >= 0:         # a launcher unit loosing its salvo
            self.anim[uid] = ("fire", now, 0)
        elif rec.get("src") in ("catapult", "trebuchet", "ballista", "mangonel", "tank_destroyer", "mlrs", "v2_launcher"):
            self.anim[uid] = ("fire", now, 0)
            if rec["src"] != "ballista":
                self._burst("tick", rec["x0"], rec["y0"], 2)
        elif rec.get("src") != "hero":
            self.anim[uid] = ("shoot", now, 0)

    def _sparks(self, x, y, col, n, spread, lift, life, inward=False):
        """A burst of n bright specks of one colour."""
        for _ in range(n):
            ang = self.rng.uniform(0, 2 * math.pi)
            speed = self.rng.uniform(2, spread)
            sx, sy = (x + math.cos(ang) * spread, y + math.sin(ang) * spread * 0.5) if inward else (x, y)
            vx, vy = math.cos(ang) * speed * (-1 if inward else 1), math.sin(ang) * speed * 0.5 * (-1 if inward else 1)
            self.particles.append({"x": sx, "y": sy, "h": self.rng.uniform(2, 14), "vx": vx, "vy": vy,
                                   "vh": self.rng.uniform(*lift), "life": life * self.rng.uniform(0.6, 1.2), "col": col})

    def _hero_name(self, battle, uid):
        for h in battle.heroes.values():
            if h["unit"].uid == uid:
                return h["name"]
        return ""

    def _hero_fx(self, battle, fx):
        """A hero's skill, return or fall: a ring and sparks in the skill's colour, a floating name and a sound."""
        now = self.now
        kind, x, y, uid = fx[0], fx[1], fx[2], fx[3]
        seen = self._seen(x)
        if kind == "skill":
            sk = heroes.SKILLS[fx[4]]
            col, r, k = sk["color"], fx[5], sk["kind"]
            self.cast[uid] = (now, col)
            if seen:
                self.floaters.append({"x": x, "y": y, "h": 52, "text": sk["name"] + "!", "col": col, "born": now, "life": 1.8})
                if k in ("buff_allies", "debuff_foes", "aoe_hit", "heal"):
                    size = max(24, r)
                    self.rings.append({"x": x, "y": y, "born": now, "life": 0.7, "size": size, "col": col})
                    self.rings.append({"x": x, "y": y, "born": now + 0.12, "life": 0.6, "size": size * 0.7, "col": col})
                if k == "buff_allies":
                    self._sparks(x, y, col, 22, r * 0.9, (20, 80), 1.0)
                elif k == "debuff_foes":
                    self._sparks(x, y, col, 22, r * 0.9, (10, 50), 0.9, inward=True)
                elif k == "heal":
                    self._sparks(x, y, col, 26, r * 0.8, (50, 120), 1.2)
                elif k == "aoe_hit":
                    self._burst("dust", x, y, 3)
                    self._burst("debris", x, y, 1)
                    self.shake = max(self.shake, 6.0 if r > 40 else 3.0)
                elif k == "charge":
                    self._burst("dust", x, y, 2)
                    self.rings.append({"x": x, "y": y, "born": now, "life": 0.5, "size": 26, "col": col})
                else:
                    self._sparks(x, y, col, 10, 14, (30, 80), 0.7)
            if self.audio:
                name = {"buff_allies": "rally", "debuff_foes": "curse", "aoe_hit": "slam", "heal": "heal",
                        "charge": "charge", "pierce": "zap"}.get(k)
                if name:
                    self.audio.sfx(name, x)
        elif kind == "respawn":
            self.pillars.append({"x": x, "y": y, "born": now, "life": 1.6, "col": (255, 236, 170), "h": 120})
            self.rings.append({"x": x, "y": y, "born": now, "life": 0.9, "size": 40, "col": (255, 236, 170)})
            self._sparks(x, y, (255, 236, 170), 24, 26, (50, 150), 1.4)
            self.floaters.append({"x": x, "y": y, "h": 60, "text": self._hero_name(battle, uid) + " returns!",
                                  "col": (255, 236, 170), "born": now, "life": 2.4})
            if self.audio:
                self.audio.sfx("respawn", x)
        elif kind == "hero_fall":
            self.rings.append({"x": x, "y": y, "born": now, "life": 0.8, "size": 36, "col": (200, 70, 60)})
            self._sparks(x, y, (230, 200, 120), 16, 24, (30, 110), 1.0)
            self.floaters.append({"x": x, "y": y, "h": 40, "text": self._hero_name(battle, uid) + " falls",
                                  "col": (240, 120, 100), "born": now, "life": 2.4})
            if self.audio:
                self.audio.sfx("gong", x)

    def _update_camera(self, battle):
        """Pan with the arrow keys (the speed eases in and out); otherwise glide toward the fighting. The point it
        chases is itself smoothed, and the camera has momentum (a critically damped spring with a top speed), so it
        never snaps when the action jumps from one place to another."""
        dt = max(1e-3, self._dt)
        if self.pan_dir or abs(self._pan_v) > 8:
            self._pan_v += (self.pan_dir * C.PAN_SPEED - self._pan_v) * min(1.0, dt * 6.0)
            self.cam_x += self._pan_v * dt
            self._cam_v = self._pan_v                      # hand the speed on, so following resumes without a jolt
            if self.pan_dir:
                self._manual_until = self.now + C.CAM_RESUME_SECONDS
        else:
            if self.now - self._cam_scan > 0.5:
                self._cam_scan = self.now
                self._cam_goal = self._action_x(battle)
            self._cam_aim += (self._cam_goal - self._cam_aim) * (1 - math.exp(-dt / C.CAM_AIM_SMOOTH))
            if self.cinematic and self.now >= self._manual_until:
                goal = self._cam_aim - C.SCREEN_W / 2 + math.sin(self.now * 0.13) * 70
                self.cam_x, self._cam_v = self._smooth_damp(self.cam_x, goal, self._cam_v, C.CAM_SMOOTH_TIME,
                                                            C.CAM_MAX_SPEED, dt)
            else:
                self._cam_v *= math.exp(-dt * 4)           # let go of the keys: coast to a stop
                self.cam_x += self._cam_v * dt
        if self.cam_x < 0 or self.cam_x > self.W - C.SCREEN_W:
            self.cam_x = max(0.0, min(self.W - C.SCREEN_W, self.cam_x))
            self._cam_v = self._pan_v = 0.0

    @staticmethod
    def _smooth_damp(cur, goal, vel, smooth, max_speed, dt):
        """A critically damped spring toward the goal: eases out of the start and into the stop, no overshoot."""
        omega = 2.0 / smooth
        x = omega * dt
        k = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x ** 3)
        limit = max_speed * smooth
        change = max(-limit, min(limit, cur - goal))
        target = cur - change
        temp = (vel + omega * change) * dt
        vel = (vel - omega * temp) * k
        out = target + (change + temp) * k
        if (goal - cur > 0) == (out > goal):
            out, vel = goal, 0.0
        return out, vel

    def _action_x(self, battle):
        """Where the fighting is: the middle of the men who have a foe in sight, else of all the marching men."""
        fighters = sorted(u.x for u in battle.units if u.state == "fighting" and u.target is not None
                          and u.stats["speed"] > 0)
        if len(fighters) >= 4:
            return fighters[len(fighters) // 2]
        movers = [u.x for u in battle.units if u.state == "fighting" and u.stats["speed"] > 0]
        return sum(movers) / len(movers) if movers else self.W / 2

    def _burst(self, kind, x, y, times):
        """A puff of particles where something landed or died: dust or debris from a stone, blood from a hit, fire and
        smoke from burning pitch."""
        for _ in range(times):
            if kind == "blood":
                n, cols, lift, life, spread = 4, [(150, 24, 24)], (50, 110), 0.5, 22
            elif kind == "fire":
                n, cols, lift, life, spread = 9, [(255, 120, 30), (255, 190, 60), (255, 236, 150)], (50, 130), 0.7, 30
            elif kind == "smoke":
                n, cols, lift, life, spread = 6, [(70, 66, 62), (96, 90, 84)], (20, 60), 1.4, 12
            elif kind == "debris":
                n, cols, lift, life, spread = 8, [(92, 80, 64), (120, 106, 86), (60, 52, 42)], (90, 190), 0.9, 40
            elif kind == "splash":
                n, cols, lift, life, spread = 8, [(226, 242, 250), (150, 206, 222), (255, 255, 255)], (60, 140), 0.6, 18
            elif kind == "tick":
                n, cols, lift, life, spread = 2, [(150, 130, 100)], (15, 40), 0.35, 8
            else:
                n, cols, lift, life, spread = 10, [(168, 152, 124), (190, 174, 140), (138, 122, 98)], (30, 100), 1.0, 26
            for _ in range(n):
                ang = self.rng.uniform(0, 2 * math.pi)
                speed = self.rng.uniform(4, spread)
                self.particles.append({"x": x, "y": y, "h": 2.0, "vx": math.cos(ang) * speed,
                                       "vy": math.sin(ang) * speed * 0.5, "vh": self.rng.uniform(*lift),
                                       "life": life * self.rng.uniform(0.6, 1.2), "col": self.rng.choice(cols)})

    def _draw_craters(self, low, battle):
        """Old shell holes (permanent: dark pits with a raised lip) and the fresher craters of this battle's stones."""
        for x, y, r in battle.pits:
            if not self._seen(x - r, x + r) or (self.shore is not None and y >= self.shore - 6):
                continue
            sx, sy, sc = self.project(x, y, 0)
            w = max(4, round(r * sc * 2 / C.PIXEL))
            h = max(2, round(r * sc * 0.95 / C.PIXEL))
            cx, cy = round(sx / C.PIXEL), round(sy / C.PIXEL)
            pygame.draw.ellipse(low, (122, 100, 70), pygame.Rect(cx - w // 2 - 1, cy - h // 2 - 1, w + 2, h + 2))   # the lip
            pygame.draw.ellipse(low, (52, 42, 30), pygame.Rect(cx - w // 2, cy - h // 2, w, h))
            pygame.draw.ellipse(low, (34, 28, 20), pygame.Rect(cx - w // 3, cy - h // 6, max(1, 2 * w // 3), max(1, h // 2)))
        for x, y, r in self.craters:
            if not self._seen(x - r, x + r):
                continue
            sx, sy, sc = self.project(x, y, 0)
            w = max(2, round(r * sc * 2 / C.PIXEL))
            h = max(1, round(r * sc * 0.9 / C.PIXEL))
            cx, cy = round(sx / C.PIXEL), round(sy / C.PIXEL)
            pygame.draw.ellipse(low, (50, 66, 36), pygame.Rect(cx - w // 2, cy - h // 2, w, h))
            pygame.draw.ellipse(low, (34, 44, 24), pygame.Rect(cx - w // 4, cy - h // 4, max(1, w // 2), max(1, h // 2)))

    def _arc(self, rec, ox0, oy0, ox1, oy1, p, angle):
        """Screen position of a shot a share p of the way along its flight: it moves in a straight line over the ground
        and its height follows a parabola: launched at `angle`, it peaks at d * tan(angle) / 4 above the line from the
        shooter's height to the target's height."""
        d = math.hypot(ox1 - ox0, oy1 - oy0)
        peak = min(d * math.tan(math.radians(angle)) / 4, rec.get("maxpeak", 1e9))
        x = ox0 + (ox1 - ox0) * p
        y = oy0 + (oy1 - oy0) * p
        h = rec["h0"] + (rec["h1"] - rec["h0"]) * p + 4 * peak * p * (1 - p)
        return self._low(x, y, h), self._low(x, y, 0)

    def _draw_shots(self, low):
        """Arrows and stones in the air, each on its own arc from the shooter to where it comes down."""
        for rec, start, flight in self.shot_live.values():
            if not self._seen(min(rec["x0"], rec["x1"]), max(rec["x0"], rec["x1"])):
                continue
            if rec.get("src") == "barrage":                      # the Allied missile salvo and the Axis V-2
                self._draw_barrage(low, rec, start, flight)
                continue
            if rec["kind"] == "shower":
                self._draw_shower(low, rec, start, flight)
                continue
            if rec.get("drop"):                                  # a bomb: it falls, picking up speed
                p = min(1.0, (self.now - start) / flight)
                x = rec["x0"] + (rec["x1"] - rec["x0"]) * p
                y = rec["y0"] + (rec["y1"] - rec["y0"]) * p
                hh = rec["h0"] * (1 - p * p)
                bx, by, _ = self._low(x, y, hh)
                gx, gy, _ = self._low(x, y, 0)
                pygame.draw.ellipse(low, (34, 52, 30), pygame.Rect(gx - 1, gy, 3, 1))
                burning = rec.get("ammo") == "fire"
                big = rec.get("src") == "heavy_bomber"                                       # a heavy bomber's bomb is larger
                pygame.draw.rect(low, (40, 30, 26) if burning else (64, 68, 74), pygame.Rect(bx - 1 - big, by - 2 - big, 3 + 2 * big, 4 + 2 * big))   # a bomb ...
                _px(low, (206, 172, 70), bx - 2 - big, by - 3 - big)                                                  # ... with fins
                _px(low, (206, 172, 70), bx + 2 + big, by - 3 - big)
                if burning:
                    _px(low, (255, 170, 50), bx, by - 2)
                    _px(low, (255, 226, 120), bx, by - 3 - int(self.now * 12) % 2)
                    if self.night > 0.15:
                        self.lights.append((bx, by, 9, "torch"))
                continue
            if rec.get("torpedo"):                               # a torpedo running along the water
                self._draw_torpedo(low, rec, start, flight)
                continue
            if rec.get("tracer"):                                # an aircraft's machine-gun burst
                self._draw_tracers(low, rec, start, flight)
                continue
            if rec.get("round") in self.ROUND_ART and not (rec.get("src") in self.SHIP_SRC and rec["round"] != "rocket_salvo"):
                self._draw_round(low, rec, start, flight)         # this unit's own kind of round
                continue
            arrow = rec["kind"] in ("arrow", "fire")
            orb = arrow and rec.get("ammo") in ("holy", "hex")
            p = min(1.0, (self.now - start) / flight)
            q = max(0.0, p - 0.1)
            args = (rec["x0"], rec["y0"], rec["x1"], rec["y1"])
            ((hx, hy, _), (gx, gy, _)) = self._arc(rec, *args, p, rec["angle"])
            ((tx, ty, _), _g) = self._arc(rec, *args, q, rec["angle"])
            if rec.get("src") in self.SHIP_SRC:
                self._draw_ship_shot(low, rec, p, args, arrow, hx, hy, tx, ty, gx, gy)
                continue
            pygame.draw.ellipse(low, (34, 52, 30), pygame.Rect(gx - 1, gy, 3, 1))     # its shadow on the ground
            if orb:                                             # a caster's bolt: a glowing orb with a short tail
                col = (255, 232, 150) if rec["ammo"] == "holy" else (255, 96, 72)
                pygame.draw.circle(low, shade(col, 0.6), (hx, hy), 2)
                _px(low, (255, 255, 240), hx, hy)
                _px(low, col, tx, ty)
                if self.night > 0.15:
                    self.lights.append((hx, hy, 8, "torch"))
            elif arrow:
                self._draw_arrow(low, tx, ty, hx, hy, rec["kind"] == "fire", rec.get("bolt", False) or rec.get("src") == "siege_tower")   # a tower's volley is drawn bold: it must read from the field
            elif rec.get("ammo") == "holy":                      # a ball of holy fire
                pygame.draw.circle(low, (255, 214, 110), (hx, hy), 2)
                _px(low, (255, 255, 235), hx, hy)
                if self.night > 0.15:
                    self.lights.append((hx, hy, 11, "torch"))
            else:
                burning = rec.get("ammo") == "fire"
                pygame.draw.line(low, (60, 62, 70) if not burning else (70, 44, 30), (tx, ty), (hx, hy), 2)     # a shell
                _px(low, (196, 198, 206) if not burning else (255, 200, 90), hx, hy)                           # its nose
                _px(low, (206, 172, 70), tx, ty)                                                              # the brass base
                if burning:                                     # a ball of burning pitch trails flame and smoke
                    for k in range(1, 4):
                        a = max(0.0, p - 0.05 * k)
                        ((ax, ay, _), _g) = self._arc(rec, *args, a, rec["angle"])
                        _px(low, (255, 150 - 30 * k, 40), ax, ay)
                    if self.night > 0.15:
                        self.lights.append((hx, hy, 11, "torch"))
                elif p > 0.08:                                  # a faint streak shows the stone's path
                    ((ax, ay, _), _g) = self._arc(rec, *args, p - 0.07, rec["angle"])
                    _px(low, (120, 120, 126), ax, ay)

    def _draw_tracers(self, low, rec, start, flight):
        """A burst of tracers from a fighter or a strafing run: bright, long streaks in a staggered line, flying straight
        from the aircraft to the target, with a flash at the guns."""
        t = (self.now - start) / flight
        args = (rec["x0"], rec["y0"], rec["x1"], rec["y1"])
        for i in range(rec["tracer"]):
            p = (t - 0.11 * i) / 0.42
            if not 0.0 < p < 1.0:
                continue
            jy = (rec["uid"] * 5 + i * 11) % 5 - 2
            ((hx, hy, _), _g) = self._arc(rec, *args, p, 0.0)
            ((tx, ty, _), _g) = self._arc(rec, *args, max(0.0, p - 0.2), 0.0)
            self._draw_arrow(low, tx, ty + jy, hx, hy + jy, False, True)
            if i == 0 and p < 0.25:                              # the muzzle flash
                _px(low, (255, 240, 180), tx - 1, ty + jy - 1, 3, 3)
            if self.night > 0.2:
                self.lights.append((hx, hy + jy, 7, "torch"))

    SHIP_SRC = ("longship", "galley", "catapult_ship", "destroyer", "dreadnought", "carrier")      # shots drawn large: from a deck or a tower top

    def _muzzle(self, rec):
        """The puff where a ship looses a shot: smoke and a flash for a stone, a few sparks for a volley of arrows."""
        if rec["kind"] == "stone":
            self._burst("smoke", rec["x0"], rec["y0"], 1)
            self._burst("tick", rec["x0"], rec["y0"], 2)
            self.rings.append({"x": rec["x0"], "y": rec["y0"], "born": self.now, "life": 0.3, "size": 14, "col": (255, 214, 140)})
        else:
            self._burst("tick", rec["x0"], rec["y0"], 1)

    def _draw_ship_shot(self, low, rec, p, args, arrow, hx, hy, tx, ty, gx, gy):
        """A shot from a ship, drawn larger than a soldier's so it reads across the water: a galley looses three bright
        arrows with long shafts, a catapult ship a heavy stone with a trail of smoke. Its shadow is on the water."""
        sea = rec["y1"] >= self.shore if self.shore is not None else False
        _px(low, (14, 44, 84) if sea else (34, 52, 30), gx - 1, gy, 3, 1)
        if arrow:
            for k, (dp, dy) in enumerate(((0.0, 0), (-0.05, 3), (-0.1, -3))):
                q = min(1.0, max(0.0, p + dp))
                ((ax, ay, _), _g) = self._arc(rec, rec["x0"], rec["y0"] + dy, rec["x1"], rec["y1"] + dy, q, rec["angle"])
                ((bx, by, _), _g) = self._arc(rec, rec["x0"], rec["y0"] + dy, rec["x1"], rec["y1"] + dy, max(0.0, q - 0.14), rec["angle"])
                pygame.draw.line(low, (70, 40, 20), (bx, by + 1), (ax, ay + 1))
                pygame.draw.line(low, (255, 222, 120), (bx, by), (ax, ay))
                _px(low, (255, 255, 236), ax, ay, 2, 1)
                _px(low, (255, 120, 50), bx, by)
            return
        burning = rec.get("ammo") == "fire"
        for k in range(1, 7):                                       # a trail of smoke along the stone's path
            a = max(0.0, p - 0.035 * k)
            ((ax, ay, _), _g) = self._arc(rec, *args, a, rec["angle"])
            c = (255, 190 - 20 * k, 60) if k < 4 else (190 - 14 * k, 188 - 14 * k, 190 - 14 * k)    # a glowing tracer trail, then smoke
            _px(low, c, ax, ay, 2 if k < 4 else 1, 2 if k < 4 else 1)
        ((qx, qy, _), _g) = self._arc(rec, *args, max(0.0, p - 0.06), rec["angle"])
        pygame.draw.line(low, (24, 22, 24), (qx, qy), (hx, hy), 5)                                  # a heavy naval shell
        pygame.draw.line(low, (96, 92, 96) if not burning else (70, 44, 30), (qx, qy), (hx, hy), 3)
        _px(low, (210, 212, 220) if not burning else (255, 210, 100), hx, hy, 2, 2)
        _px(low, (210, 176, 70), qx, qy, 2, 2)
        if self.night > 0.15 and burning:
            self.lights.append((hx, hy, 11, "torch"))

    def _draw_arrow(self, low, tx, ty, hx, hy, burning, heavy=False):
        """A tracer round: a short bright streak with a hot head and a fading tail. An incendiary one burns red-orange;
        a hero's or a vehicle gun's round is drawn long and bold so it reads from across the field."""
        if heavy:
            pygame.draw.line(low, (255, 232, 150), (2 * tx - hx, 2 * ty - hy), (hx, hy))
        body = (255, 140, 56) if burning else ((255, 226, 140) if heavy else (255, 206, 100))
        pygame.draw.line(low, body, (tx, ty), (hx, hy))
        _px(low, (255, 236, 160) if burning else (255, 255, 238), hx, hy)                  # the hot head
        _px(low, (255, 110, 40) if burning else (206, 120, 50), tx, ty)                    # the fading tail
        if burning and self.night > 0.2:
            self.lights.append((hx, hy, 8, "torch"))

    SHOWER_ARROWS = 7

    def _draw_shower(self, low, rec, start, flight):
        """An arrow shower: a flight of arrows loosed together. Each leaves the archer's bow, climbs on its own arc and
        comes down on its own spot in the target area, a little after the one before."""
        t = (self.now - start) / flight
        args_ang = max(rec["angle"], 62)                  # a volley is lobbed high to drop on the crowd
        n = self.SHOWER_ARROWS
        for i in range(n):
            p = (t - 0.03 * i) / 0.78
            if not 0.0 < p < 1.0:
                continue
            off = (rec["uid"] * 7 + i * 13) % 31 - 15
            depth = (i * 11 + rec["uid"]) % 13 - 6
            ox0 = rec["x0"] + (i % 3 - 1) * 2
            args = (ox0, rec["y0"], rec["x1"] + off, rec["y1"] + depth)
            ((hx, hy, _), (gx, gy, _)) = self._arc(rec, *args, p, args_ang)
            ((tx, ty, _), _g) = self._arc(rec, *args, max(0.0, p - 0.1), args_ang)
            _px(low, (34, 52, 30), gx, gy)
            rd = rec.get("round")
            if rd == "flame":                                         # a spray of burning fuel
                _px(low, (255, 150, 40), hx, hy, 2, 2)
                _px(low, (255, 226, 120), tx, ty)
            elif rd in ("bullet", "hmg"):                             # a burst of bullets
                self._draw_arrow(low, tx, ty, hx, hy, False, rd == "hmg")
            else:
                _px(low, (64, 68, 74), hx, hy, 2, 2)                  # a mortar bomb dropping
                _px(low, (255, 214, 110), tx, ty)

    def _draw_flames(self, low):
        """Fires left by burning pitch, and the shock rings of stones coming down."""
        for x, y, until in self.flames:
            if not self._seen(x):
                continue
            sx, sy, sc = self._low(x, y, 0)
            life = min(1.0, (until - self.now) / 1.5)
            flick = int(self.now * 10 + x) % 3
            hgt = max(1, round((3 + flick) * sc * life))
            pygame.draw.line(low, (255, 120, 30), (sx, sy), (sx, sy - hgt))
            pygame.draw.line(low, (255, 200, 80), (sx - 1, sy), (sx - 1, sy - max(1, hgt - 2)))
            pygame.draw.line(low, (255, 150, 40), (sx + 1, sy), (sx + 1, sy - max(1, hgt - 1)))
            _px(low, (255, 240, 170), sx, sy - hgt)
            if self.night > 0.15:
                self.lights.append((sx, sy - 2, 11, "torch"))
        for r in self.rings:
            if not self._seen(r["x"] - r["size"], r["x"] + r["size"]):
                continue
            p = (self.now - r["born"]) / r["life"]
            if p < 0:
                continue                                        # a ring set to start a moment from now
            sx, sy, sc = self._low(r["x"], r["y"], 0)
            w = max(2, round(r["size"] * sc * p))
            h = max(1, round(w * 0.45))
            col = tuple(int(c * (1 - 0.6 * p)) for c in r["col"])
            pygame.draw.ellipse(low, col, pygame.Rect(sx - w, sy - h, 2 * w, 2 * h), 1)

    def _draw_auras(self, low, battle):
        """A faint ring on the ground round each hero whose passive skill reaches friends: its radius is the aura's."""
        pulse = 0.65 + 0.35 * math.sin(self.now * 2.2)
        for h in battle.heroes.values():
            u = h["unit"]
            if h["status"] != "alive" or u.state != "fighting" or not self._seen(u.x - 160, u.x + 160):
                continue
            reach = max((heroes.SKILLS[sid].get("r", 0) for sid in u.stats.get("skills", ())
                         if heroes.SKILLS[sid]["passive"]), default=0)
            if reach < 30:
                continue
            cx, cy, sc = self._low(u.x, u.y)
            w = max(6, round(reach * sc / C.PIXEL))
            hh = max(3, round(w * 0.43))
            col = shade(battle.sc["sides"][u.side]["color"], 0.55 + 0.5 * pulse)
            pygame.draw.ellipse(low, col, pygame.Rect(cx - w, cy - hh, 2 * w, 2 * hh), 1)

    def _draw_pillars(self, low):
        """Columns of light: a hero returning to the field, holy fire coming down."""
        for p in self.pillars:
            if not self._seen(p["x"]):
                continue
            k = (self.now - p["born"]) / p["life"]
            x, y, sc = self._low(p["x"], p["y"])
            hgt = round(p["h"] * sc / C.PIXEL * min(1.0, k * 4))
            w = max(1, round((1 - k) * 4 * sc))
            col = tuple(int(c * (1 - 0.7 * k)) for c in p["col"])
            for i in range(w):
                pygame.draw.line(low, col, (x + i - w // 2, y), (x + i - w // 2, y - hgt))
            if self.night > 0.15:
                self.lights.append((x, y - hgt // 2, 14, "torch"))

    def _draw_floaters(self, screen):
        """Floating text above heroes: skill names, falls and returns. Drawn on the full-size screen so it is crisp."""
        for f in self.floaters:
            k = (self.now - f["born"]) / f["life"]
            x, y, sc = self.project(f["x"], f["y"])
            if not -80 < x < C.SCREEN_W + 80:
                continue
            y -= (f["h"] + 34 * k) * sc
            text = self.font.render(f["text"], True, f["col"])
            shadow = self.font.render(f["text"], True, (0, 0, 0))
            alpha = int(255 * min(1.0, (1 - k) * 2.2))
            text.set_alpha(alpha)
            shadow.set_alpha(alpha)
            pos = (round(x - text.get_width() / 2), round(y))
            screen.blit(shadow, (pos[0] + 1, pos[1] + 1))
            screen.blit(text, pos)

    def _draw_hero_tags(self, screen, battle):
        """A name, a health bar and two lamps (one per active skill: lit when ready) over each living hero; the time
        until a fallen hero returns where he fell."""
        for h in battle.heroes.values():
            u = h["unit"]
            col = battle.sc["sides"][h["side"]]["color"]
            if h["status"] == "fallen":
                if h.get("respawn_at") is None or not self._seen(u.x):
                    continue
                left = max(0, math.ceil(h["respawn_at"] - battle.time))
                x, y, sc = self.project(u.x, u.y)
                text = self.small.render(f"{h['name']}  {left}s", True, (214, 204, 184))
                text.set_alpha(150)
                screen.blit(text, (round(x - text.get_width() / 2), round(y - 20 * sc)))
                continue
            if u.state != "fighting" or u.hidden or not self._seen(u.x):
                continue
            x, y, sc = self.project(u.x, u.y, u.height)
            top = y - 40 * sc - 4
            text = self.small.render(h["name"], True, GOLD)
            shadow = self.small.render(h["name"], True, INK)
            pos = (round(x - text.get_width() / 2), round(top - 16))
            screen.blit(shadow, (pos[0] + 1, pos[1] + 1))
            screen.blit(text, pos)
            frac = max(0.0, u.hp / u.stats["hp"])
            bx, by = round(x - 16), round(top - 2)
            pygame.draw.rect(screen, (30, 10, 10), (bx - 1, by - 1, 34, 6))
            pygame.draw.rect(screen, (214, 70, 60) if frac < 0.35 else (110, 220, 90), (bx, by, round(32 * frac), 4))
            lamp = 0
            for sid in u.stats.get("skills", ()):
                sk = heroes.SKILLS[sid]
                if sk["passive"]:
                    continue
                ready = battle.time >= (u.cds or {}).get(sid, 0.0)
                pygame.draw.rect(screen, sk["color"] if ready else (60, 56, 52), (bx + 12 + lamp * 6, by + 6, 4, 4))
                lamp += 1

    def _draw_particles(self, low):
        for p in self.particles:
            sx, sy, _ = self.project(p["x"], p["y"], p["h"])
            _px(low, p["col"], round(sx / C.PIXEL), round(sy / C.PIXEL))

    def _draw_mid_trees(self, low):
        dx = -self.cam_x * (0.45 if self.parallax else 0.0)
        for x, r, y in self.mid_trees:
            sx = (x + dx) / C.PIXEL
            if -8 <= sx <= C.LOW_W + 8:
                pygame.draw.circle(low, (38, 64, 42), (round(sx), round(y / C.PIXEL)), max(1, round(r / C.PIXEL)))

    def _draw_foreground(self, low):
        """The nearest layer: grass tufts along the bottom edge, drawn over everything else."""
        if self.shore is not None:
            return
        dx = -self.cam_x * (1.5 if self.parallax else 1.0)
        for x, y, k in self.tufts:
            bx = round((x + dx) / C.PIXEL)
            if not -4 <= bx <= C.LOW_W + 4:
                continue
            by = round(y / C.PIXEL)
            for lean in (-2, 0, 2):
                pygame.draw.line(low, (48, 92, 44), (bx, by), (bx + lean, by - round(4 * k)))

    # ------------------------------------------------------------------ world
    def _draw_world(self, battle):
        """Draws the battle in layers, back to front: sky and hills, the trees, the ground and road, the craters,
        trenches and water on the ground, then the doodads, walls, towers, keeps and men in order of depth, the arrows
        and stones in the air, the dust and blood, and the grass in front of everything. Last, the colour of the hour
        is laid over the scene and the torches and windows are lit."""
        low = self.low
        self.lights = []
        self._draw_background(low)
        self._draw_mid_trees(low)
        self._draw_shore(low)
        self._draw_road(low)
        self._draw_flat_terrain(low, battle)
        self._draw_craters(low, battle)
        self._draw_auras(low, battle)

        # everything that stands up, in depth order: a block is drawn at its front edge, a unit at its feet.
        # A block at the back is drawn before the units in front of it, and a wall hides what stands behind it.
        x0, x1 = self.cam_x - 90, self.cam_x + C.SCREEN_W + 90
        drawables = []
        for t in battle.terrain:
            x, y, w, h = t["rect"]
            if x + w < x0 or x > x1:
                continue
            if t["hidden"]:
                if t.get("style") == "gate":                  # an open gate: its archway and the passage through it
                    drawables.append((y + h + 0.5, lambda t=t: self._gate_open(low, t)))
                continue
            if t["solid"] and t.get("style") not in ("moat", "river"):
                drawables.append((y + h + 0.5, lambda t=t: self._block(low, t, battle)))
            elif t.get("style") == "keep":
                drawables.append((y - 0.5, lambda t=t: self._keep(low, t, battle)))
        fronts = {t["id"]: t["rect"][1] + t["rect"][3] for t in battle.terrain}
        for u in battle.units:
            if not x0 <= u.x <= x1 or u.hidden:        # men lying in ambush are not drawn: you cannot see them
                continue
            if u.stats.get("flying"):
                key = 1e5 + u.y                       # flyers are drawn over everything on the ground
            elif u.stats["speed"] == 0:
                # an archer on a wall or tower is drawn just after the block it stands on: in front of the block's
                # top, and behind whatever stands in front of that wall
                key = fronts.get(u.perch, u.y) + 0.6
            else:
                key = u.y
            drawables.append((key, lambda u=u: self._draw_unit(battle, u)))
        for sk in self.sinks:
            if x0 <= sk['x'] <= x1:
                drawables.append((sk['y'], lambda sk=sk: self._draw_sink(low, sk)))
        for c in self.corpses:                          # the fallen lie under the living, on the ground
            if x0 <= c["x"] <= x1:
                drawables.append((c["y"] - 0.5, lambda c=c: self._draw_corpse(c)))
        for w in self.wrecks:                           # crashed aircraft
            if x0 <= w["x"] <= x1:
                drawables.append((w["y"] - 0.4, lambda w=w: self._draw_wreck(w)))
        i0, i1 = bisect.bisect_left(self.prop_x, x0), bisect.bisect_right(self.prop_x, x1)
        for p in self.props[i0:i1]:
            drawables.append((p["y"], lambda p=p: self._draw_prop(p)))
        drawables.sort(key=lambda d: d[0])
        for _, draw in drawables:
            draw()
        self._draw_plunges(low)
        self._draw_shots(low)
        self._draw_crates(low, battle)
        self._draw_smokes(low, battle)
        self._draw_searchlights(low, battle)
        self._draw_pillars(low)
        self._draw_flames(low)
        self._draw_particles(low)
        self._draw_foreground(low)
        self._draw_weather_fog(low)
        self._grade(low)
        self._draw_lights(low)
        self._draw_night_sky(low)
        self._draw_sea_foreground(low)
        self._draw_weather_front(low)

    # ------------------------------------------------------------------ frame
    def draw(self, screen, battle, speed_label, paused):
        self._update_effects(battle)
        self._update_camera(battle)
        alive = {u.uid for u in battle.units}          # forget the walk history of units that are gone
        for d in (self._last_pos, self._walk_until, self._ip):
            for uid in [k for k in d if k not in alive]:
                del d[uid]
        saved = self._glide(battle)
        try:
            self._compose(screen, battle, speed_label, paused)
        finally:
            self._unglide(saved)

    def _compose(self, screen, battle, speed_label, paused):
        """One frame, drawn with every unit at its gliding spot (see _glide)."""
        self._draw_world(battle)
        pygame.transform.scale(self.low, (C.SCREEN_W, C.SCREEN_H), screen)
        screen.blit(self.vignette, (0, 0))
        if self.letterbox:                              # cinematic bars
            bar = int(C.SCREEN_H * C.LETTERBOX)
            pygame.draw.rect(screen, (0, 0, 0), (0, 0, C.SCREEN_W, bar))
            pygame.draw.rect(screen, (0, 0, 0), (0, C.SCREEN_H - bar, C.SCREEN_W, bar))
        self._draw_hero_tags(screen, battle)
        self._draw_floaters(screen)
        if self.show_hud:
            self._draw_hud(screen, battle, speed_label, paused)
        text, until = self.toast
        if text and self.now < until:
            surf = self.mid.render(text, True, (240, 232, 210))
            shadow = self.mid.render(text, True, (0, 0, 0))
            pos = surf.get_rect(center=(C.SCREEN_W // 2, C.SCREEN_H - 90))
            screen.blit(shadow, pos.move(2, 2))
            screen.blit(surf, pos)

    def _draw_hero_labels(self, screen, battle):
        for h in battle.heroes.values():
            u = h["unit"]
            if h["status"] == "fallen":
                continue
            x, y, sc = self.project(u.x, u.y)
            top = y - 52 * sc
            text = self.small.render(h["name"], True, GOLD)
            shadow = self.small.render(h["name"], True, INK)
            pos = (round(x - text.get_width() / 2), round(top))
            screen.blit(shadow, (pos[0] + 1, pos[1] + 1))
            screen.blit(text, pos)

    def _text(self, screen, font, text, color, pos, center=False):
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=pos) if center else surf.get_rect(topleft=pos)
        screen.blit(surf, rect)
        return rect

    def _panel(self, screen, rect, alpha=160):
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((10, 12, 14, alpha))
        screen.blit(panel, rect.topleft)
        pygame.draw.rect(screen, (60, 54, 44), rect, 1)

    def _draw_hud(self, screen, battle, speed_label, paused):
        sc = battle.sc
        top = pygame.Rect(0, 0, C.SCREEN_W, 40)
        self._panel(screen, top, 200)
        self._text(screen, self.mid, sc["name"], (240, 230, 200), (14, 20))
        status = speed_label + ("  PAUSED" if paused else "")
        self._text(screen, self.font, status, (230, 230, 230), (C.SCREEN_W // 2 - 40, 12))
        x = C.SCREEN_W - 14
        for sid in reversed(list(sc["sides"])):
            s = sc["sides"][sid]
            label = f"{s['name']}: {battle.active(sid)}"
            txt = self.font.render(label, True, s["color"])
            x -= txt.get_width()
            screen.blit(txt, (x, 12))
            x -= 28

        from render_weather import NAMES
        self._text(screen, self.small, NAMES[battle.wx_kind], (200, 214, 232), (C.SCREEN_W // 2 + 60, 14))
        # objectives, top left under the bar
        y = 50
        for o in sc["objectives"]:
            done = battle.objectives_done[o["id"]]
            mark = "[x]" if done else "[ ]"
            color = (150, 230, 150) if done else (220, 220, 220)
            self._text(screen, self.small, f"{mark} {o['text']}", color, (14, y))
            y += 20

        # heroes, top right under the bar (only if the scenario has named heroes)
        if battle.heroes:
            panel = pygame.Rect(C.SCREEN_W - 252, 50, 240, 22 + 18 * len(battle.heroes))
            self._panel(screen, panel)
            self._text(screen, self.small, "HEROES  (kills)", GOLD, (panel.x + 8, panel.y + 5))
            y = panel.y + 24
            for h in battle.heroes.values():
                side = sc["sides"][h["side"]]["color"]
                status = f"back in {max(0, math.ceil((h['respawn_at'] or 0) - battle.time))}s" \
                    if h["status"] == "fallen" else "alive"
                color = (150, 150, 150) if h["status"] == "fallen" else (236, 230, 210)
                self._text(screen, self.small, f"{h['name']}", color, (panel.x + 8, y))
                self._text(screen, self.small, f"{h['kills']:>3}  {status}", side, (panel.right - 92, y))
                y += 18

        # the message log, bottom left
        log = pygame.Rect(8, C.SCREEN_H - 104, 560, 96)
        self._panel(screen, log, 170)
        for i, (_, text) in enumerate(battle.log[-4:]):
            self._text(screen, self.small, text, (235, 225, 200), (16, C.SCREEN_H - 96 + i * 22))
        hint = self.small.render("SPACE pause  +/- speed  arrows pan  C follow  H hud  W weather  L bars  F11 fullscreen  R new  ESC quit",
                                 True, (200, 200, 200))
        screen.blit(hint, (C.SCREEN_W - hint.get_width() - 12, C.SCREEN_H - 24))
