# engine/physics.py
import pymunk, random
from engine.game_objects import Saw
import pygame

active_saws = []
# active_bombs = [] # No longer needed

# DEFAULT_BOMB_COUNTDOWN = 3.0 # Unused
DEFAULT_BOMB_RADIUS = 150
DEFAULT_BOMB_DAMAGE = 3
DEFAULT_BOMB_IMPULSE = 7500
# FREEZE_DURATION = 2.0 # Freeze is now until next hit

# --- Helper for Post-Step Unfreezing ---
def _unfreeze_orb_post_step(space, key, orb_to_unfreeze):
    if orb_to_unfreeze.is_frozen and orb_to_unfreeze.original_body_type is not None:
        print(f"DEBUG: Post-step unfreezing {orb_to_unfreeze.name}. Restoring body type: {orb_to_unfreeze.original_body_type}")
        orb_to_unfreeze.body.body_type = orb_to_unfreeze.original_body_type
        orb_to_unfreeze.is_frozen = False
        orb_to_unfreeze.original_body_type = None
        # Potentially play an unfreeze sound effect via battle_context
    elif not orb_to_unfreeze.is_frozen:
        print(f"DEBUG: Post-step unfreeze called for {orb_to_unfreeze.name}, but it's not marked as frozen.")
    elif orb_to_unfreeze.original_body_type is None:
        print(f"DEBUG: Post-step unfreeze called for {orb_to_unfreeze.name}, but original_body_type is missing.")

def make_space(arena_size=(800, 800)):
    space = pymunk.Space()
    space.damping = 0.99

    w, h = arena_size
    static = [pymunk.Segment(space.static_body, (0, 0), (w, 0), 2),
              pymunk.Segment(space.static_body, (w, 0), (w, h), 2),
              pymunk.Segment(space.static_body, (w, h), (0, h), 2),
              pymunk.Segment(space.static_body, (0, h), (0, 0), 2)]
    for s in static:
        s.elasticity = 1.0
        space.add(s)

    return space

def register_orb_collisions(space, battle_context, dmg=1):
    handler = space.add_collision_handler(1, 1)  # orb vs orb

    def post_solve(arbiter, _space, _data):
        orb_a, orb_b = arbiter.shapes[0].orb_ref, arbiter.shapes[1].orb_ref
        # Unfreeze logic: if a frozen orb is hit, it unfreezes post-step.
        if orb_a.is_frozen:
            print(f"DEBUG: Orb '{orb_a.name}' (frozen) hit by Orb '{orb_b.name}'. Scheduling unfreeze.")
            space.add_post_step_callback(_unfreeze_orb_post_step, (id(orb_a), "unfreeze"), orb_a)
        if orb_b.is_frozen:
            print(f"DEBUG: Orb '{orb_b.name}' (frozen) hit by Orb '{orb_a.name}'. Scheduling unfreeze.")
            space.add_post_step_callback(_unfreeze_orb_post_step, (id(orb_b), "unfreeze"), orb_b)
        pass # Orb-orb collision bounce only, no damage etc.

    handler.post_solve = post_solve

