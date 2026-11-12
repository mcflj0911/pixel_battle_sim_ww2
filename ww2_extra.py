"""More WW2 art for Pixel BS: combat engineers, medics, commandos, flame squads, paratroopers and machine-gun nests;
the armoured car and the tank destroyer; the transport plane and the heavy bomber; the destroyer and the submarine.
Same conventions as the other art modules: sprites face right, take (color, white, frame) (the tank destroyer takes
(color, white, pose, style) like the other heavy weapons), and read the side from its colour, so one function dresses
both the Allies and the Axis."""
import math

import pygame

import ww2_art
from ww2_art import (INK, LOOK, METAL, METALD, SKIN, _soldier, _w, blank, line, outlined, pal, put, shade, side_of)
from ww2_air_sea import GLASS, YELLOW, _gunpos, _hull, _prop, _roundel, _sailor, _tail, _wing
from ww2_vehicles import _look, _mark, _wheel, TIRE


# ---------------------------------------------------------------------------------------------- infantry
def engineer(color, white=False, frame=0):
    """A combat engineer: a satchel charge with a red-banded fuse on the back, a shovel across the shoulder, a roll
    of wire at the belt. He breaches walls and clears minefields."""
    s, p = _soldier(color, white, frame)
    put(s, p, [(0, 5), (1, 5), (0, 6), (1, 6), (0, 7), (1, 7)], "G")             # the satchel
    put(s, p, [(0, 5), (1, 5)], "r")                                              # its red band
    put(s, p, [(0, 4)], "f")                                                      # a lit fuse
    line(s, p["w"], (2, 9), (9, 3))                                               # the shovel's haft
    put(s, p, [(9, 2), (10, 2), (10, 3), (9, 3)], "m")                            # the blade
    put(s, p, [(5, 7), (6, 7)], "s")
    put(s, p, [(3, 8), (4, 8)], "y")                                              # wire at the belt
    return outlined(s)


def medic(color, white=False, frame=0):
    """A medic: a white helmet disc with a red cross, a red-cross armband and a satchel, no weapon."""
    s, p = _soldier(color, white, frame)
    put(s, p, [(4, 0), (3, 1), (4, 1), (5, 1), (4, 2)], "c")                      # the helmet disc ...
    put(s, p, [(4, 1)], "r")                                                      # ... and its cross
    put(s, p, [(0, 5), (1, 5), (0, 6), (1, 6), (0, 7), (1, 7)], "c")              # the bag
    put(s, p, [(0, 6), (1, 6), (1, 5), (1, 7)], "r")
    put(s, p, [(4, 6), (5, 6), (4, 7)], "c")                                      # the armband
    put(s, p, [(4, 6)], "r")
    put(s, p, [(6, 7), (7, 7)], "s")
    put(s, p, [(7, 8), (8, 8)], "W")                                              # a stretcher pole in hand
    return outlined(s)


def commando(color, white=False, frame=0):
    """A commando: a dark knit cap, a blackened face, a suppressed carbine and a fighting knife strapped to the leg."""
    s, p = _soldier(color, white, frame, helmet=False)
    put(s, p, [(3, 0), (4, 0), (5, 0), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1)], "G")
    put(s, p, [(3, 2), (4, 2), (5, 2), (6, 2)], "G")
    put(s, p, [(3, 3), (4, 3), (3, 4), (4, 4)], "d")                              # the blackened face
    line(s, p["M"], (4, 8), (11, 7))                                              # the carbine
    put(s, p, [(10, 7), (11, 7), (12, 7)], "d")                                   # the suppressor
    put(s, p, [(6, 6), (7, 6)], "s")
    put(s, p, [(4, 10)], "m")                                                     # the knife on the leg
    put(s, p, [(1, 5), (1, 6), (0, 6)], "q")                                      # a coil of rope
    return outlined(s)


