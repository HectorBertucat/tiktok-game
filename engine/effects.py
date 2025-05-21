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
    # For circle particles:
    radius: float
    max_radius: float 
    # Removed length, thickness, angle
    color: tuple[int, int, int]
    start_color: tuple[int, int, int]
    end_color: tuple[int, int, int]
    bounces_remaining: int

    def __init__(self, position, velocity, lifespan, radius, color, end_color=None):
        self.position = pygame.math.Vector2(position)
        self.velocity = pygame.math.Vector2(velocity)
        self.lifespan = lifespan
        self.max_lifespan = lifespan
        self.radius = radius
        self.max_radius = radius # Initial radius is max_radius
        self.start_color = color
        self.end_color = end_color if end_color else color
        self.color = color
        self.bounces_remaining = 2 

    def update(self, dt, arena_rect: pygame.Rect, gravity: pygame.math.Vector2, drag: float):
        if self.lifespan <= 0:
            return

        # Apply physics
        self.velocity += gravity * dt
        self.velocity *= (drag ** dt) 
        self.position += self.velocity * dt
        
        self.lifespan -= dt
        
        life_ratio = max(0, self.lifespan / self.max_lifespan)
        self.radius = self.max_radius * life_ratio # Radius shrinks
        
        r = int(self.start_color[0] * life_ratio + self.end_color[0] * (1 - life_ratio))
        g = int(self.start_color[1] * life_ratio + self.end_color[1] * (1 - life_ratio))
        b = int(self.start_color[2] * life_ratio + self.end_color[2] * (1 - life_ratio))
        self.color = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

        # Wall bouncing
        if self.bounces_remaining > 0 and self.radius > 0:
            bounce_occurred = False
            if self.position.x - self.radius < arena_rect.left:
                self.position.x = arena_rect.left + self.radius
                self.velocity.x *= -0.7 # Dampen more for circles
                bounce_occurred = True
            elif self.position.x + self.radius > arena_rect.right:
                self.position.x = arena_rect.right - self.radius
                self.velocity.x *= -0.7
                bounce_occurred = True
            
            if self.position.y - self.radius < arena_rect.top:
                self.position.y = arena_rect.top + self.radius
                self.velocity.y *= -0.7
                bounce_occurred = True
            elif self.position.y + self.radius > arena_rect.bottom:
                self.position.y = arena_rect.bottom - self.radius
                self.velocity.y *= -0.7
                bounce_occurred = True
            
            if bounce_occurred:
                self.bounces_remaining -= 1
                if self.bounces_remaining == 0:
                    self.lifespan = min(self.lifespan, 0.05) # Die very quickly after last bounce

    def draw(self, surface, total_arena_offset_on_screen: pygame.math.Vector2):
        if self.lifespan > 0 and self.radius >= 1: 
            render_center_x = self.position.x + total_arena_offset_on_screen.x
            render_center_y = self.position.y + total_arena_offset_on_screen.y

            pygame.draw.circle(surface, self.color, 
                             (int(render_center_x), int(render_center_y)), 
                             max(1, int(self.radius)))

class ParticleEmitter:
    def __init__(self):
        self.particles: list[Particle] = []
        # Define default physics properties for particles, can be overridden in emit or globally changed
        self.gravity = pygame.math.Vector2(0, 250) # Pixels/sec^2, positive Y is down
        self.drag = 0.98 # Factor per second for velocity reduction (e.g., 0.98 means 2% reduction per sec)
        self.default_particle_bounces = 2

    def emit(self, num_particles, position, base_particle_color=(200,0,0), 
             base_velocity_scale=60, lifespan_s=0.5, 
             base_max_radius=10, # Changed from max_length
             # base_thickness is no longer used for circle particles directly in Particle, but can influence visual density if desired elsewhere
             fade_to_color=None, 
             impact_normal: pygame.math.Vector2 = None, 
             impact_strength: float = 1.0, 
             orb_radius_ratio: float = 1.0 
             ):
        
        actual_fade_color = fade_to_color if fade_to_color else (int(base_particle_color[0]*0.3), int(base_particle_color[1]*0.3), int(base_particle_color[2]*0.3))
        if len(actual_fade_color) == 4: 
             actual_fade_color = (actual_fade_color[0], actual_fade_color[1], actual_fade_color[2])

        # Scale particle properties by orb size
        effective_scaled_max_radius = base_max_radius * orb_radius_ratio

        for _ in range(num_particles):
            if impact_normal:
                normal_angle_rad = math.atan2(impact_normal.y, impact_normal.x)
                # Make the splash wider, e.g., +/- 60 to 75 degrees from the normal direction
                angle_offset = random.uniform(-math.pi * 0.4, math.pi * 0.4) 
                angle_rad = normal_angle_rad + angle_offset
                # Significantly increase speed based on impact_strength for a bigger splash
                speed = random.uniform(base_velocity_scale * 0.8, base_velocity_scale * 1.5) * (1 + impact_strength / 1500.0) 
            else:
                angle_rad = random.uniform(0, 2 * math.pi)
                speed = random.uniform(base_velocity_scale * 0.7, base_velocity_scale * 1.3)
            
            velocity = pygame.math.Vector2(math.cos(angle_rad) * speed, math.sin(angle_rad) * speed)
            
            particle_lifespan = lifespan_s * random.uniform(0.5, 1.5)
            # Vary particle sizes more for a splashy look
            particle_initial_radius = max(1, effective_scaled_max_radius * random.uniform(0.3, 1.0))
            
            particle = Particle(position, velocity, particle_lifespan, particle_initial_radius, base_particle_color, actual_fade_color)
            particle.bounces_remaining = self.default_particle_bounces 
            self.particles.append(particle)

    def update(self, dt, arena_rect: pygame.Rect):
        self.particles = [p for p in self.particles if p.lifespan > 0]
        for particle in self.particles:
            particle.update(dt, arena_rect, self.gravity, self.drag) # Pass through physics params

    def draw(self, surface, total_arena_offset_on_screen: pygame.math.Vector2):
        for particle in self.particles:
            particle.draw(surface, total_arena_offset_on_screen) 