"""WW2 unit art for Pixel BS: infantry, heroes and the helpers every other art module shares.

Every function keeps the signature of the sprite it replaces (see sprites.py, which re-exports these names), so the
renderer is unchanged: (color, white, frame) for soldiers, (color, style, white, frame) for heroes. The side's colour
(blue for the Allies, red for the Axis) is only an accent here (armband, helmet band, flag); the uniforms are drawn in
each side's own khaki-olive or field-grey. The renderer registers which colour belongs to which side (register_sides)
so the art can tell the two apart. Sprites face right; the renderer flips them. `white` paints everything white (the
hit flash)."""
import pygame

INK = (22, 16, 14)
SKIN = (226, 188, 148)

STYLE_OF = {}          # side colour (a tuple) -> "allies" or "axis"; filled by Renderer through register_sides()


def register_sides(styles):
    STYLE_OF.clear()
    for col, st in styles.items():
        STYLE_OF[tuple(col)] = st


def side_of(color):
    return STYLE_OF.get(tuple(color), "allies")


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


LOOK = {
    "allies": dict(uni=(112, 120, 72), unid=(76, 84, 46), unil=(152, 160, 100), helm=(100, 112, 68), helmh=(146, 158, 102),
                   helmj=(66, 76, 44), gear=(184, 166, 116), geard=(122, 106, 70), boot=(88, 62, 40), bootd=(52, 38, 26),
                   veh=(98, 110, 62), vehd=(62, 72, 40), vehl=(138, 150, 92), mark=(240, 240, 244), roundel=(42, 74, 160),
                   hull=(150, 156, 160), hulld=(104, 110, 116), hulll=(196, 202, 206)),
    "axis": dict(uni=(112, 120, 126), unid=(74, 80, 86), unil=(148, 154, 160), helm=(88, 94, 100), helmh=(128, 134, 140),
                 helmj=(54, 58, 64), gear=(58, 56, 58), geard=(32, 32, 36), boot=(38, 36, 38), bootd=(20, 20, 22),
                 veh=(110, 114, 108), vehd=(70, 74, 70), vehl=(148, 152, 144), mark=(24, 24, 28), roundel=(24, 24, 28),
                 hull=(104, 112, 120), hulld=(68, 74, 82), hulll=(142, 150, 158)),
}
METAL, METALD, WOOD, WOODL = (156, 158, 168), (62, 62, 72), (140, 100, 60), (190, 146, 90)
FLAME, FLAMEL = (255, 150, 40), (255, 226, 120)


def _w(white, col):
    return (255, 255, 255) if white else col


