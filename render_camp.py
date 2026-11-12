"""Drawing the two camps: the perimeter walls, watchtowers, checkpoints (gates), tank traps, barbed-wire belts and the
headquarters bunkers. CampRender is a mixin for Renderer; it uses the renderer's projection (_low), its banner and
light lists and its night amount.

The Allied camp is built of sandbags, timber and olive canvas; the Axis camp of grey poured concrete and steel. Both
fence their perimeter with barbed wire, and both mark the checkpoint with a striped barrier."""
import math

import pygame

import config as C

SAND, SAND_D, SAND_L = (176, 158, 112), (122, 106, 74), (206, 190, 142)
CONC, CONC_D, CONC_L = (140, 142, 136), (96, 98, 94), (176, 178, 170)
TIMBER, TIMBER_D, TIMBER_L = (126, 98, 62), (84, 62, 38), (170, 138, 92)
OLIVE, OLIVE_D = (92, 104, 62), (60, 70, 40)
STEEL, STEEL_D, RUST = (120, 124, 132), (60, 62, 68), (140, 82, 50)
WIRE = (196, 196, 204)


def shade(color, k):
    return tuple(max(0, min(255, int(c * k))) for c in color)


def _px(surf, color, x, y, w=1, h=1):
    surf.fill(color, pygame.Rect(x, y, w, h))


