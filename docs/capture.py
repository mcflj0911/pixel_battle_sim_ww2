"""Regenerate the README screenshots: python docs/capture.py (run from anywhere)."""
import os, sys, time
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import pygame
import config as C
from battle import Battle
from render import Renderer
from scenario import load
from weather import TARGETS

sc = load(os.path.join("scenarios", "camp_war.json"))
pygame.init()
surf = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
view = Renderer(sc)
b = Battle(sc, seed=1)
b.run_for(150)


def shot(name, cam, phase, kind):
    b.set_weather(kind)
    b.wx.update(TARGETS[kind])
    view.snow_cover = 1.0 if kind == "snow" else 0.0
    view.set_phase(phase)
    view.look_at(cam)
    for _ in range(30):
        view.draw(surf, b, "1x", False)
        time.sleep(0.02)
    pygame.image.save(surf, os.path.join("docs", name + ".png"))


shot("battle-day", 3000, 0.5, "clear")
shot("camp-assault", 700, 0.5, "cloudy")
shot("axis-camp", 5300, 0.5, "clear")
shot("night", 3000, 0.0, "clear")
shot("storm", 3000, 0.5, "storm")
shot("river-bridges", 2200, 0.5, "clear")
shot("town-hills", 1100, 0.5, "clear")
