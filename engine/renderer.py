# engine/renderer.py
import pygame, numpy as np

def draw_hp_bar(screen, orb, y_offset=10):
    pct = orb.hp / orb.max_hp
    bar_w, bar_h = 120, 8
    x = orb.body.position.x - bar_w // 2
    y = y_offset
    bg_rect = pygame.Rect(x, y, bar_w, bar_h)
    fg_rect = pygame.Rect(x, y, int(bar_w * pct), bar_h)
    pygame.draw.rect(screen, (60, 60, 60), bg_rect)
    pygame.draw.rect(screen, (200, 50, 50), fg_rect)

def surface_to_array(surf):
    '''Pygame Surface -> RGB numpy array (H, W, 3)'''
    return pygame.surfarray.array3d(surf).swapaxes(0,1)