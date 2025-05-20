# battle.py – tout en haut
import pygame, random, math
from moviepy import ImageSequenceClip
from pathlib import Path
from ruamel.yaml import YAML
import numpy as np

from engine.game_objects import Orb, Saw
from engine.physics import make_space, register_orb_collisions, register_saw_hits
from engine.renderer import draw_top_hp_bar, surface_to_array

# --- Layout 1080 × 1920 ---
CANVAS_W, CANVAS_H = 1080, 1920
SAFE_TOP    = 220
ARENA_SIZE  = 1080
ARENA_X0    = (CANVAS_W - ARENA_SIZE)
ARENA_Y0    = SAFE_TOP + 80
SAW_SPAWN_T = 5
CFG = Path("configs/demo.yml")
OUT = Path("export")
FPS = 60
DURATION = 70        # on vise 10 s pour tester

def load_cfg(path):
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text())

def main():
    cfg = load_cfg(CFG)
    random.seed(cfg["seed"])

    pygame.init()

    screen = pygame.display.set_mode((CANVAS_W, CANVAS_H))
    clock  = pygame.time.Clock()
    saw_img = pygame.image.load("assets/fx/blade.png").convert_alpha()

    space = make_space((ARENA_SIZE, ARENA_SIZE))

    orbs = []
    for orb_cfg in cfg["orbs"]:
        img = pygame.image.load(orb_cfg["logo"]).convert_alpha()
        img = pygame.transform.smoothscale(img, (120, 120))

        orb = Orb(orb_cfg["name"], img, None, None, orb_cfg["max_hp"])
        orb.attach_shape(space, radius=60)
        orbs.append(orb)

    register_orb_collisions(space)
    register_saw_hits(space)
    saws = []

    frames, winner = [], None
    for frame_idx in range(int(DURATION * FPS)):
        # quit event
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return

        space.step(1 / FPS)
        t_sec = frame_idx / FPS
        # SPAWN une scie unique à 5 s
        if t_sec >= SAW_SPAWN_T and not saws:
            owner = random.choice(orbs)
            saws.append(Saw(saw_img, owner, space))

        # update/clean saws
        for s in saws[:]:
            if not s.alive:
                saws.remove(s)
            else:
                s.update(1 / FPS)

        # Check defeat
        living = [o for o in orbs if o.hp > 0]
        if winner is None and len(living) == 1:
            winner = living[0]
            win_frame = frame_idx

                # ----- DRAW -----
        screen.fill((20, 20, 20))

        # 1) barres de vie (marge haute)
        for i, orb in enumerate(orbs):
            draw_top_hp_bar(screen, orb, index=i, y=SAFE_TOP // 2)

        # 2) cadre rose de l’arène
        pygame.draw.rect(
            screen, (255, 0, 90),
            (ARENA_X0, ARENA_Y0, ARENA_SIZE, ARENA_SIZE), width=6)

        # 3) orbs à l’intérieur (offset)
        for orb in orbs:
            if orb.hp > 0:
                orb.draw(screen, offset=(ARENA_X0, ARENA_Y0))

        # 4) saws
        for s in saws:
            s.draw(screen, offset=(ARENA_X0, ARENA_Y0))

        # 4) célébration du vainqueur
        if winner:
            if frame_idx - win_frame < 2 * FPS:
                giant = pygame.transform.smoothscale(
                    winner.logo_surface, (300, 300))
                rect = giant.get_rect(center=(CANVAS_W//2, CANVAS_H//2))
                screen.blit(giant, rect)
            else:
                break

        pygame.display.flip()
        frames.append(surface_to_array(screen).copy())
        clock.tick(FPS)

    pygame.quit()
    OUT.mkdir(exist_ok=True)
    video_path = OUT / f"{cfg['title'].replace(' ','_')}.mp4"
    ImageSequenceClip(frames, fps=FPS).write_videofile(
        video_path.as_posix(), codec="libx264")
    print("Saved ->", video_path)

if __name__ == "__main__":
    main()