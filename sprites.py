"""Unit art for Pixel BS (WW2). The art itself lives in three modules and this file only gathers it under the names the
renderer asks for (the "sprite" slot of each unit type in the scenario):

    ww2_art.py        soldiers, dogs and the five hero kinds, plus the helpers the others share
    ww2_vehicles.py   jeep / sidecar motorcycle, assault tank, halftrack, field gun, howitzer, mortar, flak gun
    ww2_air_sea.py    dive bomber, fighter, heavy fighter, strafer, torpedo boat, gunboat, cruiser, landing craft

The slot names are older than the war (a "foot" soldier, a "catapult"): they are only the keys the scenario file and the
renderer agree on. Every sprite faces right; the renderer flips it for a unit facing left."""
import pygame

import ww2_art
from ww2_art import INK, SKIN, HEROES, from_art, outlined, shade  # noqa: F401
from ww2_air_sea import catapult_ship, galley, griffon, harpy, hawk, landing_boat, longship, wyvern  # noqa: F401
from ww2_art import (assault_trooper as berserker, at_rifle as pavise_cross, bazooka as halberdier, foot,  # noqa: F401
                     foot_flamer as flamer, marine, sniper as longbow, war_dog)
from ww2_extra import (armored_car, commando, destroyer, engineer, flame_squad, heavy_bomber, hmg_nest, medic,  # noqa: F401
                       paratrooper, submarine, tank_destroyer, transport)
from ww2_big import carrier, dreadnought, mlrs, v2_launcher  # noqa: F401
from ww2_vehicles import ballista, catapult, mangonel, ram_crew, rider, siege_tower, trebuchet  # noqa: F401

GOLD = (236, 196, 84)

# slots drawn by a function named after the slot, called with (color, white, frame)
EXTRA_KINDS = ("longbow", "halberdier", "berserker", "pavise_cross", "war_dog", "flamer", "mangonel", "ram_crew",
               "griffon", "harpy", "longship", "galley", "catapult_ship", "landing_boat", "siege_tower",
               "engineer", "medic", "commando", "flame_squad", "paratrooper", "hmg_nest", "armored_car", "transport",
               "heavy_bomber", "destroyer", "submarine", "carrier", "dreadnought")
# slots drawn by (color, white, pose, style=side)
SIEGE_KINDS = ("catapult", "trebuchet", "ballista", "mangonel", "ram_crew", "siege_tower", "tank_destroyer", "mlrs", "v2_launcher")


def register_sides(styles):
    """Tells the art which side colour is the Allies and which the Axis (the renderer does this once)."""
    ww2_art.register_sides(styles)


def huorn(white=False):
    """A pile of sandbags (a spare slot the scenario format keeps)."""
    s = pygame.Surface((13, 9), pygame.SRCALPHA)
    for x, y, w in ((0, 5, 6), (6, 5, 6), (3, 1, 6)):
        pygame.draw.rect(s, (255, 255, 255) if white else (176, 158, 112), (x, y, w, 4))
        pygame.draw.rect(s, (255, 255, 255) if white else (122, 108, 74), (x, y + 3, w, 1))
    return outlined(s)


def dress(s, kind, style):
    """Kept for the renderer's sake: the art already knows the side it is drawing for."""
    return s


def restyle(s, kind, style):
    return s
