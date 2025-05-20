# battle.py – tout en haut
import pygame, random, math
from moviepy import ImageSequenceClip
from pathlib import Path
from ruamel.yaml import YAML
import numpy as np

from engine.game_objects import Orb, Saw, Pickup
import engine.physics as phys
from engine.physics import make_space, register_orb_collisions, register_saw_hits, register_pickup_handler, active_saws
from engine.renderer import draw_top_hp_bar, surface_to_array

# --- Layout 1080 × 1920 ---
CANVAS_W, CANVAS_H = 1080, 1920
SAFE_TOP    = 220
ARENA_SIZE  = 1080
ARENA_X0    = (CANVAS_W - ARENA_SIZE)
ARENA_Y0    = SAFE_TOP + 80
SAW_SPAWN_T = 5
SAW_TOKEN_T = 4
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
    saw_token_img = pygame.image.load("assets/pickups/saw_token.png").convert_alpha()
    blade_img     = pygame.image.load("assets/pickups/blade.png").convert_alpha()
    heart_token_img = pygame.image.load("assets/pickups/heart_token.png").convert_alpha()
    phys.blade_img = blade_img

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
    register_pickup_handler(space)
    saws = []
    pickups = []

    frames, winner = [], None
    for frame_idx in range(int(DURATION * FPS)):
        # quit event
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return

        space.step(1 / FPS)
        t_sec = frame_idx / FPS
        if t_sec >= SAW_TOKEN_T and not any(p.kind=='saw' for p in pickups):
            # position aléa dans l'arène
            px = random.randint(60, ARENA_SIZE-60)
            py = random.randint(60, ARENA_SIZE-60)
            pickup = Pickup('saw', saw_token_img, (px, py), space)
            pickups.append(pickup)

        # Spawn heart pickups (less frequent than saw tokens)
        # Check if it's time to spawn a heart and if no heart pickup already exists
        HEART_TOKEN_T = SAW_TOKEN_T * 2 # Example: hearts spawn half as often as saws
        if t_sec >= HEART_TOKEN_T and not any(p.kind == 'heart' for p in pickups) and random.random() < 0.25: # Adjust probability as needed
            px = random.randint(60, ARENA_SIZE - 60)
            py = random.randint(60, ARENA_SIZE - 60)
            pickup = Pickup('heart', heart_token_img, (px, py), space)
            pickups.append(pickup)

        # update saws
        for s in active_saws[:]:
            if not s.alive:
                active_saws.remove(s)
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
            if orb.heal_effect_active:
                # Flash effect: change color and slightly scale the bar
                # This is a simple version. You might want a more complex animation.
                flash_color = (0, 255, 0) # Green flash
                original_bar_w, original_bar_h = 360, 14 # Assuming these are the default values from draw_top_hp_bar
                scaled_bar_w, scaled_bar_h = int(original_bar_w * 1.1), int(original_bar_h * 1.1)

                # Calculate position for the scaled bar to keep it centered
                bar_w, bar_h = 360, 14 # from draw_top_hp_bar
                seg_w = screen.get_width() // 2 # Assuming 2 orbs from draw_top_hp_bar total=2 default
                original_x = i * seg_w + (seg_w - bar_w) // 2
                original_y = SAFE_TOP // 2

                scaled_x = original_x - (scaled_bar_w - original_bar_w) // 2
                scaled_y = original_y - (scaled_bar_h - original_bar_h) // 2

                pct = orb.hp / orb.max_hp
                bg_rect = pygame.Rect(scaled_x, scaled_y, scaled_bar_w, scaled_bar_h)
                fg_rect = pygame.Rect(scaled_x, scaled_y, int(scaled_bar_w * pct), scaled_bar_h)

                pygame.draw.rect(screen, (60,60,60), bg_rect, border_radius=5)
                pygame.draw.rect(screen, flash_color, fg_rect, border_radius=5)

                orb.heal_effect_timer -= 1
                if orb.heal_effect_timer <= 0:
                    orb.heal_effect_active = False

        # 2) cadre rose de l'arène
        pygame.draw.rect(
            screen, (255, 0, 90),
            (ARENA_X0, ARENA_Y0, ARENA_SIZE, ARENA_SIZE), width=6)

        for p in pickups:
            p.draw(screen, offset=(ARENA_X0, ARENA_Y0))
        for s in active_saws:
            s.draw(screen, offset=(ARENA_X0, ARENA_Y0))
        for orb in orbs:
            if orb.hp > 0:
                orb.draw(screen, offset=(ARENA_X0, ARENA_Y0))
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