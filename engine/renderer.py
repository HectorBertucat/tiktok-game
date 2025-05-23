# engine/renderer.py
import pygame, numpy as np, random
from engine.game_objects import HP_ANIMATION_DURATION # Import the constant

# Enhanced neon health bar colors
COLOR_HP_HIGH = (0, 255, 100)      # Bright neon green (HP 6-7)
COLOR_HP_HIGH_GLOW = (0, 255, 100, 120)  # Green glow
COLOR_HP_MID = (255, 200, 0)       # Bright neon yellow (HP 3-5)  
COLOR_HP_MID_GLOW = (255, 200, 0, 120)   # Yellow glow
COLOR_HP_LOW = (255, 50, 50)       # Bright neon red (HP 1-2)
COLOR_HP_LOW_GLOW = (255, 50, 50, 120)   # Red glow
COLOR_HP_EMPTY = (30, 30, 40)      # Dark background for empty segments
COLOR_HP_BORDER = (100, 255, 255)  # Cyan neon border
COLOR_TEXT = (255, 255, 255)       # Pure white for text
COLOR_TEXT_GLOW = (255, 255, 255, 100)  # White glow for text

# HP Bar Style Constants
HP_BAR_PADDING_HORIZONTAL = 30  # Increased padding for better spacing
HP_BAR_PADDING_VERTICAL_TOP = 40 # Increased padding from screen top
HP_BAR_SPACING_BETWEEN = 35     # More space between HP bars
HP_BAR_HEIGHT_PER_ORB = 40      # Increased height for more impressive bars
HP_SEGMENT_GAP = 6              # Increased gap between segments
HP_SEGMENT_BORDER_RADIUS = 12   # More rounded corners for modern look
HP_NAME_FONT_SIZE = 64          # Even larger font for orb names
HP_NAME_BOTTOM_MARGIN = 12      # More space between name and HP bar
HP_SEGMENT_SHAKE_INTENSITY = 6  # Increased shake for more drama