def flame_squad(color, white=False, frame=0):
    """A flame squad: two flamethrower men side by side, so one unit reads as a team."""
    a = ww2_art.foot_flamer(color, white, frame)
    b = ww2_art.foot_flamer(color, white, frame + 1)
    s = pygame.Surface((a.get_width() + 7, a.get_height() + 1), pygame.SRCALPHA)
    s.blit(b, (7, 0))
    s.blit(a, (0, 1))
    return s


def paratrooper(color, white=False, frame=0):
    """A paratrooper: a jump helmet with a chin strap, a reserve chute on the belly and a submachine gun."""
    s, p = _soldier(color, white, frame)
    put(s, p, [(2, 2), (2, 3), (6, 2), (6, 3)], "e")                              # the chin strap
    pygame.draw.rect(s, p["c"], (4, 6, 3, 3))                                      # the reserve pack
    pygame.draw.rect(s, p["g"], (4, 6, 3, 1))
    line(s, p["M"], (5, 8), (10, 7))
    put(s, p, [(7, 8), (7, 9)], "M")
    put(s, p, [(6, 6), (7, 6)], "s")
    return outlined(s)


def hmg_nest(color, white=False, frame=0):
    """A machine-gun nest: a ring of sandbags with a heavy gun on a tripod and a gunner behind it, a belt feeding in."""
    st = side_of(color)
    lk = LOOK[st]
    bag, bagd = _w(white, (186, 168, 120)), _w(white, (124, 108, 74))
    s = blank(22, 16)
    for x, y, w in ((0, 11, 7), (7, 11, 8), (15, 11, 7), (2, 8, 7), (13, 8, 7), (7, 5, 8)):
        pygame.draw.rect(s, bag, (x, y, w, 4))
        pygame.draw.rect(s, bagd, (x, y + 3, w, 1))
        s.set_at((x + w - 1, y), bagd)
    pygame.draw.rect(s, _w(white, lk["helm"]), (7, 1, 5, 3))                       # the gunner's helmet
    pygame.draw.rect(s, _w(white, SKIN), (8, 4, 3, 1))
    pygame.draw.line(s, _w(white, METALD), (10, 6), (20, 5), 2)                    # the barrel
    pygame.draw.line(s, _w(white, METAL), (10, 6), (20, 5))
    pygame.draw.line(s, _w(white, METALD), (13, 7), (11, 10))                      # the tripod
    pygame.draw.rect(s, _w(white, (66, 62, 60)), (5, 6, 3, 2))                     # the ammo box
    pygame.draw.rect(s, _w(white, tuple(color)), (1, 13, 3, 1))                    # a patch in the side's colour
    if frame % 2 and not white:
        s.set_at((21, 5), (255, 226, 120))                                         # muzzle flicker
    return outlined(s)


