"""The big weapons: the Allied MLRS pod and the Axis V-2 launcher (siege units on land), the Allied aircraft carrier and the
Axis dreadnought (capital ships). Every sprite faces right and is drawn for the side the colour belongs to.

  mlrs         a truck with a rack of twelve rocket tubes; the pose is the firing sequence (1-2 the flash, 3 the smoke)
  v2_launcher  a trailer carrying a raised V-2 rocket, with a tractor; at pose 1-3 the rocket's exhaust blazes at its tail
  carrier      a flat deck with an island; the pose is how many aircraft are parked on the deck (0 to 3)
  dreadnought  a long armoured hull with eight heavy guns in four turrets; the pose is the gun recoil as in `catapult_ship`
"""
import math

import pygame

from ww2_air_sea import _gunpos, _hull, _sailor
from ww2_art import METAL, METALD, _w, blank, outlined, shade, side_of
from ww2_vehicles import RECOIL, _flash, _look, _mark, _wheel


def _truck_wheels(s, xs, y, white):
    for x in xs:
        _wheel(s, x, y, 3, 0, white)


def mlrs(color, white=False, pose=0, style=""):
    """A multiple rocket launcher pod: a six-by-two rack of rocket tubes on a lorry bed, raised toward the front, a small
    cab, a stabiliser jack. At pose 1-2 a salvo leaves the rack in a fan of fire, at 3 smoke hangs over the tubes."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(46, 28)
    pygame.draw.rect(s, vd, (2, 16, 31, 4))                                         # the lorry bed
    pygame.draw.rect(s, v, (3, 15, 29, 3))
    pygame.draw.rect(s, v, (33, 9, 11, 11))                                         # the cab
    pygame.draw.rect(s, vl, (33, 9, 11, 1))
    pygame.draw.rect(s, _w(white, (120, 170, 196)), (38, 11, 5, 4))                 # its window
    pygame.draw.rect(s, vd, (43, 15, 2, 5))                                         # the bonnet
    ang = math.radians(33)
    ca, sa = math.cos(ang), math.sin(ang)
    px, py = 7, 15                                                                  # the rack pivots at the rear of the bed
    for row in range(3):                                                            # three layers of four tubes, side by side
        x0, y0 = px + 3 - row * 1, py - 2 - row * 3
        x1, y1 = round(x0 + 24 * ca), round(y0 - 24 * sa)
        pygame.draw.line(s, _w(white, METALD if row == 1 else (96, 98, 106)), (x0, y0), (x1, y1), 3)
        pygame.draw.line(s, _w(white, METAL), (x0, y0 - 1), (x1, y1 - 1))
        for k in range(1, 5):                                                       # the tube mouths and their bands
            tx, ty = round(x0 + 24 * ca * k / 5), round(y0 - 24 * sa * k / 5)
            pygame.draw.rect(s, _w(white, (60, 62, 68)), (tx, ty, 1, 2))
        if pose in (0, 4, 5):
            pygame.draw.circle(s, _w(white, (210, 90, 60)), (x1, y1), 1)           # a warhead nose in each tube
    pygame.draw.rect(s, vd, (px - 2, py - 3, 8, 3))                                 # the frame under the rack
    pygame.draw.rect(s, _w(white, tuple(color)), (35, 17, 4, 2))                    # the side's colour on the door
    if 1 <= pose <= 2:                                                              # the salvo: rockets fanning out
        for k in range(5):
            ex = 29 + k * 3
            pygame.draw.line(s, _w(white, (255, 190, 70)), (ex, 2 + k % 2 * 2), (ex + 4 + k, 1 - k % 2), 2)
            pygame.draw.circle(s, _w(white, (255, 240, 170)), (ex, 4 + k % 2 * 2), 1)
        pygame.draw.circle(s, _w(white, (255, 200, 100)), (28, 6), 3)
    elif pose == 3:
        for dx, dy, r in ((29, 4, 3), (33, 2, 3), (37, 1, 2)):
            pygame.draw.circle(s, _w(white, (130, 126, 122)), (dx, dy), r)
    pygame.draw.rect(s, _w(white, METALD), (1, 20, 4, 3))                           # the jack that steadies it
    _truck_wheels(s, (9, 18, 38), 22, white)
    s.fill((0, 0, 0, 0), pygame.Rect(0, 26, 46, 2))
    _mark(s, style, 25, 17, white)
    return outlined(s)


def v2_launcher(color, white=False, pose=0, style=""):
    """A V-2 launcher: a tractor hauling a flat trailer, the long black-and-white rocket standing on it at a steep angle, a
    gantry arm holding it. At pose 1-3 the exhaust blazes at its tail and billows over the trailer."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(62, 46)
    pygame.draw.rect(s, vd, (14, 28, 30, 4))                                        # the trailer deck
    pygame.draw.rect(s, v, (15, 27, 28, 3))
    pygame.draw.rect(s, vd, (3, 25, 12, 8))                                         # the tractor
    pygame.draw.rect(s, v, (4, 24, 10, 7))
    pygame.draw.rect(s, _w(white, (120, 170, 196)), (5, 25, 4, 3))
    pygame.draw.line(s, vd, (14, 30), (4, 33), 1)                                   # the drawbar
    ang = math.radians(78)
    bx, by = 30, 27                                                                 # the rocket's foot on the trailer
    ln = 27
    tx, ty = round(bx + ln * math.cos(ang) * -1), round(by - ln * math.sin(ang))    # leaning back over the tractor
    tx = bx + 6
    body = (236, 236, 240) if style == "axis" else (210, 210, 200)
    for i in range(0, ln, 3):                                                       # the black-and-white chequered body
        px = round(bx + (tx - bx) * i / ln)
        py = round(by - i * 0.97)
        pygame.draw.rect(s, _w(white, (24, 24, 28) if (i // 3) % 2 == 0 else body), (px - 2, py - 3, 5, 3))
    pygame.draw.polygon(s, _w(white, (74, 78, 66)), [(tx - 2, by - ln), (tx + 2, by - ln), (tx, by - ln - 6)])  # the warhead
    pygame.draw.rect(s, _w(white, (176, 50, 44)), (tx - 2, by - ln, 5, 2))
    for fx in (-1, 1):                                                              # four fins at the tail
        pygame.draw.polygon(s, _w(white, (36, 36, 42)), [(bx + 3 * fx, by - 1), (bx + 6 * fx + (1 if fx > 0 else -1), by + 2),
                                                          (bx + 1 * fx, by - 7)])
    pygame.draw.line(s, vd, (bx + 8, by), (tx + 3, by - 17), 2)                     # the gantry arm holding it
    pygame.draw.line(s, vl, (bx + 8, by - 1), (tx + 3, by - 18))
    if 1 <= pose <= 3:                                                              # the exhaust and the billowing smoke
        pygame.draw.polygon(s, _w(white, (255, 170, 60)), [(bx - 3, by), (bx + 5, by), (bx + 1, by + 8)])
        pygame.draw.polygon(s, _w(white, (255, 236, 160)), [(bx - 1, by), (bx + 3, by), (bx + 1, by + 5)])
        for dx, dy, r in ((bx - 8, by - 2, 5), (bx + 12, by - 4, 5), (bx + 2, by - 9, 4)):
            pygame.draw.circle(s, _w(white, (140, 136, 130)), (dx, dy), r)
    _truck_wheels(s, (8, 22, 38), 35, white)
    pygame.draw.rect(s, _w(white, tuple(color)), (6, 27, 3, 2))
    s.fill((0, 0, 0, 0), pygame.Rect(0, 38, 62, 8))
    _mark(s, style, 24, 28, white)
    return outlined(s)


def carrier(color, white=False, pose=0):
    """An aircraft carrier: a long flat flight deck with a white centre line, a small island with a funnel and radar mast
    on one side, anti-aircraft tubs at the edge, and `pose` aircraft (0-3) parked on the deck."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    s = blank(100, 34)
    pts = [(1, 19), (86, 19), (98, 14), (90, 28), (80, 31), (10, 31), (3, 26)]
    base, dark, light = _hull(s, st, pts, white)
    pygame.draw.rect(s, c(tuple(color)), (4, 25, 82, 2))
    pygame.draw.polygon(s, c(shade(dark, 0.9)), [(0, 15), (92, 15), (99, 13), (91, 19), (2, 19)])   # the flight deck
    pygame.draw.polygon(s, c(shade(dark, 1.25)), [(0, 15), (92, 15), (99, 13), (95, 15), (2, 16)])
    pygame.draw.line(s, c((228, 228, 220)), (4, 17), (90, 17))                       # the centre line
    for gx in range(10, 86, 10):
        pygame.draw.line(s, c((228, 228, 220)), (gx, 16), (gx + 3, 16))
    pygame.draw.rect(s, c(dark), (58, 5, 14, 11))                                    # the island
    pygame.draw.rect(s, c(base), (59, 6, 12, 8))
    pygame.draw.rect(s, c((120, 170, 196)), (61, 7, 9, 2))
    pygame.draw.rect(s, c(dark), (62, 1, 4, 5))                                       # the funnel
    pygame.draw.circle(s, c((80, 80, 86)), (64, 0), 2)
    pygame.draw.line(s, c(METAL), (70, 5), (70, -1 if False else 0))                  # the radar mast
    pygame.draw.polygon(s, c(tuple(color)), [(70, 0), (75, 1), (70, 3)])
    for gx in (14, 36, 84):                                                           # AA tubs at the deck edge
        _gunpos(s, gx, 17, white, 60, 4)
    for n in range(min(3, pose)):                                                    # aircraft parked on the deck
        ax = 12 + n * 14
        pygame.draw.rect(s, c(shade((110, 120, 82) if st == "allies" else (96, 102, 110), 0.85)), (ax, 12, 9, 2))
        pygame.draw.rect(s, c(shade((110, 120, 82) if st == "allies" else (96, 102, 110), 1.2)), (ax + 1, 11, 4, 1))
        pygame.draw.line(s, c(METALD), (ax + 4, 10), (ax + 4, 14))                    # the wings seen edge-on
        pygame.draw.line(s, c((40, 40, 44)), (ax + 9, 11), (ax + 9, 13))              # the propeller
    for sx in (50, 76):
        _sailor(s, sx, 13, st, white)
    return outlined(s)


def dreadnought(color, white=False, pose=0):
    """A dreadnought: a massive grey hull with a raised bow, a tall armoured tower, two funnels, and four turrets of twin
    heavy guns (two forward, two aft). pose is the gun recoil: 1 and 2 flash at the muzzles, then the barrels slide out."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    s = blank(84, 40)
    pts = [(1, 22), (60, 22), (76, 15), (70, 31), (58, 36), (8, 36), (3, 29)]
    base, dark, light = _hull(s, st, pts, white)
    pygame.draw.line(s, c(light), pts[0], pts[1])
    pygame.draw.rect(s, c(tuple(color)), (3, 24, 64, 2))
    rec = (0, 3, 3, 2, 1, 1)[max(0, min(5, pose))]
    pygame.draw.rect(s, c(dark), (28, 9, 10, 14))                                    # the armoured tower
    pygame.draw.rect(s, c(base), (29, 10, 8, 10))
    pygame.draw.rect(s, c((120, 170, 196)), (31, 12, 6, 2))
    pygame.draw.rect(s, c(dark), (26, 7, 14, 2))
    pygame.draw.rect(s, c(base), (30, 4, 6, 3))
    pygame.draw.line(s, c(METAL), (33, 4), (33, -0))                                  # the mast
    pygame.draw.polygon(s, c(tuple(color)), [(33, 0), (40, 1), (33, 3)])
    for fx in (19, 23):                                                              # two funnels
        pygame.draw.rect(s, c(dark), (fx, 9, 3, 13))
        pygame.draw.rect(s, c(tuple(color)), (fx, 11, 3, 1))
        pygame.draw.circle(s, c((74, 74, 80)), (fx + 1, 8), 2)
    for tx in (44, 56, 4, 12):                                                       # four turrets: fore, fore, aft, aft
        fore = tx > 30
        pygame.draw.rect(s, c(dark), (tx - 2, 15, 10, 7))
        pygame.draw.rect(s, c(base), (tx - 1, 16, 8, 5))
        if fore:
            for gy in (16, 18):
                pygame.draw.line(s, c(METALD), (tx + 7 - rec, gy), (tx + 17 - rec, gy - 1), 2)
        else:
            for gy in (16, 18):
                pygame.draw.line(s, c(METALD), (tx - 1 + rec, gy), (tx - 9 + rec, gy - 1), 2)
    if 1 <= pose <= 2:                                                               # flashes at the forward guns
        for fx, fy in ((73, 14), (61, 14)):
            pygame.draw.circle(s, c((255, 190, 70)), (fx, fy), 3)
            pygame.draw.circle(s, c((255, 240, 170)), (fx, fy), 1)
    elif pose == 3:
        pygame.draw.circle(s, c((126, 122, 118)), (70, 12), 3)
    for sx in (40, 52):
        _sailor(s, sx, 12, st, white)
    return outlined(s)
