# engine/renderer.py
import pygame, numpy as np, random

# renderer.py  — nouvelle fonction
def draw_top_hp_bar(screen, orb, index, y, total=2):
    bar_w, bar_h = 360, 14
    seg_w = screen.get_width() // total
    x = index * seg_w + (seg_w - bar_w) // 2
    pct = orb.hp / orb.max_hp
    bg = pygame.Rect(x, y, bar_w, bar_h)
    fg = pygame.Rect(x, y, int(bar_w * pct), bar_h)
    pygame.draw.rect(screen, (60, 60, 60), bg, border_radius=4)
    pygame.draw.rect(screen, (255, 66, 66), fg, border_radius=4)

# renderer.py  — nouvelle fonction
def draw_top_hp_bar(screen, orb, index, y, total=2):
    bar_w, bar_h = 360, 14
    seg_w = screen.get_width() // total
    x = index * seg_w + (seg_w - bar_w) // 2
    pct = orb.hp / orb.max_hp
    bg = pygame.Rect(x, y, bar_w, bar_h)
    fg = pygame.Rect(x, y, int(bar_w * pct), bar_h)
    pygame.draw.rect(screen, (60, 60, 60), bg, border_radius=4)
    pygame.draw.rect(screen, (255, 66, 66), fg, border_radius=4)

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