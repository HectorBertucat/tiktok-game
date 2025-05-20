# engine/physics.py
import pymunk, random
from engine.game_objects import Saw
import pygame

active_saws = []

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
        # Orb-orb collisions now only cause a bounce.
        # No damage, no sfx, no camera shake, no particles from direct orb-orb collision.
        # If you want a very light, distinct sound for bounces, you could add it here.
        # For example:
        # if arbiter.total_impulse.length > 10: # Only if bounce is noticeable
        #     battle_context.play_sfx(battle_context.orb_bounce_sfx) # Assuming you add an orb_bounce_sfx
        pass # Explicitly do nothing for effects/damage

    handler.post_solve = post_solve


def register_saw_hits(space, battle_context, dmg=2):
    """
    orb (1) touche scie (2) —> celui qui n'est PAS le propriétaire perd dmg HP
    """
    handler = space.add_collision_handler(1, 2)

    def post_solve(arbiter, _space, _data):
        shape_a, shape_b = arbiter.shapes
        saw_shape = shape_a if hasattr(shape_a, "saw_ref") else shape_b
        orb_shape = shape_b if hasattr(shape_a, "saw_ref") else shape_a
        
        saw   = saw_shape.saw_ref
        orb   = orb_shape.orb_ref
        
        if orb == saw.owner or not saw.alive:
            return
        
        emission_pos_orb = orb.body.position # Fallback
        contact_points = arbiter.contact_point_set.points
        if contact_points:
            # Determine which point (point_a or point_b) is on the orb
            # If shape_a was the orb, point_a is on orb. If shape_b was orb, point_b is on orb.
            # However, point_a and point_b are world coordinates of the contact on each shape.
            # So, either point_a or point_b from the set can be used as the world emission point.
            emission_pos_orb = pygame.math.Vector2(contact_points[0].point_a.x, contact_points[0].point_a.y)

        orb.take_hit(dmg)
        battle_context.play_sfx(battle_context.hit_blade_sfx)
        battle_context.camera.shake(intensity=8, duration=0.25)
        if battle_context.particle_emitter:
            battle_context.particle_emitter.emit(num_particles=70, position=emission_pos_orb, 
                                                 base_particle_color=orb.outline_color,
                                                 base_velocity_scale=90, lifespan_s=0.7, 
                                                 max_length=18, base_thickness=3)
        saw.destroy(space)

    handler.post_solve = post_solve

def register_pickup_handler(space, battle_context):
    """
    orb (1) touche pickup (3) → applique l'effet, supprime le token.
    """
    handler = space.add_collision_handler(1, 3)

    def begin(arbiter, _space, _data):
        orb_shape, pick_shape = arbiter.shapes
        orb   = orb_shape.orb_ref
        pickup = pick_shape.pickup_ref
        if not pickup.alive:
            return False

        if pickup.kind == 'saw':
            # équipe l'orb d'une scie (si pas déjà)
            if not getattr(orb, "saw_equipped", None):
                orb.saw_equipped = Saw(battle_context.blade_img, orb, space)
                globals()["active_saws"].append(orb.saw_equipped)
        elif pickup.kind == 'heart':
            orb.heal(2)
            battle_context.play_sfx(battle_context.health_boost_sfx)
        # d'autres kinds plus tard…

        pickup.destroy(space)
        return False  # on ne veut pas la physique standard

    handler.begin = begin