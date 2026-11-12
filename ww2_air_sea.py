"""WW2 aircraft and ships for Pixel BS. Aircraft keep the four flyer slots (wyvern = dive bomber, hawk = fighter,
griffon = heavy fighter, harpy = ground-attack strafer); ships keep the four ship slots (longship = torpedo boat,
galley = gunboat, catapult_ship = cruiser, landing_boat = landing craft). The side picks the shape and markings: the
Allies fly silver and olive with blue roundels, the Axis fly grey-green with black crosses and yellow noses. Aircraft
take (color, white, frame): frame 0..2 spins the propeller and rocks the wings. Ships take (color, white, frame), and
the cruiser's `frame` is its gun recoil pose. Everything faces right."""
import math

import pygame

from ww2_art import INK, LOOK, METAL, METALD, SKIN, _w, blank, outlined, shade, side_of

GLASS = (150, 196, 214)
YELLOW = (230, 196, 62)


def _roundel(s, style, x, y, white=False):
    """The national marking on a fuselage side: a blue disc with a white star dot, or a black cross edged white."""
    if white:
        s.set_at((x, y), (255, 255, 255))
        return
    if style == "allies":
        pygame.draw.circle(s, (240, 240, 244), (x, y), 2)
        pygame.draw.circle(s, (42, 74, 160), (x, y), 1)
    else:
        pygame.draw.rect(s, (240, 240, 244), (x - 2, y - 2, 5, 5))
        pygame.draw.rect(s, (24, 24, 28), (x - 1, y - 2, 3, 5))
        pygame.draw.rect(s, (24, 24, 28), (x - 2, y - 1, 5, 3))


def _prop(s, x, y, r, frame, white):
    """A spinning propeller: a blurred disc edge-on, its blades alternating with the frame."""
    col = _w(white, (214, 214, 220))
    pygame.draw.line(s, col, (x, y - r), (x, y + r))
    if frame % 3 == 1:
        pygame.draw.line(s, _w(white, (120, 120, 126)), (x - 1, y - r + 1), (x - 1, y + r - 1))
    elif frame % 3 == 2:
        pygame.draw.line(s, _w(white, (120, 120, 126)), (x + 1, y - r + 1), (x + 1, y + r - 1))


def _tail(s, col, hi, pts):
    pygame.draw.polygon(s, col, pts)
    pygame.draw.line(s, hi, pts[0], pts[1])


def _wing(s, col, dark, x, y, length, sweep=3, drop=1):
    """A wing seen from just below the plane: a slanted slab starting at the fuselage."""
    pygame.draw.polygon(s, col, [(x, y), (x + length, y), (x + length - sweep, y + 3 + drop), (x - sweep, y + 3 + drop)])
    pygame.draw.line(s, dark, (x - sweep, y + 3 + drop), (x + length - sweep, y + 3 + drop))


