# battle.py – tout en haut
import pygame, random, math
from moviepy import ImageSequenceClip
from pathlib import Path
from ruamel.yaml import YAML
import numpy as np
import pymunk

# from director import Director # Removed Director
from engine.game_objects import Orb, Saw, Pickup
import engine.physics as phys
from engine.physics import (
    make_space, register_orb_collisions, register_saw_hits,
    register_pickup_handler, active_saws, register_orb_wall_collisions
)
from engine.renderer import draw_top_hp_bar, surface_to_array, Camera
from engine.effects import ParticleEmitter

# --- Layout 1080 × 1920 ---
CANVAS_W, CANVAS_H = 1080, 1920
SAFE_TOP    = 220
ARENA_SIZE  = 1080 # This will be the width and height of the square arena
ARENA_W = ARENA_SIZE
ARENA_H = ARENA_SIZE
ARENA_X0 = 0 # Arena starts at left edge of canvas
ARENA_Y0    = SAFE_TOP + 80
SAW_SPAWN_T = 5
SAW_TOKEN_T = 4
CFG = Path("configs/generated_battle_script.yml")
OUT = Path("export")
# FPS = 120 # Will be loaded from cfg
# DURATION = 70 # Will be implicit from events or a cfg field if added
# SCRIPT_FILE = Path("configs/generated_battle_script.yml") # Removed SCRIPT_FILE
SFX_BOUNCE_DIR = Path("assets/sfx/bounce") # Path to bounce SFX

# Dynamic Spawning Constants
SAFETY_PERIOD_SECONDS = 61
LOW_HEALTH_THRESHOLD = 1 # HP value at or below which emergency heart may spawn
EMERGENCY_HEART_COOLDOWN_SECONDS = 10 # Min time between emergency hearts for the same orb
EMERGENCY_HEART_PREDICTION_TIME_SECONDS = 0.75 # Predict 0.75s ahead for heart spawn
ASSISTANCE_ITEM_COOLDOWN_SECONDS = 10 # Min time between assistance (saw/shield) items for the same orb under low HP

# Unified Predictive Spawning Constants
UNIFIED_SPAWN_INTERVAL_SECONDS = 3 # Try to spawn a pickup every X seconds
UNIFIED_PREDICTION_TIME_MIN_SECONDS = 1.5
UNIFIED_PREDICTION_TIME_MAX_SECONDS = 2.5
MAX_PICKUPS_ON_SCREEN = 6 # Max total pickups of all kinds

# Weights for choosing pickups. Heart gets higher priority if an orb is low HP during safety period.
PICKUP_KINDS_WEIGHTS = {
    "heart": 8,    # Increased for frequent health
    "saw": 20,     # Increased for frequent saws/blades
    "shield": 3,   # Less frequent than saw/heart
    "bomb": 0.5    # Remains rare
}
# No separate LOW_HEALTH_THRESHOLD for general spawning, but safety period gives hearts priority.

# Constants from engine.game_objects that might be needed for prediction
# This isn't ideal, better to pass them or have them in a shared config.
# For now, hardcoding a reference value if not easily available.
PRED_MAX_ORB_VELOCITY = 1500 # Must match MAX_ORB_VELOCITY in engine.game_objects.py

def load_cfg(path):
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text())

