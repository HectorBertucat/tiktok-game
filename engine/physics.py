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