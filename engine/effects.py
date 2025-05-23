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

@dataclass
class Shockwave:
    position: pygame.math.Vector2
    radius: float
    max_radius: float
    lifespan: float
    max_lifespan: float
    color: tuple[int, int, int]
    thickness: int

    def __init__(self, position, max_radius, lifespan, color, thickness=3):
        self.position = pygame.math.Vector2(position)
        self.radius = 0
        self.max_radius = max_radius
        self.lifespan = lifespan
        self.max_lifespan = lifespan
        self.color = color
        self.thickness = thickness

    def update(self, dt):
        if self.lifespan <= 0:
            return
        
        self.lifespan -= dt
        life_ratio = max(0, self.lifespan / self.max_lifespan)
        
        # Radius grows quickly then fades
        self.radius = self.max_radius * (1 - life_ratio)
        
        # Alpha decreases over time
        alpha = int(255 * life_ratio)
        self.color = (*self.color[:3], alpha)

    def draw(self, surface, total_arena_offset_on_screen: pygame.math.Vector2):
        if self.lifespan > 0 and self.radius > 0:
            render_center_x = self.position.x + total_arena_offset_on_screen.x
            render_center_y = self.position.y + total_arena_offset_on_screen.y
            
            life_ratio = max(0, self.lifespan / self.max_lifespan)
            
            # Enhanced multi-ring shockwave with grid interaction
            base_alpha = int(255 * life_ratio * 0.8)
            
            # Main shockwave rings
            for ring in range(3):
                ring_radius = self.radius - (ring * 20)
                if ring_radius > 0:
                    ring_alpha = max(0, base_alpha - (ring * 60))
                    ring_thickness = max(1, self.thickness - ring)
                    
                    # Create surface for each ring
                    ring_surface = pygame.Surface((ring_radius * 2 + 40, ring_radius * 2 + 40), pygame.SRCALPHA)
                    ring_color = (*self.color[:3], ring_alpha)
                    
                    # Draw main ring
                    pygame.draw.circle(ring_surface, ring_color, 
                                     (int(ring_radius + 20), int(ring_radius + 20)), 
                                     int(ring_radius), ring_thickness)
                    
                    # Add grid distortion effect
                    grid_size = 80  # Match the arena grid size
                    grid_alpha = int(ring_alpha * 0.3)
                    
                    # Draw intersecting grid lines that react to the shockwave
                    center_grid_x = int((render_center_x) // grid_size) * grid_size
                    center_grid_y = int((render_center_y) // grid_size) * grid_size
                    
                    # Highlight nearby grid lines
                    for grid_offset in range(-2, 3):
                        # Vertical lines
                        grid_x = center_grid_x + (grid_offset * grid_size)
                        if abs(grid_x - render_center_x) < ring_radius:
                            intensity = 1.0 - (abs(grid_x - render_center_x) / ring_radius)
                            line_alpha = int(grid_alpha * intensity)
                            if line_alpha > 0:
                                line_color = (*self.color[:3], line_alpha)
                                line_start = (grid_x - render_center_x + ring_radius + 20, 0)
                                line_end = (grid_x - render_center_x + ring_radius + 20, ring_radius * 2 + 40)
                                pygame.draw.line(ring_surface, line_color, line_start, line_end, 3)
                        
                        # Horizontal lines
                        grid_y = center_grid_y + (grid_offset * grid_size)
                        if abs(grid_y - render_center_y) < ring_radius:
                            intensity = 1.0 - (abs(grid_y - render_center_y) / ring_radius)
                            line_alpha = int(grid_alpha * intensity)
                            if line_alpha > 0:
                                line_color = (*self.color[:3], line_alpha)
                                line_start = (0, grid_y - render_center_y + ring_radius + 20)
                                line_end = (ring_radius * 2 + 40, grid_y - render_center_y + ring_radius + 20)
                                pygame.draw.line(ring_surface, line_color, line_start, line_end, 3)
                    
                    # Blit the ring to the main surface
                    surface.blit(ring_surface, (render_center_x - ring_radius - 20, render_center_y - ring_radius - 20))
            
            # Add energy pulse effect
            pulse_radius = self.radius * 0.7
            pulse_alpha = int(base_alpha * 0.4)
            if pulse_alpha > 0:
                pulse_surface = pygame.Surface((pulse_radius * 2 + 20, pulse_radius * 2 + 20), pygame.SRCALPHA)
                pulse_color = (*self.color[:3], pulse_alpha)
                pygame.draw.circle(pulse_surface, pulse_color, 
                                 (int(pulse_radius + 10), int(pulse_radius + 10)), 
                                 int(pulse_radius))
                surface.blit(pulse_surface, (render_center_x - pulse_radius - 10, render_center_y - pulse_radius - 10), 
                           special_flags=pygame.BLEND_ADD)

@dataclass
class LaserGrid:
    position: pygame.math.Vector2
    radius: float
    max_radius: float
    lifespan: float
    max_lifespan: float
    color: tuple[int, int, int]

    def __init__(self, position, max_radius, lifespan, color):
        self.position = pygame.math.Vector2(position)
        self.radius = 0
        self.max_radius = max_radius
        self.lifespan = lifespan
        self.max_lifespan = lifespan
        self.color = color

    def update(self, dt):
        if self.lifespan <= 0:
            return
        
        self.lifespan -= dt
        life_ratio = max(0, self.lifespan / self.max_lifespan)
        
        # Radius grows quickly then fades
        self.radius = self.max_radius * (1 - life_ratio)

    def draw(self, surface, total_arena_offset_on_screen: pygame.math.Vector2):
        if self.lifespan > 0 and self.radius > 0:
            render_center_x = self.position.x + total_arena_offset_on_screen.x
            render_center_y = self.position.y + total_arena_offset_on_screen.y
            
            life_ratio = max(0, self.lifespan / self.max_lifespan)
            
            # Only show grid lines, no filled circles
            grid_size = 80  # Match the arena grid size
            base_alpha = int(255 * life_ratio)
            
            # Find grid center
            center_grid_x = int((render_center_x) // grid_size) * grid_size
            center_grid_y = int((render_center_y) // grid_size) * grid_size
            
            # Draw laser grid lines within radius
            for grid_offset in range(-5, 6):
                # Vertical laser lines
                grid_x = center_grid_x + (grid_offset * grid_size)
                if abs(grid_x - render_center_x) < self.radius:
                    intensity = 1.0 - (abs(grid_x - render_center_x) / self.radius)
                    line_alpha = int(base_alpha * intensity * 0.8)
                    if line_alpha > 0:
                        line_color = (*self.color, line_alpha)
                        line_surface = pygame.Surface((6, self.radius * 2), pygame.SRCALPHA)
                        line_surface.fill(line_color)
                        surface.blit(line_surface, (grid_x - 3, render_center_y - self.radius), 
                                   special_flags=pygame.BLEND_ADD)
                
                # Horizontal laser lines
                grid_y = center_grid_y + (grid_offset * grid_size)
                if abs(grid_y - render_center_y) < self.radius:
                    intensity = 1.0 - (abs(grid_y - render_center_y) / self.radius)
                    line_alpha = int(base_alpha * intensity * 0.8)
                    if line_alpha > 0:
                        line_color = (*self.color, line_alpha)
                        line_surface = pygame.Surface((self.radius * 2, 6), pygame.SRCALPHA)
                        line_surface.fill(line_color)
                        surface.blit(line_surface, (render_center_x - self.radius, grid_y - 3), 
                                   special_flags=pygame.BLEND_ADD)

class ParticleEmitter:
    def __init__(self):
        self.particles: list[Particle] = []
        self.shockwaves: list[Shockwave] = []
        self.laser_grids: list[LaserGrid] = []
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
        
        # Enhanced neon particle colors
        if fade_to_color is None:
            # Create more vibrant fade colors for neon effect
            fade_to_color = (int(base_particle_color[0]*0.6), int(base_particle_color[1]*0.6), int(base_particle_color[2]*0.6))
        
        actual_fade_color = fade_to_color
        if len(actual_fade_color) == 4: 
             actual_fade_color = (actual_fade_color[0], actual_fade_color[1], actual_fade_color[2])
        
        # Enhance base particle color for neon effect
        enhanced_base_color = tuple(min(255, int(c * 1.3)) for c in base_particle_color)

        # Scale particle properties by orb size
        effective_scaled_max_radius = base_max_radius * orb_radius_ratio

        for _ in range(num_particles):
            if impact_normal:
                normal_angle_rad = math.atan2(impact_normal.y, impact_normal.x)
                # Make the splash wider, e.g., +/- 60 to 75 degrees from the normal direction
                angle_offset = random.uniform(-math.pi * 0.4, math.pi * 0.4) 
                angle_rad = normal_angle_rad + angle_offset
                # Significantly increase speed based on impact_strength for a bigger splash
                speed = random.uniform(base_velocity_scale * 0.8, base_velocity_scale * 1.5) * (1 + impact_strength / 1000.0) 
            else:
                angle_rad = random.uniform(0, 2 * math.pi)
                speed = random.uniform(base_velocity_scale * 0.7, base_velocity_scale * 1.3)
            
            velocity = pygame.math.Vector2(math.cos(angle_rad) * speed, math.sin(angle_rad) * speed)
            
            particle_lifespan = lifespan_s * random.uniform(0.5, 1.5)
            # Vary particle sizes more for a splashy look
            particle_initial_radius = max(1, effective_scaled_max_radius * random.uniform(0.3, 1.0))
            
            particle = Particle(position, velocity, particle_lifespan, particle_initial_radius, enhanced_base_color, actual_fade_color)
            particle.bounces_remaining = self.default_particle_bounces 
            self.particles.append(particle)

    def emit_shockwave(self, position, max_radius=100, lifespan=0.8, color=(255, 0, 0), thickness=4):
        """Emit a shockwave effect at the given position"""
        shockwave = Shockwave(position, max_radius, lifespan, color, thickness)
        self.shockwaves.append(shockwave)
    
    def emit_laser_grid(self, position, max_radius=150, lifespan=0.6, color=(255, 255, 255)):
        """Emit a laser grid effect that only shows on grid lines"""
        laser_grid = LaserGrid(position, max_radius, lifespan, color)
        self.laser_grids.append(laser_grid)

    def update(self, dt, arena_rect: pygame.Rect):
        self.particles = [p for p in self.particles if p.lifespan > 0]
        for particle in self.particles:
            particle.update(dt, arena_rect, self.gravity, self.drag) # Pass through physics params
        
        # Update shockwaves
        self.shockwaves = [s for s in self.shockwaves if s.lifespan > 0]
        for shockwave in self.shockwaves:
            shockwave.update(dt)
        
        # Update laser grids
        self.laser_grids = [lg for lg in self.laser_grids if lg.lifespan > 0]
        for laser_grid in self.laser_grids:
            laser_grid.update(dt)

    def draw(self, surface, total_arena_offset_on_screen: pygame.math.Vector2):
        for particle in self.particles:
            particle.draw(surface, total_arena_offset_on_screen)
        
        # Draw shockwaves
        for shockwave in self.shockwaves:
            shockwave.draw(surface, total_arena_offset_on_screen)
        
        # Draw laser grids
        for laser_grid in self.laser_grids:
            laser_grid.draw(surface, total_arena_offset_on_screen) 