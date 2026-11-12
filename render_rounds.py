"""Drawing the rounds that weapons fire, each after the weapon (a mixin for Renderer).

A unit type's `round` in the scenario picks the art: a sniper's thin streak, a machine gun's red tracers, a flame jet, a
rocket on its smoke, a howitzer's heavy shell, a mortar bomb with fins, an armour-piercing round, a flak burst. The
`barrage` event action fires the Allied missile salvo (many small rockets) and the Axis V-2 (one huge rocket)."""
import math

import pygame

import config as C

ROUND_ART = ("sniper", "heavy_bullet", "hmg", "flame", "rocket", "rocket_salvo", "heavy", "bomb", "ap", "flak")


def _px(surf, color, x, y, w=1, h=1):
    surf.fill(color, pygame.Rect(x, y, w, h))


class RoundRender:
    ROUND_ART = ROUND_ART

    def _trail(self, low, rec, args, ang, p, n, step, hot, size0=1):
        """A rocket's exhaust: n puffs behind its head, hot orange near it and grey smoke, growing, farther back."""
        for k in range(n, 0, -1):
            a = p - step * k
            if a <= 0:
                continue
            ((ax, ay, _), _g) = self._arc(rec, *args, a, ang)
            if k <= hot:
                pygame.draw.circle(low, (255, max(60, 190 - 30 * k), 60), (ax, ay), size0)
            else:
                g = max(110, 214 - 5 * k)
                pygame.draw.circle(low, (g, g, g + 4), (ax, ay), size0 + (k - hot) // 4)

    def _draw_round(self, low, rec, start, flight):
        rd = rec["round"]
        p = min(1.0, (self.now - start) / flight)
        ang = rec["angle"]
        args = (rec["x0"], rec["y0"], rec["x1"], rec["y1"])
        ((hx, hy, _), (gx, gy, _)) = self._arc(rec, *args, p, ang)
        pygame.draw.ellipse(low, (34, 52, 30), pygame.Rect(gx - 1, gy, 3, 1))
        if rd in ("sniper", "ap"):                           # a very fast round: a long, thin, hot streak
            ((tx, ty, _), _g) = self._arc(rec, *args, max(0.0, p - (0.4 if rd == "sniper" else 0.3)), ang)
            pygame.draw.line(low, (150, 176, 230) if rd == "sniper" else (255, 150, 70), (tx, ty), (hx, hy))
            ((mx, my, _), _g) = self._arc(rec, *args, max(0.0, p - 0.1), ang)
            pygame.draw.line(low, (232, 244, 255) if rd == "sniper" else (255, 236, 160), (mx, my), (hx, hy),
                             1 if rd == "sniper" else 2)
            if p < 0.2:
                _px(low, (255, 240, 190), tx - 1, ty - 1, 3, 3)               # the muzzle flash
        elif rd == "heavy_bullet":
            ((tx, ty, _), _g) = self._arc(rec, *args, max(0.0, p - 0.1), ang)
            self._draw_arrow(low, tx, ty, hx, hy, False, True)
        elif rd == "hmg":                                    # two red tracers side by side, streaming from the gun
            for k, dy in enumerate((-1, 1)):
                q = max(0.0, p - 0.09 * k)
                ((ax, ay, _), _g) = self._arc(rec, *args, q, ang)
                ((bx, by, _), _g) = self._arc(rec, *args, max(0.0, q - 0.12), ang)
                pygame.draw.line(low, (255, 70, 50), (bx, by + dy), (ax, ay + dy))
                _px(low, (255, 236, 200), ax, ay + dy)
            if p < 0.25:
                _px(low, (255, 230, 150), hx - 2, hy - 1, 3, 3)
            if self.night > 0.2:
                self.lights.append((hx, hy, 6, "torch"))
        elif rd == "flame":                                  # a jet of burning fuel: fat embers that thin out
            for k in range(9):
                q = p - 0.035 * k
                if q <= 0:
                    break
                ((ax, ay, _), _g) = self._arc(rec, *args, q, ang)
                jit = (rec["uid"] * 3 + k * 7) % 3 - 1
                col = ((255, 240, 150), (255, 190, 60), (255, 120, 40), (190, 70, 30))[min(3, k // 2)]
                pygame.draw.circle(low, col, (ax, ay + jit), 3 if k < 6 else 2)
            if self.night > 0.15:
                self.lights.append((hx, hy, 10, "torch"))
        elif rd in ("rocket", "rocket_salvo"):               # rockets: a slim body on a thick trail of smoke
            salvo = ((0.0, 0), (-0.06, 3), (-0.12, -3)) if rd == "rocket_salvo" else ((0.0, 0),)
            for dp, dy in salvo:
                q = min(1.0, max(0.0, p + dp))
                if q <= 0:
                    continue
                a2 = (rec["x0"], rec["y0"] + dy, rec["x1"], rec["y1"] + dy)
                self._trail(low, rec, a2, ang, q, 11, 0.02, 3)
                ((ax, ay, _), _g) = self._arc(rec, *a2, q, ang)
                ((bx, by, _), _g) = self._arc(rec, *a2, max(0.0, q - 0.03), ang)
                pygame.draw.line(low, (92, 98, 84), (bx, by), (ax, ay), 2)
                _px(low, (236, 236, 226), ax, ay)
                _px(low, (255, 200, 80), bx, by)
                if self.night > 0.15:
                    self.lights.append((ax, ay, 8, "torch"))
        elif rd == "heavy":                                  # a howitzer shell: big, dark, with a brass band
            ((tx, ty, _), _g) = self._arc(rec, *args, max(0.0, p - 0.05), ang)
            pygame.draw.line(low, (28, 28, 32), (tx, ty), (hx, hy), 4)
            pygame.draw.line(low, (88, 90, 96), (tx, ty), (hx, hy), 2)
            _px(low, (214, 216, 224), hx, hy, 2, 2)
            _px(low, (210, 176, 70), tx, ty, 2, 2)
        elif rd == "bomb":                                   # a mortar bomb dropping nose down, with tail fins
            ((tx, ty, _), _g) = self._arc(rec, *args, max(0.0, p - 0.04), ang)
            _px(low, (60, 66, 52), hx - 1, hy - 1, 2, 3)
            _px(low, (190, 190, 180), hx - 1, hy + 1, 2, 1)
            _px(low, (206, 172, 70), tx - 1, ty - 2)
            _px(low, (206, 172, 70), tx + 1, ty - 2)
        elif rd == "flak":                                   # a flak round: a fast orange dash, then a black burst
            ((tx, ty, _), _g) = self._arc(rec, *args, max(0.0, p - 0.12), ang)
            if p < 0.93:
                pygame.draw.line(low, (255, 170, 60), (tx, ty), (hx, hy))
                _px(low, (255, 250, 220), hx, hy)
            else:
                pygame.draw.circle(low, (36, 34, 38), (hx, hy), 3)
                pygame.draw.circle(low, (96, 92, 96), (hx - 1, hy - 1), 2)
                _px(low, (255, 190, 80), hx + 1, hy + 1)

    def _draw_barrage(self, low, rec, start, flight):
        """The Allied missile salvo (small rockets on thin trails) and the Axis V-2 (one huge black-and-white rocket
        that climbs out of the castle on a thick plume and drops nearly straight down; a red ring shows where)."""
        v2 = rec["ammo"] == "v2"
        p = min(1.0, (self.now - start) / flight)
        ang = rec["angle"]
        args = (rec["x0"], rec["y0"], rec["x1"], rec["y1"])
        ((hx, hy, _), (gx, gy, _)) = self._arc(rec, *args, p, ang)
        if v2:
            if p > 0.5:                                      # the target ring pulses as it falls
                cx, cy, sc = self._low(rec["x1"], rec["y1"], 0)
                w = max(4, round(rec["r"] * sc / C.PIXEL))
                pulse = 1.0 + 0.15 * math.sin(self.now * 14)
                pygame.draw.ellipse(low, (255, 70, 60), pygame.Rect(cx - int(w * pulse), cy - int(w * 0.45 * pulse),
                                                                    int(2 * w * pulse), int(0.9 * w * pulse)), 1)
            self._trail(low, rec, args, ang, p, 22, 0.012, 4, 2)
        else:
            self._trail(low, rec, args, ang, p, 9, 0.014, 2, 1)
        pygame.draw.ellipse(low, (34, 52, 30), pygame.Rect(gx - 1, gy, 3, 1))
        ((tx, ty, _), _g) = self._arc(rec, *args, max(0.0, p - 0.012), ang)
        dx, dy = hx - tx, hy - ty
        n = math.hypot(dx, dy) or 1.0
        L = 12 if v2 else 5
        ux, uy = dx / n, dy / n
        bx, by = hx - ux * L, hy - uy * L
        if v2:
            for k in range(4):                               # the chequered body, black and white
                a = (round(bx + ux * L * k / 4), round(by + uy * L * k / 4))
                b = (round(bx + ux * L * (k + 1) / 4), round(by + uy * L * (k + 1) / 4))
                pygame.draw.line(low, (232, 232, 236) if k % 2 else (24, 24, 28), a, b, 3)
            _px(low, (170, 60, 50), hx, hy, 2, 2)                                        # the warhead
            _px(low, (40, 40, 46), round(bx - uy * 2), round(by + ux * 2))               # fins
            _px(low, (40, 40, 46), round(bx + uy * 2), round(by - ux * 2))
            pygame.draw.circle(low, (255, 170, 50), (round(bx - ux), round(by - uy)), 2)
            _px(low, (255, 240, 170), round(bx - ux), round(by - uy))
            if self.night > 0.1:
                self.lights.append((round(bx), round(by), 16, "torch"))
        else:
            pygame.draw.line(low, (150, 158, 138), (round(bx), round(by)), (hx, hy), 1)
            _px(low, (236, 236, 226), hx, hy)
            _px(low, (255, 170, 60), round(bx - ux), round(by - uy))
            if self.night > 0.1:
                self.lights.append((round(bx), round(by), 6, "torch"))

    def _barrage_land(self, rec, v2):
        """Where a missile or a V-2 comes down: a missile is a small flash and a puff; the V-2 a vast fireball."""
        x, y, r = rec["x1"], rec["y1"], rec.get("r", 28)
        if v2:
            self._burst("fire", x, y, 10)
            self._burst("smoke", x, y, 9)
            self._burst("debris", x, y, 6)
            self._burst("dust", x, y, 6)
            self.flames += [(x + self.rng.uniform(-r * 0.6, r * 0.6), y + self.rng.uniform(-r * 0.25, r * 0.25),
                             self.now + self.rng.uniform(5, 10)) for _ in range(8)]
            for i, (k, life, col) in enumerate(((1.0, 0.9, (255, 150, 60)), (0.7, 0.8, (255, 226, 140)),
                                                (0.4, 0.7, (255, 255, 235)))):
                self.rings.append({"x": x, "y": y, "born": self.now + 0.08 * i, "life": life, "size": r * k, "col": col})
            self.pillars.append({"x": x, "y": y, "born": self.now, "life": 1.2, "col": (255, 180, 90), "h": 120})
            if self._seen(x - r, x + r):
                self.shake = max(self.shake, 13.0)
            if self.audio:
                self.audio.sfx("boulder", x)
                self.audio.sfx("crash", x)
        else:
            self._burst("fire", x, y, 2)
            self._burst("smoke", x, y, 1)
            self._burst("dust", x, y, 1)
            self.rings.append({"x": x, "y": y, "born": self.now, "life": 0.4, "size": r, "col": (255, 190, 90)})
            if self.rng.random() < 0.35:
                self.flames.append((x, y, self.now + 3.0))
            if self.audio:
                self.audio.sfx("thud", x)
