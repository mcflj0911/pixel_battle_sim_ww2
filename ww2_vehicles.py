"""WW2 vehicles and guns for Pixel BS: jeep and sidecar motorcycle (the fast mounted units), the assault tank, the
halftrack (it carries a garrison that shoots from it), and the guns that replace the siege engines: field gun / rocket
launcher, howitzer, mortar and flak gun. Siege-style sprites take (color, white, pose, style) where pose counts up
through the recoil (0 ready, 1-2 firing, 3-5 settling back); the style ("allies" or "axis") picks the side's look."""
import math

import pygame

from ww2_art import (INK, LOOK, METAL, METALD, SKIN, WOOD, WOODL, _w, blank, outlined, shade, side_of)

TIRE, HUB = (30, 30, 34), (150, 150, 158)


def _look(style, color=None):
    return LOOK[style or (side_of(color) if color is not None else "allies")]


def _mark(s, style, x, y, white=False):
    """The side's national marking: a white star (Allies) or a black cross edged in white (Axis)."""
    if white:
        pygame.draw.rect(s, (255, 255, 255), (x - 2, y - 2, 5, 5))
        return
    if style == "allies":
        pygame.draw.rect(s, (42, 74, 160), (x - 2, y - 2, 5, 5)) if False else None
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)):
            s.set_at((x + dx, y + dy), (240, 240, 244))
        s.set_at((x, y), (42, 74, 160))
    else:
        pygame.draw.rect(s, (240, 240, 244), (x - 2, y - 2, 5, 5))
        pygame.draw.rect(s, (24, 24, 28), (x - 1, y - 2, 3, 5))
        pygame.draw.rect(s, (24, 24, 28), (x - 2, y - 1, 5, 3))
        s.set_at((x, y), (240, 240, 244))


def _wheel(s, cx, cy, r, frame, white=False):
    pygame.draw.circle(s, _w(white, TIRE), (cx, cy), r)
    pygame.draw.circle(s, _w(white, HUB), (cx, cy), max(1, r - 2))
    a = frame % 2
    s.set_at((cx + (1 if a else -1), cy), _w(white, TIRE))
    s.set_at((cx, cy + (-1 if a else 1)), _w(white, TIRE))


def _head(s, x, y, white, lk, style):
    """A soldier's head and helmet, seen over a vehicle's side."""
    pygame.draw.rect(s, _w(white, SKIN), (x, y + 2, 3, 2))
    pygame.draw.rect(s, _w(white, lk["helm"]), (x - 1, y, 5, 2))
    s.set_at((x + 2, y + 2), _w(white, INK))
    if style == "axis":
        s.set_at((x - 1, y + 2), _w(white, lk["helmj"]))


