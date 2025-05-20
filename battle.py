# battle.py
import pygame, random
from moviepy import ImageSequenceClip, VideoFileClip, TextClip, CompositeVideoClip
import pymunk
from pathlib import Path
from ruamel.yaml import YAML
import numpy as np
from engine.game_objects import Orb
from engine.physics import make_space
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
        radius = img.get_width() // 2

        body = pymunk.Body(mass=1, moment=10_000)
        body.position = random.randint(150, W-150), random.randint(150, H-150)
        body.velocity = random.choice([(250,150), (-200,230), (200,-220)])

        shape = pymunk.Circle(body, radius)
        shape.elasticity = 1.0
        space.add(body, shape)

        orbs.append(Orb(orb_cfg["name"], img, body, shape, orb_cfg["max_hp"]))

    frames = []
    for frame_idx in range(int(DURATION * FPS)):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return

        # handle collisions (simple = chaque rebond = -1 HP)
        for arbiter in space.step(1/FPS) or []:
            pass  # pymunk 6.x renvoie None, on gérera plus tard

        screen.fill((20, 20, 20))
        for orb in orbs:
            orb.draw(screen)
            draw_hp_bar(screen, orb)

        pygame.display.flip()
        frames.append(surface_to_array(screen).copy())
        clock.tick(FPS)

    pygame.quit()
    OUT.mkdir(exist_ok=True)
    video_path = OUT / f"{cfg['title'].replace(' ','_')}.mp4"
    clip = ImageSequenceClip(frames, fps=FPS)
    clip.write_videofile(video_path.as_posix(), codec="libx264")
    print("Saved ->", video_path)

if __name__ == "__main__":
    main()