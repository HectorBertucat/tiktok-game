# engine/renderer.py
import pygame, numpy as np, random
from engine.game_objects import HP_ANIMATION_DURATION # Import the constant

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
HP_SEGMENT_SHAKE_INTENSITY = 4  # Max pixels for HP segment shake

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
        
        # Simplified animation for fallback bar (just color change, no wipe/shake)
        current_display_hp = orb.hp
        if orb.hp_animation_timer > 0:
            # For fallback, just show the target HP color during animation
            # Or one could lerp the width if feeling fancy, but simple is fine for fallback
            pass # Color is already determined by orb.hp (target)

        filled_width_ratio = current_display_hp / num_segments if num_segments > 0 else 0
        filled_width = filled_width_ratio * segments_total_available_width
        if filled_width > 0:
            filled_rect = pygame.Rect(bar_segments_start_x + 1, hp_bar_y_position + 1, filled_width - 2 , HP_BAR_HEIGHT_PER_ORB - 2)
            # Determine color for fallback based on actual current orb.hp
            final_color_for_fallback = COLOR_HP_EMPTY
            if orb.hp >= 6: final_color_for_fallback = COLOR_HP_HIGH
            elif orb.hp >= 3: final_color_for_fallback = COLOR_HP_MID
            else: final_color_for_fallback = COLOR_HP_LOW # Covers 1 & 2, and 0 if it somehow happens
            if orb.hp == 0 : final_color_for_fallback = COLOR_HP_EMPTY # Explicitly empty if 0
            pygame.draw.rect(screen, final_color_for_fallback, filled_rect, border_radius=max(0, HP_SEGMENT_BORDER_RADIUS -1))
        return

    # Animation calculations
    anim_progress = 0.0
    is_animating = orb.hp_animation_timer > 0
    if is_animating:
        anim_progress = 1.0 - (orb.hp_animation_timer / HP_ANIMATION_DURATION) # Use imported constant
        anim_progress = max(0, min(1, anim_progress)) # Clamp progress

    hp_lost_start_segment_idx = orb.hp_target_for_animation # For loss, this is the first newly empty segment
    hp_gained_end_segment_idx = orb.hp_target_for_animation -1 # For gain, this is the last newly filled segment

    for i in range(num_segments):
        segment_x_base = bar_segments_start_x + i * (segment_width + HP_SEGMENT_GAP)
        segment_y_base = hp_bar_y_position
        
        current_segment_shake_x = 0
        current_segment_shake_y = 0

        # Determine if this segment is part of the animated change
        segment_is_part_of_animation = False
        is_loss_animation = orb.hp_target_for_animation < orb.hp_at_animation_start
        is_gain_animation = orb.hp_target_for_animation > orb.hp_at_animation_start

        if is_animating:
            if is_loss_animation and i >= orb.hp_target_for_animation and i < orb.hp_at_animation_start:
                segment_is_part_of_animation = True # This segment is being lost
            elif is_gain_animation and i < orb.hp_target_for_animation and i >= orb.hp_at_animation_start:
                segment_is_part_of_animation = True # This segment is being gained
        
        if segment_is_part_of_animation:
            # Apply shake: simple random offset, could be a sine wave for smoothness
            shake_intensity = HP_SEGMENT_SHAKE_INTENSITY * (1 - anim_progress) # Shake more at start
            current_segment_shake_x = random.uniform(-shake_intensity, shake_intensity)
            current_segment_shake_y = random.uniform(-shake_intensity, shake_intensity)

        segment_rect = pygame.Rect(segment_x_base + current_segment_shake_x,
                                  segment_y_base + current_segment_shake_y, 
                                  segment_width, HP_BAR_HEIGHT_PER_ORB)
        
        pygame.draw.rect(screen, COLOR_HP_BORDER, segment_rect, border_radius=HP_SEGMENT_BORDER_RADIUS)
        
        inner_fill_rect_base = pygame.Rect(segment_rect.left + 1, segment_rect.top + 1, 
                                          segment_rect.width - 2, segment_rect.height - 2)
        inner_border_radius = max(0, HP_SEGMENT_BORDER_RADIUS - 1)

        # Determine visual state of the segment (filled, empty, or animating)
        is_currently_filled_visual = i < orb.hp_target_for_animation # What it will be post-animation
        was_previously_filled_visual = i < orb.hp_at_animation_start # What it was pre-animation

        final_segment_color = COLOR_HP_EMPTY
        final_highlight_color = None # No highlight for empty or partially filled animating segments initially
        apply_highlight = False
        segment_width_for_wipe = inner_fill_rect_base.width

        if segment_is_part_of_animation:
            if is_loss_animation: # Segment is being lost (animates from full to empty)
                wipe_progress = anim_progress # For loss, wipe goes R to L, so width reduces with progress
                current_fill_width = inner_fill_rect_base.width * (1 - wipe_progress)
                final_segment_color = current_hp_color # Color of the HP being lost
                segment_width_for_wipe = current_fill_width
                # Highlight only if substantially filled
                apply_highlight = current_fill_width > inner_fill_rect_base.width * 0.3 
            elif is_gain_animation: # Segment is being gained (animates from empty to full)
                wipe_progress = anim_progress # For gain, wipe goes L to R, so width increases with progress
                current_fill_width = inner_fill_rect_base.width * wipe_progress
                final_segment_color = current_hp_color # Color of the HP being gained
                segment_width_for_wipe = current_fill_width
                apply_highlight = current_fill_width > inner_fill_rect_base.width * 0.3
            if apply_highlight: final_highlight_color = highlight_hp_color
        else:
            # Not animating, just draw based on target HP state
            if i < orb.hp_target_for_animation: # Stays filled or is already filled
                final_segment_color = current_hp_color
                final_highlight_color = highlight_hp_color
                apply_highlight = True
            else: # Stays empty or is already empty
                final_segment_color = COLOR_HP_EMPTY
                apply_highlight = False
        
        # Draw the segment fill (potentially wiped)
        if segment_width_for_wipe > 0:
            animated_segment_fill_rect = pygame.Rect(inner_fill_rect_base.left, inner_fill_rect_base.top, 
                                                     segment_width_for_wipe, inner_fill_rect_base.height)
            pygame.draw.rect(screen, final_segment_color, animated_segment_fill_rect, border_radius=inner_border_radius)

            if apply_highlight and final_highlight_color and segment_width_for_wipe > 0:
                highlight_rect_height = max(1, animated_segment_fill_rect.height // 3)
                actual_highlight_rect = pygame.Rect(animated_segment_fill_rect.left, 
                                                    animated_segment_fill_rect.top, 
                                                    animated_segment_fill_rect.width, 
                                                    highlight_rect_height)
                pygame.draw.rect(screen, final_highlight_color, actual_highlight_rect, 
                                 border_top_left_radius=inner_border_radius, 
                                 border_top_right_radius=inner_border_radius)
        elif final_segment_color == COLOR_HP_EMPTY and not segment_is_part_of_animation : # Explicitly draw empty if it should be empty and not animating
             pygame.draw.rect(screen, COLOR_HP_EMPTY, inner_fill_rect_base, border_radius=inner_border_radius)

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