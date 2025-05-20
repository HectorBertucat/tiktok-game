# battle.py
import pygame, random
from moviepy import ImageSequenceClip, VideoFileClip, TextClip, CompositeVideoClip
import pymunk
from pathlib import Path
from ruamel.yaml import YAML
import numpy as np
from engine.game_objects import Orb
from engine.physics import make_space, register_orb_collisions
from engine.renderer import draw_hp_bar, surface_to_array

CFG = Path("configs/demo.yml")
OUT = Path("export")
FPS = 60
DURATION = 10        # on vise 10 s pour tester

def load_cfg(path):
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text())

def main():
    cfg = load_cfg(CFG)
    random.seed(cfg["seed"])

    pygame.init()
    W, H = cfg["arena"]["size"]
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()

    space = make_space((W, H))
    orbs = []
    for orb_cfg in cfg["orbs"]:
        img = pygame.image.load(orb_cfg["logo"]).convert_alpha()
        img = pygame.transform.smoothscale(img, (120, 120))
        orb = Orb(orb_cfg["name"], img, None, None, orb_cfg["max_hp"])
        orb.attach_shape(space, radius=60)        # ← nouveau
        orbs.append(orb)

    register_orb_collisions(space)

    frames, winner = [], None
    for frame_idx in range(int(DURATION * FPS)):
        # quit event
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return

        space.step(1 / FPS)

        # Check defeat
        living = [o for o in orbs if o.hp > 0]
        if winner is None and len(living) == 1:
            winner = living[0]
            win_frame = frame_idx

        screen.fill((20, 20, 20))
        for orb in orbs:
            if orb.hp > 0:
                orb.draw(screen)
            draw_hp_bar(screen, orb)

        # Affichage logo gagnant pendant 2 s
        if winner:
            if frame_idx - win_frame < 2 * FPS:
                giant = pygame.transform.smoothscale(
                    winner.logo_surface, (300, 300))
                rect = giant.get_rect(center=(W//2, H//2))
                screen.blit(giant, rect)
            else:
                break  # on stoppe la capture une fois la célébration finie

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