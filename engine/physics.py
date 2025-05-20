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