# ---------------------------------------------------------------------------------------------- vehicles
def armored_car(color, white=False, frame=0, style=None):
    """An armoured car: a sloped steel body on six wheels with a small turret and an autocannon. The Allies' is round
    and low, the Axis' angular with a long barrel. 30 wide."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(31, 15)
    bob = frame % 2
    if style == "allies":
        pygame.draw.polygon(s, v, [(2, 9), (4, 4), (24, 4), (29, 8), (29, 10), (2, 10)])
        pygame.draw.line(s, vl, (4, 4), (24, 4))
        pygame.draw.ellipse(s, v, (10, 0, 10, 6))                                   # the turret
        pygame.draw.rect(s, _w(white, METALD), (19, 2 + bob, 11, 1))                # the gun
    else:
        pygame.draw.polygon(s, v, [(2, 9), (3, 4), (25, 4), (29, 7), (29, 10), (2, 10)])
        pygame.draw.line(s, vl, (3, 4), (25, 4))
        pygame.draw.rect(s, v, (9, 0, 11, 5))                                       # a boxy turret
        pygame.draw.rect(s, vl, (9, 0, 11, 1))
        pygame.draw.rect(s, _w(white, METALD), (19, 2 + bob, 12, 1))
        pygame.draw.rect(s, _w(white, METALD), (30, 1 + bob, 1, 3))
    pygame.draw.rect(s, vd, (2, 8, 27, 2))
    pygame.draw.rect(s, _w(white, tuple(color)), (3, 5, 3, 2))
    _mark(s, style, 14, 7, white)
    for cx in (6, 13, 21):
        _wheel(s, cx, 11, 3, frame, white)
    pygame.draw.line(s, _w(white, METAL), (6, 4), (4, -0 if False else 0))          # antenna
    return outlined(s)


def tank_destroyer(color, white=False, pose=0, style=""):
    """A tank destroyer: a low, long-gunned hull built to kill vehicles. The Allies' has an open-topped turret, the
    Axis' a fixed casemate. `pose` is the recoil: the gun slides back on a shot and creeps forward again."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(44, 18)
    back = {1: 3, 2: 3, 3: 2, 4: 1}.get(pose, 0)
    pygame.draw.rect(s, _w(white, (36, 36, 40)), (4, 11, 34, 5))
    for wx in range(7, 36, 5):
        pygame.draw.circle(s, _w(white, (66, 66, 72)), (wx, 13), 2)
        s.set_at((wx, 13), _w(white, (120, 120, 128)))
    pygame.draw.polygon(s, vd, [(3, 12), (6, 15), (36, 15), (40, 12)])
    if style == "allies":
        pygame.draw.polygon(s, v, [(4, 11), (9, 6), (30, 6), (39, 11)])
        pygame.draw.line(s, vl, (9, 6), (30, 6))
        pygame.draw.polygon(s, v, [(12, 6), (14, 1), (27, 1), (29, 6)])               # the open-topped turret
        pygame.draw.line(s, vl, (14, 1), (27, 1))
        pygame.draw.rect(s, vd, (17, 1, 4, 2))                                        # a crewman's hatch
        pygame.draw.rect(s, _w(white, METALD), (27 - back, 3, 15, 2))                 # the long 76 mm gun
        pygame.draw.rect(s, _w(white, METAL), (27 - back, 3, 15, 1))
        _mark(s, "allies", 20, 9, white)
    else:
        pygame.draw.polygon(s, v, [(4, 11), (6, 5), (36, 5), (40, 11)])               # a sloped casemate
        pygame.draw.polygon(s, vl, [(6, 5), (10, 2), (28, 2), (34, 5)])
        pygame.draw.line(s, v, (10, 2), (28, 2))
        pygame.draw.rect(s, vd, (4, 10, 34, 3))                                       # side skirts
        pygame.draw.rect(s, _w(white, METALD), (30 - back, 3, 14, 3))                 # the long 75 mm gun
        pygame.draw.rect(s, _w(white, METAL), (30 - back, 3, 14, 1))
        pygame.draw.rect(s, _w(white, METALD), (42 - back, 2, 2, 5))                  # muzzle brake
        _mark(s, "axis", 20, 8, white)
    if pose in (1, 2) and not white:
        pygame.draw.polygon(s, (255, 214, 120), [(43, 3), (43, 6), (43 + 0, 6)])
    pygame.draw.line(s, _w(white, METAL), (8, 6), (6, 0))
    pygame.draw.polygon(s, _w(white, tuple(color)), [(6, 0), (10, 1), (6, 3)])
    return outlined(s)


