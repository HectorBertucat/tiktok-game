# engine/renderer.py
import pygame, numpy as np, random

# Health bar colors
COLOR_HP_HIGH = (8, 188, 19)  # Green #08BC13 (HP 6-7)
COLOR_HP_MID = (215, 214, 10) # Yellow #D7D60A (HP 3-5)
COLOR_HP_LOW = (231, 65, 8)   # Red #E74108 (HP 1-2)
COLOR_HP_EMPTY = (60, 60, 60) # Background for empty segments
COLOR_HP_BORDER = (0, 0, 0)   # Black border for segments

# renderer.py  — nouvelle fonction
def draw_top_hp_bar(screen, orb, index, y, total_orbs=2, bar_width_total=360, bar_height=20, segment_gap=3, name_font_size=24):
    if not orb or orb.hp < 0: # Ensure orb exists and hp is not negative for safety
        return

    # Determine HP color based on current HP
    if orb.hp >= 6:
        current_hp_color = COLOR_HP_HIGH
    elif orb.hp >= 3:
        current_hp_color = COLOR_HP_MID
    else: # orb.hp is 1 or 2 (or 0, handled by segment drawing)
        current_hp_color = COLOR_HP_LOW

    # Positioning for the entire bar for this orb
    screen_w = screen.get_width()
    available_width_per_orb = screen_w // total_orbs
    bar_start_x = index * available_width_per_orb + (available_width_per_orb - bar_width_total) // 2
    
    # Orb Name Display
    font = pygame.font.SysFont(None, name_font_size)
    name_surface = font.render(orb.name, True, orb.outline_color) # Use orb's outline color for name
    name_rect = name_surface.get_rect(center=(bar_start_x + bar_width_total // 2, y - bar_height // 2 - name_font_size // 2))
    screen.blit(name_surface, name_rect)

    # Segmented HP Bar
    num_segments = orb.max_hp # Should be 7
    segment_width = (bar_width_total - (segment_gap * (num_segments - 1))) // num_segments
    if segment_width <= 0: segment_width = 1 # Prevent zero or negative width

    for i in range(num_segments):
        segment_x = bar_start_x + i * (segment_width + segment_gap)
        segment_rect = pygame.Rect(segment_x, y, segment_width, bar_height)
        
        # Draw border for the segment
        pygame.draw.rect(screen, COLOR_HP_BORDER, segment_rect, border_radius=0) # Outer black box for segment
        
        # Inner fill color
        inner_rect = pygame.Rect(segment_x + 1, y + 1, segment_width - 2, bar_height - 2) # 1px inset for border
        if i < orb.hp:
            pygame.draw.rect(screen, current_hp_color, inner_rect, border_radius=0)
        else:
            pygame.draw.rect(screen, COLOR_HP_EMPTY, inner_rect, border_radius=0)

def surface_to_array(surf):
    '''Pygame Surface -> RGB numpy array (H, W, 3)'''
    return pygame.surfarray.array3d(surf).swapaxes(0,1)

import random

class Camera:
    def __init__(self):
        self.offset = pygame.math.Vector2(0, 0)
        self.shake_timer = 0.0
        self.shake_intensity = 0
        self.base_offset = pygame.math.Vector2(0,0) # For future use like following a player

    def shake(self, intensity=5, duration=0.2):
        self.shake_intensity = intensity
        self.shake_timer = duration

    def update(self, dt):
        if self.shake_timer > 0:
            self.shake_timer -= dt
            if self.shake_timer <= 0:
                self.offset.x = 0
                self.offset.y = 0
                self.shake_intensity = 0
            else:
                # Simple random shake. Could be made smoother (e.g., Perlin noise, decay)
                self.offset.x = random.randint(-self.shake_intensity, self.shake_intensity)
                self.offset.y = random.randint(-self.shake_intensity, self.shake_intensity)
        else:
            self.offset.x = 0
            self.offset.y = 0
        
        # Combine with base offset if you implement camera following
        # current_display_offset = self.base_offset + self.offset 
        # return current_display_offset
        return self.offset # For now, just the shake offset