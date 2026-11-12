"""Pixel BS: plays a castle war on screen. Nothing ends: the battle runs on for as long as the program does, with
troops mustering and sallying out as the scenario's events say. R starts a fresh battle with a new seed.

Run with:  python main.py                       (the castle war)
           python main.py scenarios/other.json  (any scenario file)"""
import os
import sys
import time

import pygame

import config as C
from battle import Battle
from render import Renderer
from scenario import ScenarioError, load
from sound import Audio

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SCENARIO = os.path.join(HERE, "scenarios", "camp_war.json")


def sim_frame(battle, acc, rate, last_draw):
    """Advance a battle by one frame's worth of time. `rate` is ticks owed per second of real time, `acc` the ticks
    owed so far, and `last_draw` the seconds the last frame took to draw (the simulation gets the rest of the frame).
    A tick that does not finish this frame carries on in the next, so a big battle slows down rather than making the
    window stutter. Returns the ticks still owed."""
    acc = min(acc + rate, 4.0)                  # never owe more than a few ticks
    deadline = time.perf_counter() + max(0.002, C.FRAME_SIM_SHARE / C.FPS - last_draw)
    while True:
        if not battle.mid_tick:
            if acc < 1:
                break
            acc -= 1
        if not battle.step(max(0.0, deadline - time.perf_counter())):
            break
    return acc


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SCENARIO
    try:
        scenario = load(path)
    except (OSError, ScenarioError) as err:
        print(f"Could not load {path}: {err}")
        sys.exit(1)

    pygame.init()
    fullscreen = True                           # F11 switches; SCALED keeps the 1280x720 picture sharp at any size
    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H), pygame.FULLSCREEN | pygame.SCALED)
    pygame.mouse.set_visible(False)
    pygame.display.set_caption(f"Pixel BS - {scenario['name']}")
    clock = pygame.time.Clock()
    view = Renderer(scenario)
    view.audio = Audio()                        # synthesized effects and music; silent if there is no sound device

    battle_no = 0
    battle = Battle(scenario, seed=scenario["seed"])
    speed = 1                                   # an index into SPEEDS: starts at 4x
    paused = False
    acc = 0.0                                   # fractional simulation ticks carried between frames
    last_draw = 0.0                             # seconds the last frame took to draw (the simulation gets the rest)
    running = True

    def new_battle():
        nonlocal battle, battle_no, acc
        battle_no += 1
        battle = Battle(scenario, seed=scenario["seed"] + battle_no)
        acc = 0.0

    while running:
        dt = clock.tick(C.FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                    view.notify("PAUSED" if paused else f"{C.SPEEDS[speed]}x")
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    speed = min(len(C.SPEEDS) - 1, speed + 1)
                    view.notify(f"{C.SPEEDS[speed]}x")
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed = max(0, speed - 1)
                    view.notify(f"{C.SPEEDS[speed]}x")
                elif event.key == pygame.K_r:
                    new_battle()
                elif event.key == pygame.K_h:
                    view.show_hud = not view.show_hud
                elif event.key == pygame.K_l:
                    view.letterbox = not view.letterbox
                elif event.key == pygame.K_c:
                    view.cinematic = not view.cinematic
                    view.notify("Camera follows the fighting" if view.cinematic else "Camera is yours")
                elif event.key == pygame.K_w:
                    battle.next_weather()
                elif event.key == pygame.K_x:
                    view.parallax = not view.parallax
                    view.notify("Parallax on" if view.parallax else "Parallax off")
                elif event.key == pygame.K_m:
                    view.notify(view.audio.toggle_mute() if view.audio.ok else "No sound device")
                elif event.key == pygame.K_LEFTBRACKET:
                    view.notify(view.audio.change_music(-0.1) if view.audio.ok else "No sound device")
                elif event.key == pygame.K_RIGHTBRACKET:
                    view.notify(view.audio.change_music(0.1) if view.audio.ok else "No sound device")
                elif event.key == pygame.K_COMMA:
                    view.notify(view.audio.change_sfx(-0.1) if view.audio.ok else "No sound device")
                elif event.key == pygame.K_PERIOD:
                    view.notify(view.audio.change_sfx(0.1) if view.audio.ok else "No sound device")
                elif event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    pygame.display.toggle_fullscreen()

        keys = pygame.key.get_pressed()
        view.pan_dir = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])      # the arrow keys pan the camera

        view.speed = C.SPEEDS[speed]
        view.audio.speed = view.speed
        view.audio.listen(view.cam_x)
        view.audio.update()
        if not paused:
            acc = sim_frame(battle, acc, dt * C.SIM_RATE * C.SPEEDS[speed], last_draw)
        t_draw = time.perf_counter()
        view.draw(screen, battle, f"{C.SPEEDS[speed]}x", paused)
        last_draw = time.perf_counter() - t_draw
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