def wyvern(color, white=False, frame=0):
    """The dive bomber: the Allies' Dauntless (straight blue-grey wings, white belly) or the Axis' Stuka (inverted
    gull wings, fixed spats, a yellow nose). A bomb hangs under the belly."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    s = blank(30, 18)
    ty = (0, 1, 2)[frame % 3]
    if st == "allies":
        top, belly, dark = (64, 90, 134), (214, 220, 228), (40, 60, 96)
    else:
        top, belly, dark = (74, 92, 72), (150, 172, 188), (46, 58, 48)
    pygame.draw.polygon(s, c(top), [(2, 6), (8, 5), (22, 5), (27, 7), (27, 10), (22, 11), (8, 11), (2, 8)])       # the fuselage
    pygame.draw.polygon(s, c(belly), [(6, 10), (24, 10), (21, 11), (8, 11)])
    _tail(s, c(top), c(dark), [(2, 6), (1, 1), (5, 1), (7, 6)])                                                  # fin
    pygame.draw.rect(s, c(dark), (0, 7 + ty // 2, 7, 1))                                                          # tailplane
    pygame.draw.polygon(s, c(GLASS), [(12, 5), (15, 2), (19, 2), (20, 5)])                                       # the glazed canopy
    pygame.draw.line(s, c(dark), (16, 2), (16, 5))
    if st == "allies":
        _wing(s, c(top), c(dark), 11, 8, 11, sweep=2)
    else:
        pygame.draw.polygon(s, c(top), [(11, 8), (22, 8), (20, 11 + ty // 2), (16, 11), (10, 10)])                # an inverted gull
        pygame.draw.line(s, c(dark), (10, 10), (20, 11 + ty // 2))
        for sx in (13, 19):                                                                                        # fixed wheel spats
            pygame.draw.rect(s, c(top), (sx, 11, 3, 4))
            pygame.draw.rect(s, c((30, 30, 34)), (sx, 14, 3, 1))
        pygame.draw.rect(s, c(YELLOW), (24, 6, 3, 4))                                                              # the yellow nose
    pygame.draw.rect(s, c((60, 62, 66)), (11, 12, 8, 2))                                                           # the bomb ...
    pygame.draw.polygon(s, c((60, 62, 66)), [(19, 12), (21, 13), (19, 14)])
    pygame.draw.line(s, c((226, 190, 70)), (11, 12), (11, 14))                                                    # ... and its fins
    _roundel(s, st, 5, 8, white)
    pygame.draw.rect(s, c(tuple(color)), (1, 2, 3, 2))                                                            # the side's tail colour
    _prop(s, 28, 8, 3, frame, white)
    return outlined(s)


def hawk(color, white=False, frame=0):
    """The fighter: the Allies' silver Mustang (bubble canopy, long nose) or the Axis' grey-green Messerschmitt
    (angular tail, a yellow nose and a black cross)."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    s = blank(28, 14)
    ty = (0, 1, 2)[frame % 3]
    if st == "allies":
        top, belly, dark = (176, 184, 192), (222, 226, 230), (110, 118, 128)
    else:
        top, belly, dark = (92, 110, 96), (150, 170, 184), (52, 64, 56)
    pygame.draw.polygon(s, c(top), [(1, 5), (8, 4), (20, 4), (26, 6), (26, 8), (20, 9), (8, 9), (1, 7)])
    pygame.draw.polygon(s, c(belly), [(5, 8), (22, 8), (19, 9), (7, 9)])
    if st == "allies":
        _tail(s, c(top), c(dark), [(1, 5), (0, 0), (4, 0), (6, 5)])
        pygame.draw.polygon(s, c(GLASS), [(10, 4), (12, 1), (17, 1), (18, 4)])                                   # a bubble canopy
        pygame.draw.rect(s, c((200, 40, 40)), (21, 5, 5, 2))                                                      # a red nose
    else:
        _tail(s, c(top), c(dark), [(1, 5), (1, 0), (5, 0), (6, 5)])
        pygame.draw.polygon(s, c(GLASS), [(10, 4), (12, 1), (16, 1), (18, 4)])
        pygame.draw.rect(s, c(YELLOW), (23, 5, 3, 3))                                                              # the yellow nose
    pygame.draw.rect(s, c(dark), (0, 6 + ty // 2, 6, 1))
    _wing(s, c(top), c(dark), 10, 7, 9, sweep=2)
    _roundel(s, st, 6, 6, white)
    _prop(s, 27, 6, 3, frame, white)
    return outlined(s)


def griffon(color, white=False, frame=0):
    """The heavy fighter: the Allies' barrel-bodied Thunderbolt or the Axis' radial-engined Focke-Wulf, with
    wing-mounted guns."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    s = blank(32, 17)
    ty = (0, 1, 2)[frame % 3]
    if st == "allies":
        top, belly, dark = (96, 110, 72), (190, 196, 192), (60, 72, 46)
    else:
        top, belly, dark = (96, 106, 112), (156, 172, 184), (58, 66, 72)
    if st == "allies":
        pygame.draw.ellipse(s, c(top), (4, 4, 26, 9))                                                              # a fat barrel of a fuselage
        pygame.draw.ellipse(s, c(belly), (8, 9, 18, 4))
        pygame.draw.circle(s, c(dark), (28, 8), 4)                                                                 # the big round cowl
        pygame.draw.circle(s, c((120, 130, 138)), (28, 8), 3)
        pygame.draw.line(s, c((58, 58, 62)), (25, 8), (28, 5))
    else:
        pygame.draw.polygon(s, c(top), [(3, 6), (10, 5), (22, 5), (27, 7), (27, 11), (22, 12), (10, 12), (3, 9)])
        pygame.draw.polygon(s, c(belly), [(7, 11), (24, 11), (21, 12), (9, 12)])
        pygame.draw.circle(s, c((40, 40, 44)), (27, 9), 3)                                                          # the radial cowling
        pygame.draw.circle(s, c(YELLOW), (28, 9), 1)
    _tail(s, c(top), c(dark), [(3, 6), (1, 0), (6, 0), (8, 6)])
    pygame.draw.rect(s, c(dark), (0, 8 + ty // 2, 6, 1))
    pygame.draw.polygon(s, c(GLASS), [(12, 5), (15, 2), (20, 2), (21, 5)])
    _wing(s, c(top), c(dark), 11, 9, 12, sweep=3)
    pygame.draw.line(s, c(METALD), (18, 12), (24, 12))                                                              # a wing gun
    _roundel(s, st, 7, 8, white)
    pygame.draw.rect(s, c(tuple(color)), (2, 1, 3, 2))
    _prop(s, 31, 8, 4, frame, white)
    return outlined(s)


def harpy(color, white=False, frame=0):
    """The ground-attack strafer: the Allies' rocket-armed Typhoon (black-and-white invasion stripes) or the Axis'
    twin-engined Henschel (a boxy, glazed nose and two engines)."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    s = blank(30, 15)
    ty = (0, 1, 2)[frame % 3]
    if st == "allies":
        top, belly, dark = (112, 120, 84), (180, 186, 180), (70, 78, 50)
        pygame.draw.polygon(s, c(top), [(1, 5), (8, 4), (20, 4), (27, 6), (27, 9), (20, 10), (8, 10), (1, 7)])
        pygame.draw.polygon(s, c(belly), [(5, 9), (22, 9), (19, 10), (7, 10)])
        _tail(s, c(top), c(dark), [(1, 5), (0, 0), (4, 0), (6, 5)])
        pygame.draw.polygon(s, c(GLASS), [(10, 4), (12, 1), (17, 1), (18, 4)])
        for sx in (2, 3, 6, 7):                                                                                     # invasion stripes
            pygame.draw.line(s, c((236, 236, 240) if sx % 2 else (30, 30, 34)), (sx + 3, 5), (sx + 3, 9))
        _wing(s, c(top), c(dark), 10, 8, 11, sweep=2)
        for rx in (13, 18):                                                                                         # rockets under the wing
            pygame.draw.rect(s, c((60, 60, 64)), (rx, 12, 4, 1))
            s.set_at((rx + 4, 12), c((200, 40, 40)))
        _prop(s, 28, 7, 4, frame, white)
    else:
        top, belly, dark = (126, 118, 82), (150, 168, 176), (78, 72, 50)
        pygame.draw.polygon(s, c(top), [(2, 5), (9, 4), (20, 4), (26, 6), (26, 9), (20, 10), (9, 10), (2, 8)])
        pygame.draw.polygon(s, c(belly), [(6, 9), (22, 9), (19, 10), (8, 10)])
        _tail(s, c(top), c(dark), [(2, 5), (1, 0), (5, 0), (7, 5)])
        pygame.draw.polygon(s, c(GLASS), [(19, 4), (21, 3), (25, 5), (25, 7), (20, 7)])                            # the cramped nose cockpit
        _wing(s, c(top), c(dark), 10, 8, 12, sweep=3)
        for ex in (14, 20):                                                                                         # two engine nacelles on the wing
            pygame.draw.ellipse(s, c(dark), (ex - 2, 10, 7, 4))
            _prop(s, ex + 5, 12, 2, frame, white)
        pygame.draw.rect(s, c(YELLOW), (1, 9, 2, 1))
    _roundel(s, st, 7, 7, white)
    pygame.draw.rect(s, c(tuple(color)), (1, 2, 3, 2))
    return outlined(s)


# ---------------------------------------------------------------------------------------------- ships
HULL = {"allies": ((150, 158, 162), (102, 110, 116), (196, 204, 208)), "axis": ((100, 108, 116), (66, 72, 80), (140, 148, 156))}


def _hull(s, st, pts, white, deck_y=None):
    base, dark, light = (_w(white, k) for k in HULL[st])
    pygame.draw.polygon(s, base, pts)
    top = min(p[1] for p in pts)
    bot = max(p[1] for p in pts)
    for y in range(top + 3, bot, 3):                                                                                 # plate seams
        xs = [p[0] for p in pts]
        pygame.draw.line(s, dark, (min(xs) + 3 + (y - top) // 2, y), (max(xs) - 3 - (y - top) // 2, y))
    pygame.draw.line(s, light, pts[0], pts[-1]) if False else None
    return base, dark, light


def _sailor(s, x, y, st, white, tilt=0):
    lk = LOOK[st]
    pygame.draw.rect(s, _w(white, lk["helm"]), (x - 1, y, 4, 2))
    pygame.draw.rect(s, _w(white, SKIN), (x, y + 2, 2, 1))


def _gunpos(s, x, y, white, ang=20, ln=5, col=METALD):
    """A small gun on a deck: a round tub and a barrel raised at `ang` degrees."""
    pygame.draw.rect(s, _w(white, (70, 74, 80)), (x - 2, y, 5, 3))
    ex, ey = round(x + ln * math.cos(math.radians(ang))), round(y + 1 - ln * math.sin(math.radians(ang)))
    pygame.draw.line(s, _w(white, col), (x, y + 1), (ex, ey), 2)


def longship(color, white=False, frame=0):
    """A torpedo boat: the Allies' PT boat (a short, high-sided plywood hull, a doghouse, torpedo tubes angled out and
    a twin machine-gun turret) or the Axis' long, slim E-boat (a flak gun aft and a torpedo tube forward)."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    s = blank(46, 24)
    if st == "allies":
        pts = [(2, 12), (36, 12), (45, 10), (40, 19), (30, 22), (7, 22), (3, 18)]
    else:
        pts = [(1, 13), (34, 13), (46, 9), (42, 19), (31, 22), (6, 22), (2, 18)]
    base, dark, light = _hull(s, st, pts, white)
    pygame.draw.line(s, c(light), pts[0], pts[1])
    pygame.draw.rect(s, c(tuple(color)), (3, 13, 38, 1))                                          # a stripe in the side's colour
    # the superstructure
    if st == "allies":
        pygame.draw.rect(s, c(dark), (15, 6, 11, 7))                                              # the doghouse
        pygame.draw.rect(s, c(base), (16, 7, 9, 5))
        pygame.draw.rect(s, c((120, 170, 196)), (22, 8, 3, 2))
        for ty, x0 in ((9, 4), (11, 27)):                                                         # torpedo tubes on the deck
            pygame.draw.line(s, c(METALD), (x0, ty + 2), (x0 + 9, ty - 1), 3)
        _gunpos(s, 33, 9, white, 25, 5)
        _gunpos(s, 7, 9, white, 20, 4)
    else:
        pygame.draw.rect(s, c(dark), (18, 7, 9, 6))
        pygame.draw.rect(s, c(base), (19, 8, 7, 4))
        pygame.draw.rect(s, c((120, 170, 196)), (23, 9, 3, 2))
        pygame.draw.line(s, c(METALD), (33, 12), (42, 10), 3)                                     # a torpedo tube at the bow
        _gunpos(s, 8, 9, white, 55, 6)                                                            # flak aft
    for sx in (11, 29, 33):
        _sailor(s, sx, 7 if sx < 20 else 8, st, white)
    pygame.draw.line(s, c(METAL), (20, 6), (20, 1))                                               # a mast and the side's ensign
    pygame.draw.polygon(s, c(tuple(color)), [(20, 1), (25, 2 + frame % 2), (20, 4)])
    return outlined(s)


def galley(color, white=False, frame=0):
    """A gunboat: a broad hull with a deck gun forward under a shield, a bridge, a funnel and light flak guns aft."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    s = blank(52, 28)
    pts = [(1, 14), (44, 14), (50, 11), (46, 22), (36, 26), (8, 26), (3, 21)]
    base, dark, light = _hull(s, st, pts, white)
    pygame.draw.line(s, c(light), pts[0], pts[1])
    pygame.draw.rect(s, c(tuple(color)), (3, 15, 42, 2))
    pygame.draw.rect(s, c(dark), (14, 7, 14, 8))                                                  # the bridge
    pygame.draw.rect(s, c(base), (15, 8, 12, 6))
    pygame.draw.rect(s, c((120, 170, 196)), (21, 9, 5, 2))
    pygame.draw.rect(s, c(dark), (28, 2, 5, 9))                                                   # the funnel, with its band
    pygame.draw.rect(s, c(tuple(color)), (28, 4, 5, 1))
    pygame.draw.circle(s, c((90, 90, 96)), (31, 1), 2)                                            # a puff of smoke
    pygame.draw.rect(s, c((70, 74, 80)), (36, 9, 8, 5))                                           # the deck gun's shield
    pygame.draw.line(s, c(METALD), (41, 10), (50, 7), 3)                                          # the deck gun
    pygame.draw.line(s, c(METAL), (41, 9), (50, 6))
    _gunpos(s, 7, 12, white, 50, 5)                                                               # flak aft
    _gunpos(s, 12, 12, white, 45, 5)
    for sx in (31, 18, 4):
        _sailor(s, sx, 11 if sx > 20 else 9, st, white)
    pygame.draw.line(s, c(METAL), (22, 7), (22, 1))
    pygame.draw.polygon(s, c(tuple(color)), [(22, 1), (28, 2 + frame % 2), (22, 5)])
    return outlined(s)


def catapult_ship(color, white=False, pose=0):
    """A cruiser: a long grey hull with a raised bow, a tall bridge with a rangefinder, two funnels, and turrets of
    heavy guns fore and aft. pose is the gun recoil: 1 and 2 flash at the muzzle, then the barrels slide back out."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    s = blank(66, 34)
    pts = [(1, 18), (46, 18), (59, 13), (54, 26), (44, 30), (8, 30), (3, 25)]
    base, dark, light = _hull(s, st, pts, white)
    pygame.draw.line(s, c(light), pts[0], pts[1])
    pygame.draw.rect(s, c(tuple(color)), (3, 19, 50, 2))
    rec = (0, 3, 3, 2, 1, 1)[max(0, min(5, pose))]
    # the tall bridge and rangefinder
    pygame.draw.rect(s, c(dark), (22, 8, 9, 11))
    pygame.draw.rect(s, c(base), (23, 9, 7, 8))
    pygame.draw.rect(s, c((120, 170, 196)), (25, 10, 5, 2))
    pygame.draw.rect(s, c(METALD), (20, 6, 13, 2))                                                # the rangefinder crosspiece
    pygame.draw.line(s, c(METAL), (27, 6), (27, 0))                                               # the mast
    pygame.draw.polygon(s, c(tuple(color)), [(27, 0), (33, 1), (27, 4)])
    for fx in (13, 17):                                                                           # two funnels
        pygame.draw.rect(s, c(dark), (fx, 7, 3, 11))
        pygame.draw.rect(s, c(tuple(color)), (fx, 9, 3, 1))
        pygame.draw.circle(s, c((80, 80, 86)), (fx + 1, 6), 2)
    for tx, gx2 in ((37, 41), (47, 51)):                                                          # two forward turrets
        pygame.draw.rect(s, c(dark), (tx - 2, 12, 9, 6))
        pygame.draw.rect(s, c(base), (tx - 1, 13, 7, 4))
        for gy in (13, 15):
            pygame.draw.line(s, c(METALD), (tx + 6 - rec, gy), (tx + 15 - rec, gy - 1), 2)
    pygame.draw.rect(s, c(dark), (5, 13, 9, 6))                                                   # the aft turret
    pygame.draw.rect(s, c(base), (6, 14, 7, 4))
    pygame.draw.line(s, c(METALD), (3, 15), (-0, 15)) if False else None
    if 1 <= pose <= 2:                                                                            # muzzle flashes
        for fx, fy in ((64, 11), (54, 12)):
            pygame.draw.circle(s, c((255, 190, 70)), (fx, fy), 3)
            pygame.draw.circle(s, c((255, 240, 170)), (fx, fy), 1)
    elif pose == 3:
        pygame.draw.circle(s, c((126, 122, 118)), (60, 10), 3)
    for sx in (34, 44):
        _sailor(s, sx, 10, st, white)
    return outlined(s)


def landing_boat(color, white=False, frame=0):
    """A landing craft: a boxy open hull with a bow ramp, rows of helmets over the gunwale, a coxswain's tub aft with
    a machine gun. The Axis' version is a flat barge with a light gun."""
    st = side_of(color)
    c = lambda col: _w(white, col)
    lk = LOOK[st]
    s = blank(38, 20)
    if st == "allies":
        pts = [(1, 10), (31, 10), (37, 8), (35, 17), (28, 19), (5, 19), (2, 15)]
        hull = (92, 102, 64)
    else:
        pts = [(1, 11), (33, 11), (37, 9), (36, 17), (30, 19), (4, 19), (2, 16)]
        hull = (92, 98, 104)
    pygame.draw.polygon(s, c(hull), pts)
    pygame.draw.line(s, c(shade(hull, 1.35)), pts[0], pts[1])
    pygame.draw.line(s, c(shade(hull, 0.6)), (5, 16), (31, 16))
    pygame.draw.rect(s, c(tuple(color)), (3, 11, 28, 1))
    pygame.draw.polygon(s, c(shade(hull, 0.8)), [(31, 10), (37, 8), (37, 11), (32, 12)])           # the bow ramp
    for hx in (6, 10, 14, 18, 22):                                                                 # troops packed shoulder to shoulder
        bob = 1 if (hx // 4 + frame) % 3 == 0 else 0
        pygame.draw.rect(s, c(lk["helm"]), (hx, 5 + bob, 4, 3))
        pygame.draw.rect(s, c(SKIN), (hx + 1, 8 + bob, 2, 1))
        pygame.draw.rect(s, c(lk["uni"]), (hx, 9 + bob, 4, 2))
    pygame.draw.rect(s, c(shade(hull, 0.7)), (25, 6, 5, 5))                                        # the coxswain's tub
    pygame.draw.line(s, c(METALD), (28, 6), (32, 4), 2)                                            # its gun
    pygame.draw.line(s, c(METAL), (3, 10), (3, 4))                                                 # a flag pole aft
    pygame.draw.polygon(s, c(tuple(color)), [(3, 4), (8, 5 + frame % 2), (3, 7)])
    return outlined(s)
