# engine/physics.py
import pymunk, random
from engine.game_objects import Saw

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
        # On ne décompte qu'un coup si l'impulsion est assez forte
        if arbiter.total_impulse.length < 50:
            return
        o1, o2 = arbiter.shapes[0].orb_ref, arbiter.shapes[1].orb_ref
        o1.take_hit(dmg)
        battle_context.camera.shake(intensity=5, duration=0.2)
        # Convert Pymunk Vec2d to tuple for particle emitter position
        pos_o1 = (o1.body.position.x, o1.body.position.y)
        battle_context.particle_emitter.emit(position=pos_o1, count=30, initial_lifetime=0.4, initial_radius=5, spread_velocity=50)
        o2.take_hit(dmg)
        battle_context.camera.shake(intensity=5, duration=0.2) # Or maybe a slightly different shake or combine them? For now, separate shakes.
        # Convert Pymunk Vec2d to tuple for particle emitter position
        pos_o2 = (o2.body.position.x, o2.body.position.y)
        battle_context.particle_emitter.emit(position=pos_o2, count=30, initial_lifetime=0.4, initial_radius=5, spread_velocity=50)
        battle_context.play_sfx(battle_context.hit_normal_sfx)

    handler.post_solve = post_solve


def register_saw_hits(space, battle_context, dmg=2):
    """
    orb (1) touche scie (2) —> celui qui n'est PAS le propriétaire perd dmg HP
    """
    handler = space.add_collision_handler(1, 2)

    def post_solve(arbiter, _space, _data):
        shape_a, shape_b = arbiter.shapes
        # identifie qui est le saw, qui est l'orb
        saw   = shape_a.saw_ref if hasattr(shape_a, "saw_ref") else shape_b.saw_ref
        orb   = shape_a.orb_ref if hasattr(shape_a, "orb_ref") else shape_b.orb_ref
        if orb == saw.owner or not saw.alive:
            return           # on touche son propre porteur => rien
        orb.take_hit(dmg)
        battle_context.camera.shake(intensity=5, duration=0.2)
        # Convert Pymunk Vec2d to tuple for particle emitter position
        pos_orb = (orb.body.position.x, orb.body.position.y)
        battle_context.particle_emitter.emit(position=pos_orb, count=30, initial_lifetime=0.4, initial_radius=5, spread_velocity=50)
        battle_context.play_sfx(battle_context.hit_blade_sfx)
        saw.destroy(space)   # one-shot

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