# engine/renderer.py
import pygame, numpy as np, random

def draw_hp_bar(screen, orb, y_offset=10):
    pct = orb.hp / orb.max_hp
    bar_w, bar_h = 120, 8

    # tremble si <30 %
    jitter = 3 if pct < 0.3 else 0
    x = orb.body.position.x - bar_w // 2 + random.randint(-jitter, jitter)
    y = y_offset + random.randint(-jitter, jitter)

    bg = pygame.Rect(x, y, bar_w, bar_h)
    fg = pygame.Rect(x, y, int(bar_w * pct), bar_h)

    pygame.draw.rect(screen, (60, 60, 60), bg, border_radius=3)
    pygame.draw.rect(screen, (220, 50, 50), fg, border_radius=3)

    # petit contour blanc
    pygame.draw.rect(screen, (240, 240, 240), bg, width=1, border_radius=3)

def surface_to_array(surf):
    '''Pygame Surface -> RGB numpy array (H, W, 3)'''
    return pygame.surfarray.array3d(surf).swapaxes(0,1)