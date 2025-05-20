import pygame
import random
import math
from dataclasses import dataclass

@dataclass
class Particle:
    position: pygame.math.Vector2
    velocity: pygame.math.Vector2
    lifespan: float
    max_lifespan: float
    # For line particles:
    length: float
    max_length: float
    thickness: int
    angle: float # Derived from velocity for drawing line
    # Removed radius fields
    color: tuple[int, int, int]
    start_color: tuple[int, int, int]
    end_color: tuple[int, int, int]

    def __init__(self, position, velocity, lifespan, length, thickness, color, end_color=None):
        self.position = pygame.math.Vector2(position)
        self.velocity = pygame.math.Vector2(velocity)
        self.lifespan = lifespan
        self.max_lifespan = lifespan
        self.length = length
        self.max_length = length
        self.thickness = thickness
        self.angle = self.velocity.as_polar()[1] # Get angle from velocity vector
        self.start_color = color
        self.end_color = end_color if end_color else color
        self.color = color

    def update(self, dt):
        self.position += self.velocity * dt
        self.lifespan -= dt
        
        life_ratio = max(0, self.lifespan / self.max_lifespan)
        self.length = self.max_length * life_ratio # Length shrinks
        # Thickness could also scale if desired: self.thickness = int(self.max_thickness * life_ratio)
        
        r = int(self.start_color[0] * life_ratio + self.end_color[0] * (1 - life_ratio))
        g = int(self.start_color[1] * life_ratio + self.end_color[1] * (1 - life_ratio))
        b = int(self.start_color[2] * life_ratio + self.end_color[2] * (1 - life_ratio))
        self.color = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
        # Update angle if velocity changes (e.g. due to gravity, though not implemented here)
        # self.angle = self.velocity.as_polar()[1]

    def draw(self, surface, total_arena_offset_on_screen: pygame.math.Vector2):
        if self.lifespan > 0 and self.length > 1: 
            # self.position is in arena space (0 to ARENA_W/H)
            # total_arena_offset_on_screen is (ARENA_SCREEN_X0 + camera_shake.x, ARENA_SCREEN_Y0 + camera_shake.y)
            
            half_vec = self.velocity.normalize() * (self.length / 2.0)
            start_point_arena = self.position - half_vec
            end_point_arena = self.position + half_vec
            
            render_start_x = start_point_arena.x + total_arena_offset_on_screen.x
            render_start_y = start_point_arena.y + total_arena_offset_on_screen.y
            render_end_x = end_point_arena.x + total_arena_offset_on_screen.x
            render_end_y = end_point_arena.y + total_arena_offset_on_screen.y

            pygame.draw.line(surface, self.color, 
                             (int(render_start_x), int(render_start_y)), 
                             (int(render_end_x), int(render_end_y)), 
                             max(1, int(self.thickness)))

class ParticleEmitter:
    def __init__(self):
        self.particles: list[Particle] = []

    def emit(self, num_particles, position, base_particle_color=(200,0,0), 
             base_velocity_scale=60, lifespan_s=0.5, 
             max_length=12, base_thickness=2, 
             fade_to_color=None):
        
        actual_fade_color = fade_to_color if fade_to_color else (int(base_particle_color[0]*0.3), int(base_particle_color[1]*0.3), int(base_particle_color[2]*0.3))
        if len(actual_fade_color) == 4: # Strip alpha if present for color calcs
             actual_fade_color = (actual_fade_color[0], actual_fade_color[1], actual_fade_color[2])

        for _ in range(num_particles):
            angle_rad = random.uniform(0, 2 * math.pi)
            speed = random.uniform(base_velocity_scale * 0.7, base_velocity_scale * 1.3)
            velocity = pygame.math.Vector2(math.cos(angle_rad) * speed, math.sin(angle_rad) * speed)
            
            particle_lifespan = lifespan_s * random.uniform(0.6, 1.4)
            particle_length = max_length * random.uniform(0.4, 1.2)
            particle_thickness = max(1, int(base_thickness * random.uniform(0.7, 1.3)))
            
            particle = Particle(position, velocity, particle_lifespan, particle_length, particle_thickness, base_particle_color, actual_fade_color)
            self.particles.append(particle)

    def update(self, dt):
        self.particles = [p for p in self.particles if p.lifespan > 0]
        for particle in self.particles:
            particle.update(dt)

    def draw(self, surface, total_arena_offset_on_screen: pygame.math.Vector2):
        for particle in self.particles:
            particle.draw(surface, total_arena_offset_on_screen) 