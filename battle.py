# battle.py – tout en haut
import pygame, random, math
from moviepy import ImageSequenceClip
from pathlib import Path
from ruamel.yaml import YAML
import numpy as np
import pymunk

from director import Director
from engine.game_objects import Orb, Saw, Pickup
import engine.physics as phys
from engine.physics import (
    make_space, register_orb_collisions, register_saw_hits,
    register_pickup_handler, active_saws
)
from engine.renderer import draw_top_hp_bar, surface_to_array, Camera
from engine.effects import ParticleEmitter

# --- Layout 1080 × 1920 ---
CANVAS_W, CANVAS_H = 1080, 1920
SAFE_TOP    = 220
ARENA_SIZE  = 1080 # This will be the width and height of the square arena
ARENA_W = ARENA_SIZE
ARENA_H = ARENA_SIZE
ARENA_X0    = (CANVAS_W - ARENA_W) // 2 # Centered horizontally
ARENA_Y0    = SAFE_TOP + 80
SAW_SPAWN_T = 5
SAW_TOKEN_T = 4
CFG = Path("configs/demo.yml")
OUT = Path("export")
FPS = 120
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
    pygame.mixer.init() # Initialize the mixer

    # Load SFX
    try:
        slow_mo_start_sfx = pygame.mixer.Sound("assets/sfx/slow_mo_start.wav")
        slow_mo_end_sfx = pygame.mixer.Sound("assets/sfx/slow_mo_end.wav")
        health_boost_sfx = pygame.mixer.Sound("assets/sfx/health_boost.wav")
        hit_normal_sfx = pygame.mixer.Sound("assets/sfx/hit_normal.wav")
        hit_blade_sfx = pygame.mixer.Sound("assets/sfx/hit_blade.wav")
        # New SFX
        bomb1_sfx = pygame.mixer.Sound("assets/sfx/bomb1.wav")
        bomb_sfx = pygame.mixer.Sound("assets/sfx/bomb.wav")
        shield_pickup_sfx = pygame.mixer.Sound("assets/sfx/shield.wav")
    except pygame.error as e:
        print(f"Warning: Could not load SFX - {e}")
        slow_mo_start_sfx = None
        slow_mo_end_sfx = None
        health_boost_sfx = None
        hit_normal_sfx = None
        hit_blade_sfx = None
        bomb1_sfx = None
        bomb_sfx = None
        shield_pickup_sfx = None

    default_font = pygame.font.SysFont(None, 48)
    active_text_overlays = []
    camera = Camera()
    particle_emitter = ParticleEmitter()

    screen = pygame.display.set_mode((CANVAS_W, CANVAS_H))
    clock  = pygame.time.Clock()
    saw_token_img = pygame.image.load("assets/pickups/saw_token.png").convert_alpha()
    heart_token_img = pygame.image.load("assets/pickups/heart_token.png").convert_alpha()
    blade_img     = pygame.image.load("assets/pickups/blade.png").convert_alpha()
    shield_token_img = pygame.image.load("assets/pickups/shield_token.webp").convert_alpha()
    bomb_token_img = pygame.image.load("assets/pickups/bomb_token.png").convert_alpha()
    freeze_token_img = pygame.image.load("assets/pickups/ice_token.webp").convert_alpha()
    phys.blade_img = blade_img

    space = make_space((ARENA_W, ARENA_H))
    director = Director(SCRIPT_FILE)

    # Game state dictionary
    game_state = {
        "game_speed_factor": 1.0, # Current multiplier for game speed
        "slowmo_end_time": 0,     # Time (in t_sec) when current slowmo should end
        "pending_slowmo_factor": 1.0,
        "pending_slowmo_duration": 0,
        "pending_slowmo_activate_time": 0
    }

    orbs = []
    pickups = [] # Initialize pickups list here
    saws = [] # Initialize saws list here (though it's not directly in context, good practice)

    # Create the context that director and physics callbacks will use
    # This instance holds references to game objects and state that events might modify.
    battle_context = MainBattleContext(
        screen, space, pickups, # pickups must be initialized before this
        saw_token_img, heart_token_img, shield_token_img, bomb_token_img, freeze_token_img, blade_img, 
        active_text_overlays, default_font, game_state, orbs,
        slow_mo_start_sfx, slow_mo_end_sfx,
        health_boost_sfx, hit_normal_sfx, hit_blade_sfx,
        bomb1_sfx, bomb_sfx, shield_pickup_sfx, # Added new SFX to context
        camera, particle_emitter
    )

    for orb_cfg in cfg["orbs"]:
        img = pygame.image.load(orb_cfg["logo"]).convert_alpha()
        img = pygame.transform.smoothscale(img, (120, 120))
        orb_color = tuple(orb_cfg.get("outline_color", [255,255,255])) # Load color, default white

        orb = Orb(orb_cfg["name"], img, None, None, orb_cfg["max_hp"], outline_color=orb_color)
        orb.attach_shape(space, radius=60)
        orbs.append(orb) # Orbs list is populated here, context already has a reference to the empty list

    register_orb_collisions(space, battle_context)  # Pass context
    register_saw_hits(space, battle_context)      # Pass context
    register_pickup_handler(space, battle_context) # Pass context
    # saws = [] # Moved up
    # pickups = [] # Moved up

    frames, winner = [], None
    current_game_time_sec = 0.0 # Initialize current game time

    for frame_idx in range(int(DURATION * FPS)):
        previous_game_time_sec = current_game_time_sec
        current_game_time_sec = frame_idx / FPS
        battle_context.current_game_time_sec = current_game_time_sec # Update context

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return

        director.tick(current_game_time_sec, battle_context)

        if game_state["pending_slowmo_activate_time"] > 0 and current_game_time_sec >= game_state["pending_slowmo_activate_time"]:
            if game_state["game_speed_factor"] == 1.0:
                game_state["game_speed_factor"] = game_state["pending_slowmo_factor"]
                game_state["slowmo_end_time"] = game_state["pending_slowmo_activate_time"] + game_state["pending_slowmo_duration"]
                print(f"MainLoop: Slowmo activated at {current_game_time_sec:.2f}s, factor: {game_state['game_speed_factor']}, ends at: {game_state['slowmo_end_time']:.2f}s")
                battle_context.start_slowmo_audio_effect(game_state['pending_slowmo_factor'])
            game_state["pending_slowmo_activate_time"] = 0

        if game_state["game_speed_factor"] < 1.0 and current_game_time_sec >= game_state["slowmo_end_time"]:
            game_state["game_speed_factor"] = 1.0
            game_state["slowmo_end_time"] = 0
            print(f"MainLoop: Slowmo ended at {current_game_time_sec:.2f}s")
            battle_context.stop_slowmo_audio_effect()
        
        current_simulation_fps_factor = game_state["game_speed_factor"]
        # Actual time passed for game logic and physics, affected by slow-mo
        # dt_frame = (current_game_time_sec - previous_game_time_sec) # More accurate dt
        # If FPS is super stable, (1/FPS) is fine. If there can be frame drops, use actual time delta.
        # For now, using the original dt_simulation which is scaled 1/FPS
        dt_logic = (1 / FPS) * current_simulation_fps_factor

        # Handle Frozen Orbs: ensure their velocity is zero if they are kinematic due to freeze
        for orb in orbs:
            if orb.is_frozen and orb.body.body_type == pymunk.Body.KINEMATIC:
                orb.body.velocity = (0, 0)
                orb.body.angular_velocity = 0 # Also zero angular velocity
            # The old logic for unfreezing based on orb.frozen_until > current_game_time_sec is removed.
            # Unfreezing is now handled by collision callbacks in physics.py.

        space.step(dt_logic)
        
        camera.update(dt_logic)
        particle_emitter.update(dt_logic)

        # Update active saws
        for s in phys.active_saws[:]:
            if not s.alive: # Saw might have been destroyed by hit or owner death
                if s in phys.active_saws: # Check if still in list before removing
                     phys.active_saws.remove(s)
                continue
            # s.update() will call s.destroy() if owner is dead, which clears owner.has_saw
            s.update(dt_logic) 
            if not s.alive and s in phys.active_saws: # Re-check after update, if it self-destroyed
                phys.active_saws.remove(s)

        # phys.handle_bomb_explosions(...) is removed as bombs are instant.

        # --- Temporary test spawners (replace with director events) ---
        if "pickups" not in cfg: # Fallback if not in demo.yml
            if current_game_time_sec >= SAW_TOKEN_T and not any(p.kind=='saw' for p in pickups) and len(pickups) == 0:
                px = random.randint(60, ARENA_W - 60)
                py = random.randint(60, ARENA_H - 60)
                pickup = Pickup('saw', saw_token_img, (px, py), space)
                pickups.append(pickup)

            HEART_TOKEN_T = SAW_TOKEN_T * 1.5 # Example
            if current_game_time_sec >= HEART_TOKEN_T and not any(p.kind == 'heart' for p in pickups) and len(pickups) <= 1:
                 if random.random() < 0.5: # Chance to spawn
                    px = random.randint(60, ARENA_W - 60)
                    py = random.randint(60, ARENA_H - 60)
                    pickup = Pickup('heart', heart_token_img, (px, py), space)
                    pickups.append(pickup)
        # --- End temporary spawners ---

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

        arena_render_offset_x = ARENA_X0 + camera.offset.x
        arena_render_offset_y = ARENA_Y0 + camera.offset.y

        pygame.draw.rect(
            screen, (255, 0, 90),
            (arena_render_offset_x, arena_render_offset_y, ARENA_W, ARENA_H), width=6)

        # Draw particles: their positions are in arena space.
        # We pass the total offset of the arena on the screen (ARENA_X0/Y0 + camera_shake)
        effective_arena_offset_for_particles = pygame.math.Vector2(arena_render_offset_x, arena_render_offset_y)
        particle_emitter.draw(screen, effective_arena_offset_for_particles)

        current_time_for_overlay = current_game_time_sec
        for overlay in active_text_overlays[:]:
            if current_time_for_overlay < overlay["end_time"]:
                screen.blit(overlay["surface"], overlay["rect"])
            else:
                active_text_overlays.remove(overlay)

        for p in pickups:
            p.draw(screen, offset=(arena_render_offset_x, arena_render_offset_y))
        for s in phys.active_saws:
            s.draw(screen, offset=(arena_render_offset_x, arena_render_offset_y))
        for orb_to_draw in orbs:
            if orb_to_draw.hp > 0:
                orb_to_draw.draw(screen, offset=(arena_render_offset_x, arena_render_offset_y))

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
                 saw_token_img, heart_token_img, shield_token_img, bomb_token_img, freeze_token_img, blade_img,
                 active_text_overlays_list, default_font_instance,
                 game_state_dict, orbs_list,
                 slow_mo_start_sfx=None, slow_mo_end_sfx=None,
                 health_boost_sfx=None, hit_normal_sfx=None, hit_blade_sfx=None,
                 bomb1_sfx=None, bomb_sfx=None, shield_pickup_sfx=None, # Added new SFX params
                 camera_instance=None, particle_emitter_instance=None):
        self.screen = screen
        self.space = space
        self.pickups = pickups_list
        self.saw_token_img = saw_token_img
        self.heart_token_img = heart_token_img
        self.shield_token_img = shield_token_img
        self.bomb_token_img = bomb_token_img
        self.freeze_token_img = freeze_token_img
        self.blade_img = blade_img
        self.active_text_overlays = active_text_overlays_list
        self.default_font = default_font_instance
        self.game_state = game_state_dict
        self.orbs = orbs_list
        self.slow_mo_start_sfx = slow_mo_start_sfx
        self.slow_mo_end_sfx = slow_mo_end_sfx
        self.health_boost_sfx = health_boost_sfx
        self.hit_normal_sfx = hit_normal_sfx
        self.hit_blade_sfx = hit_blade_sfx
        # New SFX assignments
        self.bomb1_sfx = bomb1_sfx
        self.bomb_sfx = bomb_sfx
        self.shield_pickup_sfx = shield_pickup_sfx
        self.camera = camera_instance
        self.particle_emitter = particle_emitter_instance
        self.current_game_time_sec = 0.0 # Added to context
        # You might want to initialize an audio manager or pydub interface here
        # self.audio_manager = MyAudioManager() 

    def play_sfx(self, sfx_to_play):
        if sfx_to_play:
            sfx_to_play.play()

    def handle_spawn_pickup_event(self, payload):
        kind = payload.get("kind")
        x_is_abs = isinstance(payload.get("x"), (int, float)) and payload.get("x") > 1.0
        y_is_abs = isinstance(payload.get("y"), (int, float)) and payload.get("y") > 1.0

        px = payload.get("x")
        py = payload.get("y")

        if px is None: px = random.uniform(0.1, 0.9)
        if py is None: py = random.uniform(0.1, 0.9)

        final_x = int(px * ARENA_W) if not x_is_abs and isinstance(px, float) and 0 <= px <= 1 else int(px)
        final_y = int(py * ARENA_H) if not y_is_abs and isinstance(py, float) and 0 <= py <= 1 else int(py)
        
        final_x = max(40, min(ARENA_W - 40, final_x))
        final_y = max(40, min(ARENA_H - 40, final_y))

        img = None
        if kind == "saw":
            img = self.saw_token_img
        elif kind == "heart":
            img = self.heart_token_img
        elif kind == "shield":
            img = self.shield_token_img
        elif kind == "bomb":
            img = self.bomb_token_img
        elif kind == "freeze":
            img = self.freeze_token_img
        
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
        
        # Cap the slowmo factor
        capped_factor = max(0.15, float(factor))

        # Store the details from the event. The main loop will apply them when event_time is reached.
        self.game_state["pending_slowmo_factor"] = capped_factor
        self.game_state["pending_slowmo_duration"] = float(duration)
        self.game_state["pending_slowmo_activate_time"] = event_time
        print(f"Director: Queued Slowmo event - factor: {capped_factor:.2f} (original: {factor:.2f}), duration: {duration:.2f}s, scheduled for {event_time:.2f}s")
        
        # Placeholder for starting audio effect for slowmo
        # self.start_slowmo_audio_effect(capped_factor) # Removed from here

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

    # --- Conceptual Audio Handling Methods ---
    def start_slowmo_audio_effect(self, factor):
        print(f"AUDIO: Playing slow_mo_start.wav (factor: {factor:.2f})")
        if self.slow_mo_start_sfx:
            self.slow_mo_start_sfx.play()
        # pass # Original pass removed

    def stop_slowmo_audio_effect(self):
        print("AUDIO: Playing slow_mo_end.wav")
        if self.slow_mo_end_sfx:
            self.slow_mo_end_sfx.play()
        # pass # Original pass removed

if __name__ == "__main__":
    main()