def register_saw_hits(space, battle_context, dmg=2):
    """
    orb (1) touche scie (2) —> celui qui n'est PAS le propriétaire perd dmg HP
    """
    handler = space.add_collision_handler(1, 2)

    def post_solve(arbiter, _space, _data):
        saw_shape = arbiter.shapes[0] if hasattr(arbiter.shapes[0], "saw_ref") else arbiter.shapes[1]
        orb_shape = arbiter.shapes[1] if hasattr(arbiter.shapes[0], "saw_ref") else arbiter.shapes[0]
        
        saw = saw_shape.saw_ref
        orb_hit_by_saw = orb_shape.orb_ref

        # If the orb hit by the saw is frozen, it unfreezes post-step.
        if orb_hit_by_saw.is_frozen:
            print(f"DEBUG: Orb '{orb_hit_by_saw.name}' (frozen) hit by Saw from '{saw.owner.name if saw.owner else 'N/A'}'. Scheduling unfreeze.")
            space.add_post_step_callback(_unfreeze_orb_post_step, (id(orb_hit_by_saw), "unfreeze"), orb_hit_by_saw)
            # Frozen orbs take damage from saw but don't get knockback if kinematic
            # The take_hit below will still apply, which is fine.

        # Standard saw hit logic (damage, effects, saw destruction)
        if orb_hit_by_saw == saw.owner or not saw.alive:
            return
        
        # If saw owner is frozen, the saw should still work (it's kinematic)
        # If the target orb is frozen, it still takes damage. Repulsion is skipped if kinematic.

        emission_pos_orb = orb_hit_by_saw.body.position
        contact_points = arbiter.contact_point_set.points
        if contact_points:
            emission_pos_orb = pygame.math.Vector2(contact_points[0].point_a.x, contact_points[0].point_a.y)

        orb_hit_by_saw.take_hit(dmg)
        battle_context.play_sfx(battle_context.hit_blade_sfx)
        battle_context.camera.shake(intensity=8, duration=0.25)
        if battle_context.particle_emitter:
            battle_context.particle_emitter.emit(num_particles=70, position=emission_pos_orb,
                                                 base_particle_color=orb_hit_by_saw.outline_color,
                                                 base_velocity_scale=90, lifespan_s=0.7,
                                                 max_length=18, base_thickness=3)
        saw.destroy() # Call new destroy without space arg

    handler.post_solve = post_solve