# ---------------------------------------------------------------------------------------------- jeep, car, motorcycle
def car(color, white=False, frame=0, style=None, crew=True):
    """An Allied jeep (flat hood, a windscreen folded up, a pintle machine gun) or an Axis staff car (rounded
    fenders, a canvas-less open body). 22 wide, 12 tall, facing right."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(23, 13)
    bob = frame % 2
    pygame.draw.rect(s, vd, (1, 4, 20, 5))                                   # the underbody
    pygame.draw.rect(s, v, (1, 3, 15, 5))                                    # the open body
    pygame.draw.rect(s, vl, (1, 3, 15, 1))
    pygame.draw.polygon(s, v, [(15, 4), (22, 5), (22, 8), (15, 8)])          # the hood
    pygame.draw.line(s, vl, (15, 4), (21, 5))
    if style == "axis":                                                      # rounded fenders and a spare wheel
        pygame.draw.ellipse(s, vd, (2, 6, 8, 4))
        pygame.draw.ellipse(s, vd, (13, 6, 8, 4))
        pygame.draw.circle(s, _w(white, TIRE), (2, 6), 2)
    pygame.draw.rect(s, _w(white, METALD), (14, 1, 1, 3))                    # the windscreen frame
    pygame.draw.line(s, _w(white, (150, 190, 210)), (14, 1), (14, 3))
    pygame.draw.rect(s, _w(white, tuple(color)), (1, 4, 3, 2))               # a colour patch on the tail
    _mark(s, style, 9, 6, white)
    _wheel(s, 5, 9, 3, frame, white)
    _wheel(s, 17, 9, 3, frame, white)
    pygame.draw.rect(s, _w(white, (250, 240, 180)), (21, 5, 1, 2))           # a headlight
    if crew:
        _head(s, 11, 0 + bob, white, lk, style)                              # the driver
        _head(s, 5, 0 + bob, white, lk, style)                               # the gunner
        pygame.draw.line(s, _w(white, METALD), (6, 3), (10, 1 + bob))        # the pintle machine gun, aimed forward
        pygame.draw.line(s, _w(white, METAL), (9, 2), (12, 1 + bob))
    return s


def rider(color, hero=False, white=False, frame=0, variant=0):
    """The mounted slot: an Allied jeep with a driver and a gunner, or an Axis sidecar motorcycle."""
    style = side_of(color)
    if style == "allies":
        return outlined(car(color, white, frame, "allies"))
    return outlined(bike(color, white, frame))


def bike(color, white=False, frame=0):
    """A sidecar motorcycle: the rider hunched over the bars, a gunner in the sidecar with a machine gun."""
    lk = _look("axis")
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(24, 14)
    bob = frame % 2
    _wheel(s, 4, 10, 3, frame, white)
    _wheel(s, 20, 10, 3, frame, white)
    pygame.draw.line(s, vd, (4, 10), (10, 6), 2)                              # the frame
    pygame.draw.line(s, vd, (20, 10), (17, 5), 2)                             # the forks
    pygame.draw.rect(s, v, (8, 5, 8, 3))                                      # the tank and engine
    pygame.draw.rect(s, vl, (8, 5, 8, 1))
    pygame.draw.rect(s, _w(white, (44, 44, 48)), (12, 8, 3, 3))               # the engine block
    pygame.draw.line(s, _w(white, METALD), (17, 4), (19, 3))                  # the handlebars
    pygame.draw.rect(s, _w(white, tuple(color)), (6, 4, 3, 2))                # a colour patch
    _head(s, 10, 0 + bob, True if white else False, lk, "axis")               # the rider
    pygame.draw.rect(s, _w(white, lk["uni"]), (9, 3 + bob, 5, 3))
    pygame.draw.rect(s, vd, (13, 6, 9, 5)) if False else None
    pygame.draw.polygon(s, v, [(11, 9), (23, 9), (22, 12), (13, 12)])          # the sidecar tub
    pygame.draw.line(s, vl, (11, 9), (23, 9))
    _wheel(s, 17, 12, 2, frame, white)
    _head(s, 16, 5 + bob, white, lk, "axis")                                  # the gunner in the sidecar
    pygame.draw.line(s, _w(white, METALD), (18, 8), (23, 7))                  # his machine gun
    _mark(s, "axis", 14, 10, white)
    return s


# ---------------------------------------------------------------------------------------------- tank
def ram_crew(color, white=False, frame=0, style=""):
    """The assault tank (the slot the battering ram used): tracks with road wheels, a hull, a turret and a gun. The
    Allied tank is rounded and high with a short gun; the Axis tank is boxy with a long gun and side skirts. The
    frame makes the tracks creep and the gun rock as it batters a wall."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(40, 20)
    rock = 1 if frame % 2 else 0
    pygame.draw.rect(s, _w(white, (36, 36, 40)), (3, 12, 33, 6))               # the track run
    for wx in range(6, 35, 5):                                                  # road wheels
        pygame.draw.circle(s, _w(white, (66, 66, 72)), (wx, 15), 2)
        s.set_at((wx, 15), _w(white, (120, 120, 128)))
    for tx in range(4 + (frame % 2) * 2, 36, 4):                                # the track links creep
        s.set_at((tx, 12), _w(white, (88, 88, 94)))
        s.set_at((tx + 1, 18), _w(white, (88, 88, 94)))
    pygame.draw.polygon(s, vd, [(2, 14), (5, 17), (34, 17), (38, 14)])          # the track front and rear
    if style == "allies":                                                       # a rounded cast hull and turret
        pygame.draw.polygon(s, v, [(3, 12), (6, 7), (32, 7), (38, 12)])
        pygame.draw.line(s, vl, (6, 7), (32, 7))
        pygame.draw.ellipse(s, v, (13, 1, 16, 9))                               # the turret
        pygame.draw.arc(s, vl, pygame.Rect(13, 1, 16, 9), 0.4, 2.8, 1)
        pygame.draw.rect(s, _w(white, METALD), (28, 4 + rock, 11, 2))           # the short gun
        pygame.draw.rect(s, _w(white, METAL), (28, 4 + rock, 11, 1))
        pygame.draw.rect(s, vd, (24, 2, 3, 3))                                  # a commander's cupola
        _mark(s, "allies", 14, 10, white)
    else:                                                                       # a boxy hull, flat turret, long gun
        pygame.draw.polygon(s, v, [(3, 12), (4, 7), (34, 7), (38, 12)])
        pygame.draw.line(s, vl, (4, 7), (34, 7))
        pygame.draw.rect(s, vd, (4, 10, 32, 3))                                  # the side skirts
        for sx in range(6, 36, 6):
            pygame.draw.line(s, v, (sx, 10), (sx, 12))
        pygame.draw.rect(s, v, (12, 1, 16, 7))                                  # the turret
        pygame.draw.rect(s, vl, (12, 1, 16, 1))
        pygame.draw.rect(s, vd, (12, 5, 16, 1))
        pygame.draw.rect(s, _w(white, METALD), (27, 3 + rock, 13, 2))           # the long gun
        pygame.draw.rect(s, _w(white, METAL), (27, 3 + rock, 13, 1))
        pygame.draw.rect(s, _w(white, METALD), (38, 2 + rock, 2, 4))            # muzzle brake
        pygame.draw.rect(s, vd, (16, 0, 4, 2))                                  # the cupola
        _mark(s, "axis", 22, 9, white)
    pygame.draw.line(s, _w(white, METAL), (9, 7), (7, 0))                       # a whip antenna
    pygame.draw.polygon(s, _w(white, tuple(color)), [(7, 0), (11, 1), (7, 3)])  # the side's pennant
    return outlined(s)


