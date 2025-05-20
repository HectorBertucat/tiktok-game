# engine/physics.py
import pymunk, random

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

def register_orb_collisions(space, dmg=1):
    handler = space.add_collision_handler(1, 1)  # orb vs orb

    def post_solve(arbiter, _space, _data):
        # On ne décompte qu'un coup si l'impulsion est assez forte
        if arbiter.total_impulse.length < 50:
            return
        o1, o2 = arbiter.shapes[0].orb_ref, arbiter.shapes[1].orb_ref
        o1.take_hit(dmg)
        o2.take_hit(dmg)

    handler.post_solve = post_solve


def register_saw_hits(space, dmg=2):
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
        saw.destroy(space)   # one-shot

    handler.post_solve = post_solve