# ---------------------------------------------------------------------------------------------- aircraft
def transport(color, white=False, frame=0):
    """A transport plane: the Allies' olive twin-engined Skytrain with white invasion stripes or the Axis' corrugated
    grey three-engined Ju 52. It drops supply crates and paratroopers. 40 wide."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    if st == "allies":
        top, belly, dark = (96, 110, 66), (150, 156, 150), (62, 72, 44)
    else:
        top, belly, dark = (104, 114, 112), (150, 158, 160), (64, 72, 72)
    s = blank(42, 16)
    pygame.draw.polygon(s, c(top), [(2, 5), (10, 4), (32, 4), (40, 6), (40, 9), (32, 11), (10, 11), (2, 8)])
    pygame.draw.polygon(s, c(belly), [(8, 10), (34, 10), (30, 11), (10, 11)])
    _tail(s, c(top), c(dark), [(2, 5), (1, 0), (7, 0), (9, 5)])
    pygame.draw.rect(s, c(dark), (0, 7, 8, 1))
    pygame.draw.polygon(s, c(GLASS), [(32, 4), (35, 3), (39, 5), (39, 7), (33, 7)])                           # the cockpit glass
    for x in range(12, 30, 3):                                                                                 # the paratroop door windows
        s.set_at((x, 7), c(GLASS))
    _wing(s, c(top), c(dark), 16, 8, 14, sweep=3, drop=1)
    if st == "allies":
        for x in (7, 9):                                                                                      # invasion stripes
            pygame.draw.line(s, c((236, 236, 240)), (x, 5), (x, 10))
            pygame.draw.line(s, c((24, 24, 28)), (x + 1, 5), (x + 1, 10))
        pygame.draw.rect(s, c(dark), (22, 12, 5, 3))                                                          # an engine nacelle
        _prop(s, 27, 13, 3, frame, white)
    else:
        for x in range(10, 30, 3):                                                                            # corrugated skin
            pygame.draw.line(s, c(dark), (x, 5), (x, 10))
        pygame.draw.rect(s, c(dark), (22, 12, 5, 3))
        _prop(s, 27, 13, 3, frame, white)
        _prop(s, 41, 7, 3, frame + 1, white)                                                                  # the nose engine
    _roundel(s, st, 20, 7, white)
    _prop(s, 41 if st == "allies" else 40, 7, 3, frame, white) if st == "allies" else None
    return outlined(s)


def heavy_bomber(color, white=False, frame=0):
    """A heavy bomber: the Allies' four-engined silver Fortress with a tall tail fin and gun turrets or the Axis'
    twin-engined glass-nosed Heinkel. It flies a long run over the enemy army, shedding bombs. 48 wide."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    if st == "allies":
        top, belly, dark = (180, 186, 192), (222, 226, 230), (112, 120, 130)
    else:
        top, belly, dark = (84, 100, 92), (140, 156, 164), (48, 58, 52)
    s = blank(50, 18)
    pygame.draw.polygon(s, c(top), [(2, 6), (12, 5), (38, 5), (48, 7), (48, 10), (38, 12), (12, 12), (2, 9)])
    pygame.draw.polygon(s, c(belly), [(10, 11), (40, 11), (36, 12), (12, 12)])
    _tail(s, c(top), c(dark), [(2, 6), (1, 0), (8, 0), (11, 6)])
    pygame.draw.rect(s, c(dark), (0, 8, 10, 1))
    if st == "allies":
        pygame.draw.polygon(s, c(GLASS), [(40, 5), (44, 4), (48, 7), (46, 8), (41, 8)])
        pygame.draw.circle(s, c(dark), (26, 5), 2)                                                            # a top turret
        pygame.draw.circle(s, c(dark), (30, 12), 2)                                                           # the ball turret
    else:
        pygame.draw.polygon(s, c(GLASS), [(38, 5), (44, 3), (49, 7), (49, 10), (40, 10)])                      # the glazed nose
        for x in (41, 44, 47):
            s.set_at((x, 6), c(dark))
        pygame.draw.circle(s, c(dark), (24, 5), 2)
    _wing(s, c(top), c(dark), 18, 9, 17, sweep=4, drop=1)
    _wing(s, c(top), c(dark), 14, 9, 8, sweep=2, drop=1)
    for ex in ((22, 30) if st == "allies" else (24,)):
        pygame.draw.rect(s, c(dark), (ex, 13, 5, 3))
        _prop(s, ex + 5, 14, 3, frame + ex, white)
    if st == "allies":
        pygame.draw.rect(s, c(dark), (16, 13, 4, 3))
        _prop(s, 20, 14, 3, frame + 1, white)
        pygame.draw.rect(s, c(dark), (34, 13, 4, 3))
        _prop(s, 38, 14, 3, frame + 2, white)
    _roundel(s, st, 14, 8, white)
    return outlined(s)