def _wire(low, x0, x1, y, rise=2):
    """A strand of barbed wire between two posts: a zigzag with a barb at each corner."""
    n = max(1, abs(x1 - x0) // 2)
    prev = (x0, y)
    for i in range(1, n + 1):
        px = x0 + (x1 - x0) * i // n
        py = y + (rise if i % 2 else 0) * (1 if i % 4 < 2 else -1)
        pygame.draw.line(low, WIRE, prev, (px, py))
        prev = (px, py)


class CampRender:
    # ------------------------------------------------------------------ the camp's wire and traps (flat or low)
    def _spikes(self, low, t):
        """A belt of barbed wire: churned dark ground, rows of short iron stakes and coils of wire strung between."""
        x, y, w, h = t["rect"]
        ground = [self._low(x, y)[:2], self._low(x + w, y)[:2], self._low(x + w, y + h)[:2], self._low(x, y + h)[:2]]
        pygame.draw.polygon(low, (62, 54, 42), ground)
        for wy in range(int(y) + 4, int(y + h), 9):
            prev = None
            for wx in range(int(x) + 3, int(x + w), 7):
                bx, by, _ = self._low(wx, wy, 0)
                tx, ty, _ = self._low(wx, wy, 5)
                pygame.draw.line(low, STEEL_D, (bx, by), (tx, ty))                          # a picket
                _px(low, RUST, tx, ty)
                if prev is not None:                                                         # wire sagging between pickets
                    mid = ((prev[0] + tx) // 2, (prev[1] + ty) // 2 + 1)
                    pygame.draw.line(low, WIRE, prev, mid)
                    pygame.draw.line(low, WIRE, mid, (tx, ty))
                    _px(low, (240, 240, 246), mid[0], mid[1] - 1)                             # a barb
                prev = (tx, ty)

    def _palisade(self, low, t):
        """Tank traps: a row of Czech hedgehogs, three angle-iron bars crossed at their middles."""
        x, y, w, h = t["rect"]
        height = t.get("height", 16)
        n = max(1, int(max(w, h) // 9))
        for i in range(n + 1):
            wx = x + (w * i / n if w >= h else w / 2)
            wy = y + (h * i / n if h > w else h / 2)
            bx, by, sc = self._low(wx, wy, 0)
            r = max(3, round(5 * sc))
            c0 = (bx, by - r)
            for dx, dy in ((-r, r), (r, r), (0, 0)):
                pass
            pygame.draw.line(low, STEEL_D, (bx - r, by), (bx + r, by - 2 * r), 2)
            pygame.draw.line(low, STEEL_D, (bx + r, by), (bx - r, by - 2 * r), 2)
            pygame.draw.line(low, STEEL_D, (bx, by), (bx, by - 2 * r), 2)
            pygame.draw.line(low, STEEL, (bx - r, by - 1), (bx + r, by - 2 * r - 1))
            pygame.draw.line(low, RUST, (bx + r, by - 1), (bx - r, by - 2 * r - 1))
            _px(low, (30, 30, 34), bx - r, by, 2, 1)
            _px(low, (30, 30, 34), bx + r - 1, by, 2, 1)

    def _wall_top(self, low, a, b, style):
        """The top edge of a perimeter wall, from a to b in screen pixels: a row of sandbag humps (Allied) or concrete
        posts strung with barbed wire (Axis)."""
        length = max(1, math.hypot(b[0] - a[0], b[1] - a[1]))
        pts = []
        for k in range(0, int(length), 5):
            px = a[0] + (b[0] - a[0]) * k / length
            py = a[1] + (b[1] - a[1]) * k / length
            pts.append((int(px), int(py)))
        if style == "axis":
            for i, (px, py) in enumerate(pts):
                if i % 2 == 0:
                    pygame.draw.line(low, CONC_D, (px, py), (px, py - 5))                    # a post leaning out
                    _px(low, CONC_L, px, py - 5)
            for lvl in (3, 5):
                for i in range(0, len(pts) - 2, 2):
                    (x0, y0), (x1, y1) = pts[i], pts[i + 2]
                    _wire(low, x0, x1, (y0 + y1) // 2 - lvl, 1)
        else:
            for i, (px, py) in enumerate(pts):
                if i % 3 != 2:                                                                  # firing gaps between humps
                    pygame.draw.ellipse(low, SAND, pygame.Rect(px - 2, py - 3, 6, 4))
                    _px(low, SAND_L, px - 1, py - 3, 3, 1)
                    _px(low, SAND_D, px - 1, py, 4, 1)
            for i in range(0, len(pts) - 3, 3):                                                # wire on stakes over the gaps
                px, py = pts[i + 2]
                pygame.draw.line(low, TIMBER_D, (px, py), (px, py - 6))
                _wire(low, px - 4, px + 4, py - 5, 1)
        if self.night > 0.2:
            for k in range(10, int(length), 34):                                               # a lantern on a post
                self.lights.append((int(a[0] + (b[0] - a[0]) * k / length) + 1,
                                    int(a[1] + (b[1] - a[1]) * k / length) - 5, 8, "torch"))

    # ------------------------------------------------------------------ solid blocks
    def _front_sandbags(self, low, fx0, fx1, ya, yb, col):
        for row, yy in enumerate(range(ya, yb + 1, 3)):
            off = 3 if row % 2 else 0
            pygame.draw.line(low, shade(col, 0.62), (min(fx0, fx1), yy), (max(fx0, fx1), yy))
            for i, xx in enumerate(range(min(fx0, fx1) + off, max(fx0, fx1), 6)):
                tone = (1.12, 1.0, 0.92)[(i + row) % 3]
                pygame.draw.rect(low, shade(col, tone), pygame.Rect(xx + 1, yy + 1, 5, 2))
                _px(low, shade(col, tone * 1.18), xx + 1, yy + 1, 5, 1)
                _px(low, shade(col, 0.7), xx, yy, 1, 3)

    def _front_concrete(self, low, fx0, fx1, ya, yb, col, slits=False):
        lo, hi = min(fx0, fx1), max(fx0, fx1)
        for xx in range(lo + 11, hi, 12):                                                      # panel joints
            pygame.draw.line(low, shade(col, 0.66), (xx, ya + 1), (xx, yb))
        pygame.draw.line(low, shade(col, 1.25), (lo, ya), (hi, ya))
        pygame.draw.line(low, shade(col, 0.6), (lo, yb), (hi, yb))
        for xx in range(lo + 5, hi, 17):                                                       # rain stains and chips
            _px(low, shade(col, 0.82), xx, ya + 2, 2, max(1, (yb - ya) // 2))
        if slits and yb - ya >= 14:
            for xx in range(lo + 6, hi - 4, 14):                                               # narrow embrasures
                _px(low, (16, 14, 16), xx, ya + (yb - ya) // 2, 6, 2)
                if self.night > 0.2:
                    self.lights.append((xx + 3, ya + (yb - ya) // 2 + 1, 9, "window"))

    def _block(self, low, t, battle=None):
        """A solid block: a top face (its back edge to its front edge) and a front face towards the viewer, dressed as
        sandbags, timber, concrete or steel depending on the piece and the side that owns it."""
        kind = t.get("style")
        if kind == "palisade":
            self._palisade(low, t)
            return
        if kind == "house":
            self._house(low, t)
            return
        x, y, w, h = t["rect"]
        height = t.get("height", C.WALL_HEIGHT)
        owner_side = battle.sc["sides"].get(t.get("owner")) if battle is not None and t.get("owner") else None
        style = owner_side.get("style", "") if owner_side else ""
        allied = style != "axis"
        if kind == "wall":
            col = SAND if allied else CONC
        elif kind == "tower":
            col = TIMBER if allied else CONC
        elif kind == "gate":
            col = STEEL
        else:
            col = t["color"]
        top_col, front_col = shade(col, 1.12), shade(col, 0.74)
        top = [self._low(x, y, height)[:2], self._low(x + w, y, height)[:2],
               self._low(x + w, y + h, height)[:2], self._low(x, y + h, height)[:2]]
        front = [self._low(x, y + h, 0)[:2], self._low(x + w, y + h, 0)[:2],
                 self._low(x + w, y + h, height)[:2], self._low(x, y + h, height)[:2]]
        base = [self._low(x - 4, y + h, 0)[:2], self._low(x + w + 8, y + h, 0)[:2],
                self._low(x + w + 14, y + h + 10, 0)[:2], self._low(x - 2, y + h + 10, 0)[:2]]
        pygame.draw.polygon(low, shade((70, 98, 52), 0.8), base)                              # the shadow on the ground
        pygame.draw.polygon(low, top_col, top)
        pygame.draw.polygon(low, front_col, front)
        pygame.draw.line(low, shade(col, 1.25), top[3], top[2])
        fx0, fy0 = front[0][0], front[3][1]
        fx1, fy1 = front[1][0], front[0][1]
        ya, yb = min(fy0, fy1), max(fy0, fy1)
        if kind == "wall":
            if allied:
                self._front_sandbags(low, fx0, fx1, ya, yb, col)
            else:
                self._front_concrete(low, fx0, fx1, ya, yb, col)
        elif kind == "tower":
            if allied:                                                                           # timber legs, X bracing, sandbag foot
                lo, hi = min(fx0, fx1), max(fx0, fx1)
                for xx in range(lo + 2, hi, 8):
                    pygame.draw.line(low, TIMBER_D, (xx, ya), (xx, yb), 2)
                    pygame.draw.line(low, TIMBER_L, (xx, ya), (xx, yb))
                for yy in range(ya + 3, yb - 4, 10):
                    for xx in range(lo + 2, hi - 8, 8):
                        pygame.draw.line(low, TIMBER_D, (xx, yy), (xx + 8, yy + 8))
                        pygame.draw.line(low, TIMBER_D, (xx + 8, yy), (xx, yy + 8))
                self._front_sandbags(low, fx0, fx1, max(ya, yb - 6), yb, SAND)
            else:
                self._front_concrete(low, fx0, fx1, ya, yb, col, slits=True)
        elif kind == "gate":                                                                       # chain-link and a striped bar
            lo, hi = min(fx0, fx1), max(fx0, fx1)
            ftop, fbot = ya, yb
            pygame.draw.rect(low, STEEL_D, pygame.Rect(lo, ftop, hi - lo, 1))
            for xx in range(lo + 1, hi, 3):
                pygame.draw.line(low, STEEL, (xx, ftop + 1), (xx + 3, fbot))
                pygame.draw.line(low, STEEL, (xx + 3, ftop + 1), (xx, fbot))
            bar = ftop + 3
            for xx in range(lo, hi, 4):                                                            # a red-and-white barrier bar
                _px(low, (214, 56, 50) if (xx // 4) % 2 else (240, 240, 244), xx, bar, 4, 2)
            _px(low, STEEL_D, lo, ftop, 2, fbot - ftop + 1)
            _px(low, STEEL_D, hi - 2, ftop, 2, fbot - ftop + 1)
        if kind == "wall" and battle is not None and t.get("owner"):
            side = battle.sc["sides"][t["owner"]]
            end = top[1] if w >= h else top[3]
            self._wall_top(low, top[0], end, style)
            if max(w, h) >= 60:                                                                    # a sign board with the side's emblem
                mid = (front[2][0] + front[3][0]) // 2
                self._hang(low, mid, front[3][1] + 1, side["color"], side["emblem"])
        if kind == "tower":
            self._tower_top(low, top, front, owner_side, allied)

    def _tower_top(self, low, top, front, owner, allied):
        """What stands on a watchtower: a roofed lookout hut with a flag (Allied) or a flat concrete cab with a
        searchlight and a flak gun (Axis)."""
        cx = top[0][0] + (top[1][0] - top[0][0]) // 2
        rim = top[0][1] - 1
        half = (top[1][0] - top[0][0]) // 2 + 1
        flag = tuple(owner["color"]) if owner is not None else (178, 40, 36)
        if allied:
            pygame.draw.rect(low, TIMBER, pygame.Rect(cx - half + 1, rim - 7, 2 * half - 1, 7))      # the lookout hut
            pygame.draw.rect(low, TIMBER_L, pygame.Rect(cx - half + 1, rim - 7, 2 * half - 1, 1))
            _px(low, (20, 18, 16), cx - half + 3, rim - 5, 2 * half - 5, 3)                          # the open window
            pygame.draw.polygon(low, OLIVE, [(cx - half - 1, rim - 7), (cx + half + 1, rim - 7), (cx + 1, rim - 12)])   # canvas roof
            pygame.draw.line(low, OLIVE_D, (cx + 1, rim - 12), (cx + half + 1, rim - 7))
            if owner is not None:
                self._banner(low, cx, rim - 12, 8, owner["color"], owner["emblem"])
            if self.night > 0.2:
                self.lights.append((cx, rim - 4, 11, "window"))
        else:
            pygame.draw.rect(low, CONC, pygame.Rect(cx - half, rim - 6, 2 * half, 6))                 # the concrete cab
            pygame.draw.rect(low, CONC_L, pygame.Rect(cx - half, rim - 6, 2 * half, 1))
            _px(low, (16, 14, 16), cx - half + 2, rim - 4, 2 * half - 4, 2)                          # a firing slit
            pygame.draw.circle(low, STEEL_D, (cx - half + 3, rim - 8), 2)                            # a searchlight
            _px(low, (250, 246, 200), cx - half + 4, rim - 8)
            pygame.draw.line(low, STEEL_D, (cx + half - 3, rim - 6), (cx + half + 1, rim - 11), 2)  # a flak barrel pointing up
            if owner is not None:
                self._banner(low, cx + 1, rim - 6, 11, owner["color"], owner["emblem"])
            if self.night > 0.2:
                self.lights.append((cx - half + 3, rim - 8, 13, "torch"))
                self.lights.append((cx, rim - 4, 11, "window"))
        if self.night > 0.2:
            self.lights.append((cx, front[3][1] + 6, 14, "window"))

    def _gate_open(self, low, t):
        """An open checkpoint: a bare road through the perimeter, the striped barrier swung up on its post."""
        x, y, w, h = t["rect"]
        height = t.get("height", C.WALL_HEIGHT)
        ground = [self._low(x, y, 0)[:2], self._low(x + w, y, 0)[:2], self._low(x + w, y + h, 0)[:2],
                  self._low(x, y + h, 0)[:2]]
        top = [self._low(x, y, height)[:2], self._low(x + w, y, height)[:2], self._low(x + w, y + h, height)[:2],
               self._low(x, y + h, height)[:2]]
        pygame.draw.polygon(low, (112, 96, 68), ground)                                         # the beaten road
        for rut in (0.3, 0.7):
            pygame.draw.line(low, (88, 72, 50), (int(ground[3][0] + (ground[2][0] - ground[3][0]) * rut), ground[3][1]),
                             (int(ground[0][0] + (ground[1][0] - ground[0][0]) * rut), ground[0][1]))
        for gx, gy, tx, ty in ((ground[3][0], ground[3][1], top[3][0], top[3][1]),
                               (ground[2][0], ground[2][1], top[2][0], top[2][1])):
            pygame.draw.line(low, STEEL_D, (gx, gy), (tx, ty), 2)                                # the two posts
        bx, by = top[3][0], top[3][1]
        for k in range(0, 14, 3):                                                               # the bar, swung up and back
            _px(low, (214, 56, 50) if (k // 3) % 2 else (240, 240, 244), bx + k // 2, by - k, 3, 2)

    def _keep(self, low, t, battle=None):
        """A headquarters bunker: sandbag-banked and canvas-roofed (Allies) or poured concrete with a sloped roof and
        camouflage (Axis), with embrasures, a steel door, an antenna mast and its side's flag. Units can walk inside."""
        x, y, w, h = t["rect"]
        height = t.get("height", 34)
        base_l, base_r = self._low(x, y + h, 0)[:2], self._low(x + w, y + h, 0)[:2]
        top_l, top_r = self._low(x, y + h, height)[:2], self._low(x + w, y + h, height)[:2]
        back_l, back_r = self._low(x, y, height)[:2], self._low(x + w, y, height)[:2]
        owner = battle.sc["sides"].get(t.get("owner")) if battle is not None and t.get("owner") else None
        allied = (owner.get("style", "") if owner is not None else "") != "axis"
        flag = tuple(owner["color"]) if owner is not None else (178, 40, 36)
        front_c, roof_c = (SAND, OLIVE) if allied else (CONC, CONC_L)
        pygame.draw.polygon(low, shade(front_c, 0.8), [base_l, base_r, top_r, top_l])
        pygame.draw.polygon(low, roof_c, [top_l, top_r, back_r, back_l])
        fy0, fy1 = top_l[1], base_l[1]
        lo, hi = base_l[0], base_r[0]
        if allied:
            self._front_sandbags(low, lo, hi, fy0 + 2, fy1, SAND)
            for sx in range(lo + 3, hi - 6, 11):                                                   # camouflage-net blotches on the roof
                pygame.draw.ellipse(low, OLIVE_D, pygame.Rect(sx, back_l[1] + 1, 7, 3))
            pygame.draw.line(low, TIMBER_D, back_l, back_r)
        else:
            self._front_concrete(low, lo, hi, fy0 + 1, fy1, CONC, slits=False)
            for sx in range(lo + 2, hi - 8, 13):                                                   # camouflage splotches
                pygame.draw.ellipse(low, (82, 96, 62), pygame.Rect(sx, fy0 + 3, 8, 4))
                pygame.draw.ellipse(low, (112, 92, 60), pygame.Rect(sx + 5, fy0 + 9, 6, 3))
            pygame.draw.line(low, CONC_D, back_l, back_r)
            pygame.draw.polygon(low, CONC_L, [(top_l[0], top_l[1]), (top_r[0], top_r[1]), (top_r[0] - 3, top_l[1] - 3), (top_l[0] + 3, top_l[1] - 3)])
        for sx in range(lo + 8, hi - 6, 16):                                                       # embrasures
            _px(low, (14, 12, 14), sx, fy0 + 7, 7, 2)
            if self.night > 0.2:
                self.lights.append((sx + 3, fy0 + 8, 11, "window"))
        cx = (lo + hi) // 2
        pygame.draw.rect(low, (20, 18, 20), pygame.Rect(cx - 5, fy1 - 12, 10, 12))                # the steel door, ajar
        pygame.draw.rect(low, STEEL, pygame.Rect(cx - 5, fy1 - 12, 5, 12))
        pygame.draw.line(low, STEEL_D, (cx - 5, fy1 - 8), (cx, fy1 - 8))
        for dx in (-9, 9):                                                                         # sandbags banked at the door
            pygame.draw.ellipse(low, SAND, pygame.Rect(cx + dx - 3, fy1 - 4, 7, 4))
            _px(low, SAND_L, cx + dx - 2, fy1 - 4, 4, 1)
        mast_x = back_r[0] - 6
        pygame.draw.line(low, STEEL_D, (mast_x, back_r[1]), (mast_x, back_r[1] - 18))              # the radio mast
        for k in (6, 11, 16):
            pygame.draw.line(low, STEEL, (mast_x - 2, back_r[1] - k), (mast_x + 2, back_r[1] - k))
        if self.night > 0.2:
            self.lights.append((mast_x, back_r[1] - 18, 8, "torch"))
            self.lights.append((cx - 8, fy1 - 6, 14, "torch"))
            self.lights.append((cx + 8, fy1 - 6, 14, "torch"))
        if owner is not None:
            self._banner(low, (back_l[0] + back_r[0]) // 2 - 8, back_l[1], 16, owner["color"], owner["emblem"])

    # ------------------------------------------------------------------ field extras: smoke, crates, mines, searchlights
    EXTRA_FX = ("heal", "mine", "defuse", "rank", "supply", "drop", "blast", "wire_cut", "bridge", "bridge_up")

    def _extra_fx(self, battle, fx):
        """Effects of the field extras: healing sparkles, a mine going off, a promotion, a supply crate picked up, a
        satchel charge, wire cut."""
        kind, x, y = fx[0], fx[1], fx[2]
        if not self._seen(x):
            return
        now = self.now
        if kind == "heal":
            self._sparks(x, y, (120, 255, 150), 3, 9, (30, 70), 0.7)
        elif kind == "mine":
            self._burst("dust", x, y, 2)
            self._burst("debris", x, y, 1)
            self._burst("smoke", x, y, 1)
            self.rings.append({"x": x, "y": y, "born": now, "life": 0.45, "size": 22, "col": (255, 214, 140)})
            self.shake = max(self.shake, 3.0)
            if self.audio:
                self.audio.sfx("boulder", x)
        elif kind == "blast":
            self._burst("dust", x, y, 3)
            self._burst("debris", x, y, 3)
            self._burst("smoke", x, y, 2)
            self.rings.append({"x": x, "y": y, "born": now, "life": 0.6, "size": 34, "col": (255, 214, 140)})
            self.shake = max(self.shake, 5.0)
            if self.audio:
                self.audio.sfx("boulder", x)
        elif kind in ("bridge", "bridge_up"):
            self._bridge_fx(kind, x, y)
        elif kind == "defuse":
            self._sparks(x, y, (230, 230, 150), 4, 8, (20, 50), 0.5)
        elif kind == "wire_cut":
            self._sparks(x, y, (210, 210, 220), 8, 16, (20, 60), 0.6)
            if self.audio:
                self.audio.sfx("clash", x)
        elif kind == "supply":
            self._sparks(x, y, (255, 226, 120), 14, 18, (40, 100), 1.0)
            self.floaters.append({"x": x, "y": y, "h": 30, "text": "Supplies!", "col": (255, 226, 120), "born": now, "life": 1.4})
        elif kind == "rank":
            self._sparks(x, y, (255, 214, 90), 10, 14, (40, 90), 0.9)
            self.floaters.append({"x": x, "y": y, "h": 26, "text": "Promoted!", "col": (255, 214, 90), "born": now, "life": 1.3})

    def _puff(self, d, alpha):
        key = (d, alpha // 8)
        s = self._puffs.get(key)
        if s is None:
            s = pygame.Surface((d, d), pygame.SRCALPHA)
            pygame.draw.circle(s, (204, 204, 208, alpha), (d // 2, d // 2), d // 2)
            pygame.draw.circle(s, (236, 236, 240, alpha), (d // 2 - d // 8, d // 2 - d // 8), max(1, d // 3))
            self._puffs[key] = s
        return s

    def _draw_smokes(self, low, battle):
        """Smoke screens: a slow churn of grey puffs that fade in as the shell bursts and out as the cloud thins."""
        if not hasattr(self, "_puffs"):
            self._puffs = {}
        for s in battle.smokes:
            if not self._seen(s["x"] - s["r"], s["x"] + s["r"]):
                continue
            a = min(1.0, (battle.time - s["born"]) / 1.5 + 0.2) * min(1.0, (s["until"] - battle.time) / 3.0)
            if a <= 0:
                continue
            cx, cy, sc = self._low(s["x"], s["y"], 0)
            rr = max(8, round(s["r"] * sc / C.PIXEL * 1.3))
            for i in range(11):
                ang = i * 2.4 + self.now * (0.22 if i % 2 else -0.17)
                dist = rr * (0.25 + 0.75 * ((i * 5) % 7) / 7)
                px = cx + round(math.cos(ang) * dist)
                py = cy - 3 - (i % 4) * 3 + round(math.sin(ang) * dist * 0.3)
                d = max(8, round(rr * (0.9 + 0.25 * ((i * 3) % 4) / 4)))
                low.blit(self._puff(d, int(110 * a)), (px - d // 2, py - d // 2))

    def _draw_crates(self, low, battle):
        """Supply crates: a parachute floats one down, then it sits on the ground with a small flag until someone
        collects it."""
        seen = getattr(self, "_crate_seen", None)
        if seen is None:
            seen = self._crate_seen = {}
        live = {id(c) for c in battle.crates}
        for k in [k for k in seen if k not in live]:
            del seen[k]
        for c in battle.crates:
            born = seen.setdefault(id(c), self.now)
            if not self._seen(c["x"] - 12, c["x"] + 12):
                continue
            color = tuple(battle.sc["sides"][c["side"]]["color"])
            fall = max(0.0, 1.0 - (self.now - born) / (C.CRATE_FALL / max(1, self.speed)))
            x, y, sc = self._low(c["x"], c["y"], 74 * fall)
            gx, gy, _ = self._low(c["x"], c["y"], 0)
            pygame.draw.ellipse(low, (34, 52, 30), pygame.Rect(gx - 4, gy - 1, 9, 3))
            pygame.draw.rect(low, (150, 112, 66), pygame.Rect(x - 3, y - 5, 7, 5))
            pygame.draw.rect(low, (96, 70, 40), pygame.Rect(x - 3, y - 5, 7, 5), 1)
            _px(low, color, x - 3, y - 3, 7, 1)
            _px(low, (240, 240, 244), x, y - 5, 1, 5)
            if fall > 0:
                pygame.draw.ellipse(low, (236, 236, 226), pygame.Rect(x - 8, y - 16, 16, 8))
                pygame.draw.ellipse(low, color, pygame.Rect(x - 3, y - 16, 6, 8))
                pygame.draw.line(low, (200, 200, 190), (x - 8, y - 12), (x - 3, y - 5))
                pygame.draw.line(low, (200, 200, 190), (x + 7, y - 12), (x + 3, y - 5))
            else:
                pygame.draw.line(low, (96, 64, 36), (x + 4, y), (x + 4, y - 9))
                pygame.draw.polygon(low, color, [(x + 4, y - 9), (x + 8, y - 8), (x + 4, y - 6)])
                if self.night > 0.2:
                    self.lights.append((x, y - 3, 10, "torch"))

    def _draw_mine_dots(self, low, battle, t):
        for mf in battle.minefields:
            if mf["t"] is t:
                for mx, my in mf["mines"]:
                    sx, sy, _ = self._low(mx, my, 0)
                    _px(low, (60, 48, 34), sx, sy, 2, 1)
                    _px(low, (112, 96, 70), sx, sy - 1)
                return

    def _draw_searchlights(self, low, battle):
        """A searchlight: a lamp on a tripod throws a pale beam that sweeps the sky, or locks on to an enemy aircraft."""
        for sl in battle.searchlights:
            if not self._seen(sl["x"] - 200, sl["x"] + 200):
                continue
            bx, by, sc = self._low(sl["x"], sl["y"], 5)
            gx, gy, _ = self._low(sl["x"], sl["y"], 0)
            target, best = None, sl.get("range", C.SEARCH_RANGE)
            for e in battle.enemies[sl["side"]]:
                for a in battle._air_units.get(e, ()):
                    d = math.hypot(a.x - sl["x"], a.y - sl["y"])
                    if d < best:
                        target, best = a, d
            if target is not None:
                tx, ty, _ = self._low(target.x, target.y, target.height)
            else:
                ang = math.sin(self.now * 0.5 + sl["x"] * 0.013) * 0.95
                tx, ty = bx + round(math.sin(ang) * 80), by - round(math.cos(ang) * 130)
            alpha = int(18 + 70 * self.night + (36 if target is not None else 0))
            w = 7 if target is None else 5
            pts = [(bx, by), (tx - w, ty), (tx + w, ty)]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            x0, y0 = min(xs) - 1, min(ys) - 1
            bw, bh = max(xs) - x0 + 2, max(ys) - y0 + 2
            beam = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.polygon(beam, (255, 250, 200, alpha), [(px - x0, py - y0) for px, py in pts])
            low.blit(beam, (x0, y0))
            if target is not None:
                pygame.draw.ellipse(low, (255, 250, 214), pygame.Rect(tx - 3, ty - 2, 7, 4), 1)
            pygame.draw.line(low, (60, 60, 66), (gx - 3, gy), (bx, by))
            pygame.draw.line(low, (60, 60, 66), (gx + 3, gy), (bx, by))
            pygame.draw.rect(low, (82, 86, 92), pygame.Rect(bx - 3, by - 3, 7, 5))
            _px(low, (255, 250, 214), bx + (2 if tx >= bx else -3), by - 2, 2, 3)
            if self.night > 0.2:
                self.lights.append((bx, by - 1, 12, "torch"))

    def _draw_torpedo(self, low, rec, start, flight):
        """A torpedo running just under the surface: a trail of bubbles and a dark nose."""
        p = min(1.0, (self.now - start) / flight)
        for k in range(0, 9):
            q = max(0.0, p - 0.02 * k)
            x = rec["x0"] + (rec["x1"] - rec["x0"]) * q
            y = rec["y0"] + (rec["y1"] - rec["y0"]) * q
            sx, sy, _ = self._low(x, y, 0)
            _px(low, (236, 246, 250) if k % 2 == 0 else (150, 200, 224), sx, sy, 2 if k < 4 else 1, 1)
        x = rec["x0"] + (rec["x1"] - rec["x0"]) * p
        y = rec["y0"] + (rec["y1"] - rec["y0"]) * p
        sx, sy, _ = self._low(x, y, 0)
        _px(low, (40, 44, 50), sx - 2, sy, 4, 2)
        _px(low, (255, 214, 120), sx + 2, sy, 1, 1)

