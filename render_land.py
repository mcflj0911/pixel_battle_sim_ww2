"""Drawing the land of the middle field: rivers that run to the sea, the bridges and pontoons across them, hills and the
houses of the towns (a mixin for Renderer)."""
import math

import pygame

import config as C

WATER, WATER_D, WATER_L = (58, 104, 158), (40, 80, 132), (122, 170, 214)
BANK, BANK_D = (122, 104, 66), (84, 72, 46)
PLANK, PLANK_D, PLANK_L = (150, 118, 78), (104, 80, 50), (186, 152, 106)
TIMBER_D = (84, 62, 38)


def _px(surf, color, x, y, w=1, h=1):
    surf.fill(color, pygame.Rect(x, y, w, h))


def _shade(color, k):
    return tuple(max(0, min(255, int(c * k))) for c in color)


class LandRender:
    # ------------------------------------------------------------------ rivers
    def _river_seg(self, low, t):
        """One block of river: a band of water between two muddy banks, with ripples drifting down toward the sea. A
        block whose bridge has fallen (`gap_of`) also shows the stumps of its piers."""
        x, y, w, h = t["rect"]
        if not self._seen(x, x + w):
            return
        a, b = self._low(x, y), self._low(x + w, y)
        c, d = self._low(x + w, y + h), self._low(x, y + h)
        pygame.draw.polygon(low, WATER, [a[:2], b[:2], c[:2], d[:2]])
        pygame.draw.line(low, BANK, (a[0] - 1, a[1]), (d[0] - 1, d[1]), 2)                 # the banks
        pygame.draw.line(low, BANK, (b[0], b[1]), (c[0], c[1]), 2)
        pygame.draw.line(low, BANK_D, (a[0] - 2, a[1]), (d[0] - 2, d[1]))
        pygame.draw.line(low, BANK_D, (b[0] + 1, b[1]), (c[0] + 1, c[1]))
        hp = max(1, d[1] - a[1])
        wp = max(2, b[0] - a[0])
        seed = int(x * 7 + y * 3)
        for j in range(2):                                                                 # ripples run toward the sea
            yy = a[1] + int((self.now * 6 + j * hp / 2 + (seed % 7)) % hp)
            xx = a[0] + 2 + (seed * (j + 3)) % max(1, wp - 6)
            pygame.draw.line(low, WATER_L, (xx, yy), (xx + 3, yy))
        if (seed + int(self.now * 2)) % 5 == 0:
            _px(low, (214, 236, 250), a[0] + 3 + seed % max(1, wp - 6), a[1] + seed % hp)   # a glint
        if t.get("gap_of") and not t.get("hidden"):                                        # the ruin of a bridge
            for px in (a[0] - 1, b[0] - 1):
                pygame.draw.line(low, TIMBER_D, (px, d[1] - 1), (px, d[1] - 5 - seed % 3), 2)
            if seed % 2:
                pygame.draw.line(low, PLANK_D, (a[0] + 2, a[1] + hp // 2), (a[0] + wp // 2, a[1] + hp // 2 + 1), 2)
        if t["rect"][1] + t["rect"][3] >= self.shore - 1 if self.shore is not None else False:   # the mouth
            for k in range(0, wp, 3):
                _px(low, (226, 240, 244), d[0] + k + int(self.now * 3) % 3, d[1] - 1)

    # ------------------------------------------------------------------ bridges and pontoons
    def _bridge(self, low, t, battle):
        x, y, w, h = t["rect"]
        if not self._seen(x, x + w):
            return
        pont = t.get("pontoon")
        ratio = max(0.0, t["hp"] / max(1.0, t.get("max_hp", t["hp"])))
        wx0, wx1 = x + 8, x + w - 8                                  # the water under the span
        pts = [self._low(wx0, y)[:2], self._low(wx1, y)[:2], self._low(wx1, y + h)[:2], self._low(wx0, y + h)[:2]]
        pygame.draw.polygon(low, WATER, pts)
        for j in range(3):
            yy = pts[0][1] + int((self.now * 6 + j * 3) % max(1, pts[3][1] - pts[0][1]))
            pygame.draw.line(low, WATER_L, (pts[0][0] + 2 + j * 3, yy), (pts[0][0] + 5 + j * 3, yy))
        hh = 2.0 if pont else 4.0
        inset = 3 if pont else 0
        dx0, dx1, dy0, dy1 = x + inset, x + w - inset, y + inset, y + h - inset
        deck = [self._low(dx0, dy0, hh)[:2], self._low(dx1, dy0, hh)[:2], self._low(dx1, dy1, hh)[:2], self._low(dx0, dy1, hh)[:2]]
        if pont:                                                       # rubber floats under a light deck
            for k in range(3):
                fx = dx0 + (dx1 - dx0) * (k + 0.5) / 3
                for fy in (dy0 + 3, dy1 - 3):
                    px, py, sc = self._low(fx, fy, 0)
                    pygame.draw.ellipse(low, (70, 78, 60), pygame.Rect(px - 5, py - 1, 10, 4))
                    pygame.draw.ellipse(low, (112, 120, 94), pygame.Rect(px - 4, py - 1, 8, 2))
        else:
            for fy in (dy0, dy1):                                      # piers going down into the river
                for fx in (dx0 + 2, dx1 - 2):
                    p0, p1 = self._low(fx, fy, hh)[:2], self._low(fx, fy, -2)[:2]
                    pygame.draw.line(low, TIMBER_D, p0, p1, 2)
        pygame.draw.polygon(low, PLANK if not pont else (132, 128, 100), deck)
        step = 5 if not pont else 6
        n = 0
        px_ = dx0
        while px_ < dx1:                                               # planks lie across the way over
            a, b = self._low(px_, dy0, hh)[:2], self._low(px_, dy1, hh)[:2]
            broken = ratio < 0.5 and (n * 7 + int(y)) % 5 == 0
            if broken:
                pygame.draw.line(low, WATER_D, a, b, 1)
            else:
                pygame.draw.line(low, PLANK_D if n % 2 else PLANK_L, a, b)
            px_ += step
            n += 1
        pygame.draw.polygon(low, TIMBER_D, deck, 1)
        if not pont:                                                   # rails along both edges: posts and two rails
            for fy in (dy0, dy1):
                prev = None
                fx = dx0
                while fx <= dx1 + 0.1:
                    foot, top = self._low(fx, fy, hh)[:2], self._low(fx, fy, hh + 8)[:2]
                    pygame.draw.line(low, TIMBER_D, foot, top)
                    if prev is not None:
                        pygame.draw.line(low, PLANK_L, prev, top)
                    prev = top
                    fx += (dx1 - dx0) / 4
        if ratio < 0.35:                                               # a bridge about to go: smoke and a lean
            px, py, sc = self._low((dx0 + dx1) / 2, dy0, hh + 2)
            _px(low, (150, 150, 154), px + int(self.now * 7) % 3, py - 2 - int(self.now * 5) % 4)

    # ------------------------------------------------------------------ hills
    def _hill(self, low, t):
        """A hill: a dome of stacked, lighter rings of grass with a few stones, drawn once (the ground does not move)."""
        x, y, w, h = t["rect"]
        cx, cy = x + w / 2, y + h / 2
        rx, ry = w / 2, h / 2
        height = t.get("height", 30.0)
        n = 22
        base = _shade(t["color"], 0.78)
        steps = 6
        for k in range(steps + 1):
            s = 1.0 - 0.15 * k
            hz = height * k / steps
            ring = [self._low(cx + math.cos(i * 2 * math.pi / n) * rx * s, cy + math.sin(i * 2 * math.pi / n) * ry * s, hz)[:2]
                    for i in range(n)]
            col = _shade(t["color"], 0.7 + 0.11 * k)
            pygame.draw.polygon(low, col, ring)
            if k == 0:
                pygame.draw.polygon(low, _shade(col, 0.7), ring, 1)
            else:                                                       # the sunlit crest of this terrace
                top = [p for i, p in enumerate(ring) if 4 <= i <= 10]
                if len(top) > 1:
                    pygame.draw.lines(low, _shade(col, 1.18), False, top)
        for i in range(10):                                             # tufts and stones
            a = i * 2.399
            r = 0.2 + 0.7 * ((i * 37) % 10) / 10
            px, py, _ = self._low(cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r * 0.9, height * (1 - r) * 0.9)
            if i % 3 == 0:
                _px(low, (138, 136, 128), px, py, 2, 1)
            else:
                pygame.draw.line(low, _shade(t["color"], 1.4), (px, py), (px, py - 1))

    # ------------------------------------------------------------------ houses
    def _house(self, low, t):
        """A house of a town: plaster walls with a door and windows under a gabled tile roof, and a chimney."""
        x, y, w, h = t["rect"]
        hgt = t.get("height", 24.0)
        wall = t["color"]
        roof = t.get("roof") or (140, 70, 56)
        base = [self._low(x - 3, y + h, 0)[:2], self._low(x + w + 6, y + h, 0)[:2],
                self._low(x + w + 12, y + h + 8, 0)[:2], self._low(x - 1, y + h + 8, 0)[:2]]
        pygame.draw.polygon(low, _shade((70, 98, 52), 0.8), base)                       # its shadow on the grass
        front = [self._low(x, y + h, 0)[:2], self._low(x + w, y + h, 0)[:2],
                 self._low(x + w, y + h, hgt)[:2], self._low(x, y + h, hgt)[:2]]
        pygame.draw.polygon(low, _shade(wall, 0.86), front)
        eave_f = [self._low(x - 2, y + h + 2, hgt)[:2], self._low(x + w + 2, y + h + 2, hgt)[:2]]
        ridge = [self._low(x - 2, y + h / 2, hgt + 10)[:2], self._low(x + w + 2, y + h / 2, hgt + 10)[:2]]
        eave_b = [self._low(x - 2, y - 2, hgt)[:2], self._low(x + w + 2, y - 2, hgt)[:2]]
        pygame.draw.polygon(low, _shade(roof, 0.8), [eave_b[0], eave_b[1], ridge[1], ridge[0]])          # the far slope
        pygame.draw.polygon(low, roof, [ridge[0], ridge[1], eave_f[1], eave_f[0]])                       # the near slope
        pygame.draw.line(low, _shade(roof, 1.25), ridge[0], ridge[1])
        for k in range(1, 3):                                                                            # rows of tiles
            f = k / 3
            a = (round(ridge[0][0] + (eave_f[0][0] - ridge[0][0]) * f), round(ridge[0][1] + (eave_f[0][1] - ridge[0][1]) * f))
            b = (round(ridge[1][0] + (eave_f[1][0] - ridge[1][0]) * f), round(ridge[1][1] + (eave_f[1][1] - ridge[1][1]) * f))
            pygame.draw.line(low, _shade(roof, 0.82), a, b)
        cx, cy = self._low(x + w * 0.75, y + h * 0.5, hgt + 12)[:2]                                      # the chimney
        pygame.draw.rect(low, (96, 80, 72), pygame.Rect(cx - 1, cy - 1, 3, 4))
        fx0, fx1 = front[0][0], front[1][0]
        fy0, fy1 = front[3][1], front[0][1]
        pygame.draw.line(low, _shade(wall, 1.12), front[3], front[2])
        wd = max(3, (fx1 - fx0) // 5)
        door_x = fx0 + (fx1 - fx0) // 2 - wd // 2
        pygame.draw.rect(low, (82, 56, 36), pygame.Rect(door_x, fy1 - wd - 2, wd, wd + 2))
        lit = self.night > 0.3
        for wx in (fx0 + 2, fx1 - wd - 2):
            col = (255, 214, 120) if lit else (140, 170, 196)
            pygame.draw.rect(low, (70, 54, 40), pygame.Rect(wx - 1, fy0 + 2, wd + 2, wd))
            pygame.draw.rect(low, col, pygame.Rect(wx, fy0 + 3, wd, wd - 2))
            if lit:
                self.lights.append((wx + wd // 2, fy0 + 4, 10, "torch"))

    # ------------------------------------------------------------------ effects
    def _bridge_fx(self, kind, x, y):
        now = self.now
        if kind == "bridge":                                           # a bridge falls into the river
            self._burst("debris", x, y, 5)
            self._burst("dust", x, y, 3)
            self._burst("smoke", x, y, 2)
            self._sparks(x, y, (200, 228, 250), 18, 26, (50, 130), 0.9)    # a great splash
            self.rings.append({"x": x, "y": y, "born": now, "life": 0.9, "size": 44, "col": (200, 228, 250)})
            self.rings.append({"x": x, "y": y, "born": now + 0.1, "life": 0.7, "size": 26, "col": (255, 214, 140)})
            self.shake = max(self.shake, 6.0)
            if self.audio:
                self.audio.sfx("crash", x)
        else:                                                          # engineers finish a bridge or pontoon
            self._sparks(x, y, (255, 226, 120), 12, 18, (40, 100), 0.9)
            self.floaters.append({"x": x, "y": y, "h": 30, "text": "Bridged!", "col": (255, 226, 120), "born": now, "life": 1.4})
            if self.audio:
                self.audio.sfx("thud", x)