# ---------------------------------------------------------------------------------------------- ships
def destroyer(color, white=False, frame=0):
    """A destroyer: a long, low grey hull with two forward gun turrets, twin funnels, a mast and a row of flak guns.
    It shoots ships and aircraft and hunts submarines. 60 wide."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    s = blank(62, 28)
    pts = [(1, 15), (54, 15), (60, 11), (54, 24), (42, 27), (8, 27), (2, 22)]
    base, dark, light = _hull(s, st, pts, white)
    pygame.draw.line(s, c(light), pts[0], pts[1])
    pygame.draw.rect(s, c(tuple(color)), (3, 16, 52, 2))
    pygame.draw.rect(s, c(dark), (22, 8, 14, 8))                                                  # the bridge
    pygame.draw.rect(s, c(base), (23, 9, 12, 6))
    pygame.draw.rect(s, c((120, 170, 196)), (30, 10, 5, 2))
    for fx in (14, 38):                                                                           # the funnels
        pygame.draw.rect(s, c(dark), (fx, 5, 5, 11))
        pygame.draw.rect(s, c(tuple(color)), (fx, 7, 5, 1))
    pygame.draw.circle(s, c((90, 90, 96)), (16, 3), 2)
    for gx in (45, 52):                                                                           # two forward turrets
        pygame.draw.rect(s, c((70, 74, 80)), (gx - 3, 11, 7, 5))
        pygame.draw.line(s, c(METALD), (gx + 3, 12), (gx + 9, 10), 2)
    _gunpos(s, 7, 13, white, 60, 5)
    _gunpos(s, 11, 13, white, 55, 5)
    pygame.draw.line(s, c(METAL), (26, 8), (26, 0))
    pygame.draw.line(s, c(METAL), (22, 3), (30, 3))
    pygame.draw.polygon(s, c(tuple(color)), [(26, 0), (32, 1 + frame % 2), (26, 3)])
    for sx in (20, 40, 49):
        _sailor(s, sx, 13, st, white)
    return outlined(s)


def submarine(color, white=False, frame=0):
    """A submarine, running on the surface with most of its hull under water: a low whale-backed hull, a conning
    tower with a periscope and a deck gun forward. 54 wide; the renderer sinks the lower half."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    if st == "allies":
        base, dark, light = (70, 82, 74), (40, 50, 46), (104, 118, 108)
    else:
        base, dark, light = (66, 72, 80), (36, 40, 48), (100, 108, 118)
    s = blank(56, 20)
    pygame.draw.ellipse(s, c(base), (1, 6, 54, 13))
    pygame.draw.ellipse(s, c(dark), (1, 12, 54, 7))
    pygame.draw.line(s, c(light), (6, 8), (48, 8))
    pygame.draw.rect(s, c(base), (24, 1, 11, 8))                                                  # the conning tower
    pygame.draw.rect(s, c(dark), (24, 6, 11, 3))
    pygame.draw.rect(s, c(light), (24, 1, 11, 1))
    pygame.draw.rect(s, c(tuple(color)), (27, 3, 5, 1))
    pygame.draw.line(s, c(METAL), (31, 1), (31, -0 if False else 0))
    pygame.draw.line(s, c(METALD), (36, 5), (36, 2))                                              # the periscope
    pygame.draw.line(s, c(METAL), (36, 2), (39, 2))
    pygame.draw.rect(s, c((70, 74, 80)), (43, 5, 5, 3))                                           # the deck gun
    pygame.draw.line(s, c(METALD), (47, 6), (54, 5), 2)
    pygame.draw.polygon(s, c(dark), [(1, 10), (-0 if False else 0, 6), (5, 8)])                   # a fin aft
    if st == "allies":
        pygame.draw.polygon(s, c(tuple(color)), [(24, 1), (21, 3), (24, 3)])
    return outlined(s)


KINDS = {"engineer": engineer, "medic": medic, "commando": commando, "flame_squad": flame_squad,
         "paratrooper": paratrooper, "hmg_nest": hmg_nest, "armored_car": armored_car, "tank_destroyer": tank_destroyer,
         "transport": transport, "heavy_bomber": heavy_bomber, "destroyer": destroyer, "submarine": submarine}