def blank(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def outlined(s, col=INK):
    """A copy of the sprite with a one-pixel outline all round it."""
    w, h = s.get_size()
    out = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    m = pygame.mask.from_surface(s).to_surface(setcolor=col, unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(m, (dx, dy))
    out.blit(s, (1, 1))
    return out


def pal(color, white=False):
    """Character -> colour for the character art below."""
    lk = LOOK[side_of(color)]
    acc = tuple(color)
    p = {
        "h": lk["helm"], "H": lk["helmh"], "j": lk["helmj"], "s": SKIN, "S": shade(SKIN, 0.78), "e": INK,
        "u": lk["uni"], "U": lk["unid"], "L": lk["unil"], "a": acc, "A": shade(acc, 0.6),
        "g": lk["gear"], "G": lk["geard"], "k": lk["boot"], "K": lk["bootd"],
        "m": METAL, "M": METALD, "w": WOOD, "W": WOODL, "f": FLAME, "F": FLAMEL,
        "r": (200, 40, 40), "c": (236, 234, 226), "y": (226, 190, 70), "o": (232, 140, 40),
        "n": (110, 104, 100), "d": (66, 62, 60), "q": (160, 112, 70), "z": (120, 84, 52),
        "v": lk["veh"], "V": lk["vehd"], "l": lk["vehl"],
    }
    if white:
        return {k: (255, 255, 255) for k in p}
    return p


def from_art(rows, p):
    h, w = len(rows), max(len(r) for r in rows)
    s = blank(w, h)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in p:
                s.set_at((x, y), p[ch])
    return s


def put(s, p, pts, ch):
    for x, y in pts:
        if 0 <= x < s.get_width() and 0 <= y < s.get_height():
            s.set_at((x, y), p[ch] if isinstance(ch, str) else ch)


def line(s, col, a, b, w=1):
    pygame.draw.line(s, col, a, b, w)


def dressed(style):
    return LOOK[style]


# ---------------------------------------------------------------------------------------------- soldiers
# Helmets: the Allies' round pot, the Axis' coal-scuttle with its flared neck. 11 wide, facing right.
HELM = {
    "allies": ["...hhhh....", "..hHhhhh...", "..jhhhhhj.."],
    "axis":   ["...hhhh....", "..hHhhhhj..", ".jjhhhhhj.."],
}
FACE = ["...ssse....", "...sSss...."]
TORSO = [
    ".gLuuuU....",
    ".gUuuuuU...",
    ".gGuaauU...",
    "..GgggUU...",
    "..uuuuUu...",
]
LEGS = (["...kk.kk...", "...KK.KK..."], ["...kk..kk..", "..KK...KK.."])


def _soldier(color, white, frame, helmet=True, torso=None, wounded=False, routing=False):
    p = pal(color, white)
    st = side_of(color)
    rows = (HELM[st] if helmet else ["...uuuu....", "..uuuuuu...", "...uuuu...."]) + FACE + (torso or TORSO) + LEGS[frame % 2]
    s = from_art(rows, p)
    if not helmet:                                    # bare-headed: hair and a cap
        put(s, p, [(3, 0), (4, 0), (5, 0), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1)], "z")
        put(s, p, [(3, 2), (4, 2), (5, 2), (6, 2)], "z")
    if wounded:
        put(s, p, [(3, 1), (4, 1), (5, 1)], "c")
        put(s, p, [(4, 1)], "r")
    if routing:
        put(s, p, [(1, 3), (1, 4), (0, 2)], "s")
    return s, p


def foot(color, archer=False, hero=False, white=False, frame=0, wounded=False, routing=False, variant=0):
    """A rifleman: helmet, pack, a rifle carried across the chest with its bayonet fixed. `archer` is the machine
    gunner (the renderer's name for the shooter slot)."""
    s, p = _soldier(color, white, frame, wounded=wounded, routing=routing)
    if archer:
        return machine_gunner(s, p, frame)
    bob = frame % 2
    line(s, p["w"], (3, 8), (7, 6))                                   # stock and wrist
    line(s, p["m"], (7, 6), (10, 4))                                  # barrel
    put(s, p, [(10, 3)], "c")                                         # the bayonet tip
    put(s, p, [(6, 7), (7, 7)], "s")                                  # hands
    put(s, p, [(4, 9 + bob)], "k") if False else None
    return outlined(s)


def machine_gunner(s, p, frame):
    """The light machine gun: a long barrel, a drum or belt box, a bipod, the gunner leaning into it."""
    line(s, p["M"], (4, 8), (10, 7))                                  # barrel
    line(s, p["m"], (4, 7), (9, 6))
    put(s, p, [(5, 9), (6, 9), (5, 10), (6, 10)], "d")                # the ammo box
    put(s, p, [(10, 8), (9, 9), (10, 9)], "M")                        # a bipod folded under the muzzle
    put(s, p, [(6, 6), (7, 6)], "s")
    put(s, p, [(3, 7), (4, 7)], "w")
    if frame % 2:
        put(s, p, [(11, 7)], "F")                                     # muzzle flicker while it walks and fires
    return outlined(s)


def foot_flamer(color, white=False, frame=0, wounded=False, routing=False):
    """A flamethrower trooper: a fuel tank on his back, a hose and a nozzle with a pilot flame."""
    s, p = _soldier(color, white, frame, wounded=wounded, routing=routing)
    put(s, p, [(0, 5), (1, 5), (0, 6), (1, 6), (0, 7), (1, 7), (0, 8), (1, 8)], "M")      # twin tanks on the back
    put(s, p, [(0, 5), (0, 6)], "o")
    line(s, p["M"], (2, 8), (5, 8))                                   # the hose
    line(s, p["m"], (5, 7), (9, 6))                                   # the nozzle
    put(s, p, [(6, 7), (7, 7)], "s")
    put(s, p, [(10, 6), (10, 5)], "F" if frame % 2 else "f")          # the pilot flame
    put(s, p, [(11, 5)], "o")
    return outlined(s)


def sniper(color, white=False, frame=0):
    """A sniper: a hood of netting over the helmet, a long rifle with a scope, a bedroll."""
    s, p = _soldier(color, white, frame)
    put(s, p, [(3, 0), (4, 0), (5, 0), (2, 1), (6, 1), (2, 2), (7, 2)], "G")       # the netting
    put(s, p, [(1, 4), (1, 5), (1, 6), (0, 5)], "z")                              # a bedroll
    line(s, p["w"], (2, 8), (7, 6))
    line(s, p["m"], (7, 6), (11, 5))
    put(s, p, [(6, 5), (7, 5)], "M")                                              # the scope
    put(s, p, [(6, 7), (7, 7)], "s")
    if frame % 2 == 0:
        put(s, p, [(11, 4)], "c")
    return outlined(s)


def bazooka(color, white=False, frame=0):
    """A bazooka team: the long tube rests on the shoulder, aimed ahead, and the man carries a rocket in the other
    hand. It stops tanks and armoured cars."""
    s, p = _soldier(color, white, frame)
    line(s, p["m"], (1, 6), (11, 3), 2)                               # the tube over the shoulder
    line(s, p["M"], (1, 7), (11, 4))
    put(s, p, [(11, 2), (11, 3)], "d")                                # the flared muzzle
    put(s, p, [(5, 7), (6, 7)], "s")
    put(s, p, [(1, 8), (1, 9), (0, 9)], "o")                          # a spare rocket on the back
    if frame % 2:
        put(s, p, [(0, 5)], "F")                                      # backblast
    return outlined(s)


def assault_trooper(color, white=False, frame=0):
    """An assault trooper: a knit cap and blackened face, a submachine gun with a long magazine, a knife on the
    belt. Fast, fragile and wild."""
    s, p = _soldier(color, white, frame, helmet=False)
    put(s, p, [(3, 3), (4, 3), (3, 4)], "d")                                      # face paint
    line(s, p["M"], (5, 8), (10, 7))                                              # the SMG
    put(s, p, [(7, 8), (7, 9), (7, 10)], "M")                                     # its long magazine
    put(s, p, [(4, 8), (5, 8)], "w")
    put(s, p, [(6, 6), (7, 6)], "s")
    put(s, p, [(3, 9)], "m")                                                      # a knife on the belt
    return outlined(s)


def at_rifle(color, white=False, frame=0):
    """An anti-tank rifleman behind a small steel shield: a very long rifle on a bipod, a plate with a slit, a heavy
    round that pierces armour (and shield walls)."""
    s, p = _soldier(color, white, frame)
    s2 = blank(14, 13)
    s2.blit(s, (0, 0))
    put(s2, p, [(8, 4), (9, 4), (9, 5), (9, 6), (9, 7), (9, 8), (9, 9)], "M")      # the plate's edge ...
    pygame.draw.rect(s2, p["n"], (8, 4, 3, 8))                                    # ... the steel shield
    pygame.draw.rect(s2, p["m"], (8, 4, 1, 8))
    put(s2, p, [(9, 6), (10, 6)], "d")                                            # the slit
    line(s2, p["w"], (2, 8), (7, 7))
    line(s2, p["M"], (7, 7), (13, 6))                                             # the long barrel
    put(s2, p, [(13, 7), (12, 8)], "M")                                           # bipod
    put(s2, p, [(6, 7)], "s")
    return outlined(s2)


# dogs ------------------------------------------------------------------------------------------
DOG_A = [
    ".........K.K.",
    ".........kkkK",
    "K......kkkkkse",
    "Kk.qqqqqqkkccd",
    ".kqqqqqqqAqc..",
    "..qqqqqqqqq...",
    "..k.k...q.q...",
    "..K.K...K.K...",
]
DOG_B = [
    ".........K.K.",
    ".........kkkK",
    ".K.....kkkkkse",
    "Kk.qqqqqqkkccd",
    ".kqqqqqqqAqc..",
    "..qqqqqqqqq...",
    "...kk....qq...",
    "..K..K..K..K..",
]


def war_dog(color, white=False, frame=0):
    """A war dog in a canvas harness with the side's colour on it: lean and low, ears pricked."""
    p = pal(color, white)
    s = from_art(DOG_A if frame % 2 == 0 else DOG_B, p)
    put(s, p, [(5, 3), (6, 3), (7, 3), (8, 3)], "g")                  # the harness
    return outlined(s)


def marine(color, white=False, frame=0):
    return foot(color, False, False, white, frame)


# ---------------------------------------------------------------------------------------------- heroes
# Style 0 is the Allies, style 1 the Axis. They are bigger than the rank and file, so a hero stands out in a crowd.
def champion(color, style=0, white=False, frame=0):
    """Heavy infantry: a big man in a helmet and flak vest, a drum-fed submachine gun (Allies) or a belt-fed machine
    gun slung from the hip (Axis), grenades on the chest."""
    lk = LOOK["allies" if style == 0 else "axis"]
    acc = tuple(color)
    c = lambda col: _w(white, col)
    s = blank(17, 17)
    step = frame % 2
    pygame.draw.rect(s, c(lk["bootd"]), (5 - step, 13, 3, 4))                        # legs
    pygame.draw.rect(s, c(lk["bootd"]), (9 + step, 13, 3, 4 - step))
    pygame.draw.rect(s, c(lk["unid"]), (5, 8, 8, 6))                                 # trousers and hips
    pygame.draw.rect(s, c(lk["uni"]), (4, 5, 9, 6))                                  # the chest
    pygame.draw.rect(s, c(lk["gear"]), (5, 7, 7, 2))                                 # the vest
    pygame.draw.rect(s, c(acc), (4, 5, 2, 3))                                        # an armband in the side's colour
    for gx in (7, 9, 11):                                                            # grenades on the chest
        s.set_at((gx, 7), c((52, 60, 40) if style == 0 else (84, 84, 90)))
    pygame.draw.rect(s, c(lk["helm"]), (5, 1, 7, 4))                                 # the helmet
    pygame.draw.rect(s, c(lk["helmh"]), (6, 1, 4, 1))
    if style == 1:                                                                   # the flared neck guard
        pygame.draw.rect(s, c(lk["helmj"]), (4, 4, 2, 2))
        pygame.draw.rect(s, c(lk["helmj"]), (11, 3, 1, 2))
    else:
        pygame.draw.rect(s, c(lk["helmj"]), (11, 4, 1, 1))
    pygame.draw.rect(s, c(SKIN), (8, 4, 3, 3))                                       # the face
    s.set_at((10, 5), c(INK))
    pygame.draw.rect(s, c((226, 190, 70)), (7, 2, 1, 1))                             # a gold star or badge
    if style == 0:
        pygame.draw.line(s, c(METALD), (7, 9), (15, 7), 2)                           # the SMG
        pygame.draw.rect(s, c((120, 84, 52)), (5, 9, 3, 2))                          # its stock
        pygame.draw.circle(s, c(METAL), (10, 11), 2)                                 # the drum magazine
        s.set_at((16, 7), c(METAL))
    else:
        pygame.draw.line(s, c(METALD), (6, 9), (16, 8), 2)                           # the machine gun
        pygame.draw.line(s, c(METAL), (10, 10), (13, 14))                            # its bipod
        pygame.draw.line(s, c(METAL), (14, 10), (14, 14))
        for bx in range(3, 8):                                                       # the ammunition belt
            s.set_at((bx, 10 + bx % 2), c((226, 190, 70)))
    pygame.draw.rect(s, c(SKIN), (10, 8, 2, 2))
    return outlined(s)


def commander(color, style=0, white=False, frame=0):
    """A commander in a command car: an officer standing in the open car behind the windscreen, a whip antenna and a
    big pennant flying. Style 0 is an Allied jeep, style 1 an Axis staff car."""
    from ww2_vehicles import car
    lk = LOOK["allies" if style == 0 else "axis"]
    c = lambda col: _w(white, col)
    s = blank(26, 26)
    s.blit(car(color, white, frame, "allies" if style == 0 else "axis", crew=False), (2, 10))
    sway = frame % 2
    pygame.draw.rect(s, c(lk["uni"]), (11, 6, 5, 8))                                 # the officer's body
    pygame.draw.rect(s, c(lk["unid"]), (11, 10, 5, 1))
    pygame.draw.rect(s, c(SKIN), (12, 3, 3, 3))                                      # his face
    s.set_at((14, 4), c(INK))
    pygame.draw.rect(s, c(lk["helm"]), (11, 1, 5, 3))                                # the cap or helmet
    pygame.draw.rect(s, c((226, 190, 70)), (12, 3, 3, 1))                            # a gold cap band
    pygame.draw.line(s, c(SKIN), (15, 8), (18, 6))                                   # his arm raised, pointing the way
    pygame.draw.line(s, c(METAL), (22, 12), (22 + 1, 0))                             # the whip antenna
    pygame.draw.line(s, c((150, 110, 64)), (7, 12), (7, 1))                          # the flag pole
    pygame.draw.polygon(s, c(tuple(color)), [(7, 1), (13, 2 + sway), (13, 6 + sway), (7, 6)])
    pygame.draw.line(s, c((226, 190, 70)), (7, 1), (13, 2 + sway))
    return outlined(s)


def ranger(color, style=0, white=False, frame=0):
    """A sharpshooter in a boonie hat with a long scoped rifle (style 0, the Allies' Wren) or a flamethrower with a
    fuel tank and a roaring jet (style 1, the Axis' Sable)."""
    lk = LOOK["allies" if style == 0 else "axis"]
    c = lambda col: _w(white, col)
    s = blank(18, 17)
    step = frame % 2
    pygame.draw.rect(s, c(lk["bootd"]), (4 - step, 13, 2, 4))
    pygame.draw.rect(s, c(lk["bootd"]), (7 + step, 13, 2, 4 - step))
    pygame.draw.polygon(s, c(lk["uni"]), [(4, 5), (10, 5), (11, 14), (3, 14)])       # coat
    pygame.draw.rect(s, c(lk["unid"]), (3, 12, 9, 2))
    pygame.draw.rect(s, c(tuple(color)), (4, 6, 2, 3))                               # armband
    pygame.draw.rect(s, c(lk["gear"]), (4, 10, 7, 1))                                # belt
    pygame.draw.rect(s, c(SKIN), (6, 3, 4, 3))                                       # face
    s.set_at((9, 4), c(INK))
    pygame.draw.polygon(s, c(lk["helm"]), [(4, 3), (12, 3), (10, 0), (6, 0)])        # hat / helmet
    pygame.draw.line(s, c(lk["helmj"]), (4, 3), (12, 3))
    if style == 0:
        pygame.draw.line(s, c((120, 84, 52)), (3, 10), (9, 8), 2)                    # stock
        pygame.draw.line(s, c(METALD), (9, 8), (17, 6))                              # the long barrel
        pygame.draw.rect(s, c(METAL), (9, 6, 3, 2))                                  # the scope
        s.set_at((17, 6), c(METAL))
        pygame.draw.rect(s, c(SKIN), (8, 8, 2, 2))
        pygame.draw.circle(s, c(lk["uni"]), (2, 9), 2)                               # a rolled blanket
    else:
        pygame.draw.rect(s, c((84, 84, 90)), (1, 4, 3, 8))                           # the fuel tank
        pygame.draw.rect(s, c((226, 140, 40)), (1, 4, 3, 1))
        pygame.draw.line(s, c(METALD), (3, 9), (10, 9))                              # the hose
        pygame.draw.line(s, c(METAL), (10, 8), (14, 7), 2)                           # the nozzle
        pygame.draw.rect(s, c(SKIN), (9, 8, 2, 2))
        for k in range(4):                                                           # the jet of flame
            s.set_at((15 + k % 3, 6 + k % 2), c(FLAMEL if k % 2 else FLAME))
        s.set_at((14, 6), c(FLAME))
    return outlined(s)


def mage(color, style=0, white=False, frame=0):
    """A medic (style 0): helmet with a red cross, a satchel with a cross, a cup of morphine and a flare gun. Or a
    spotter (style 1): peaked cap, radio on his back with a whip antenna, binoculars."""
    lk = LOOK["allies" if style == 0 else "axis"]
    c = lambda col: _w(white, col)
    s = blank(17, 18)
    sway = frame % 2
    pygame.draw.rect(s, c(lk["bootd"]), (5, 14, 2, 4))
    pygame.draw.rect(s, c(lk["bootd"]), (8, 14, 2, 4 - sway))
    pygame.draw.polygon(s, c(lk["uni"]), [(4, 6), (10, 6), (11, 15), (3, 15)])
    pygame.draw.rect(s, c(lk["unid"]), (4, 11, 7, 1))
    pygame.draw.rect(s, c(SKIN), (6, 3, 4, 3))
    s.set_at((9, 4), c(INK))
    if style == 0:
        pygame.draw.rect(s, c(lk["helm"]), (5, 0, 6, 4))                             # the medic's helmet, white panel
        pygame.draw.rect(s, c((236, 234, 226)), (7, 1, 3, 2))
        s.set_at((8, 1), c((200, 40, 40)))
        s.set_at((8, 2), c((200, 40, 40)))
        pygame.draw.rect(s, c((236, 234, 226)), (3, 8, 4, 4))                        # the satchel with a red cross
        pygame.draw.line(s, c((200, 40, 40)), (5, 8), (5, 11))
        pygame.draw.line(s, c((200, 40, 40)), (3, 9), (6, 9))
        pygame.draw.rect(s, c((236, 234, 226)), (4, 6, 2, 3))                        # armband with a cross
        pygame.draw.line(s, c(METALD), (11, 9), (14, 8), 2)                          # a flare gun
        pygame.draw.circle(s, c((255, 232, 130)), (15, 7), 1)
    else:
        pygame.draw.rect(s, c(lk["helmj"]), (5, 1, 6, 2))                            # a peaked cap
        pygame.draw.rect(s, c(lk["helm"]), (5, 0, 5, 2))
        pygame.draw.line(s, c(INK), (10, 2), (12, 2))
        pygame.draw.rect(s, c((84, 84, 90)), (1, 6, 4, 7))                           # the radio set
        pygame.draw.rect(s, c((226, 140, 40)), (2, 7, 2, 1))
        pygame.draw.line(s, c(METAL), (2, 6), (0, 0))                                # whip antenna
        pygame.draw.rect(s, c(METALD), (10, 5, 3, 2))                                # binoculars at his eyes
        pygame.draw.line(s, c(SKIN), (9, 8), (10, 6))
        pygame.draw.circle(s, c((255, 90, 70)), (14, 9), 1)                          # a red signal flare
    return outlined(s)


def king(color, style=0, white=False, frame=0):
    """A general: a peaked cap, a greatcoat with stars or lapel flashes, medals, binoculars. Cheers with both arms up
    (and a baton) when he calls an order. Style 1 is the Axis' marshal in field grey and red."""
    lk = LOOK["allies" if style == 0 else "axis"]
    c = lambda col: _w(white, col)
    s = blank(17, 19)
    sway = frame % 2
    pygame.draw.rect(s, c(lk["bootd"]), (5, 15, 2, 4))
    pygame.draw.rect(s, c(lk["bootd"]), (8, 15, 2, 4))
    pygame.draw.polygon(s, c(lk["uni"]), [(4, 6), (11, 6), (12 + sway, 17), (3 - sway, 17)])     # the greatcoat
    pygame.draw.rect(s, c(lk["unid"]), (3, 16, 10, 1))
    pygame.draw.rect(s, c(tuple(color) if style else (226, 190, 70)), (4, 6, 2, 5))             # the lapel flash
    pygame.draw.rect(s, c(tuple(color) if style else (226, 190, 70)), (10, 6, 2, 5))
    pygame.draw.rect(s, c(lk["gear"]), (6, 11, 4, 1))                                           # belt
    for mx in (6, 7, 8):                                                                        # a row of medals
        s.set_at((mx, 8), c((226, 190, 70) if mx % 2 else (200, 40, 40)))
    pygame.draw.rect(s, c(SKIN), (6, 3, 4, 4))
    s.set_at((9, 4), c(INK))
    pygame.draw.rect(s, c(lk["helmj"]), (5, 1, 6, 2))                                           # the cap
    pygame.draw.rect(s, c(lk["helm"]), (5, 0, 6, 2))
    pygame.draw.rect(s, c((226, 190, 70)), (6, 2, 4, 1))                                        # gold cap band
    pygame.draw.line(s, c(INK), (10, 2), (12, 2))                                               # the peak
    if frame >= 2:                                                                              # cheering: both arms up
        pygame.draw.rect(s, c(SKIN), (12, 5, 2, 3))
        pygame.draw.line(s, c((214, 186, 90)), (13, 5), (13, 0))
        pygame.draw.rect(s, c(SKIN), (2, 5, 2, 3))
    else:
        pygame.draw.line(s, c((214, 186, 90)), (13, 17), (13, 9))                               # a swagger stick
        pygame.draw.rect(s, c(SKIN), (11, 9, 2, 2))
        pygame.draw.rect(s, c(METALD), (11, 8, 3, 2))                                           # binoculars at his side
    return outlined(s)


HEROES = {"champion": champion, "commander": commander, "ranger": ranger, "mage": mage, "king": king}