# ---------------------------------------------------------------------------------------------- halftrack
def siege_tower(color, white=False, pose=0, style=""):
    """A halftrack (the slot the siege tower used): an armoured cab, a tracked rear and an open troop compartment.
    pose = 2 * (men aboard, 0..3) + (1 while a gunner is firing): the men show as helmets over the side, the top one
    behind a pintle machine gun that flashes when he fires."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    manned, firing = max(0, min(3, pose // 2)), pose % 2
    s = blank(42, 24)
    pygame.draw.rect(s, vd, (4, 13, 36, 6))                                      # the chassis
    if style == "allies":                                                        # a long hood and an open box body
        pygame.draw.polygon(s, v, [(28, 9), (40, 11), (40, 15), (28, 15)])        # the hood
        pygame.draw.line(s, vl, (28, 9), (39, 11))
        pygame.draw.rect(s, v, (3, 6, 26, 9))                                     # the troop box
        pygame.draw.rect(s, vl, (3, 6, 26, 1))
        pygame.draw.rect(s, _w(white, METALD), (24, 3, 1, 4))                     # the windscreen
    else:                                                                         # an angular Sd.Kfz-style body
        pygame.draw.polygon(s, v, [(3, 5), (28, 5), (31, 9), (40, 11), (40, 15), (3, 15)])
        pygame.draw.line(s, vl, (3, 5), (28, 5))
        pygame.draw.line(s, vl, (28, 5), (31, 9))
        pygame.draw.line(s, vd, (3, 10), (30, 10))
        pygame.draw.rect(s, _w(white, (24, 24, 28)), (16, 12, 1, 0))
    for gx in range(8 if manned else 99, 26, 6):                                  # the men aboard
        if (gx - 8) // 6 >= manned:
            break
        pygame.draw.rect(s, _w(white, SKIN), (gx, 3, 3, 2))
        pygame.draw.rect(s, _w(white, lk["helm"]), (gx - 1, 1, 5, 2))
        s.set_at((gx + 2, 4), _w(white, INK))
    if manned:                                                                    # the pintle machine gun on the cab
        pygame.draw.line(s, _w(white, METALD), (24, 4), (31, 2), 2)
        if firing:
            pygame.draw.rect(s, _w(white, (255, 236, 150)), (32, 1, 3, 2))
            s.set_at((35, 1), _w(white, (255, 190, 70)))
    _mark(s, style, 14, 10, white)
    pygame.draw.rect(s, _w(white, tuple(color)), (4, 7, 3, 2))                    # a colour patch on the tail
    pygame.draw.circle(s, _w(white, TIRE), (35, 17), 4)                           # the front wheel
    pygame.draw.circle(s, _w(white, HUB), (35, 17), 2)
    pygame.draw.rect(s, _w(white, (36, 36, 40)), (4, 15, 26, 6))                  # the rear tracks
    for wx in range(7, 30, 5):
        pygame.draw.circle(s, _w(white, (66, 66, 72)), (wx, 18), 2)
    for tx in range(5 + (pose % 2) * 2, 30, 4):
        s.set_at((tx, 15), _w(white, (88, 88, 94)))
    pygame.draw.line(s, _w(white, METAL), (5, 5), (3, 0))                         # antenna and pennant
    pygame.draw.polygon(s, _w(white, tuple(color)), [(3, 0), (7, 1), (3, 3)])
    return outlined(s)


# ---------------------------------------------------------------------------------------------- guns
def _gun_wheel(s, cx, cy, r, white):
    pygame.draw.circle(s, _w(white, (40, 38, 38)), (cx, cy), r)
    pygame.draw.circle(s, _w(white, (110, 100, 86)), (cx, cy), r - 1)
    pygame.draw.circle(s, _w(white, (60, 56, 52)), (cx, cy), max(1, r - 3))
    pygame.draw.line(s, _w(white, (40, 38, 38)), (cx - r + 1, cy), (cx + r - 1, cy))
    pygame.draw.line(s, _w(white, (40, 38, 38)), (cx, cy - r + 1), (cx, cy + r - 1))


RECOIL = (0, 3, 3, 2, 1, 1)


def _flash(s, x, y, pose, white):
    if 1 <= pose <= 2:
        pygame.draw.circle(s, _w(white, (255, 190, 70)), (x, y), 3 if pose == 1 else 2)
        pygame.draw.circle(s, _w(white, (255, 240, 170)), (x, y), 1)
    elif pose == 3:
        pygame.draw.circle(s, _w(white, (120, 116, 112)), (x + 1, y - 1), 2)


def catapult(color, white=False, pose=0, style=""):
    """A field gun on a split trail (Allies), or a six-tube rocket launcher on a carriage (Axis). The barrel kicks
    back as it fires and flashes at the muzzle."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(40, 24)
    rec = RECOIL[max(0, min(5, pose))]
    pygame.draw.line(s, vd, (3, 20), (17, 15), 2)                                # the trail legs, spread behind
    pygame.draw.line(s, vd, (1, 18), (17, 14), 2)
    pygame.draw.rect(s, _w(white, METALD), (0, 19, 4, 2))                        # their spades
    if style == "allies":
        pygame.draw.line(s, _w(white, METALD), (15 - rec, 14), (35 - rec, 9), 3)  # the barrel
        pygame.draw.line(s, _w(white, METAL), (15 - rec, 13), (35 - rec, 8))
        pygame.draw.rect(s, _w(white, METALD), (33 - rec, 7, 3, 4))                # the muzzle brake
        pygame.draw.rect(s, vd, (13, 14, 6, 4))                                    # the breech and cradle
        pygame.draw.polygon(s, v, [(19, 7), (23, 7), (24, 17), (19, 17)])          # the gun shield
        pygame.draw.line(s, vl, (19, 7), (23, 7))
        pygame.draw.rect(s, _w(white, tuple(color)), (20, 9, 3, 2))                # the side's colour on the shield
        _flash(s, 38 - rec, 8, pose, white)
    else:
        for i in range(6):                                                         # six tubes in two rows
            ox, oy = (i % 3) * 2, (i // 3) * 3
            pygame.draw.line(s, _w(white, METALD), (14 + ox - rec, 12 - oy), (31 + ox - rec, 6 - oy), 2)
            pygame.draw.line(s, _w(white, METAL), (14 + ox - rec, 11 - oy), (31 + ox - rec, 5 - oy))
        pygame.draw.rect(s, vd, (12, 12, 8, 5))                                    # the cradle
        pygame.draw.rect(s, _w(white, tuple(color)), (13, 13, 3, 2))
        if 1 <= pose <= 3:                                                         # rockets leaving in a trail of fire
            for k in range(3):
                pygame.draw.line(s, _w(white, (255, 190, 70)), (33 + k * 2, 5 - k), (39, 2 - k))
            pygame.draw.circle(s, _w(white, (255, 240, 170)), (33, 5), 2)
    _gun_wheel(s, 15, 18, 4, white)
    s.fill((0, 0, 0, 0), pygame.Rect(0, 22, 40, 2))
    _mark(s, style, 21, 14, white) if style == "axis" else None
    return outlined(s)


def trebuchet(color, white=False, pose=0, style=""):
    """A heavy howitzer: a long elevated barrel on a big box trail, a wide shield, two wheels, a stack of shells. It
    recoils on its cradle when it fires."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(52, 34)
    rec = RECOIL[max(0, min(5, pose))]
    pygame.draw.line(s, vd, (2, 30), (24, 22), 3)                                # the box trail, planted behind
    pygame.draw.line(s, vd, (0, 27), (24, 21), 3)
    pygame.draw.rect(s, _w(white, METALD), (0, 29, 5, 3))
    ang = math.radians(32)
    bx, by = 22 - rec, 20                                                         # the trunnion
    ex, ey = round(bx + 28 * math.cos(ang)), round(by - 28 * math.sin(ang))
    pygame.draw.line(s, _w(white, METALD), (bx, by), (ex, ey), 4)                # the barrel
    pygame.draw.line(s, _w(white, METAL), (bx, by - 1), (ex, ey - 1), 1)
    pygame.draw.rect(s, vd, (bx - 6, by - 2, 8, 6))                               # the breech
    pygame.draw.line(s, _w(white, METALD), (bx + 8, by + 3), (bx + 17, by - 5), 2)  # the recuperator
    pygame.draw.polygon(s, v, [(26, 12), (31, 12), (32, 27), (26, 27)])           # the shield
    pygame.draw.line(s, vl, (26, 12), (31, 12))
    pygame.draw.rect(s, _w(white, tuple(color)), (27, 15, 4, 2))
    _flash(s, ex + 1, ey - 1, pose, white)
    _gun_wheel(s, 24, 27, 5, white)
    for sx in (36, 40):                                                           # shells stacked beside the gun
        pygame.draw.rect(s, _w(white, (190, 160, 70)), (sx, 28, 3, 5))
        pygame.draw.rect(s, _w(white, (86, 86, 92)), (sx, 28, 3, 2))
    _mark(s, style, 28, 22, white) if style == "axis" else None
    return outlined(s)


def mangonel(color, white=False, pose=0, style=""):
    """A mortar: a baseplate, a short smooth tube at a steep angle held by a bipod, a crate of bombs. Smoke and a
    flash puff from the muzzle when it fires."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(34, 28)
    rec = (0, 2, 2, 1, 1, 0)[max(0, min(5, pose))]
    pygame.draw.ellipse(s, _w(white, METALD), (6, 21, 12, 4))                     # the baseplate
    ang = math.radians(72)
    bx, by = 11, 22 + rec
    ex, ey = round(bx + 17 * math.cos(ang)), round(by - 17 * math.sin(ang))
    pygame.draw.line(s, _w(white, METALD), (bx, by), (ex, ey), 3)                # the tube
    pygame.draw.line(s, _w(white, METAL), (bx, by - 1), (ex, ey - 1))
    pygame.draw.rect(s, _w(white, METAL), (ex - 2, ey - 1, 5, 2))                  # the muzzle ring
    pygame.draw.line(s, _w(white, METALD), (ex - 2, ey + 6), (4, 25))             # the bipod legs
    pygame.draw.line(s, _w(white, METALD), (ex + 1, ey + 6), (19, 25))
    pygame.draw.rect(s, v, (22, 19, 9, 6))                                         # a crate of bombs
    pygame.draw.rect(s, vl, (22, 19, 9, 1))
    pygame.draw.rect(s, vd, (22, 22, 9, 1))
    for bx2 in (24, 27):
        pygame.draw.rect(s, _w(white, (190, 160, 70)), (bx2, 17, 2, 3))
    pygame.draw.rect(s, _w(white, tuple(color)), (23, 20, 3, 2))
    if 1 <= pose <= 3:                                                              # the flash and the smoke
        pygame.draw.circle(s, _w(white, (255, 214, 120)), (ex, ey - 2), 3 if pose == 1 else 2)
        pygame.draw.circle(s, _w(white, (190, 188, 184)), (ex + 1, ey - 5 - pose), 2)
    return outlined(s)


def ballista(color, white=False, pose=0, style=""):
    """A flak gun, the air-only gun: a cruciform platform, a slender barrel pointed high at the sky, a small shield and
    a seat. The barrel kicks as it fires and flashes at the muzzle."""
    style = style or side_of(color)
    lk = _look(style)
    v, vd, vl = _w(white, lk["veh"]), _w(white, lk["vehd"]), _w(white, lk["vehl"])
    s = blank(34, 30)
    rec = RECOIL[max(0, min(5, pose))]
    pygame.draw.rect(s, vd, (3, 24, 28, 3))                                        # the cruciform platform
    pygame.draw.rect(s, vd, (14, 22, 6, 4))
    for ox in (1, 29):
        pygame.draw.rect(s, _w(white, METALD), (ox, 25, 4, 3))                      # outriggers
    pygame.draw.rect(s, v, (12, 15, 10, 8))                                          # the mounting
    pygame.draw.rect(s, vl, (12, 15, 10, 1))
    ang = math.radians(66)
    bx, by = 17, 16
    ex, ey = round(bx + (22 - rec) * math.cos(ang)), round(by - (22 - rec) * math.sin(ang))
    pygame.draw.line(s, _w(white, METALD), (bx, by), (ex, ey), 3)                    # the barrel, up at the sky
    pygame.draw.line(s, _w(white, METAL), (bx - 1, by), (ex - 1, ey))
    pygame.draw.rect(s, _w(white, METALD), (ex - 1, ey - 1, 3, 3))                    # the muzzle brake
    pygame.draw.polygon(s, v, [(18, 11), (24, 13), (24, 21), (18, 20)])              # the shield
    pygame.draw.rect(s, _w(white, tuple(color)), (19, 14, 4, 2))
    pygame.draw.rect(s, _w(white, (60, 56, 52)), (9, 17, 4, 3))                       # the gunner's seat
    _flash(s, ex, ey - 2, pose, white)
    _mark(s, style, 17, 20, white) if style == "axis" else None
    return outlined(s)