# renderer.py  — nouvelle fonction
def draw_top_hp_bar(screen, orb, index, total_orbs=2):
    if not orb or orb.hp < 0: 
        return

    screen_w = screen.get_width()
    
    # Determine HP color and glow based on current HP
    if orb.hp >= 6:
        current_hp_color = COLOR_HP_HIGH
        current_glow_color = COLOR_HP_HIGH_GLOW
        highlight_hp_color = (255, 255, 255)  # Pure white highlight for neon effect
    elif orb.hp >= 3:
        current_hp_color = COLOR_HP_MID
        current_glow_color = COLOR_HP_MID_GLOW
        highlight_hp_color = (255, 255, 255)  # Pure white highlight for neon effect
    else: 
        current_hp_color = COLOR_HP_LOW
        current_glow_color = COLOR_HP_LOW_GLOW
        highlight_hp_color = (255, 255, 255)  # Pure white highlight for neon effect

    # Enhanced Orb Name Display with glow effect
    font = pygame.font.SysFont(None, HP_NAME_FONT_SIZE, bold=True)  # Make it bold
    name_text_color = orb.outline_color if orb.outline_color else COLOR_TEXT
    
    # Create multiple name surfaces for glow effect
    name_surface = font.render(orb.name, True, name_text_color)
    name_glow_surface = font.render(orb.name, True, COLOR_TEXT_GLOW[:3])  # Remove alpha for direct render
    
    name_rect = name_surface.get_rect()
    name_height = name_rect.height

    # Calculate Y positions
    single_orb_display_total_height = name_height + HP_NAME_BOTTOM_MARGIN + HP_BAR_HEIGHT_PER_ORB
    
    name_y_position = HP_BAR_PADDING_VERTICAL_TOP + index * (single_orb_display_total_height + HP_BAR_SPACING_BETWEEN)
    hp_bar_y_position = name_y_position + name_height + HP_NAME_BOTTOM_MARGIN
    
    # Center the name horizontally
    name_rect.centerx = screen_w // 2
    name_rect.top = name_y_position
    
    # Draw name with glow effect (multiple offset copies for glow)
    glow_offsets = [(-2, -2), (-2, 2), (2, -2), (2, 2), (-1, 0), (1, 0), (0, -1), (0, 1)]
    for offset_x, offset_y in glow_offsets:
        glow_rect = name_rect.copy()
        glow_rect.x += offset_x
        glow_rect.y += offset_y
        # Create a glow surface with alpha
        glow_surf = pygame.Surface(name_glow_surface.get_size(), pygame.SRCALPHA)
        glow_surf.blit(name_glow_surface, (0, 0))
        glow_surf.set_alpha(60)  # Semi-transparent glow
        screen.blit(glow_surf, glow_rect)
    
    # Draw main name on top
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
        
        # Draw enhanced neon border with glow effect
        # Outer glow
        glow_rect = pygame.Rect(segment_rect.x - 2, segment_rect.y - 2, 
                               segment_rect.width + 4, segment_rect.height + 4)
        glow_surface = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(glow_surface, (*COLOR_HP_BORDER, 60), 
                        (0, 0, glow_rect.width, glow_rect.height), 
                        border_radius=HP_SEGMENT_BORDER_RADIUS + 2)
        screen.blit(glow_surface, glow_rect)
        
        # Main border
        pygame.draw.rect(screen, COLOR_HP_BORDER, segment_rect, 
                        width=3, border_radius=HP_SEGMENT_BORDER_RADIUS)
        
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
        
        # Draw the segment fill with enhanced neon glow
        if segment_width_for_wipe > 0:
            animated_segment_fill_rect = pygame.Rect(inner_fill_rect_base.left, inner_fill_rect_base.top, 
                                                     segment_width_for_wipe, inner_fill_rect_base.height)
            
            # Draw inner glow for the segment
            if final_segment_color != COLOR_HP_EMPTY:
                # Create glow effect inside the segment
                inner_glow_rect = pygame.Rect(animated_segment_fill_rect.x - 1, 
                                            animated_segment_fill_rect.y - 1,
                                            animated_segment_fill_rect.width + 2, 
                                            animated_segment_fill_rect.height + 2)
                inner_glow_surface = pygame.Surface((inner_glow_rect.width, inner_glow_rect.height), pygame.SRCALPHA)
                pygame.draw.rect(inner_glow_surface, (*final_segment_color, 100), 
                               (0, 0, inner_glow_rect.width, inner_glow_rect.height), 
                               border_radius=inner_border_radius + 1)
                screen.blit(inner_glow_surface, inner_glow_rect)
            
            # Draw main segment fill
            pygame.draw.rect(screen, final_segment_color, animated_segment_fill_rect, border_radius=inner_border_radius)

            # Enhanced highlight with neon effect
            if apply_highlight and final_highlight_color and segment_width_for_wipe > 0:
                highlight_rect_height = max(1, animated_segment_fill_rect.height // 2)  # Bigger highlight
                actual_highlight_rect = pygame.Rect(animated_segment_fill_rect.left, 
                                                    animated_segment_fill_rect.top, 
                                                    animated_segment_fill_rect.width, 
                                                    highlight_rect_height)
                
                # Create highlight with gradient effect
                highlight_surface = pygame.Surface((actual_highlight_rect.width, actual_highlight_rect.height), pygame.SRCALPHA)
                pygame.draw.rect(highlight_surface, (*final_highlight_color, 180), 
                               (0, 0, actual_highlight_rect.width, actual_highlight_rect.height),
                               border_top_left_radius=inner_border_radius, 
                               border_top_right_radius=inner_border_radius)
                screen.blit(highlight_surface, actual_highlight_rect)
                
        elif final_segment_color == COLOR_HP_EMPTY and not segment_is_part_of_animation:
            # Draw empty segment with subtle inner shadow
            pygame.draw.rect(screen, COLOR_HP_EMPTY, inner_fill_rect_base, border_radius=inner_border_radius)
            # Add inner shadow for depth
            shadow_surface = pygame.Surface((inner_fill_rect_base.width, inner_fill_rect_base.height), pygame.SRCALPHA)
            pygame.draw.rect(shadow_surface, (0, 0, 0, 40), 
                           (0, 0, inner_fill_rect_base.width, inner_fill_rect_base.height), 
                           border_radius=inner_border_radius)
            screen.blit(shadow_surface, inner_fill_rect_base)

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