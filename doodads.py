"""Doodads: the props scattered over the battlefield (trees, rocks, bushes, barbed wire, drums and crates, trucks, wrecks, tents). They are only scenery:
they do not change the battle. Each is drawn once from shapes into a small outlined sprite, and placed with a seeded
random generator so the field looks the same every run. Campfires and lanterns glow at night."""
import math
import random

import pygame

from scenery import KINDS, place  # noqa: F401  (the renderer imports these from here)
from sprites import INK, outlined, shade

GLOWING = ("campfire", "lantern")


def _g(white, c):
    return (255, 255, 255) if white else c


def build(kind, variant=0, white=False):
    """The sprite for one kind of doodad (outlined). `variant` (0-2) changes colours and shapes a little."""
    rnd = random.Random(variant * 977 + len(kind))
    leaf = [(54, 104, 52), (70, 112, 48), (44, 92, 70)][variant % 3]
    if kind == "oak":
        s = pygame.Surface((22, 26), pygame.SRCALPHA)
        pygame.draw.rect(s, (84, 58, 36), (9, 14, 4, 12))
        pygame.draw.rect(s, (58, 40, 26), (9, 14, 1, 12))
        for cx, cy, r in ((11, 8, 8), (5, 11, 5), (17, 11, 5), (11, 4, 5)):
            pygame.draw.circle(s, shade(leaf, 0.7), (cx, cy), r)
        for cx, cy, r in ((10, 7, 6), (5, 10, 3), (16, 10, 3)):
            pygame.draw.circle(s, leaf, (cx, cy), r)
        pygame.draw.circle(s, shade(leaf, 1.35), (8, 5), 3)
        return outlined(s)
    if kind == "pine":
        s = pygame.Surface((14, 28), pygame.SRCALPHA)
        pygame.draw.rect(s, (74, 52, 32), (6, 22, 2, 6))
        dark = (30, 70, 52) if variant != 1 else (36, 78, 44)
        for i, (w, y) in enumerate(((13, 10), (11, 6), (8, 2))):
            top = y + 2 if i else 1
            pygame.draw.polygon(s, dark, [(7, top), (7 - w // 2, y + 10), (7 + w // 2, y + 10)])
            pygame.draw.polygon(s, shade(dark, 1.4), [(7, top), (7 - w // 2, y + 10), (7, y + 10)])
        return outlined(s)
    if kind == "deadtree":
        s = pygame.Surface((16, 22), pygame.SRCALPHA)
        wood = (92, 76, 62)
        pygame.draw.line(s, wood, (8, 22), (8, 6), 2)
        pygame.draw.line(s, wood, (8, 14), (2, 7), 1)
        pygame.draw.line(s, wood, (8, 10), (14, 3), 1)
        pygame.draw.line(s, wood, (8, 17), (13, 12), 1)
        pygame.draw.line(s, shade(wood, 1.3), (7, 6), (7, 20))
        return outlined(s)
    if kind == "bush":
        s = pygame.Surface((12, 8), pygame.SRCALPHA)
        for cx, cy, r in ((4, 5, 3), (8, 5, 3), (6, 3, 3)):
            pygame.draw.circle(s, shade(leaf, 0.75), (cx, cy), r)
        pygame.draw.circle(s, leaf, (6, 3), 2)
        if variant == 2:                                        # a berry bush
            for p in ((3, 4), (8, 5), (6, 2)):
                s.set_at(p, (190, 40, 50))
        return outlined(s)
    if kind in ("rock", "boulder"):
        big = kind == "boulder"
        w, h = (14, 10) if big else (7, 5)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        base = [(118, 116, 112), (104, 102, 100), (126, 118, 104)][variant % 3]
        pygame.draw.polygon(s, base, [(0, h - 1), (1, h // 2), (w // 3, 0), (w - 2, 1), (w - 1, h - 1)])
        pygame.draw.polygon(s, shade(base, 1.3), [(1, h // 2), (w // 3, 0), (w // 2, 1), (w // 3, h // 2)])
        pygame.draw.line(s, shade(base, 0.7), (1, h - 1), (w - 1, h - 1))
        return outlined(s)
    if kind == "flowers":
        s = pygame.Surface((9, 6), pygame.SRCALPHA)
        for x in range(1, 9, 2):
            pygame.draw.line(s, (50, 96, 44), (x, 5), (x, 3))
        col = [(240, 220, 90), (236, 236, 240), (200, 110, 200)][variant % 3]
        for x, y in ((1, 2), (3, 1), (5, 2), (7, 1)):
            s.set_at((x, y), col)
        return s
    if kind == "grass":
        s = pygame.Surface((8, 6), pygame.SRCALPHA)
        for x, h in ((1, 3), (3, 5), (5, 4), (7, 3)):
            pygame.draw.line(s, shade((70, 120, 54), 0.8 + 0.2 * (x % 2)), (x, 5), (x + (x % 3) - 1, 5 - h))
        return s
    if kind == "stump":
        s = pygame.Surface((8, 6), pygame.SRCALPHA)
        pygame.draw.rect(s, (92, 64, 40), (1, 2, 6, 4))
        pygame.draw.ellipse(s, (170, 134, 90), (1, 0, 6, 3))
        return outlined(s)
    if kind == "log":
        s = pygame.Surface((14, 6), pygame.SRCALPHA)
        pygame.draw.rect(s, (96, 66, 42), (0, 1, 14, 5))
        pygame.draw.rect(s, (130, 96, 62), (0, 1, 14, 1))
        pygame.draw.ellipse(s, (176, 140, 94), (11, 0, 3, 6))
        return outlined(s)
    if kind == "wirefence":
        s = pygame.Surface((20, 10), pygame.SRCALPHA)
        for x in (1, 9, 17):
            pygame.draw.line(s, (84, 70, 56), (x, 2), (x, 9), 2)
        for y, off in ((3, 0), (6, 1)):
            prev = (0, y)
            for x in range(2, 20, 2):
                cur = (x, y + (off if (x // 2) % 2 else 0))
                pygame.draw.line(s, (206, 206, 214), prev, cur)
                prev = cur
        return outlined(s)
    if kind == "drum":
        s = pygame.Surface((7, 10), pygame.SRCALPHA)
        col = [(78, 92, 56), (60, 64, 70), (150, 60, 44)][variant % 3]
        pygame.draw.rect(s, col, (0, 1, 7, 9))
        pygame.draw.rect(s, shade(col, 1.3), (0, 1, 2, 9))
        pygame.draw.rect(s, shade(col, 0.6), (0, 3, 7, 1))
        pygame.draw.rect(s, shade(col, 0.6), (0, 7, 7, 1))
        pygame.draw.rect(s, shade(col, 1.25), (1, 0, 5, 2))
        return outlined(s)
    if kind == "crates":
        s = pygame.Surface((14, 11), pygame.SRCALPHA)
        col = [(92, 104, 66), (130, 104, 66), (84, 90, 96)][variant % 3]
        for x, y, w in ((0, 5, 6), (6, 5, 7), (3, 0, 7)):
            pygame.draw.rect(s, col, (x, y, w, 6))
            pygame.draw.rect(s, shade(col, 0.6), (x, y, w, 6), 1)
            pygame.draw.line(s, shade(col, 1.3), (x + 1, y + 1), (x + w - 2, y + 1))
            pygame.draw.rect(s, (226, 220, 190), (x + 2, y + 3, 2, 1))                      # a stencilled mark
        return outlined(s)
    if kind == "sandbags":
        s = pygame.Surface((14, 8), pygame.SRCALPHA)
        for x, y, w in ((0, 4, 5), (5, 4, 5), (9, 4, 5), (2, 1, 5), (7, 1, 5)):
            pygame.draw.ellipse(s, (176, 158, 112), (x, y, w + 1, 4))
            pygame.draw.line(s, (206, 190, 142), (x + 1, y + 1), (x + w - 1, y + 1))
            pygame.draw.line(s, (122, 106, 74), (x + 1, y + 3), (x + w - 1, y + 3))
        return outlined(s)
    if kind == "truck":
        s = pygame.Surface((26, 15), pygame.SRCALPHA)
        col = [(94, 106, 64), (110, 112, 104), (140, 116, 80)][variant % 3]
        pygame.draw.rect(s, shade(col, 0.7), (2, 8, 22, 3))                                  # the chassis
        pygame.draw.rect(s, col, (2, 3, 14, 6))                                              # the cargo bed
        pygame.draw.polygon(s, shade(col, 1.2), [(3, 3), (5, 0), (14, 0), (16, 3)])         # a canvas tilt over the bed
        pygame.draw.rect(s, col, (16, 4, 8, 5))                                              # the cab
        pygame.draw.rect(s, (150, 190, 210), (20, 5, 3, 2))                                  # its window
        pygame.draw.rect(s, shade(col, 1.25), (2, 3, 14, 1))
        for cx in (6, 20):
            pygame.draw.circle(s, (30, 30, 34), (cx, 11), 3)
            pygame.draw.circle(s, (130, 130, 138), (cx, 11), 1)
        pygame.draw.rect(s, (236, 236, 240), (8, 5, 3, 3))                                   # a white star
        return outlined(s)
    if kind == "rifle":
        s = pygame.Surface((8, 16), pygame.SRCALPHA)
        pygame.draw.line(s, (120, 84, 52), (3, 15), (4, 5), 2)                               # a rifle stuck in the ground
        pygame.draw.line(s, (96, 98, 106), (4, 5), (4, 1))
        pygame.draw.ellipse(s, [(98, 110, 66), (88, 94, 100), (110, 112, 104)][variant % 3], (1, 4, 7, 4))   # a helmet on the butt
        pygame.draw.line(s, (50, 40, 30), (1, 7), (7, 7))
        return outlined(s)
    if kind == "helmet":
        s = pygame.Surface((9, 6), pygame.SRCALPHA)
        col = [(98, 110, 66), (88, 94, 100), (110, 112, 104)][variant % 3]
        pygame.draw.ellipse(s, col, (0, 0, 9, 6))
        pygame.draw.ellipse(s, shade(col, 1.35), (2, 1, 4, 2))
        pygame.draw.line(s, (50, 40, 30), (1, 5), (8, 5))
        return outlined(s)
    if kind == "debris":
        s = pygame.Surface((12, 7), pygame.SRCALPHA)
        pygame.draw.line(s, (96, 98, 104), (0, 5), (7, 1), 2)
        pygame.draw.line(s, (70, 72, 78), (3, 6), (11, 4), 2)
        pygame.draw.circle(s, (46, 46, 50), (9, 3), 2)
        for x, y in ((2, 2), (6, 6), (10, 6)):
            s.set_at((x, y), (200, 170, 70))                                                 # brass casings
        return outlined(s)
    if kind == "shells":
        s = pygame.Surface((10, 11), pygame.SRCALPHA)
        for x, lean in ((2, 0), (5, 1), (8, 0)):
            pygame.draw.rect(s, (190, 160, 70), (x - 1, 4, 3, 6))
            pygame.draw.rect(s, (96, 98, 104), (x - 1, 1 + lean, 3, 3))
            pygame.draw.rect(s, (60, 60, 66), (x - 1, 4, 3, 1))
        return outlined(s)
    if kind == "tent":
        s = pygame.Surface((22, 14), pygame.SRCALPHA)
        col = [(98, 110, 66), (146, 128, 86), (100, 104, 98)][variant % 3]
        pygame.draw.polygon(s, col, [(11, 0), (0, 13), (21, 13)])
        pygame.draw.polygon(s, shade(col, 0.7), [(11, 0), (11, 13), (21, 13)])
        pygame.draw.polygon(s, (36, 30, 24), [(11, 6), (8, 13), (14, 13)])
        pygame.draw.line(s, (60, 44, 30), (11, 0), (11, -1 if False else 0))
        pygame.draw.rect(s, (236, 234, 226), (3, 9, 3, 3))                                   # a red cross on the medical tent
        pygame.draw.rect(s, (200, 40, 40), (4, 9, 1, 3)) if variant == 1 else None
        pygame.draw.rect(s, (200, 40, 40), (3, 10, 3, 1)) if variant == 1 else None
        return outlined(s)
    if kind == "hedgehog":
        s = pygame.Surface((11, 11), pygame.SRCALPHA)
        pygame.draw.line(s, (60, 62, 68), (1, 10), (9, 1), 2)
        pygame.draw.line(s, (60, 62, 68), (9, 10), (1, 1), 2)
        pygame.draw.line(s, (60, 62, 68), (5, 10), (5, 1), 2)
        pygame.draw.line(s, (140, 82, 50), (9, 9), (2, 2))
        return outlined(s)
    if kind == "jerrycan":
        s = pygame.Surface((7, 8), pygame.SRCALPHA)
        col = [(94, 106, 64), (110, 112, 104), (150, 60, 44)][variant % 3]
        pygame.draw.rect(s, col, (0, 2, 7, 6))
        pygame.draw.rect(s, shade(col, 1.3), (0, 2, 7, 1))
        pygame.draw.rect(s, shade(col, 0.6), (1, 0, 4, 2))                                   # the handle
        pygame.draw.line(s, shade(col, 0.6), (0, 7), (6, 3))
        return outlined(s)
    if kind == "signpost":
        s = pygame.Surface((14, 18), pygame.SRCALPHA)
        pygame.draw.line(s, (84, 62, 38), (7, 17), (7, 1), 2)
        for y, x0, w in ((2, 1, 9), (6, 4, 9), (10, 2, 8)):                                  # three direction boards
            pygame.draw.rect(s, (214, 206, 176), (x0, y, w, 3))
            pygame.draw.rect(s, (50, 40, 30), (x0, y, w, 3), 1)
        return outlined(s)
    if kind == "wreck":
        s = pygame.Surface((26, 13), pygame.SRCALPHA)
        pygame.draw.rect(s, (52, 48, 46), (2, 5, 22, 6))                                     # a burnt-out hull
        pygame.draw.rect(s, (74, 66, 58), (2, 5, 22, 1))
        pygame.draw.polygon(s, (60, 54, 50), [(6, 5), (9, 1), (17, 1), (20, 5)])
        pygame.draw.line(s, (34, 32, 30), (10, 1), (14, 5))
        for cx in (7, 19):
            pygame.draw.circle(s, (28, 26, 28), (cx, 11), 2)
        pygame.draw.line(s, (110, 70, 44), (3, 7), (22, 9))                                  # rust
        return outlined(s)
    if kind == "campfire":
        s = pygame.Surface((12, 11), pygame.SRCALPHA)
        for a in (0.4, 1.4, 2.4):
            pygame.draw.line(s, (96, 64, 38), (6, 9), (6 + int(math.cos(a) * 5), 9 - int(abs(math.sin(a)) * 2)), 2)
        pygame.draw.polygon(s, (240, 120, 30), [(6, 1), (3, 8), (9, 8)])
        pygame.draw.polygon(s, (255, 214, 90), [(6, 4), (4, 8), (8, 8)])
        return outlined(s)
    if kind == "lantern":                                                                   # a hurricane lamp on a post
        s = pygame.Surface((7, 18), pygame.SRCALPHA)
        pygame.draw.rect(s, (70, 52, 36), (3, 4, 1, 14))
        pygame.draw.rect(s, (70, 52, 36), (1, 3, 5, 1))
        pygame.draw.rect(s, (255, 214, 100), (2, 4, 3, 4))
        pygame.draw.rect(s, (60, 60, 66), (2, 4, 3, 4), 1)
        return outlined(s)
    raise ValueError(kind)