def register_pickup_handler(space, battle_context):
    handler = space.add_collision_handler(1, 3) # orb vs pickup

    # --- Helper for Post-Step Freezing ---
    def _freeze_orb_post_step(space_arg, key, orb_to_freeze):
        # Note: space_arg and key are passed by Pymunk but we use orb_to_freeze directly
        if not orb_to_freeze.is_frozen: # Check if not already unfrozen by another event before this post-step runs
            print(f"DEBUG: Post-step freeze called for {orb_to_freeze.name}, but it's no longer marked to be frozen. Aborting freeze.")
            return

        if orb_to_freeze.hp > 0 and orb_to_freeze.body.body_type != pymunk.Body.KINEMATIC:
            print(f"DEBUG: Post-step freezing {orb_to_freeze.name}. Setting KINEMATIC.")
            orb_to_freeze.original_body_type = orb_to_freeze.body.body_type
            orb_to_freeze.body.body_type = pymunk.Body.KINEMATIC
            orb_to_freeze.body.velocity = (0,0)
            # No duration, is_frozen remains True until an unfreezing event
            # Potentially play freeze_start_sfx via battle_context
        elif orb_to_freeze.body.body_type == pymunk.Body.KINEMATIC and orb_to_freeze.is_frozen:
             print(f"DEBUG: Post-step freeze for {orb_to_freeze.name}: Already kinematic and marked frozen.")
        elif orb_to_freeze.hp <= 0:
             print(f"DEBUG: Post-step freeze for {orb_to_freeze.name}: Orb is dead, cannot freeze.")
             orb_to_freeze.is_frozen = False # Ensure it's not stuck in a frozen state if it died before post-step

    def begin(arbiter, _space, _data):
        current_time_sec = battle_context.current_game_time_sec # Available in context

        orb_shape, pick_shape = arbiter.shapes
        if not hasattr(orb_shape, 'orb_ref') or not hasattr(pick_shape, 'pickup_ref'):
            return False 

        orb = orb_shape.orb_ref
        pickup = pick_shape.pickup_ref

        # Generic pre-pickup checks
        if not pickup.alive:
            return False
        if orb.is_frozen: # Frozen orbs cannot pick up items
            print(f"DEBUG: Orb '{orb.name}' is frozen. Cannot pick up '{pickup.kind}'.")
            return False

        print(f"DEBUG: Orb '{orb.name}' attempting to pick up '{pickup.kind}'. Orb status - Frozen: {orb.is_frozen}, Saw: {orb.has_saw is not None}, Shielded: {orb.is_shielded}")

        # Pickup-specific logic
        if pickup.kind == 'saw':
            if not orb.has_saw:
                orb.has_saw = Saw(battle_context.blade_img, orb, space) # Saw now stores its own space
                globals()["active_saws"].append(orb.has_saw)
                print(f"'{orb.name}' picked up a saw!")
                # battle_context.play_sfx(battle_context.saw_pickup_sfx)
            else:
                print(f"DEBUG: Orb '{orb.name}' already has a saw.")
        
        elif pickup.kind == 'heart':
            orb.heal(2)
            battle_context.play_sfx(battle_context.health_boost_sfx)
            print(f"'{orb.name}' picked up a heart!")

        elif pickup.kind == 'shield':
            if not orb.is_shielded:
                orb.is_shielded = True
                battle_context.play_sfx(battle_context.shield_pickup_sfx)
                print(f"'{orb.name}' picked up a shield!")
            else:
                orb.is_shielded = True # Refresh shield if picked up again
                battle_context.play_sfx(battle_context.shield_pickup_sfx)
                print(f"'{orb.name}' refreshed shield!")

        elif pickup.kind == 'bomb': # Instant explosion
            print(f"DEBUG: Orb '{orb.name}' touched BOMB pickup. Exploding instantly!")
            exploding_orb = orb
            battle_context.play_sfx(battle_context.bomb1_sfx)
            battle_context.play_sfx(battle_context.bomb_sfx)
            battle_context.camera.shake(intensity=12, duration=0.35)

            if battle_context.particle_emitter:
                battle_context.particle_emitter.emit(num_particles=150, position=pickup.body.position,
                                                     base_particle_color=(255,100,0),
                                                     base_velocity_scale=150, lifespan_s=1.2,
                                                     max_length=30, base_thickness=5)

            for orb_in_game in battle_context.orbs:
                if orb_in_game.hp <= 0: continue
                is_target_frozen = orb_in_game.is_frozen
                distance_vec = orb_in_game.body.position - exploding_orb.body.position
                distance = distance_vec.length
                if distance <= DEFAULT_BOMB_RADIUS:
                    orb_in_game.take_hit(DEFAULT_BOMB_DAMAGE)
                    print(f"  Bomb hits '{orb_in_game.name}'! Dmg: {DEFAULT_BOMB_DAMAGE}, Frozen: {is_target_frozen}")
                    if not is_target_frozen:
                        if distance > 0: impulse_vec = distance_vec.normalized() * DEFAULT_BOMB_IMPULSE
                        else: impulse_vec = pymunk.Vec2d(random.uniform(-1,1), random.uniform(-1,1)).normalized() * DEFAULT_BOMB_IMPULSE
                        force_multiplier = 1.5 if orb_in_game == exploding_orb else 1.0
                        orb_in_game.body.apply_impulse_at_local_point(impulse_vec * force_multiplier, (0,0))
                        print(f"    Applied impulse {impulse_vec.length * force_multiplier:.0f} to '{orb_in_game.name}'.")
            print(f"Bomb triggered by '{orb.name}' processed.")

        elif pickup.kind == 'freeze':
            # The orb that picks up the freeze token freezes ITSELF.
            if not orb.is_frozen: # Only freeze if not already frozen
                print(f"DEBUG: Orb '{orb.name}' picked up freeze. Scheduling self-freeze.")
                orb.is_frozen = True # Mark for freezing
                # Schedule the actual kinematic change post-step
                # Key includes orb id to allow potential cancellation if orb dies before post-step, though _freeze_orb_post_step handles hp check.
                _space.add_post_step_callback(_freeze_orb_post_step, (id(orb), "self_freeze"), orb)
                # battle_context.play_sfx(battle_context.freeze_pickup_sfx)
            else:
                print(f"DEBUG: Orb '{orb.name}' picked up freeze, but is already frozen.")

        # Common to all successful pickups that consume the token:
        pickup.destroy(space)
        return False # Collision is handled, no default physics response

    handler.begin = begin
    # Removed the old _freeze_opponent_post_step as freeze is now self-freeze

# def handle_bomb_explosions(space, battle_context, current_time_sec): # No longer needed
#     ...