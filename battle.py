# battle.py – tout en haut
import pygame, random, math
from moviepy import ImageSequenceClip
from pathlib import Path
from ruamel.yaml import YAML
import numpy as np

from director import Director
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
SCRIPT_FILE = Path("configs/battle_script.yml")

def load_cfg(path):
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text())

def main():
    cfg = load_cfg(CFG)
    random.seed(cfg["seed"])

    pygame.init()
    pygame.font.init()
    default_font = pygame.font.SysFont(None, 48)
    active_text_overlays = []

    screen = pygame.display.set_mode((CANVAS_W, CANVAS_H))
    clock  = pygame.time.Clock()
    saw_token_img = pygame.image.load("assets/pickups/saw_token.png").convert_alpha()
    blade_img     = pygame.image.load("assets/pickups/blade.png").convert_alpha()
    heart_token_img = pygame.image.load("assets/pickups/heart_token.png").convert_alpha()
    phys.blade_img = blade_img

    space = make_space((ARENA_SIZE, ARENA_SIZE))
    director = Director(SCRIPT_FILE)

    game_state = {
        "game_speed_factor": 1.0,
        "slowmo_end_time": 0,
        "pending_slowmo_factor": 1.0,
        "pending_slowmo_duration": 0,
        "pending_slowmo_activate_time": 0
    }

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

    battle_context = MainBattleContext(
        screen, space, pickups, 
        saw_token_img, heart_token_img, 
        active_text_overlays, default_font, game_state, orbs
    )

    frames, winner = [], None
    for frame_idx in range(int(DURATION * FPS)):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return

        t_sec = frame_idx / FPS

        director.tick(t_sec, battle_context)

        if game_state["pending_slowmo_activate_time"] > 0 and t_sec >= game_state["pending_slowmo_activate_time"]:
            if game_state["game_speed_factor"] == 1.0:
                game_state["game_speed_factor"] = game_state["pending_slowmo_factor"]
                game_state["slowmo_end_time"] = game_state["pending_slowmo_activate_time"] + game_state["pending_slowmo_duration"]
                print(f"MainLoop: Slowmo activated at {t_sec:.2f}s, factor: {game_state['game_speed_factor']}, ends at: {game_state['slowmo_end_time']:.2f}s")
            game_state["pending_slowmo_activate_time"] = 0

        if game_state["game_speed_factor"] < 1.0 and t_sec >= game_state["slowmo_end_time"]:
            game_state["game_speed_factor"] = 1.0
            game_state["slowmo_end_time"] = 0
            print(f"MainLoop: Slowmo ended at {t_sec:.2f}s")
        
        current_fps_factor = game_state["game_speed_factor"]
        space.step(1 / (FPS * current_fps_factor))

        if t_sec >= SAW_TOKEN_T and not any(p.kind=='saw' for p in pickups):
            px = random.randint(60, ARENA_SIZE-60)
            py = random.randint(60, ARENA_SIZE-60)
            pickup = Pickup('saw', saw_token_img, (px, py), space)
            pickups.append(pickup)

        HEART_TOKEN_T = SAW_TOKEN_T * 2
        if t_sec >= HEART_TOKEN_T and not any(p.kind == 'heart' for p in pickups) and random.random() < 0.25:
            px = random.randint(60, ARENA_SIZE - 60)
            py = random.randint(60, ARENA_SIZE - 60)
            pickup = Pickup('heart', heart_token_img, (px, py), space)
            pickups.append(pickup)

        for s in active_saws[:]:
            if not s.alive:
                active_saws.remove(s)
            else:
                s.update(1 / FPS)

        living = [o for o in orbs if o.hp > 0]
        if winner is None and len(living) == 1:
            winner = living[0]
            win_frame = frame_idx

        screen.fill((20, 20, 20))

        for i, orb in enumerate(orbs):
            draw_top_hp_bar(screen, orb, index=i, y=SAFE_TOP // 2)
            if orb.heal_effect_active:
                flash_color = (0, 255, 0)
                original_bar_w, original_bar_h = 360, 14
                scaled_bar_w, scaled_bar_h = int(original_bar_w * 1.1), int(original_bar_h * 1.1)

                bar_w, bar_h = 360, 14
                seg_w = screen.get_width() // 2
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

        pygame.draw.rect(
            screen, (255, 0, 90),
            (ARENA_X0, ARENA_Y0, ARENA_SIZE, ARENA_SIZE), width=6)

        current_time_for_overlay = frame_idx / FPS
        for overlay in active_text_overlays[:]:
            if current_time_for_overlay < overlay["end_time"]:
                screen.blit(overlay["surface"], overlay["rect"])
            else:
                active_text_overlays.remove(overlay)

        for p in pickups:
            p.draw(screen, offset=(ARENA_X0, ARENA_Y0))
        for s in active_saws:
            s.draw(screen, offset=(ARENA_X0, ARENA_Y0))
        for orb in orbs:
            if orb.hp > 0:
                orb.draw(screen, offset=(ARENA_X0, ARENA_Y0))

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

class MainBattleContext:
    def __init__(self, screen, space, pickups_list, 
                 saw_token_img, heart_token_img, 
                 active_text_overlays_list, default_font_instance, 
                 game_state_dict, orbs_list):
        self.screen = screen
        self.space = space
        self.pickups = pickups_list
        self.saw_token_img = saw_token_img
        self.heart_token_img = heart_token_img
        self.active_text_overlays = active_text_overlays_list
        self.default_font = default_font_instance
        self.game_state = game_state_dict
        self.orbs = orbs_list

    def handle_spawn_pickup_event(self, payload):
        kind = payload.get("kind")
        x_is_abs = isinstance(payload.get("x"), (int, float)) and payload.get("x") > 1.0
        y_is_abs = isinstance(payload.get("y"), (int, float)) and payload.get("y") > 1.0

        px = payload.get("x")
        py = payload.get("y")

        if px is None: px = random.uniform(0.1, 0.9)
        if py is None: py = random.uniform(0.1, 0.9)

        final_x = int(px * ARENA_SIZE) if not x_is_abs and isinstance(px, float) and 0 <= px <= 1 else int(px) 
        final_y = int(py * ARENA_SIZE) if not y_is_abs and isinstance(py, float) and 0 <= py <= 1 else int(py)
        
        final_x = max(60, min(ARENA_SIZE - 60, final_x))
        final_y = max(60, min(ARENA_SIZE - 60, final_y))

        img = None
        if kind == "saw":
            img = self.saw_token_img
        elif kind == "heart":
            img = self.heart_token_img
        
        if img:
            pickup = Pickup(kind, img, (final_x, final_y), self.space)
            self.pickups.append(pickup)
            print(f"Director: Spawned {kind} at ({final_x},{final_y}) scheduled at {payload.get('event_time')}s")
        else:
            print(f"Director: Unknown pickup kind for spawn event: {kind}")

    def handle_slowmo_event(self, payload):
        factor = payload.get("factor", 0.5)
        duration = payload.get("duration", 2.0)
        event_time = payload.get("event_time")
        
        self.game_state["pending_slowmo_factor"] = float(factor)
        self.game_state["pending_slowmo_duration"] = float(duration)
        self.game_state["pending_slowmo_activate_time"] = event_time
        print(f"Director: Queued Slowmo event - factor: {factor}, duration: {duration}, scheduled for {event_time}s")

    def handle_text_overlay_event(self, payload):
        text = payload.get("text", "Default Text")
        duration = payload.get("duration", 3.0)
        position_key = payload.get("position", "center") 
        color = payload.get("color", (255, 255, 255))
        font_size = payload.get("font_size", 48)
        event_time = payload.get("event_time")

        custom_font = pygame.font.SysFont(None, font_size)
        text_surface = custom_font.render(text, True, color)
        rect = text_surface.get_rect()

        if position_key == "center":
            rect.center = (CANVAS_W // 2, CANVAS_H // 2)
        elif position_key == "top_center":
            rect.center = (CANVAS_W // 2, SAFE_TOP + 50) 
        elif position_key == "bottom_center":
            rect.center = (CANVAS_W // 2, ARENA_Y0 + ARENA_SIZE + 50)
        elif isinstance(position_key, (list, tuple)) and len(position_key) == 2:
            x_pos, y_pos = position_key
            abs_x = int(x_pos * CANVAS_W) if isinstance(x_pos, float) and 0 <= x_pos <= 1 else int(x_pos)
            abs_y = int(y_pos * CANVAS_H) if isinstance(y_pos, float) and 0 <= y_pos <= 1 else int(y_pos)
            rect.center = (abs_x, abs_y)
        else:
             rect.center = (CANVAS_W // 2, CANVAS_H // 2)

        end_time = event_time + duration
        self.active_text_overlays.append({"surface": text_surface, "rect": rect, "end_time": end_time})
        print(f"Director: Text overlay '{text}' for {duration}s, from {event_time:.2f}s to {end_time:.2f}s")

if __name__ == "__main__":
    main()