def main():
    cfg = load_cfg(CFG)
    # random.seed(cfg["seed"]) # Seeding is now handled by generator for scenario determinism
                               # Or, if runtime randomness is needed for non-gameplay, seed separately.

    # Load constants from the new config
    GAME_FPS = cfg.get("fps", 120)
    # ARENA_WIDTH_FROM_CFG should be CANVAS_W if generated script sets it so.
    # We use CANVAS_W directly for rendering rect, and pass it to make_space.
    # The ARENA_WIDTH_FROM_CFG from cfg is effectively CANVAS_W now from generator.
    ARENA_WIDTH_FROM_CFG = cfg.get("arena_width", CANVAS_W) # Ensure this is used, should be CANVAS_W
    ARENA_HEIGHT_FROM_CFG = cfg.get("arena_height", ARENA_H) # Use global ARENA_H as fallback
    ORB_RADIUS_CFG = cfg.get("orb_radius", 80)
    PICKUP_RADIUS_CFG = cfg.get("pickup_radius", 20) # Default if not in cfg
    BORDER_THICKNESS_CFG = int(cfg.get("border_thickness", 15)) # Ensure integer for Pygame
    BORDER_COLOR_CFG = tuple(cfg.get("border_color", [255, 0, 90]))
    BORDER_FLASH_COLOR_CFG = tuple(cfg.get("border_flash_color", [255, 255, 0]))
    DEFAULT_FLASH_DURATION_CFG = cfg.get("default_flash_duration", 1.0)

    PHYSICS_SUBSTEPS = 3 # Number of physics sub-steps per frame

    # DURATION can be set if you add a 'duration' field to the YAML, or determined by max event time.
    # For now, let's keep a default DURATION or calculate from max event time later if needed.
    # DURATION_CFG = cfg.get("duration", 70) # Example: add a duration field to YAML or calculate
    # For dynamic mode, let's set a longer or indefinite duration, or manage end conditions differently.
    DURATION_SECONDS = cfg.get("duration", 70) # Allow duration from YAML, default to 70s

    # Define arena rect for particle collisions (inner dimensions of playable area)
    # Assuming ARENA_WIDTH_FROM_CFG and ARENA_HEIGHT_FROM_CFG are these inner dimensions.
    arena_rect_for_particles = pygame.Rect(0, 0, ARENA_WIDTH_FROM_CFG, ARENA_HEIGHT_FROM_CFG)

    pygame.init()
    pygame.font.init()
    pygame.mixer.init() # Initialize the mixer

    # Load SFX
    try:
        # slow_mo_start_sfx = pygame.mixer.Sound("assets/sfx/slow_mo_start.wav") # Removed
        # slow_mo_end_sfx = pygame.mixer.Sound("assets/sfx/slow_mo_end.wav") # Removed
        health_boost_sfx = pygame.mixer.Sound("assets/sfx/health_boost.wav")
        hit_normal_sfx = pygame.mixer.Sound("assets/sfx/hit_normal.wav")
        hit_blade_sfx = pygame.mixer.Sound("assets/sfx/hit_blade.wav")
        # New SFX
        bomb1_sfx = pygame.mixer.Sound("assets/sfx/bomb1.wav")
        bomb_sfx = pygame.mixer.Sound("assets/sfx/bomb.wav")
        shield_pickup_sfx = pygame.mixer.Sound("assets/sfx/shield.wav")
        blade_get_power_up_sfx = pygame.mixer.Sound("assets/sfx/blade_get_power_up.wav")
    except pygame.error as e:
        print(f"Warning: Could not load SFX - {e}")
        # slow_mo_start_sfx = None
        # slow_mo_end_sfx = None
        health_boost_sfx = None
        hit_normal_sfx = None
        hit_blade_sfx = None
        bomb1_sfx = None
        bomb_sfx = None
        shield_pickup_sfx = None
        blade_get_power_up_sfx = None

    # Load bounce SFX
    bounce_sfx_list = []
    if SFX_BOUNCE_DIR.is_dir():
        for f_path in SFX_BOUNCE_DIR.iterdir():
            if f_path.suffix.lower() in ['.wav', '.mp3']:
                try:
                    sound = pygame.mixer.Sound(f_path)
                    bounce_sfx_list.append(sound)
                    print(f"Loaded bounce SFX: {f_path.name}")
                except pygame.error as e:
                    print(f"Warning: Could not load bounce SFX {f_path.name} - {e}")
    if not bounce_sfx_list:
        print("Warning: No bounce SFX loaded. Check assets/sfx/bounce/ directory.")

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
    # freeze_token_img = pygame.image.load("assets/pickups/ice_token.webp").convert_alpha() # Removed
    phys.blade_img = blade_img

    space = make_space((ARENA_WIDTH_FROM_CFG, ARENA_HEIGHT_FROM_CFG), border_thickness=BORDER_THICKNESS_CFG)
    # director = Director(SCRIPT_FILE) # Removed Director instance

    # Game state dictionary
    game_state = {
        # "game_speed_factor": 1.0, # Removed
        # "slowmo_end_time": 0,     # Removed
        # "pending_slowmo_factor": 1.0, # Removed
        # "pending_slowmo_duration": 0, # Removed
        # "pending_slowmo_activate_time": 0, # Removed
        "border_original_color": BORDER_COLOR_CFG,
        "border_current_color": BORDER_COLOR_CFG, # Start with original color
        "border_flash_until_time": 0.0,
        "border_flash_color_config": BORDER_FLASH_COLOR_CFG, # Store the configured flash color
        "border_flash_duration_config": DEFAULT_FLASH_DURATION_CFG # Store the configured flash duration
    }

    orbs = []
    pickups = [] # Initialize pickups list here
    saws = [] # Initialize saws list here (though it's not directly in context, good practice)

    # emergency_heart_cooldowns = {} # Orb_name: last_emergency_heart_spawn_time. Still used for safety period hearts.
    item_spawn_cooldowns = {} # Key: f"{orb_name}_{item_kind}", Value: last_spawn_time
    last_unified_pickup_spawn_attempt_time = 0.0

    # Create the context that director and physics callbacks will use
    # This instance holds references to game objects and state that events might modify.
    battle_context = MainBattleContext(
        screen, space, pickups, 
        saw_token_img, heart_token_img, shield_token_img, bomb_token_img, # freeze_token_img, # Removed
        blade_img, 
        active_text_overlays, default_font, game_state, orbs,
        # slow_mo_start_sfx, slow_mo_end_sfx, # Removed
        health_boost_sfx, hit_normal_sfx, hit_blade_sfx,
        bomb1_sfx, bomb_sfx, shield_pickup_sfx, 
        blade_get_power_up_sfx, # ADDED
        camera, particle_emitter,
        PICKUP_RADIUS_CFG, 
        ARENA_WIDTH_FROM_CFG, # Pass the actual arena width used for physics space
        ARENA_HEIGHT_FROM_CFG, # Pass the actual arena height used for physics space
        bounce_sfx_list, # Pass the list of bounce sounds
        ORB_RADIUS_CFG, # Pass orb radius for clamping
        BORDER_THICKNESS_CFG # Pass border thickness for clamping
    )

    for orb_config_data in cfg["orbs"]:
        logo_path = orb_config_data.get("logo", "assets/pickups/blade.png") # Fallback logo
        img = pygame.image.load(logo_path).convert_alpha()
        # Scale logo based on actual orb_radius from config
        scaled_size = int(ORB_RADIUS_CFG * 2), int(ORB_RADIUS_CFG * 2)
        img = pygame.transform.smoothscale(img, scaled_size)
        
        orb_name = orb_config_data.get("name", "Unknown Orb")
        orb_max_hp = orb_config_data.get("max_hp", 6)
        orb_color = tuple(orb_config_data.get("outline_color", [255,255,255]))
        initial_pos = tuple(orb_config_data.get("initial_position", [ARENA_WIDTH_FROM_CFG/2, ARENA_HEIGHT_FROM_CFG/2]))
        initial_vel = tuple(orb_config_data.get("initial_velocity", [0,0]))

        orb = Orb(orb_name, img, None, None, orb_max_hp, outline_color=orb_color)
        orb.attach_shape(space, radius=ORB_RADIUS_CFG) # Use ORB_RADIUS_CFG
        
        # Set initial position and velocity from the config
        orb.body.position = initial_pos
        orb.body.velocity = initial_vel
        
        orbs.append(orb)

    register_orb_collisions(space, battle_context)  # Pass context
    register_saw_hits(space, battle_context)      # Pass context
    register_pickup_handler(space, battle_context) # Pass context
    register_orb_wall_collisions(space, battle_context) # Register wall collisions
    # saws = [] # Moved up
    # pickups = [] # Moved up

    frames, winner = [], None
    current_game_time_sec = 0.0 # Initialize current game time

    for frame_idx in range(int(DURATION_SECONDS * GAME_FPS)):
        previous_game_time_sec = current_game_time_sec
        current_game_time_sec = frame_idx / GAME_FPS
        battle_context.current_game_time_sec = current_game_time_sec # Update context

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return

        # director.tick(current_game_time_sec, battle_context) # Removed director.tick()

        # All slowmo related logic removed from main loop
        # game_speed_factor is effectively 1.0 always now
        
        # dt_logic = (1 / GAME_FPS) # Simplified dt_logic as game_speed_factor is gone
        # The physics step dt is calculated directly later, no need for dt_logic here if only for that.

        # --- Update physics and game objects ---
        # dt = 1.0 / GAME_FPS * game_state["game_speed_factor"] # Old dt with game_speed_factor
        dt = 1.0 / GAME_FPS # Simplified dt as game_speed_factor is gone
        
        # Sub-stepping for physics
        sub_dt = dt / PHYSICS_SUBSTEPS
        for _ in range(PHYSICS_SUBSTEPS):
            space.step(sub_dt)

        # Update orb states (e.g., saw attachment, shield timers)
        for orb in orbs:
            orb.update(dt)

        camera.update(dt)
        particle_emitter.update(dt, arena_rect_for_particles)

        # Update active saws
        for s in phys.active_saws[:]:
            if not s.alive: # Saw might have been destroyed by hit or owner death
                if s in phys.active_saws: # Check if still in list before removing
                     phys.active_saws.remove(s)
                continue
            # s.update() will call s.destroy() if owner is dead, which clears owner.has_saw
            s.update(dt) 
            if not s.alive and s in phys.active_saws: # Re-check after update, if it self-destroyed
                phys.active_saws.remove(s)

        # Update active pickups (for activation timer) # This loop is now only for cleanup
        for p in pickups[:]: # Iterate a copy for safe removal if needed
            if not p.alive: # If a pickup was collected and set to not alive by physics
                if p in pickups:
                    pickups.remove(p)

        # --- Unified Dynamic Pickup Spawning Logic Integration ---
        num_current_pickups = len(pickups)
        if current_game_time_sec >= last_unified_pickup_spawn_attempt_time + UNIFIED_SPAWN_INTERVAL_SECONDS:
            if num_current_pickups < MAX_PICKUPS_ON_SCREEN:
                # Default target orb if no specific assistance is triggered
                default_target_orb = random.choice([o for o in orbs if o.hp > 0] or orbs) 
                target_orb_for_spawn = default_target_orb
                chosen_kind_for_spawn = None
                # spawn_emergency_heart_for_targeted_orb = None # Replaced by more generic system
                specific_orb_assisted = False

                if current_game_time_sec < SAFETY_PERIOD_SECONDS:
                    # Shuffle orbs to give different orbs priority in checks if multiple are low HP
                    shuffled_orbs = random.sample([o for o in orbs if o.hp > 0], len([o for o in orbs if o.hp > 0]))
                    for orb_check in shuffled_orbs:
                        if orb_check.hp <= LOW_HEALTH_THRESHOLD: # hp > 0 check already in shuffled_orbs list comp
                            # 1. Prioritize HEART
                            heart_cooldown_key = f"{orb_check.name}_heart"
                            last_heart_spawn_time = item_spawn_cooldowns.get(heart_cooldown_key, -float('inf'))
                            if current_game_time_sec >= last_heart_spawn_time + EMERGENCY_HEART_COOLDOWN_SECONDS:
                                chosen_kind_for_spawn = "heart"
                                target_orb_for_spawn = orb_check
                                specific_orb_assisted = True
                                print(f"EMERGENCY (Unified): Orb '{target_orb_for_spawn.name}' low HP. Queuing HEART.")
                                break # Assistance found

                            # 2. Prioritize SAW if no heart given and orb lacks saw
                            if not orb_check.has_saw:
                                saw_cooldown_key = f"{orb_check.name}_saw"
                                last_saw_spawn_time = item_spawn_cooldowns.get(saw_cooldown_key, -float('inf'))
                                if current_game_time_sec >= last_saw_spawn_time + ASSISTANCE_ITEM_COOLDOWN_SECONDS:
                                    chosen_kind_for_spawn = "saw"
                                    target_orb_for_spawn = orb_check
                                    specific_orb_assisted = True
                                    print(f"ASSISTANCE (Unified): Orb '{target_orb_for_spawn.name}' low HP & no saw. Queuing SAW.")
                                    break # Assistance found
                            
                            # 3. Prioritize SHIELD if no heart/saw given and orb lacks shield
                            if not orb_check.is_shielded:
                                shield_cooldown_key = f"{orb_check.name}_shield"
                                last_shield_spawn_time = item_spawn_cooldowns.get(shield_cooldown_key, -float('inf'))
                                if current_game_time_sec >= last_shield_spawn_time + ASSISTANCE_ITEM_COOLDOWN_SECONDS:
                                    chosen_kind_for_spawn = "shield"
                                    target_orb_for_spawn = orb_check
                                    specific_orb_assisted = True
                                    print(f"ASSISTANCE (Unified): Orb '{target_orb_for_spawn.name}' low HP & no shield. Queuing SHIELD.")
                                    break # Assistance found
                
                # If no specific assistance was triggered, proceed with normal weighted random spawning for the default_target_orb
                if not chosen_kind_for_spawn:
                    target_orb_for_spawn = default_target_orb # Ensure we use the initially chosen random orb
                    available_kinds = list(PICKUP_KINDS_WEIGHTS.keys())
                    kind_weights = [PICKUP_KINDS_WEIGHTS[k] for k in available_kinds]
                    if available_kinds: # Should always be true with current weights
                        chosen_kind_list = random.choices(available_kinds, weights=kind_weights, k=1)
                        chosen_kind_for_spawn = chosen_kind_list[0]

                if chosen_kind_for_spawn and target_orb_for_spawn and target_orb_for_spawn.hp > 0:
                    prediction_duration = random.uniform(UNIFIED_PREDICTION_TIME_MIN_SECONDS, UNIFIED_PREDICTION_TIME_MAX_SECONDS)
                    if chosen_kind_for_spawn == "heart" and specific_orb_assisted:
                         # Use shorter prediction for emergency hearts to make them more immediate
                        prediction_duration = EMERGENCY_HEART_PREDICTION_TIME_SECONDS 
                    
                    # --- Data for advanced prediction --- 
                    target_orb_sim_data = {
                        "name": target_orb_for_spawn.name, 
                        "pos": pymunk.Vec2d(target_orb_for_spawn.body.position.x, target_orb_for_spawn.body.position.y),
                        "vel": pymunk.Vec2d(target_orb_for_spawn.body.velocity.x, target_orb_for_spawn.body.velocity.y),
                        "radius": target_orb_for_spawn.shape.radius,
                        "id": id(target_orb_for_spawn) # Unique ID for mapping
                    }
                    all_other_orbs_sim_data = [
                        {"name": o.name, 
                         "pos": pymunk.Vec2d(o.body.position.x, o.body.position.y),
                         "vel": pymunk.Vec2d(o.body.velocity.x, o.body.velocity.y),
                         "radius": o.shape.radius,
                         "id": id(o)}
                        for o in orbs if o != target_orb_for_spawn and o.hp > 0 # Only live orbs affect path
                    ]
                    game_env_sim_params = {
                        "arena_width": battle_context.arena_width,
                        "arena_height": battle_context.arena_height,
                        "border_thickness": battle_context.border_thickness_cfg,
                        "space_damping": space.damping, # Get damping from main space
                        "max_velocity": PRED_MAX_ORB_VELOCITY,
                        "physics_substeps": PHYSICS_SUBSTEPS
                    }
                    num_prediction_steps = int(prediction_duration / (1.0 / GAME_FPS)) # Match game's physics rate for steps

                    final_spawn_pos_vec = predict_orb_future_path_point(
                        target_orb_sim_data, 
                        all_other_orbs_sim_data, 
                        game_env_sim_params, 
                        prediction_duration, 
                        max(1, num_prediction_steps) # Ensure at least 1 step
                    )
                    final_spawn_pos = (final_spawn_pos_vec.x, final_spawn_pos_vec.y)
                    
                    # Clamping is still important after prediction
                    min_x = battle_context.border_thickness_cfg + battle_context.orb_radius_cfg + battle_context.pickup_radius
                    max_x = battle_context.arena_width - battle_context.border_thickness_cfg - battle_context.orb_radius_cfg - battle_context.pickup_radius
                    min_y = battle_context.border_thickness_cfg + battle_context.orb_radius_cfg + battle_context.pickup_radius
                    max_y = battle_context.arena_height - battle_context.border_thickness_cfg - battle_context.orb_radius_cfg - battle_context.pickup_radius
                    clamped_x = max(min_x, min(final_spawn_pos[0], max_x))
                    clamped_y = max(min_y, min(final_spawn_pos[1], max_y))
                    final_spawn_pos = (clamped_x, clamped_y)
                    
                    img_surface = None
                    if chosen_kind_for_spawn == "heart": img_surface = heart_token_img
                    elif chosen_kind_for_spawn == "saw": img_surface = saw_token_img
                    elif chosen_kind_for_spawn == "shield": img_surface = shield_token_img
                    elif chosen_kind_for_spawn == "bomb": img_surface = bomb_token_img

                    if img_surface:
                        new_pickup = Pickup(
                            kind=chosen_kind_for_spawn,
                            img_surface=img_surface,
                            pos=final_spawn_pos,
                            space=space,
                            radius=battle_context.pickup_radius,
                        )
                        pickups.append(new_pickup)
                        print(f"SPAWNED (Pred) '{chosen_kind_for_spawn.upper()}' for {target_orb_for_spawn.name} at {final_spawn_pos} (pred {prediction_duration:.2f}s)")
                        # if spawn_emergency_heart_for_targeted_orb: # Old system
                        #     emergency_heart_cooldowns[spawn_emergency_heart_for_targeted_orb.name] = current_game_time_sec
                        if specific_orb_assisted: # New system: update cooldown for the specific item and orb
                            cooldown_key = f"{target_orb_for_spawn.name}_{chosen_kind_for_spawn}"
                            item_spawn_cooldowns[cooldown_key] = current_game_time_sec
            
            last_unified_pickup_spawn_attempt_time = current_game_time_sec

        # phys.handle_bomb_explosions(...) is removed as bombs are instant.

        living = [o for o in orbs if o.hp > 0]
        if winner is None and len(living) == 1 and len(orbs) > 1: # Ensure game started with >1 orb
            winner = living[0]
            win_frame = frame_idx
            print(f"WINNER: {winner.name} at frame {win_frame} ({current_game_time_sec:.2f}s)")
            # Optionally add a text overlay for winner announcement via director or directly
            # Example direct text overlay (not using director for this immediate announcement)
            win_text_payload = {
                "text": f"{winner.name} Wins!",
                "duration": 5, # Display for 5 seconds
                "position": "center",
                "font_size": 80,
                "color": winner.outline_color # Use winner's color
            }
            # battle_context.handle_text_overlay_event(win_text_payload) # If you want to use existing handler
            # Or manage a separate list for such overlays if not tied to director events.
            # For now, just printing.

        # Border flash logic
        if game_state["border_flash_until_time"] > 0:
            if current_game_time_sec >= game_state["border_flash_until_time"]:
                game_state["border_current_color"] = game_state["border_original_color"]
                game_state["border_flash_until_time"] = 0 
        # else: color remains original color (or whatever it was last set to)

        screen.fill((20, 20, 20))

        # Draw HP bars at the top
        for i, orb in enumerate(battle_context.orbs):
            # The 'y' parameter is no longer needed as it's calculated internally by draw_top_hp_bar
            draw_top_hp_bar(screen, orb, index=i, total_orbs=len(battle_context.orbs))
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

        # Arena rendering offsets
        # ARENA_X0 is now 0, so render_offset_x is just camera.offset.x
        arena_render_offset_x = ARENA_X0 + camera.offset.x 
        arena_render_offset_y = ARENA_Y0 + camera.offset.y

        pygame.draw.rect(
            screen, game_state["border_current_color"], 
            (arena_render_offset_x, arena_render_offset_y, 
             ARENA_WIDTH_FROM_CFG, ARENA_HEIGHT_FROM_CFG), # Use ARENA_WIDTH_FROM_CFG
            width=BORDER_THICKNESS_CFG)

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
            if frame_idx - win_frame < 2 * GAME_FPS:
                giant = pygame.transform.smoothscale(
                    winner.logo_surface, (300, 300))
                rect = giant.get_rect(center=(CANVAS_W//2, CANVAS_H//2))
                screen.blit(giant, rect)
            else:
                break

        pygame.display.flip()
        frames.append(surface_to_array(screen).copy())
        clock.tick(GAME_FPS)

    pygame.quit()
    OUT.mkdir(exist_ok=True)
    video_path = OUT / f"{cfg['title'].replace(' ','_')}.mp4"
    ImageSequenceClip(frames, fps=GAME_FPS).write_videofile(
        video_path.as_posix(), codec="libx264")
    print("Saved ->", video_path)

class MainBattleContext:
    def __init__(self, screen, space, pickups_list,
                 saw_token_img, heart_token_img, shield_token_img, bomb_token_img, # freeze_token_img, # Removed
                 blade_img,
                 active_text_overlays_list, default_font_instance,
                 game_state_dict, orbs_list,
                 health_boost_sfx=None, hit_normal_sfx=None, hit_blade_sfx=None,
                 bomb1_sfx=None, bomb_sfx=None, shield_pickup_sfx=None, # Added new SFX params
                 blade_get_power_up_sfx=None, # ADDED
                 camera_instance=None, particle_emitter_instance=None,
                 pickup_radius=20, # Added pickup_radius
                 arena_width=1080, arena_height=1920, # Added arena dimensions
                 bounce_sfx_list=None, # Added bounce_sfx_list
                 orb_radius_cfg=60,    # Added orb_radius_cfg for clamping
                 border_thickness_cfg=6 # Added border_thickness_cfg for clamping
                ):
        self.screen = screen
        self.space = space
        self.pickups = pickups_list
        self.saw_token_img = saw_token_img
        self.heart_token_img = heart_token_img
        self.shield_token_img = shield_token_img
        self.bomb_token_img = bomb_token_img
        # self.freeze_token_img = freeze_token_img # Removed
        self.blade_img = blade_img
        self.active_text_overlays = active_text_overlays_list
        self.default_font = default_font_instance
        self.game_state = game_state_dict
        self.orbs = orbs_list # This is a reference to the main list of orbs
        self.current_game_time_sec = 0.0 # Will be updated by main loop
        # SFX
        self.health_boost_sfx = health_boost_sfx
        self.hit_normal_sfx = hit_normal_sfx
        self.hit_blade_sfx = hit_blade_sfx
        self.bomb1_sfx = bomb1_sfx
        self.bomb_sfx = bomb_sfx
        self.shield_pickup_sfx = shield_pickup_sfx
        self.blade_get_power_up_sfx = blade_get_power_up_sfx # ADDED
        # Visuals & Effects
        self.camera = camera_instance
        self.particle_emitter = particle_emitter_instance
        self.pickup_radius = pickup_radius # Store pickup_radius
        self.arena_width = arena_width # Store arena width (outer dimension of border segments)
        self.arena_height = arena_height # Store arena height (outer dimension of border segments)
        self.bounce_sfx = bounce_sfx_list # Store the list of bounce sounds
        self.orb_radius_cfg = orb_radius_cfg
        self.border_thickness_cfg = border_thickness_cfg

    def play_sfx(self, sfx_to_play):
        if sfx_to_play:
            sfx_to_play.play()

    def play_random_bounce_sfx(self):
        if self.bounce_sfx:
            random.choice(self.bounce_sfx).play()
        # else:
            # print("DEBUG: No bounce SFX available to play.")

    def handle_spawn_pickup_event(self, payload):
        kind = payload.get("kind")
        x = payload.get("x")
        y = payload.get("y")

        # Determine position
        if x is not None and y is not None:
            # Handle normalized (0-1) or absolute coordinates from payload
            # ARENA_W and ARENA_H here should ideally be the actual arena dimensions used.
            # Using self.arena_width and self.arena_height stored in context
            current_arena_w = self.arena_width 
            current_arena_h = self.arena_height

            pos_x = x * current_arena_w if 0 <= x <= 1 else x
            pos_y = y * current_arena_h if 0 <= y <= 1 else y
            # Clamp to be within arena, away from edges for pickup radius
            pos_x = max(self.pickup_radius, min(pos_x, current_arena_w - self.pickup_radius))
            pos_y = max(self.pickup_radius, min(pos_y, current_arena_h - self.pickup_radius))
            pickup_pos = (pos_x, pos_y)
        else: # Random position if x or y is missing
            current_arena_w = self.arena_width
            current_arena_h = self.arena_height
            rand_x = random.uniform(self.pickup_radius, current_arena_w - self.pickup_radius)
            rand_y = random.uniform(self.pickup_radius, current_arena_h - self.pickup_radius)
            pickup_pos = (rand_x, rand_y)

        img_surface = None
        if kind == "saw": img_surface = self.saw_token_img
        elif kind == "heart": img_surface = self.heart_token_img
        elif kind == "shield": img_surface = self.shield_token_img
        elif kind == "bomb": img_surface = self.bomb_token_img
        # elif kind == "freeze": img_surface = self.freeze_token_img # Removed
        else: print(f"Warning: Unknown pickup kind '{kind}' in event, no image.")

        if img_surface:
            # The Pickup class itself needs to be aware of its radius for its shape
            # Assuming Pickup class in engine.game_objects.py is modified to accept radius
            # or that its default radius matches self.pickup_radius
            new_pickup = Pickup(kind, img_surface, pickup_pos, self.space, radius=self.pickup_radius) # REMOVED current_game_time_sec
            self.pickups.append(new_pickup)
            if kind == "bomb": # If a bomb pickup is spawned (this is for the pickup itself, not explosion)
                # You might not flash for bomb *spawn*, but for its *explosion*.
                # For demonstration, let's say picking up a bomb item also causes a small flash.
                # This is an example of how to call the flash logic.
                # self.game_state["border_current_color"] = self.game_state["border_flash_color_config"]
                # self.game_state["border_flash_until_time"] = self.current_game_time_sec + 0.5 # Short flash for pickup
                pass
        else:
            print(f"Could not spawn pickup of kind '{kind}' due to missing image.")

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

    def handle_bomb_pickup_effect(self, exploding_orb_pos): # Example: new method or part of bomb logic
        """Triggers effects for a bomb, including border flash."""
        # Existing bomb logic (particles, camera shake, damage etc.) would go here or be called from here
        # ... (imagine your bomb explosion logic here) ...

        # Trigger border flash
        self.game_state["border_current_color"] = self.game_state["border_flash_color_config"]
        self.game_state["border_flash_until_time"] = self.current_game_time_sec + self.game_state["border_flash_duration_config"]
        print(f"BOMB EFFECT: Border flash triggered until {self.game_state['border_flash_until_time']:.2f}s")

# Helper function for predictive spawning
def predict_orb_future_path_point(target_orb_data, all_orbs_data, game_env_params, duration_to_predict, num_steps):
    """
    Simulates the target orb's movement in a temporary space to predict future position.
    target_orb_data: {"name": str, "pos": Vec2d, "vel": Vec2d, "radius": float, "id": int}
    all_orbs_data: list of dicts, each like target_orb_data, for *other* orbs.
    game_env_params: {"arena_width": float, "arena_height": float, "border_thickness": float, 
                      "space_damping": float, "max_velocity": float, "physics_substeps": int}
    duration_to_predict: float (total time in seconds)
    num_steps: int (how many steps to divide the duration into for simulation - each step is one game frame)
    Returns: predicted Vec2d position of the target orb, or its last known if error.
    """
    temp_space = pymunk.Space()
    temp_space.damping = game_env_params["space_damping"]
    
    # dt_step is the duration of one main game frame for the prediction
    # If the main game uses GANE_FPS (e.g. 60), then dt_step = 1/60 if num_steps matches prediction_duration*GAME_FPS
    # num_steps is int(prediction_duration / (1.0 / GAME_FPS))
    # So dt_step = prediction_duration / (prediction_duration * GAME_FPS) = 1.0 / GAME_FPS
    # This is correct: each step in the outer loop simulates one "game frame"
    dt_per_simulation_step = duration_to_predict / num_steps 

    # Add arena boundaries to temp_space, matching engine/physics.py:make_space
    # arena_width and arena_height in game_env_params are the inner dimensions of the playable area.
    # border_thickness is the thickness of the walls.
    
    border_segment_radius = game_env_params["border_thickness"] / 2.0
    arena_w = game_env_params["arena_width"]
    arena_h = game_env_params["arena_height"]

    # These points define the centerlines of the wall segments.
    # The segments' own radius (border_segment_radius) makes them thick.
    # This setup ensures the *inner edges* of the physical walls are at:
    # y=0, y=arena_h, x=0, x=arena_w.
    
    # Coordinates for the centerlines of the wall segments
    # Top: centerline at y = -border_segment_radius. Inner edge at y = 0.
    # Bottom: centerline at y = arena_h + border_segment_radius. Inner edge at y = arena_h.
    # Left: centerline at x = -border_segment_radius. Inner edge at x = 0.
    # Right: centerline at x = arena_w + border_segment_radius. Inner edge at x = arena_w.

    static_body = temp_space.static_body
    wall_segments_params = [
        # Top wall
        ((-border_segment_radius, -border_segment_radius), (arena_w + border_segment_radius, -border_segment_radius), border_segment_radius),
        # Right wall
        ((arena_w + border_segment_radius, -border_segment_radius), (arena_w + border_segment_radius, arena_h + border_segment_radius), border_segment_radius),
        # Bottom wall
        ((arena_w + border_segment_radius, arena_h + border_segment_radius), (-border_segment_radius, arena_h + border_segment_radius), border_segment_radius),
        # Left wall
        ((-border_segment_radius, arena_h + border_segment_radius), (-border_segment_radius, -border_segment_radius), border_segment_radius)
    ]

    for p1, p2, radius in wall_segments_params:
        segment = pymunk.Segment(static_body, p1, p2, radius)
        segment.elasticity = 1.0  # Standard wall elasticity
        segment.friction = 0.5    # Standard wall friction
        segment.collision_type = phys.WALL_COLLISION_TYPE # Match main game wall collision type
        temp_space.add(segment)

    # Add orbs to temp_space
    temp_orbs_map = {} # id -> Pymunk Body

    # Add target orb first
    target_body = pymunk.Body(mass=1, moment=float('inf')) 
    target_body.position = target_orb_data["pos"]
    target_body.velocity = target_orb_data["vel"]
    target_shape = pymunk.Circle(target_body, target_orb_data["radius"])
    target_shape.elasticity = 1.0 # TODO: Get from actual orb config or a shared constant
    target_shape.friction = 0.1   # TODO: Get from actual orb config or a shared constant
    target_shape.collision_type = 1 # Orb collision type (assuming 1 for orbs)
    temp_space.add(target_body, target_shape)
    temp_orbs_map[target_orb_data["id"]] = target_body

    # Add other orbs
    for orb_data in all_orbs_data:
        if orb_data["id"] == target_orb_data["id"]: continue
        body = pymunk.Body(mass=1, moment=float('inf'))
        body.position = orb_data["pos"]
        body.velocity = orb_data["vel"]
        shape = pymunk.Circle(body, orb_data["radius"])
        shape.elasticity = 1.0 # TODO: Get from actual orb config
        shape.friction = 0.1   # TODO: Get from actual orb config
        shape.collision_type = 1 # Orb collision type
        temp_space.add(body, shape)
        temp_orbs_map[orb_data["id"]] = body # Store the body for velocity capping
    
    # Main simulation loop (num_steps corresponds to game frames)
    # If PHYSICS_SUBSTEPS is used in the main game, replicate it here.
    # physics_substeps = game_env_params.get("physics_substeps", 1) # Default to 1 if not provided
    # sub_dt = dt_per_simulation_step / physics_substeps
    
    # For now, let's assume game_env_params will include "physics_substeps" matching main game
    # And "game_fps" for calculating sub_dt properly.
    # The current num_steps results in dt_per_simulation_step being 1/GAME_FPS.
    # So, this dt_per_simulation_step IS the main game's frame time.
    
    main_game_physics_substeps = game_env_params.get("physics_substeps", 1) # Get from params, default 1
    actual_sub_dt = dt_per_simulation_step / main_game_physics_substeps

    for _ in range(num_steps): # Each step is one "game frame"
        # Apply velocity cap before stepping physics for this frame
        for b_id, b in temp_orbs_map.items():
            velocity = b.velocity
            speed = velocity.length
            if speed > game_env_params["max_velocity"]:
                b.velocity = velocity.normalized() * game_env_params["max_velocity"]
        
        # Perform physics sub-steps for this "game frame"
        for _ in range(main_game_physics_substeps):
            temp_space.step(actual_sub_dt)

    predicted_pos = temp_orbs_map[target_orb_data["id"]].position
    # print(f"DEBUG PREDICT: Target '{target_orb_data[\"name\"]}', Start: {target_orb_data[\"pos\"]}, End: {predicted_pos}, Vel: {target_orb_data[\"vel\"]}")
    return predicted_pos

if __name__ == "__main__":
    main()