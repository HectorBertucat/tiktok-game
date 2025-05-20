import random
import math
import pygame

class Particle:
    def __init__(self, position: tuple[float,float], velocity: tuple[float,float], color: tuple[int,int,int], initial_radius: float, lifetime: float):
        self.position = list(position) # Use list for mutable position
        self.velocity = list(velocity)
        self.color = color
        self.initial_radius = initial_radius
        self.current_radius = initial_radius
        self.lifetime = lifetime
        self.initial_lifetime = lifetime

    def update(self, dt: float):
        self.position[0] += self.velocity[0] * dt
        self.position[1] += self.velocity[1] * dt
        self.lifetime -= dt

        life_ratio = max(0, self.lifetime / self.initial_lifetime)
        self.current_radius = self.initial_radius * life_ratio

    def is_alive(self) -> bool:
        return self.lifetime > 0

    def draw(self, surface: pygame.Surface, world_to_screen_offset: tuple[float, float]):
        if not self.is_alive():
            return

        draw_x = self.position[0] + world_to_screen_offset[0]
        draw_y = self.position[1] + world_to_screen_offset[1]

        if self.current_radius <= 0:
            return

        # Calculate alpha for fading effect
        life_ratio = max(0, self.lifetime / self.initial_lifetime)
        alpha = int(255 * life_ratio)
        alpha = max(0, min(255, alpha)) # Clamp alpha

        # Create a temporary surface for the particle to handle alpha blending
        # The size should accommodate the maximum radius to avoid clipping
        particle_surface_size = int(self.initial_radius * 2)
        particle_surface = pygame.Surface((particle_surface_size, particle_surface_size), pygame.SRCALPHA)
        
        # Draw the circle onto the center of this temporary surface
        pygame.draw.circle(
            particle_surface,
            (self.color[0], self.color[1], self.color[2], alpha), 
            (self.initial_radius, self.initial_radius), # Draw at center of temp surface
            self.current_radius
        )
        
        # Blit the temporary surface onto the main screen
        # Adjust blit position so particle center is at draw_x, draw_y
        blit_position = (draw_x - self.initial_radius, draw_y - self.initial_radius)
        surface.blit(particle_surface, blit_position)


class ParticleEmitter:
    def __init__(self):
        self.particles: list[Particle] = []

    def emit(self, position: tuple[float,float], count: int, initial_lifetime: float, initial_radius: float, spread_velocity: float, color: tuple[int,int,int] = (255,0,0)):
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0, spread_velocity)
            velocity = (math.cos(angle) * speed, math.sin(angle) * speed)
            
            # Slight randomization to initial conditions can make it look better
            particle_lifetime = initial_lifetime * random.uniform(0.8, 1.2)
            particle_radius = initial_radius * random.uniform(0.8, 1.2)

            particle = Particle(
                position=position,
                velocity=velocity,
                color=color,
                initial_radius=particle_radius,
                lifetime=particle_lifetime
            )
            self.particles.append(particle)

    def update(self, dt: float):
        # Update and remove dead particles
        # Iterate backwards when removing items from a list
        for i in range(len(self.particles) - 1, -1, -1):
            particle = self.particles[i]
            particle.update(dt)
            if not particle.is_alive():
                self.particles.pop(i)

    def draw(self, surface: pygame.Surface, world_to_screen_offset: tuple[float, float]):
        for particle in self.particles:
            particle.draw(surface, world_to_screen_offset)
