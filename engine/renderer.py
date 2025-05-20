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