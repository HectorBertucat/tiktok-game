# engine/renderer.py
import pygame, numpy as np, random

# Health bar colors
COLOR_HP_HIGH = (8, 188, 19)  # Green #08BC13 (HP 6-7)
COLOR_HP_MID = (215, 214, 10) # Yellow #D7D60A (HP 3-5)
COLOR_HP_LOW = (231, 65, 8)   # Red #E74108 (HP 1-2)
COLOR_HP_EMPTY = (60, 60, 60) # Background for empty segments
COLOR_HP_BORDER = (0, 0, 0)   # Black border for segments
COLOR_TEXT = (240, 240, 240) # White-ish for text

# HP Bar Style Constants
HP_BAR_PADDING_HORIZONTAL = 20  # Padding from screen edges for the HP bar itself
HP_BAR_PADDING_VERTICAL_TOP = 30 # Padding from screen top for the first name
HP_BAR_SPACING_BETWEEN = 25     # Vertical space between Orb1's HP bar and Orb2's Name
HP_BAR_HEIGHT_PER_ORB = 30      # Height of the HP bar segments
HP_SEGMENT_GAP = 4              # Gap between segments
HP_SEGMENT_BORDER_RADIUS = 7    # Rounded corners for segments
HP_NAME_FONT_SIZE = 52          # Much larger font for orb names
HP_NAME_BOTTOM_MARGIN = 8       # Space between name and its HP bar

# renderer.py  — nouvelle fonction
def draw_top_hp_bar(screen, orb, index, total_orbs=2):
    if not orb or orb.hp < 0: 
        return

    screen_w = screen.get_width()
    
    # Determine HP color based on current HP
    if orb.hp >= 6:
        current_hp_color = COLOR_HP_HIGH
        highlight_hp_color = (min(255, COLOR_HP_HIGH[0]+35), min(255, COLOR_HP_HIGH[1]+35), min(255, COLOR_HP_HIGH[2]+35))
    elif orb.hp >= 3:
        current_hp_color = COLOR_HP_MID
        highlight_hp_color = (min(255, COLOR_HP_MID[0]+35), min(255, COLOR_HP_MID[1]+35), min(255, COLOR_HP_MID[2]+35))
    else: 
        current_hp_color = COLOR_HP_LOW
        highlight_hp_color = (min(255, COLOR_HP_LOW[0]+35), min(255, COLOR_HP_LOW[1]+35), min(255, COLOR_HP_LOW[2]+35))

    # Orb Name Display (first, to determine its height)
    font = pygame.font.SysFont(None, HP_NAME_FONT_SIZE)
    name_text_color = orb.outline_color if orb.outline_color else COLOR_TEXT
    name_surface = font.render(orb.name, True, name_text_color)
    name_rect = name_surface.get_rect() # Get rect to find its height
    name_height = name_rect.height

    # Calculate Y positions
    # Height of one full display unit (Name + Margin + HP Bar)
    single_orb_display_total_height = name_height + HP_NAME_BOTTOM_MARGIN + HP_BAR_HEIGHT_PER_ORB
    
    name_y_position = HP_BAR_PADDING_VERTICAL_TOP + index * (single_orb_display_total_height + HP_BAR_SPACING_BETWEEN)
    hp_bar_y_position = name_y_position + name_height + HP_NAME_BOTTOM_MARGIN
    
    # Center the name horizontally
    name_rect.centerx = screen_w // 2
    name_rect.top = name_y_position
    screen.blit(name_surface, name_rect)

    # HP Bar Segments (below the name)
    segments_total_available_width = screen_w - (2 * HP_BAR_PADDING_HORIZONTAL)
    bar_segments_start_x = HP_BAR_PADDING_HORIZONTAL
    
    num_segments = orb.max_hp
    if num_segments <= 0: num_segments = 1 
    
    total_gap_width = HP_SEGMENT_GAP * (num_segments -1) if num_segments > 1 else 0
    segment_width = (segments_total_available_width - total_gap_width) // num_segments
    
    if segment_width <= 2: # Fallback for very narrow screens / too many segments
        bar_rect = pygame.Rect(bar_segments_start_x, hp_bar_y_position, segments_total_available_width, HP_BAR_HEIGHT_PER_ORB)
        pygame.draw.rect(screen, COLOR_HP_BORDER, bar_rect, border_radius=HP_SEGMENT_BORDER_RADIUS)
        filled_width_ratio = orb.hp / num_segments if num_segments > 0 else 0
        filled_width = filled_width_ratio * segments_total_available_width
        if filled_width > 0:
            filled_rect = pygame.Rect(bar_segments_start_x + 1, hp_bar_y_position + 1, filled_width - 2 , HP_BAR_HEIGHT_PER_ORB - 2)
            pygame.draw.rect(screen, current_hp_color, filled_rect, border_radius=max(0, HP_SEGMENT_BORDER_RADIUS -1))
        return

    for i in range(num_segments):
        segment_x = bar_segments_start_x + i * (segment_width + HP_SEGMENT_GAP)
        segment_rect = pygame.Rect(segment_x, hp_bar_y_position, segment_width, HP_BAR_HEIGHT_PER_ORB)
        
        pygame.draw.rect(screen, COLOR_HP_BORDER, segment_rect, border_radius=HP_SEGMENT_BORDER_RADIUS)
        
        inner_fill_rect = pygame.Rect(segment_rect.left + 1, segment_rect.top + 1, segment_rect.width - 2, segment_rect.height - 2)
        inner_border_radius = max(0, HP_SEGMENT_BORDER_RADIUS - 1)

        if i < orb.hp:
            pygame.draw.rect(screen, current_hp_color, inner_fill_rect, border_radius=inner_border_radius)
            highlight_rect_height = max(1, inner_fill_rect.height // 3) # Ensure at least 1px for highlight
            highlight_rect = pygame.Rect(inner_fill_rect.left, inner_fill_rect.top, inner_fill_rect.width, highlight_rect_height)
            # Ensure highlight radius does not exceed fill radius
            highlight_top_radius = inner_border_radius 
            pygame.draw.rect(screen, highlight_hp_color, highlight_rect, border_top_left_radius=highlight_top_radius, border_top_right_radius=highlight_top_radius)
        else:
            pygame.draw.rect(screen, COLOR_HP_EMPTY, inner_fill_rect, border_radius=inner_border_radius)

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