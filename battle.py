# battle.py – tout en haut
import pygame, random, math
from moviepy import VideoFileClip, ImageSequenceClip
from pathlib import Path
from ruamel.yaml import YAML
import numpy as np
import pymunk

# from director import Director # Removed Director
from engine.game_objects import Orb, Saw, Pickup
import engine.physics as phys
from engine.physics import (
    make_space, register_orb_collisions, register_saw_hits,
    register_pickup_handler, active_saws, register_orb_wall_collisions
)
from engine.renderer import draw_top_hp_bar, surface_to_array, Camera
from engine.effects import ParticleEmitter

# --- Layout 1080 × 1920 ---
CANVAS_W, CANVAS_H = 1080, 1920
SAFE_TOP    = 220
ARENA_SIZE  = 1080 # This will be the width and height of the square arena
ARENA_W = ARENA_SIZE
ARENA_H = ARENA_SIZE
ARENA_X0 = 0 # Arena starts at left edge of canvas
ARENA_Y0    = SAFE_TOP + 80
SAW_SPAWN_T = 5
SAW_TOKEN_T = 4
CFG = Path("configs/generated_battle_script.yml")
OUT = Path("export")
# FPS = 120 # Will be loaded from cfg
# DURATION = 70 # Will be implicit from events or a cfg field if added
# SCRIPT_FILE = Path("configs/generated_battle_script.yml") # Removed SCRIPT_FILE
SFX_BOUNCE_DIR = Path("assets/sfx/bounce") # Path to bounce SFX

# Dynamic Spawning Constants
SAFETY_PERIOD_SECONDS = 61
LOW_HEALTH_THRESHOLD = 1 # HP value at or below which emergency heart may spawn
EMERGENCY_HEART_COOLDOWN_SECONDS = 10 # Min time between emergency hearts for the same orb
EMERGENCY_HEART_PREDICTION_TIME_SECONDS = 0.75 # Predict 0.75s ahead for heart spawn
ASSISTANCE_ITEM_COOLDOWN_SECONDS = 10 # Min time between assistance (saw/shield) items for the same orb under low HP

# Unified Predictive Spawning Constants
UNIFIED_SPAWN_INTERVAL_SECONDS = 3 # Try to spawn a pickup every X seconds
UNIFIED_PREDICTION_TIME_MIN_SECONDS = 1.5
UNIFIED_PREDICTION_TIME_MAX_SECONDS = 2.5
MAX_PICKUPS_ON_SCREEN = 6 # Max total pickups of all kinds

# Weights for choosing pickups. Heart gets higher priority if an orb is low HP during safety period.
PICKUP_KINDS_WEIGHTS = {
    "heart": 8,    # Increased for frequent health
    "saw": 20,     # Increased for frequent saws/blades
    "shield": 3,   # Less frequent than saw/heart
    "bomb": 0.5    # Remains rare
}
# No separate LOW_HEALTH_THRESHOLD for general spawning, but safety period gives hearts priority.

# Constants from engine.game_objects that might be needed for prediction
# This isn't ideal, better to pass them or have them in a shared config.
# For now, hardcoding a reference value if not easily available.
PRED_MAX_ORB_VELOCITY = 1500 # Must match MAX_ORB_VELOCITY in engine.game_objects.py

def load_cfg(path):
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text())

class PredictiveBattleDirector:
    """Advanced AI system for creating engaging, scripted-looking battles that finish in 61-70 seconds"""
    
    def __init__(self, target_duration_min=61, target_duration_max=70):
        self.target_duration_min = target_duration_min
        self.target_duration_max = target_duration_max
        self.target_duration = (target_duration_min + target_duration_max) / 2  # 65.5s average
        
        # Battle narrative tracking
        self.last_major_event_time = 0
        self.health_change_history = []  # Track recent health changes to avoid repetition
        self.interaction_density = []    # Track interaction frequency over time
        self.orb_aggression_scores = {}  # Track how aggressive each orb has been
        
        # Enhanced damage rate tracking for better duration prediction
        self.damage_events = []          # Track all damage events with timestamps
        self.heal_events = []            # Track all heal events with timestamps
        self.last_health_snapshot = {}   # Track orb health at regular intervals
        self.health_snapshot_interval = 5.0  # Take health snapshots every 5 seconds
        self.last_snapshot_time = 0
        
        # Predictive parameters
        self.prediction_horizon = 8.0   # Predict up to 8 seconds ahead
        self.analysis_interval = 2.0    # Re-analyze every 2 seconds
        self.last_analysis_time = 0
        
        # Battle pacing configuration
        self.early_game_phase = 25      # 0-25s: Setup phase, moderate action
        self.mid_game_phase = 45        # 25-45s: Peak action phase
        self.end_game_phase = 65        # 45-65s: Climax phase, decisive action
        
        # Strategic spawning weights based on game phase and situation
        self.phase_weights = {
            'early': {'heart': 12, 'saw': 15, 'shield': 8, 'bomb': 1},
            'mid': {'heart': 8, 'saw': 25, 'shield': 4, 'bomb': 3},
            'end': {'heart': 5, 'saw': 30, 'shield': 2, 'bomb': 8}
        }
    
    def analyze_battle_state(self, current_time, orbs, battle_context):
        """Analyze current battle state and predict optimal item placements"""
        
        # Take regular health snapshots for trend analysis
        if current_time >= self.last_snapshot_time + self.health_snapshot_interval:
            self.take_health_snapshot(current_time, orbs)
            self.last_snapshot_time = current_time
        
        # Determine current game phase
        phase = self.get_game_phase(current_time)
        
        # Analyze orb states
        orb_analysis = self.analyze_orb_states(orbs, current_time)
        
        # Predict future interactions
        interaction_predictions = self.predict_future_interactions(orbs, battle_context, 5.0)
        
        # Calculate enhanced time pressure that accounts for damage rates
        time_pressure = self.calculate_enhanced_time_pressure(current_time, orb_analysis, orbs)
        
        # Generate strategic spawning plan
        spawning_plan = self.generate_spawning_strategy(
            phase, orb_analysis, interaction_predictions, time_pressure, current_time
        )
        
        return spawning_plan
    
    def take_health_snapshot(self, current_time, orbs):
        """Take a snapshot of current orb health for trend analysis"""
        snapshot = {
            'time': current_time,
            'orb_health': {orb.name: orb.hp for orb in orbs},
            'total_health': sum(orb.hp for orb in orbs),
            'living_orbs': len([orb for orb in orbs if orb.hp > 0])
        }
        self.last_health_snapshot = snapshot
    
    def calculate_damage_rate(self, current_time, lookback_time=20.0):
        """Calculate the recent damage rate (HP lost per second)"""
        cutoff_time = current_time - lookback_time
        
        # Get recent damage events
        recent_damage = [event for event in self.damage_events if event['time'] > cutoff_time]
        recent_heals = [event for event in self.heal_events if event['time'] > cutoff_time]
        
        if not recent_damage and not recent_heals:
            return 0.0
        
        # Calculate net damage over the period
        total_damage = sum(event['damage'] for event in recent_damage)
        total_healing = sum(event['healing'] for event in recent_heals)
        net_damage = total_damage - total_healing
        
        if lookback_time <= 0:
            return 0.0
        
        return net_damage / lookback_time
    
    def predict_game_end_time(self, current_time, orbs):
        """Predict when the game will end based on current health and damage trends"""
        if len(orbs) < 2:
            return current_time  # Game should end immediately
        
        # Get current health state
        orb_healths = [orb.hp for orb in orbs if orb.hp > 0]
        if len(orb_healths) < 2:
            return current_time  # Game should end immediately
        
        orb_healths.sort()
        weakest_hp = orb_healths[0]
        second_weakest_hp = orb_healths[1] if len(orb_healths) > 1 else orb_healths[0]
        
        # Calculate damage rate
        damage_rate = self.calculate_damage_rate(current_time)
        
        # If no recent damage, use a conservative estimate
        if damage_rate <= 0:
            # Assume a modest damage rate based on game phase
            if current_time < self.early_game_phase:
                estimated_damage_rate = 0.5  # HP per second
            elif current_time < self.mid_game_phase:
                estimated_damage_rate = 0.8
            else:
                estimated_damage_rate = 1.2
        else:
            estimated_damage_rate = damage_rate
        
        # Predict time until weakest orb dies
        if estimated_damage_rate > 0:
            time_until_death = weakest_hp / estimated_damage_rate
        else:
            time_until_death = float('inf')
        
        # Consider that the game might continue a bit after first death
        # Add some buffer time for dramatic effect
        buffer_time = min(10.0, max(3.0, time_until_death * 0.2))
        
        predicted_end_time = current_time + time_until_death + buffer_time
        
        return predicted_end_time
    
    def calculate_enhanced_time_pressure(self, current_time, orb_analysis, orbs):
        """Enhanced time pressure calculation that accounts for damage rates and predicted end time"""
        # Get basic time pressure
        basic_time_pressure = self.calculate_time_pressure(current_time, orb_analysis)
        
        # Predict when the game will actually end
        predicted_end_time = self.predict_game_end_time(current_time, orbs)
        
        # Calculate pressure based on predicted vs target end time
        target_end_time = self.target_duration
        time_difference = predicted_end_time - target_end_time
        
        # If game is predicted to end too early, apply EXTENSION pressure (negative time pressure)
        if time_difference < -10:  # Game ending more than 10 seconds early
            extension_pressure = -min(0.8, abs(time_difference) / 20.0)  # Negative pressure to extend
            return extension_pressure
        
        # If game is predicted to end too late, apply ACCELERATION pressure
        elif time_difference > 10:  # Game ending more than 10 seconds late
            acceleration_pressure = min(1.0, time_difference / 15.0)
            return max(basic_time_pressure, acceleration_pressure)
        
        # Game timing looks good, use basic pressure
        return basic_time_pressure
    
    def get_game_phase(self, current_time):
        """Determine which phase of the battle we're in"""
        if current_time < self.early_game_phase:
            return 'early'
        elif current_time < self.mid_game_phase:
            return 'mid'
        else:
            return 'end'
    
    def analyze_orb_states(self, orbs, current_time):
        """Analyze current orb health, positioning, and aggression levels"""
        analysis = {
            'orbs': orbs,  # Include the orbs list for use in other methods
            'total_health': sum(orb.hp for orb in orbs),
            'health_disparity': max(orb.hp for orb in orbs) - min(orb.hp for orb in orbs),
            'low_health_orbs': [orb for orb in orbs if orb.hp <= 2],
            'dominant_orb': max(orbs, key=lambda o: o.hp) if orbs else None,
            'weakest_orb': min(orbs, key=lambda o: o.hp) if orbs else None,
            'average_health': sum(orb.hp for orb in orbs) / len(orbs) if orbs else 0
        }
        
        # Update aggression scores based on recent activity
        for orb in orbs:
            if orb.name not in self.orb_aggression_scores:
                self.orb_aggression_scores[orb.name] = 0
            
            # Increase aggression score if orb has saws or recently picked up offensive items
            if hasattr(orb, 'has_saw') and orb.has_saw:
                self.orb_aggression_scores[orb.name] += 0.1
        
        analysis['aggression_scores'] = self.orb_aggression_scores.copy()
        return analysis
    
    def predict_future_interactions(self, orbs, battle_context, prediction_time):
        """Predict where and when orbs will interact in the near future"""
        predictions = []
        
        if len(orbs) < 2:
            return predictions
        
        # Use existing prediction system to forecast orb positions
        game_env_params = {
            "arena_width": battle_context.arena_width,
            "arena_height": battle_context.arena_height, 
            "border_thickness": battle_context.border_thickness_cfg,
            "space_damping": 0.99,
            "max_velocity": 1500,
            "physics_substeps": 3
        }
        
        # Sample multiple time points to predict interaction opportunities
        time_samples = [1.0, 2.0, 3.5, 5.0]
        
        for t in time_samples:
            orb_positions = []
            for orb in orbs:
                target_data = {
                    "name": orb.name,
                    "pos": orb.body.position,
                    "vel": orb.body.velocity,
                    "radius": orb.shape.radius,
                    "id": id(orb)
                }
                other_orbs_data = [
                    {
                        "name": other.name,
                        "pos": other.body.position,
                        "vel": other.body.velocity, 
                        "radius": other.shape.radius,
                        "id": id(other)
                    }
                    for other in orbs if other != orb
                ]
                
                predicted_pos = predict_orb_future_path_point(
                    target_data, other_orbs_data, game_env_params, 
                    t, int(t * 60)  # 60 FPS
                )
                orb_positions.append((orb, predicted_pos))
            
            # Check for predicted close encounters
            for i, (orb1, pos1) in enumerate(orb_positions):
                for orb2, pos2 in orb_positions[i+1:]:
                    distance = (pos1 - pos2).length
                    if distance < (orb1.shape.radius + orb2.shape.radius) * 3:  # Close encounter threshold
                        interaction_point = (pos1 + pos2) / 2
                        predictions.append({
                            'time': t,
                            'orbs': [orb1.name, orb2.name],
                            'position': interaction_point,
                            'distance': distance,
                            'interaction_strength': max(0, 1.0 - distance / 200)
                        })
        
        return predictions
    
    def calculate_time_pressure(self, current_time, orb_analysis):
        """Calculate how much pressure to apply to end the battle on time"""
        time_remaining = self.target_duration - current_time
        
        # If we're past target time, high pressure to end quickly
        if time_remaining <= 0:
            return 1.0
        
        # Calculate pressure based on health disparity and time remaining
        health_factor = 1.0 - (orb_analysis['average_health'] / 7.0)  # Assume max HP is ~7
        time_factor = 1.0 - (time_remaining / self.target_duration)
        
        # Combine factors: more pressure as time runs out or health gets low
        pressure = (health_factor * 0.6 + time_factor * 0.4)
        
        # Special case: if one orb is very weak and time is running out, high pressure
        if orb_analysis['health_disparity'] >= 3 and time_remaining < 15:
            pressure = max(pressure, 0.8)
        
        return min(1.0, pressure)
    
    def generate_spawning_strategy(self, phase, orb_analysis, interactions, time_pressure, current_time):
        """Generate strategic item spawning plan based on analysis"""
        strategy = {
            'immediate_spawns': [],
            'scheduled_spawns': [],
            'weights_override': None
        }
        
        # Get base weights for current phase
        base_weights = self.phase_weights[phase].copy()
        
        # Adjust weights based on battle state (pass orbs from orb_analysis)
        orbs_for_prediction = orb_analysis.get('orbs', [])
        weights = self.adjust_weights_for_situation(
            base_weights, orb_analysis, time_pressure, current_time, orbs_for_prediction
        )
        
        # Generate immediate spawns for critical situations
        immediate_spawns = self.generate_immediate_spawns(
            orb_analysis, interactions, time_pressure
        )
        
        # Generate scheduled spawns based on predicted interactions
        scheduled_spawns = self.generate_scheduled_spawns(
            interactions, orb_analysis, current_time
        )
        
        strategy['immediate_spawns'] = immediate_spawns
        strategy['scheduled_spawns'] = scheduled_spawns
        strategy['weights_override'] = weights
        
        return strategy
    
    def adjust_weights_for_situation(self, base_weights, orb_analysis, time_pressure, current_time, orbs=None):
        """Adjust spawning weights based on current battle situation"""
        weights = base_weights.copy()
        
        # Get predicted game end time for more informed decisions
        if orbs:
            predicted_end = self.predict_game_end_time(current_time, orbs)
            time_until_predicted_end = predicted_end - current_time
        else:
            # Fallback: estimate based on health and time pressure
            time_until_predicted_end = self.target_duration - current_time
        
        # Game ending too early: prioritize hearts and shields to extend (NEGATIVE time pressure)
        if time_pressure < -0.1:  # Negative time pressure means extend the game
            weights['heart'] *= 4.0  # Heavily favor hearts
            weights['shield'] *= 3.0  # Favor shields
            weights['saw'] *= 0.2     # Reduce offensive items
            weights['bomb'] *= 0.1    # Heavily reduce bombs
            print(f"🎯 Game ending early (predicted: {time_until_predicted_end:.1f}s), EXTENDING with defensive items")
        
        # High positive time pressure: favor bombs and saws to end the battle
        elif time_pressure > 0.7:
            weights['bomb'] *= 3
            weights['saw'] *= 2
            weights['heart'] *= 0.3
            weights['shield'] *= 0.2
            print(f"🎯 High time pressure, ACCELERATING game end")
        
        # Game going too long: increase offensive pressure
        elif orbs and time_until_predicted_end > self.target_duration - current_time + 15:
            weights['saw'] *= 2
            weights['bomb'] *= 2.5
            weights['heart'] *= 0.4
            weights['shield'] *= 0.3
            print(f"🎯 Game running long (predicted: {time_until_predicted_end:.1f}s), increasing offensive pressure")
        
        # Large health disparity: help the weaker orb or pressure the stronger one
        elif orb_analysis['health_disparity'] >= 3:
            if len(orb_analysis['low_health_orbs']) > 0:
                # Give the weak orb a chance
                weights['heart'] *= 2
                weights['shield'] *= 2
                weights['saw'] *= 0.7
            else:
                # Pressure the dominant orb
                weights['saw'] *= 1.5
                weights['bomb'] *= 2
        
        # Very low total health: be more conservative unless time pressure is high
        elif orb_analysis['total_health'] <= 4 and time_pressure < 0.7:
            weights['heart'] *= 1.5
            weights['bomb'] *= 0.5
        
        # High aggression phase: increase offensive items
        max_aggression = max(orb_analysis['aggression_scores'].values()) if orb_analysis['aggression_scores'] else 0
        if max_aggression > 2.0:
            weights['saw'] *= 1.3
            weights['shield'] *= 1.2
        
        return weights
    
    def generate_immediate_spawns(self, orb_analysis, interactions, time_pressure):
        """Generate items that should be spawned immediately"""
        immediate = []
        
        # If time pressure is negative, we need to extend the game - prioritize hearts
        if time_pressure < -0.1:
            # Emergency hearts for any low HP orbs to extend the game
            for orb in orb_analysis['low_health_orbs']:
                if not self.should_avoid_repetitive_pattern(orb.name, +1, self.last_analysis_time):
                    immediate.append({
                        'type': 'heart',
                        'target_orb': orb.name,
                        'urgency': 'extend_game',
                        'reason': 'extend_game_healing'
                    })
                    break  # Only spawn one heart at a time
            
            # If no low HP orbs, spawn heart for weakest orb anyway
            if not immediate and orb_analysis['weakest_orb']:
                immediate.append({
                    'type': 'heart',
                    'target_orb': orb_analysis['weakest_orb'].name,
                    'urgency': 'extend_game',
                    'reason': 'extend_game_healing'
                })
        
        # Emergency heart for critically low orb (but not if we need to end soon)
        elif time_pressure < 0.8:  # Normal emergency healing when not forcing conclusion
            critical_orbs = [orb for orb in orb_analysis['low_health_orbs'] if orb.hp == 1]
            if critical_orbs:
                orb = critical_orbs[0]
                # Check if this would create a repetitive pattern
                if not self.should_avoid_repetitive_pattern(orb.name, +1, self.last_analysis_time):
                    immediate.append({
                        'type': 'heart',
                        'target_orb': orb.name,
                        'urgency': 'critical',
                        'reason': 'emergency_healing'
                    })
        
        # Decisive bomb only if we need to end the battle (high positive time pressure)
        elif time_pressure > 0.9 and orb_analysis['health_disparity'] <= 1:
            # Battle is too close and needs to end, force a decision
            immediate.append({
                'type': 'bomb',
                'target_orb': orb_analysis['dominant_orb'].name if orb_analysis['dominant_orb'] else None,
                'urgency': 'decisive',
                'reason': 'force_conclusion'
            })
        
        return immediate
    
    def generate_scheduled_spawns(self, interactions, orb_analysis, current_time):
        """Generate items scheduled for future interactions"""
        scheduled = []
        
        # Schedule items at predicted interaction points
        for interaction in interactions:
            if interaction['interaction_strength'] > 0.6:  # High-likelihood interaction
                spawn_time = current_time + interaction['time'] - 0.5  # Spawn 0.5s before interaction
                
                # Choose item type based on interaction context
                if interaction['time'] < 3.0:  # Near-term interaction
                    item_type = 'saw'  # Offensive for immediate impact
                else:  # Longer-term interaction
                    item_type = random.choice(['saw', 'shield'])  # Mix offensive and defensive
                
                scheduled.append({
                    'spawn_time': spawn_time,
                    'type': item_type,
                    'position': interaction['position'],
                    'target_interaction': interaction,
                    'reason': 'predicted_encounter'
                })
        
        return scheduled
    
    def track_health_change(self, orb_name, old_hp, new_hp, current_time, reason):
        """Track health changes to avoid repetitive patterns and analyze damage rates"""
        change = {
            'orb': orb_name,
            'old_hp': old_hp,
            'new_hp': new_hp,
            'change': new_hp - old_hp,
            'time': current_time,
            'reason': reason
        }
        
        self.health_change_history.append(change)
        
        # Track damage and heal events separately for rate analysis
        if new_hp < old_hp:  # Damage event
            self.damage_events.append({
                'orb': orb_name,
                'damage': old_hp - new_hp,
                'time': current_time,
                'reason': reason
            })
        elif new_hp > old_hp:  # Heal event
            self.heal_events.append({
                'orb': orb_name,
                'healing': new_hp - old_hp,
                'time': current_time,
                'reason': reason
            })
        
        # Keep only recent history (last 30 seconds for detailed analysis)
        cutoff_time = current_time - 30.0
        self.health_change_history = [h for h in self.health_change_history if h['time'] > cutoff_time]
        self.damage_events = [d for d in self.damage_events if d['time'] > cutoff_time]
        self.heal_events = [h for h in self.heal_events if h['time'] > cutoff_time]
        
        return change
    
    def should_avoid_repetitive_pattern(self, orb_name, proposed_change, current_time):
        """Check if we should avoid a repetitive health change pattern"""
        recent_changes = [h for h in self.health_change_history 
                         if h['orb'] == orb_name and h['time'] > current_time - 10.0]
        
        if len(recent_changes) < 2:
            return False
        
        # Check for ping-pong pattern (damage -> heal -> damage -> heal)
        if len(recent_changes) >= 3:
            last_three = recent_changes[-3:]
            signs = [1 if h['change'] > 0 else -1 for h in last_three]
            if signs == [1, -1, 1] or signs == [-1, 1, -1]:
                # Ping-pong pattern detected, avoid if proposed change continues it
                if (signs[-1] == 1 and proposed_change < 0) or (signs[-1] == -1 and proposed_change > 0):
                    return True
        
        return False

class VideoBackground:
    def __init__(self, video_path, canvas_width, canvas_height):
        """Load video and prepare for looping background"""
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.video_path = video_path
        self.video_clip = None
        self.frames = []
        self.current_frame_idx = 0
        self.fps = 30  # Default fps for video playback
        self.frame_time = 0
        self.time_per_frame = 1.0 / self.fps
        
        try:
            # Load video clip
            self.video_clip = VideoFileClip(str(video_path))
            self.fps = self.video_clip.fps
            self.time_per_frame = 1.0 / self.fps
            
            # Pre-process all frames for efficient playback
            self._preprocess_frames()
            
        except Exception as e:
            print(f"Error loading video background: {e}")
            self.frames = []
    
    def _preprocess_frames(self):
        """Convert video frames to rotated/scaled pygame surfaces"""
        if not self.video_clip:
            return
            
        try:
            # Extract all frames as numpy arrays
            frame_arrays = []
            for t in np.arange(0, self.video_clip.duration, self.time_per_frame):
                frame = self.video_clip.get_frame(t)
                frame_arrays.append(frame)
            
            # Process each frame
            for frame_array in frame_arrays:
                # Convert to pygame surface
                frame_surface = pygame.surfarray.make_surface(frame_array.swapaxes(0, 1))
                
                # Rotate 90 degrees clockwise (landscape to portrait)
                rotated_surface = pygame.transform.rotate(frame_surface, -90)
                
                # Scale to fill canvas while maintaining aspect ratio
                scaled_surface = self._scale_to_fill(rotated_surface)
                
                self.frames.append(scaled_surface)
                
        except Exception as e:
            print(f"Error preprocessing video frames: {e}")
            self.frames = []
        finally:
            # Clean up video clip to free memory
            if self.video_clip:
                self.video_clip.close()
                self.video_clip = None
    
    def _scale_to_fill(self, surface):
        """Scale surface to fill canvas completely without stretching"""
        surface_width = surface.get_width()
        surface_height = surface.get_height()
        
        # Calculate scale factors for both dimensions
        scale_x = self.canvas_width / surface_width
        scale_y = self.canvas_height / surface_height
        
        # Use the larger scale factor to ensure full coverage
        scale = max(scale_x, scale_y)
        
        # Calculate new dimensions
        new_width = int(surface_width * scale)
        new_height = int(surface_height * scale)
        
        # Scale the surface
        scaled_surface = pygame.transform.scale(surface, (new_width, new_height))
        
        # If scaled surface is larger than canvas, we'll center it when drawing
        return scaled_surface
    
    def update(self, dt):
        """Update frame timing for animation"""
        if not self.frames:
            return
            
        self.frame_time += dt
        if self.frame_time >= self.time_per_frame:
            self.frame_time = 0
            self.current_frame_idx = (self.current_frame_idx + 1) % len(self.frames)
    
    def draw(self, screen):
        """Draw current frame to screen"""
        if not self.frames:
            # Fallback to solid color if no video loaded
            screen.fill((20, 20, 20))
            return
            
        current_frame = self.frames[self.current_frame_idx]
        
        # Center the frame on the canvas
        frame_rect = current_frame.get_rect()
        frame_rect.center = (self.canvas_width // 2, self.canvas_height // 2)
        
        screen.blit(current_frame, frame_rect)

def main():
    cfg = load_cfg(CFG)
    # random.seed(cfg["seed"]) # Seeding is now handled by generator for scenario determinism
                               # Or, if runtime randomness is needed for non-gameplay, seed separately.

    # Load constants from the new config
    GAME_FPS = cfg.get("fps", 120)
    # ARENA_WIDTH_FROM_CFG should be CANVAS_W if generated script sets it so.
    # We use CANVAS_W directly for rendering rect, and pass it to make_space.
    # The ARENA_WIDTH_FROM_CFG from cfg is effectively CANVAS_W now from generator.
    ARENA_WIDTH_FROM_CFG = cfg.get("arena_width", CANVAS_W) # Ensure this is used, should be CANVAS_W
    ARENA_HEIGHT_FROM_CFG = cfg.get("arena_height", ARENA_H) # Use global ARENA_H as fallback
    ORB_RADIUS_CFG = cfg.get("orb_radius", 150)
    PICKUP_RADIUS_CFG = cfg.get("pickup_radius", 20) # Default if not in cfg
    BORDER_THICKNESS_CFG = int(cfg.get("border_thickness", 30)) # Ensure integer for Pygame
    BORDER_COLOR_CFG = tuple(cfg.get("border_color", [255, 0, 90]))
    BORDER_FLASH_COLOR_CFG = tuple(cfg.get("border_flash_color", [255, 255, 0]))
    DEFAULT_FLASH_DURATION_CFG = cfg.get("default_flash_duration", 1.0)

    PHYSICS_SUBSTEPS = 3 # Number of physics sub-steps per frame

    # DURATION can be set if you add a 'duration' field to the YAML, or determined by max event time.
    # For now, let's keep a default DURATION or calculate from max event time later if needed.
    # DURATION_CFG = cfg.get("duration", 70) # Example: add a duration field to YAML or calculate
    # For dynamic mode, let's set a longer or indefinite duration, or manage end conditions differently.
    DURATION_SECONDS = cfg.get("duration", 70) # Allow duration from YAML, default to 70s

    # Define arena rect for particle collisions (inner dimensions of playable area)
    # Assuming ARENA_WIDTH_FROM_CFG and ARENA_HEIGHT_FROM_CFG are these inner dimensions.
    arena_rect_for_particles = pygame.Rect(0, 0, ARENA_WIDTH_FROM_CFG, ARENA_HEIGHT_FROM_CFG)

    pygame.init()
    pygame.font.init()
    pygame.mixer.init() # Initialize the mixer
    
    # Initialize the advanced AI battle director
    battle_director = PredictiveBattleDirector(target_duration_min=61, target_duration_max=70)

    # Load SFX
    try:
        # slow_mo_start_sfx = pygame.mixer.Sound("assets/sfx/slow_mo_start.wav") # Removed
        # slow_mo_end_sfx = pygame.mixer.Sound("assets/sfx/slow_mo_end.wav") # Removed
        health_boost_sfx = pygame.mixer.Sound("assets/sfx/health_boost.wav")
        hit_normal_sfx = pygame.mixer.Sound("assets/sfx/hit_normal.wav")
        hit_blade_sfx = pygame.mixer.Sound("assets/sfx/hit_blade.wav")
        # New SFX
        bomb1_sfx = pygame.mixer.Sound("assets/sfx/bomb1.wav")
        bomb_sfx = pygame.mixer.Sound("assets/sfx/bomb.wav")
        shield_pickup_sfx = pygame.mixer.Sound("assets/sfx/shield.wav")
        blade_get_power_up_sfx = pygame.mixer.Sound("assets/sfx/blade_get_power_up.wav")
    except pygame.error as e:
        print(f"Warning: Could not load SFX - {e}")
        # slow_mo_start_sfx = None
        # slow_mo_end_sfx = None
        health_boost_sfx = None
        hit_normal_sfx = None
        hit_blade_sfx = None
        bomb1_sfx = None
        bomb_sfx = None
        shield_pickup_sfx = None
        blade_get_power_up_sfx = None

    # Load bounce SFX
    bounce_sfx_list = []
    if SFX_BOUNCE_DIR.is_dir():
        for f_path in SFX_BOUNCE_DIR.iterdir():
            if f_path.suffix.lower() in ['.wav', '.mp3']:
                try:
                    sound = pygame.mixer.Sound(f_path)
                    bounce_sfx_list.append(sound)
                    print(f"Loaded bounce SFX: {f_path.name}")
                except pygame.error as e:
                    print(f"Warning: Could not load bounce SFX {f_path.name} - {e}")
    if not bounce_sfx_list:
        print("Warning: No bounce SFX loaded. Check assets/sfx/bounce/ directory.")

    default_font = pygame.font.SysFont(None, 48)
    active_text_overlays = []
    camera = Camera()
    particle_emitter = ParticleEmitter()

    screen = pygame.display.set_mode((CANVAS_W, CANVAS_H))
    clock  = pygame.time.Clock()
    
    # Initialize video background
    video_bg = VideoBackground("assets/backgrounds/abstract_loop_fade.mp4", CANVAS_W, CANVAS_H)
    
    saw_token_img = pygame.image.load("assets/pickups/saw_token.png").convert_alpha()
    heart_token_img = pygame.image.load("assets/pickups/heart_token.png").convert_alpha()
    blade_img     = pygame.image.load("assets/pickups/blade.png").convert_alpha()
    shield_token_img = pygame.image.load("assets/pickups/shield_token.webp").convert_alpha()
    bomb_token_img = pygame.image.load("assets/pickups/bomb_token.png").convert_alpha()
    # freeze_token_img = pygame.image.load("assets/pickups/ice_token.webp").convert_alpha() # Removed
    phys.blade_img = blade_img

    space = make_space((ARENA_WIDTH_FROM_CFG, ARENA_HEIGHT_FROM_CFG), border_thickness=BORDER_THICKNESS_CFG)
    # director = Director(SCRIPT_FILE) # Removed Director instance

    # Game state dictionary
    game_state = {
        # "game_speed_factor": 1.0, # Removed
        # "slowmo_end_time": 0,     # Removed
        # "pending_slowmo_factor": 1.0, # Removed
        # "pending_slowmo_duration": 0, # Removed
        # "pending_slowmo_activate_time": 0, # Removed
        "border_original_color": BORDER_COLOR_CFG,
        "border_current_color": BORDER_COLOR_CFG, # Start with original color
        "border_flash_until_time": 0.0,
        "border_flash_color_config": BORDER_FLASH_COLOR_CFG, # Store the configured flash color
        "border_flash_duration_config": DEFAULT_FLASH_DURATION_CFG # Store the configured flash duration
    }

    orbs = []
    pickups = [] # Initialize pickups list here
    saws = [] # Initialize saws list here (though it's not directly in context, good practice)

    # emergency_heart_cooldowns = {} # Orb_name: last_emergency_heart_spawn_time. Still used for safety period hearts.
    item_spawn_cooldowns = {} # Key: f"{orb_name}_{item_kind}", Value: last_spawn_time
    last_unified_pickup_spawn_attempt_time = 0.0

    # Create the context that director and physics callbacks will use
    # This instance holds references to game objects and state that events might modify.
    battle_context = MainBattleContext(
        screen, space, pickups, 
        saw_token_img, heart_token_img, shield_token_img, bomb_token_img, # freeze_token_img, # Removed
        blade_img, 
        active_text_overlays, default_font, game_state, orbs,
        # slow_mo_start_sfx, slow_mo_end_sfx, # Removed
        health_boost_sfx, hit_normal_sfx, hit_blade_sfx,
        bomb1_sfx, bomb_sfx, shield_pickup_sfx, 
        blade_get_power_up_sfx, # ADDED
        camera, particle_emitter,
        PICKUP_RADIUS_CFG, 
        ARENA_WIDTH_FROM_CFG, # Pass the actual arena width used for physics space
        ARENA_HEIGHT_FROM_CFG, # Pass the actual arena height used for physics space
        bounce_sfx_list, # Pass the list of bounce sounds
        ORB_RADIUS_CFG, # Pass orb radius for clamping
        BORDER_THICKNESS_CFG # Pass border thickness for clamping
    )

    for orb_config_data in cfg["orbs"]:
        logo_path = orb_config_data.get("logo", "assets/pickups/blade.png") # Fallback logo
        img = pygame.image.load(logo_path).convert_alpha()
        # Scale logo based on actual orb_radius from config
        scaled_size = int(ORB_RADIUS_CFG * 2), int(ORB_RADIUS_CFG * 2)
        img = pygame.transform.smoothscale(img, scaled_size)
        
        orb_name = orb_config_data.get("name", "Unknown Orb")
        orb_max_hp = orb_config_data.get("max_hp", 6)
        orb_color = tuple(orb_config_data.get("outline_color", [255,255,255]))
        initial_pos = tuple(orb_config_data.get("initial_position", [ARENA_WIDTH_FROM_CFG/2, ARENA_HEIGHT_FROM_CFG/2]))
        initial_vel = tuple(orb_config_data.get("initial_velocity", [0,0]))

        orb = Orb(orb_name, img, None, None, orb_max_hp, outline_color=orb_color)
        orb.attach_shape(space, radius=ORB_RADIUS_CFG) # Use ORB_RADIUS_CFG
        
        # Set initial position and velocity from the config
        orb.body.position = initial_pos
        orb.body.velocity = initial_vel
        
        # Set up AI Director health change callback
        orb.health_change_callback = battle_director.track_health_change
        
        orbs.append(orb)

    register_orb_collisions(space, battle_context)  # Pass context
    register_saw_hits(space, battle_context)      # Pass context
    register_pickup_handler(space, battle_context) # Pass context
    register_orb_wall_collisions(space, battle_context) # Register wall collisions
    # saws = [] # Moved up
    # pickups = [] # Moved up

    frames, winner = [], None
    current_game_time_sec = 0.0 # Initialize current game time
    frames_to_generate = int(DURATION_SECONDS * GAME_FPS)
    # Initialize AI strategy for use throughout the loop
    ai_strategy = None
    
    for frame_i in range(frames_to_generate):
        current_game_time_sec = frame_i / GAME_FPS
        battle_context.current_game_time_sec = current_game_time_sec # Update context

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return

        # director.tick(current_game_time_sec, battle_context) # Removed director.tick()

        # All slowmo related logic removed from main loop
        # game_speed_factor is effectively 1.0 always now
        
        # dt_logic = (1 / GAME_FPS) # Simplified dt_logic as game_speed_factor is gone
        # The physics step dt is calculated directly later, no need for dt_logic here if only for that.
        
        # Update video background
        dt = 1.0 / GAME_FPS
        video_bg.update(dt)

        # --- Update physics and game objects ---
        # dt = 1.0 / GAME_FPS * game_state["game_speed_factor"] # Old dt with game_speed_factor
        dt = 1.0 / GAME_FPS # Simplified dt as game_speed_factor is gone
        
        # Sub-stepping for physics
        sub_dt = dt / PHYSICS_SUBSTEPS
        for _ in range(PHYSICS_SUBSTEPS):
            space.step(sub_dt)

        # Update orb states (e.g., saw attachment, shield timers)
        for orb in orbs:
            orb.update(dt)

        camera.update(dt)
        particle_emitter.update(dt, arena_rect_for_particles)

        # Update active saws
        for s in phys.active_saws[:]:
            if not s.alive: # Saw might have been destroyed by hit or owner death
                if s in phys.active_saws: # Check if still in list before removing
                     phys.active_saws.remove(s)
                continue
            # s.update() will call s.destroy() if owner is dead, which clears owner.has_saw
            s.update(dt) 
            if not s.alive and s in phys.active_saws: # Re-check after update, if it self-destroyed
                phys.active_saws.remove(s)

        # Update active pickups (for activation timer) # This loop is now only for cleanup
        for p in pickups[:]: # Iterate a copy for safe removal if needed
            if not p.alive: # If a pickup was collected and set to not alive by physics
                if p in pickups:
                    pickups.remove(p)

        # --- AI Director Analysis ---
        if current_game_time_sec >= battle_director.last_analysis_time + battle_director.analysis_interval:
            ai_strategy = battle_director.analyze_battle_state(current_game_time_sec, orbs, battle_context)
            battle_director.last_analysis_time = current_game_time_sec
            
            # Process immediate spawns from AI director
            for spawn_plan in ai_strategy['immediate_spawns']:
                if len(pickups) < MAX_PICKUPS_ON_SCREEN:
                    # Find the target orb
                    target_orb = None
                    if spawn_plan.get('target_orb'):
                        target_orb = next((o for o in orbs if o.name == spawn_plan['target_orb']), None)
                    
                    if not target_orb:
                        target_orb = random.choice([o for o in orbs if o.hp > 0] or orbs)
                    
                    # Use existing spawning logic but override the item type
                    battle_context.handle_spawn_pickup_event({
                        "kind": spawn_plan['type'],
                        "x": None,  # Let it use predictive positioning
                        "y": None,
                        "_ai_spawn": True,
                        "_ai_reason": spawn_plan['reason']
                    })
                    print(f"🤖 AI Director: {spawn_plan['reason']} -> spawning {spawn_plan['type']}")
            
            # Enhanced debug information
            orb_analysis = battle_director.analyze_orb_states(orbs, current_game_time_sec)
            time_pressure = battle_director.calculate_enhanced_time_pressure(current_game_time_sec, orb_analysis, orbs)
            predicted_end = battle_director.predict_game_end_time(current_game_time_sec, orbs)
            damage_rate = battle_director.calculate_damage_rate(current_game_time_sec)
            
            print(f"🎯 AI Phase: {battle_director.get_game_phase(current_game_time_sec)}, "
                  f"Time Pressure: {time_pressure:.2f}, "
                  f"Predicted End: {predicted_end:.1f}s (target: {battle_director.target_duration}s), "
                  f"Damage Rate: {damage_rate:.2f} HP/s, "
                  f"Total HP: {orb_analysis['total_health']}")
        
        # --- Unified Dynamic Pickup Spawning Logic Integration ---
        num_current_pickups = len(pickups)
        if current_game_time_sec >= last_unified_pickup_spawn_attempt_time + UNIFIED_SPAWN_INTERVAL_SECONDS:
            if num_current_pickups < MAX_PICKUPS_ON_SCREEN:
                # Default target orb if no specific assistance is triggered
                default_target_orb = random.choice([o for o in orbs if o.hp > 0] or orbs) 
                target_orb_for_spawn = default_target_orb
                chosen_kind_for_spawn = None
                # spawn_emergency_heart_for_targeted_orb = None # Replaced by more generic system
                specific_orb_assisted = False

                if current_game_time_sec < SAFETY_PERIOD_SECONDS:
                    # Shuffle orbs to give different orbs priority in checks if multiple are low HP
                    shuffled_orbs = random.sample([o for o in orbs if o.hp > 0], len([o for o in orbs if o.hp > 0]))
                    for orb_check in shuffled_orbs:
                        if orb_check.hp <= LOW_HEALTH_THRESHOLD: # hp > 0 check already in shuffled_orbs list comp
                            # 1. Prioritize HEART
                            heart_cooldown_key = f"{orb_check.name}_heart"
                            last_heart_spawn_time = item_spawn_cooldowns.get(heart_cooldown_key, -float('inf'))
                            if current_game_time_sec >= last_heart_spawn_time + EMERGENCY_HEART_COOLDOWN_SECONDS:
                                chosen_kind_for_spawn = "heart"
                                target_orb_for_spawn = orb_check
                                specific_orb_assisted = True
                                print(f"EMERGENCY (Unified): Orb '{target_orb_for_spawn.name}' low HP. Queuing HEART.")
                                break # Assistance found

                            # 2. Prioritize SAW if no heart given and orb lacks saw
                            if not orb_check.has_saw:
                                saw_cooldown_key = f"{orb_check.name}_saw"
                                last_saw_spawn_time = item_spawn_cooldowns.get(saw_cooldown_key, -float('inf'))
                                if current_game_time_sec >= last_saw_spawn_time + ASSISTANCE_ITEM_COOLDOWN_SECONDS:
                                    chosen_kind_for_spawn = "saw"
                                    target_orb_for_spawn = orb_check
                                    specific_orb_assisted = True
                                    print(f"ASSISTANCE (Unified): Orb '{target_orb_for_spawn.name}' low HP & no saw. Queuing SAW.")
                                    break # Assistance found
                            
                            # 3. Prioritize SHIELD if no heart/saw given and orb lacks shield
                            if not orb_check.is_shielded:
                                shield_cooldown_key = f"{orb_check.name}_shield"
                                last_shield_spawn_time = item_spawn_cooldowns.get(shield_cooldown_key, -float('inf'))
                                if current_game_time_sec >= last_shield_spawn_time + ASSISTANCE_ITEM_COOLDOWN_SECONDS:
                                    chosen_kind_for_spawn = "shield"
                                    target_orb_for_spawn = orb_check
                                    specific_orb_assisted = True
                                    print(f"ASSISTANCE (Unified): Orb '{target_orb_for_spawn.name}' low HP & no shield. Queuing SHIELD.")
                                    break # Assistance found
                
                # If no specific assistance was triggered, proceed with weighted random spawning
                if not chosen_kind_for_spawn:
                    target_orb_for_spawn = default_target_orb # Ensure we use the initially chosen random orb
                    
                    # Use AI strategy weights if available, otherwise use default weights
                    weights_to_use = PICKUP_KINDS_WEIGHTS
                    if ai_strategy and ai_strategy.get('weights_override'):
                        weights_to_use = ai_strategy['weights_override']
                        print(f"🤖 AI using strategic weights: {weights_to_use}")
                    
                    available_kinds = list(weights_to_use.keys())
                    kind_weights = [weights_to_use[k] for k in available_kinds]
                    if available_kinds: # Should always be true with current weights
                        chosen_kind_list = random.choices(available_kinds, weights=kind_weights, k=1)
                        chosen_kind_for_spawn = chosen_kind_list[0]

                if chosen_kind_for_spawn and target_orb_for_spawn and target_orb_for_spawn.hp > 0:
                    prediction_duration = random.uniform(UNIFIED_PREDICTION_TIME_MIN_SECONDS, UNIFIED_PREDICTION_TIME_MAX_SECONDS)
                    if chosen_kind_for_spawn == "heart" and specific_orb_assisted:
                         # Use shorter prediction for emergency hearts to make them more immediate
                        prediction_duration = EMERGENCY_HEART_PREDICTION_TIME_SECONDS 
                    
                    # --- Data for advanced prediction --- 
                    target_orb_sim_data = {
                        "name": target_orb_for_spawn.name, 
                        "pos": pymunk.Vec2d(target_orb_for_spawn.body.position.x, target_orb_for_spawn.body.position.y),
                        "vel": pymunk.Vec2d(target_orb_for_spawn.body.velocity.x, target_orb_for_spawn.body.velocity.y),
                        "radius": target_orb_for_spawn.shape.radius,
                        "id": id(target_orb_for_spawn) # Unique ID for mapping
                    }
                    all_other_orbs_sim_data = [
                        {"name": o.name, 
                         "pos": pymunk.Vec2d(o.body.position.x, o.body.position.y),
                         "vel": pymunk.Vec2d(o.body.velocity.x, o.body.velocity.y),
                         "radius": o.shape.radius,
                         "id": id(o)}
                        for o in orbs if o != target_orb_for_spawn and o.hp > 0 # Only live orbs affect path
                    ]
                    game_env_sim_params = {
                        "arena_width": battle_context.arena_width,
                        "arena_height": battle_context.arena_height,
                        "border_thickness": battle_context.border_thickness_cfg,
                        "space_damping": space.damping, # Get damping from main space
                        "max_velocity": PRED_MAX_ORB_VELOCITY,
                        "physics_substeps": PHYSICS_SUBSTEPS
                    }
                    num_prediction_steps = int(prediction_duration / (1.0 / GAME_FPS)) # Match game's physics rate for steps

                    final_spawn_pos_vec = predict_orb_future_path_point(
                        target_orb_sim_data, 
                        all_other_orbs_sim_data, 
                        game_env_sim_params, 
                        prediction_duration, 
                        max(1, num_prediction_steps) # Ensure at least 1 step
                    )
                    final_spawn_pos = (final_spawn_pos_vec.x, final_spawn_pos_vec.y)
                    
                    # Clamping is still important after prediction
                    min_x = battle_context.border_thickness_cfg + battle_context.orb_radius_cfg + battle_context.pickup_radius
                    max_x = battle_context.arena_width - battle_context.border_thickness_cfg - battle_context.orb_radius_cfg - battle_context.pickup_radius
                    min_y = battle_context.border_thickness_cfg + battle_context.orb_radius_cfg + battle_context.pickup_radius
                    max_y = battle_context.arena_height - battle_context.border_thickness_cfg - battle_context.orb_radius_cfg - battle_context.pickup_radius
                    clamped_x = max(min_x, min(final_spawn_pos[0], max_x))
                    clamped_y = max(min_y, min(final_spawn_pos[1], max_y))
                    final_spawn_pos = (clamped_x, clamped_y)
                    
                    img_surface = None
                    if chosen_kind_for_spawn == "heart": img_surface = heart_token_img
                    elif chosen_kind_for_spawn == "saw": img_surface = saw_token_img
                    elif chosen_kind_for_spawn == "shield": img_surface = shield_token_img
                    elif chosen_kind_for_spawn == "bomb": img_surface = bomb_token_img

                    if img_surface:
                        new_pickup = Pickup(
                            kind=chosen_kind_for_spawn,
                            img_surface=img_surface,
                            pos=final_spawn_pos,
                            space=space,
                            radius=battle_context.pickup_radius,
                        )
                        pickups.append(new_pickup)
                        print(f"SPAWNED (Pred) '{chosen_kind_for_spawn.upper()}' for {target_orb_for_spawn.name} at {final_spawn_pos} (pred {prediction_duration:.2f}s)")
                        # if spawn_emergency_heart_for_targeted_orb: # Old system
                        #     emergency_heart_cooldowns[spawn_emergency_heart_for_targeted_orb.name] = current_game_time_sec
                        if specific_orb_assisted: # New system: update cooldown for the specific item and orb
                            cooldown_key = f"{target_orb_for_spawn.name}_{chosen_kind_for_spawn}"
                            item_spawn_cooldowns[cooldown_key] = current_game_time_sec
            
            last_unified_pickup_spawn_attempt_time = current_game_time_sec

        # phys.handle_bomb_explosions(...) is removed as bombs are instant.

        living = [o for o in orbs if o.hp > 0]
        if winner is None and len(living) == 1 and len(orbs) > 1: # Ensure game started with >1 orb
            winner = living[0]
            win_frame = frame_i
            print(f"WINNER: {winner.name} at frame {win_frame} ({current_game_time_sec:.2f}s)")
            # Optionally add a text overlay for winner announcement via director or directly
            # Example direct text overlay (not using director for this immediate announcement)
            win_text_payload = {
                "text": f"{winner.name} Wins!",
                "duration": 5, # Display for 5 seconds
                "position": "center",
                "font_size": 80,
                "color": winner.outline_color # Use winner's color
            }
            # battle_context.handle_text_overlay_event(win_text_payload) # If you want to use existing handler
            # Or manage a separate list for such overlays if not tied to director events.
            # For now, just printing.

        # Border flash logic
        if game_state["border_flash_until_time"] > 0:
            if current_game_time_sec >= game_state["border_flash_until_time"]:
                game_state["border_current_color"] = game_state["border_original_color"]
                game_state["border_flash_until_time"] = 0 
        # else: color remains original color (or whatever it was last set to)

        # Draw video background
        video_bg.draw(screen)

        # Draw HP bars at the top
        for i, orb in enumerate(battle_context.orbs):
            # The 'y' parameter is no longer needed as it's calculated internally by draw_top_hp_bar
            draw_top_hp_bar(screen, orb, index=i, total_orbs=len(battle_context.orbs))

        # Arena rendering offsets
        # ARENA_X0 is now 0, so render_offset_x is just camera.offset.x
        arena_render_offset_x = ARENA_X0 + camera.offset.x 
        arena_render_offset_y = ARENA_Y0 + camera.offset.y

        pygame.draw.rect(
            screen, game_state["border_current_color"], 
            (arena_render_offset_x, arena_render_offset_y, 
             ARENA_WIDTH_FROM_CFG, ARENA_HEIGHT_FROM_CFG), # Use ARENA_WIDTH_FROM_CFG
            width=BORDER_THICKNESS_CFG)

        # Draw particles: their positions are in arena space.
        # We pass the total offset of the arena on the screen (ARENA_X0/Y0 + camera_shake)
        effective_arena_offset_for_particles = pygame.math.Vector2(arena_render_offset_x, arena_render_offset_y)
        particle_emitter.draw(screen, effective_arena_offset_for_particles)

        current_time_for_overlay = current_game_time_sec
        for overlay in active_text_overlays[:]:
            if current_time_for_overlay < overlay["end_time"]:
                screen.blit(overlay["surface"], overlay["rect"])
            else:
                active_text_overlays.remove(overlay)

        for p in pickups:
            p.draw(screen, offset=(arena_render_offset_x, arena_render_offset_y))
        for s in phys.active_saws:
            s.draw(screen, offset=(arena_render_offset_x, arena_render_offset_y))
        for orb_to_draw in orbs:
            if orb_to_draw.hp > 0:
                orb_to_draw.draw(screen, offset=(arena_render_offset_x, arena_render_offset_y))

        if winner:
            if frame_i - win_frame < 2 * GAME_FPS:
                giant = pygame.transform.smoothscale(
                    winner.logo_surface, (300, 300))
                rect = giant.get_rect(center=(CANVAS_W//2, CANVAS_H//2))
                screen.blit(giant, rect)
            else:
                break

        pygame.display.flip()
        frames.append(surface_to_array(screen).copy())
        clock.tick(GAME_FPS)

    pygame.quit()
    OUT.mkdir(exist_ok=True)
    video_path = OUT / f"{cfg['title'].replace(' ','_')}.mp4"
    ImageSequenceClip(frames, fps=GAME_FPS).write_videofile(
        video_path.as_posix(), codec="libx264")
    print("Saved ->", video_path)

class MainBattleContext:
    def __init__(self, screen, space, pickups_list,
                 saw_token_img, heart_token_img, shield_token_img, bomb_token_img, # freeze_token_img, # Removed
                 blade_img,
                 active_text_overlays_list, default_font_instance,
                 game_state_dict, orbs_list,
                 health_boost_sfx=None, hit_normal_sfx=None, hit_blade_sfx=None,
                 bomb1_sfx=None, bomb_sfx=None, shield_pickup_sfx=None, # Added new SFX params
                 blade_get_power_up_sfx=None, # ADDED
                 camera_instance=None, particle_emitter_instance=None,
                 pickup_radius=20, # Added pickup_radius
                 arena_width=1080, arena_height=1920, # Added arena dimensions
                 bounce_sfx_list=None, # Added bounce_sfx_list
                 orb_radius_cfg=60,    # Added orb_radius_cfg for clamping
                 border_thickness_cfg=6 # Added border_thickness_cfg for clamping
                ):
        self.screen = screen
        self.space = space
        self.pickups = pickups_list
        self.saw_token_img = saw_token_img
        self.heart_token_img = heart_token_img
        self.shield_token_img = shield_token_img
        self.bomb_token_img = bomb_token_img
        # self.freeze_token_img = freeze_token_img # Removed
        self.blade_img = blade_img
        self.active_text_overlays = active_text_overlays_list
        self.default_font = default_font_instance
        self.game_state = game_state_dict
        self.orbs = orbs_list # This is a reference to the main list of orbs
        self.current_game_time_sec = 0.0 # Will be updated by main loop
        # SFX
        self.health_boost_sfx = health_boost_sfx
        self.hit_normal_sfx = hit_normal_sfx
        self.hit_blade_sfx = hit_blade_sfx
        self.bomb1_sfx = bomb1_sfx
        self.bomb_sfx = bomb_sfx
        self.shield_pickup_sfx = shield_pickup_sfx
        self.blade_get_power_up_sfx = blade_get_power_up_sfx # ADDED
        # Visuals & Effects
        self.camera = camera_instance
        self.particle_emitter = particle_emitter_instance
        self.pickup_radius = pickup_radius # Store pickup_radius
        self.arena_width = arena_width # Store arena width (outer dimension of border segments)
        self.arena_height = arena_height # Store arena height (outer dimension of border segments)
        self.bounce_sfx = bounce_sfx_list # Store the list of bounce sounds
        self.orb_radius_cfg = orb_radius_cfg
        self.border_thickness_cfg = border_thickness_cfg
        

    def play_sfx(self, sfx_to_play):
        if sfx_to_play:
            sfx_to_play.play()

    def play_random_bounce_sfx(self):
        if self.bounce_sfx:
            random.choice(self.bounce_sfx).play()
        # else:
            # print("DEBUG: No bounce SFX available to play.")

    def handle_spawn_pickup_event(self, payload):
        kind = payload.get("kind")
        x = payload.get("x")
        y = payload.get("y")

        # Determine position
        if x is not None and y is not None:
            # Handle normalized (0-1) or absolute coordinates from payload
            # ARENA_W and ARENA_H here should ideally be the actual arena dimensions used.
            # Using self.arena_width and self.arena_height stored in context
            current_arena_w = self.arena_width 
            current_arena_h = self.arena_height

            pos_x = x * current_arena_w if 0 <= x <= 1 else x
            pos_y = y * current_arena_h if 0 <= y <= 1 else y
            # Clamp to be within arena, away from edges for pickup radius
            pos_x = max(self.pickup_radius, min(pos_x, current_arena_w - self.pickup_radius))
            pos_y = max(self.pickup_radius, min(pos_y, current_arena_h - self.pickup_radius))
            pickup_pos = (pos_x, pos_y)
        else: # Random position if x or y is missing
            current_arena_w = self.arena_width
            current_arena_h = self.arena_height
            rand_x = random.uniform(self.pickup_radius, current_arena_w - self.pickup_radius)
            rand_y = random.uniform(self.pickup_radius, current_arena_h - self.pickup_radius)
            pickup_pos = (rand_x, rand_y)

        img_surface = None
        if kind == "saw": img_surface = self.saw_token_img
        elif kind == "heart": img_surface = self.heart_token_img
        elif kind == "shield": img_surface = self.shield_token_img
        elif kind == "bomb": img_surface = self.bomb_token_img
        # elif kind == "freeze": img_surface = self.freeze_token_img # Removed
        else: print(f"Warning: Unknown pickup kind '{kind}' in event, no image.")

        if img_surface:
            # The Pickup class itself needs to be aware of its radius for its shape
            # Assuming Pickup class in engine.game_objects.py is modified to accept radius
            # or that its default radius matches self.pickup_radius
            new_pickup = Pickup(kind, img_surface, pickup_pos, self.space, radius=self.pickup_radius) # REMOVED current_game_time_sec
            self.pickups.append(new_pickup)
            if kind == "bomb": # If a bomb pickup is spawned (this is for the pickup itself, not explosion)
                # You might not flash for bomb *spawn*, but for its *explosion*.
                # For demonstration, let's say picking up a bomb item also causes a small flash.
                # This is an example of how to call the flash logic.
                # self.game_state["border_current_color"] = self.game_state["border_flash_color_config"]
                # self.game_state["border_flash_until_time"] = self.current_game_time_sec + 0.5 # Short flash for pickup
                pass
        else:
            print(f"Could not spawn pickup of kind '{kind}' due to missing image.")

    def handle_text_overlay_event(self, payload):
        text = payload.get("text", "Default Text")
        duration = payload.get("duration", 3.0)
        position_key = payload.get("position", "center") 
        color = payload.get("color", (255, 255, 255))
        font_size = payload.get("font_size", 48)
        event_time = payload.get("event_time")

        custom_font = pygame.font.SysFont(None, font_size)
        text_surface = custom_font.render(text, True, color)
        rect = text_surface.get_rect()

        if position_key == "center":
            rect.center = (CANVAS_W // 2, CANVAS_H // 2)
        elif position_key == "top_center":
            rect.center = (CANVAS_W // 2, SAFE_TOP + 50) 
        elif position_key == "bottom_center":
            rect.center = (CANVAS_W // 2, ARENA_Y0 + ARENA_SIZE + 50)
        elif isinstance(position_key, (list, tuple)) and len(position_key) == 2:
            x_pos, y_pos = position_key
            abs_x = int(x_pos * CANVAS_W) if isinstance(x_pos, float) and 0 <= x_pos <= 1 else int(x_pos)
            abs_y = int(y_pos * CANVAS_H) if isinstance(y_pos, float) and 0 <= y_pos <= 1 else int(y_pos)
            rect.center = (abs_x, abs_y)
        else:
             rect.center = (CANVAS_W // 2, CANVAS_H // 2)

        end_time = event_time + duration
        self.active_text_overlays.append({"surface": text_surface, "rect": rect, "end_time": end_time})
        print(f"Director: Text overlay '{text}' for {duration}s, from {event_time:.2f}s to {end_time:.2f}s")

    def handle_bomb_pickup_effect(self, exploding_orb_pos): # Example: new method or part of bomb logic
        """Triggers effects for a bomb, including border flash."""
        # Existing bomb logic (particles, camera shake, damage etc.) would go here or be called from here
        # ... (imagine your bomb explosion logic here) ...

        # Trigger border flash
        self.game_state["border_current_color"] = self.game_state["border_flash_color_config"]
        self.game_state["border_flash_until_time"] = self.current_game_time_sec + self.game_state["border_flash_duration_config"]
        print(f"BOMB EFFECT: Border flash triggered until {self.game_state['border_flash_until_time']:.2f}s")

# Helper function for predictive spawning
def predict_orb_future_path_point(target_orb_data, all_orbs_data, game_env_params, duration_to_predict, num_steps):
    """
    Simulates the target orb's movement in a temporary space to predict future position.
    target_orb_data: {"name": str, "pos": Vec2d, "vel": Vec2d, "radius": float, "id": int}
    all_orbs_data: list of dicts, each like target_orb_data, for *other* orbs.
    game_env_params: {"arena_width": float, "arena_height": float, "border_thickness": float, 
                      "space_damping": float, "max_velocity": float, "physics_substeps": int}
    duration_to_predict: float (total time in seconds)
    num_steps: int (how many steps to divide the duration into for simulation - each step is one game frame)
    Returns: predicted Vec2d position of the target orb, or its last known if error.
    """
    temp_space = pymunk.Space()
    temp_space.damping = game_env_params["space_damping"]
    
    # dt_step is the duration of one main game frame for the prediction
    # If the main game uses GANE_FPS (e.g. 60), then dt_step = 1/60 if num_steps matches prediction_duration*GAME_FPS
    # num_steps is int(prediction_duration / (1.0 / GAME_FPS))
    # So dt_step = prediction_duration / (prediction_duration * GAME_FPS) = 1.0 / GAME_FPS
    # This is correct: each step in the outer loop simulates one "game frame"
    dt_per_simulation_step = duration_to_predict / num_steps 

    # Add arena boundaries to temp_space, matching engine/physics.py:make_space
    # arena_width and arena_height in game_env_params are the inner dimensions of the playable area.
    # border_thickness is the thickness of the walls.
    
    border_segment_radius = game_env_params["border_thickness"] / 2.0
    arena_w = game_env_params["arena_width"]
    arena_h = game_env_params["arena_height"]

    # These points define the centerlines of the wall segments.
    # The segments' own radius (border_segment_radius) makes them thick.
    # This setup ensures the *inner edges* of the physical walls are at:
    # y=0, y=arena_h, x=0, x=arena_w.

    # Coordinates for the centerlines of the wall segments
    # Top: centerline at y = -border_segment_radius. Inner edge at y = 0.
    # Bottom: centerline at y = arena_h + border_segment_radius. Inner edge at y = arena_h.
    # Left: centerline at x = -border_segment_radius. Inner edge at x = 0.
    # Right: centerline at x = arena_w + border_segment_radius. Inner edge at x = arena_w.

    static_body = temp_space.static_body
    wall_segments_params = [
        # Top wall
        ((-border_segment_radius, -border_segment_radius), (arena_w + border_segment_radius, -border_segment_radius), border_segment_radius),
        # Right wall
        ((arena_w + border_segment_radius, -border_segment_radius), (arena_w + border_segment_radius, arena_h + border_segment_radius), border_segment_radius),
        # Bottom wall
        ((arena_w + border_segment_radius, arena_h + border_segment_radius), (-border_segment_radius, arena_h + border_segment_radius), border_segment_radius),
        # Left wall
        ((-border_segment_radius, arena_h + border_segment_radius), (-border_segment_radius, -border_segment_radius), border_segment_radius)
    ]

    for p1, p2, radius in wall_segments_params:
        segment = pymunk.Segment(static_body, p1, p2, radius)
        segment.elasticity = 1.0  # Standard wall elasticity
        segment.friction = 0.5    # Standard wall friction
        segment.collision_type = phys.WALL_COLLISION_TYPE # Match main game wall collision type
        temp_space.add(segment)

    # Add orbs to temp_space
    temp_orbs_map = {} # id -> Pymunk Body

    # Add target orb first
    target_body = pymunk.Body(mass=1, moment=float('inf')) 
    target_body.position = target_orb_data["pos"]
    target_body.velocity = target_orb_data["vel"]
    target_shape = pymunk.Circle(target_body, target_orb_data["radius"])
    target_shape.elasticity = 1.0 # TODO: Get from actual orb config or a shared constant
    target_shape.friction = 0.1   # TODO: Get from actual orb config or a shared constant
    target_shape.collision_type = 1 # Orb collision type (assuming 1 for orbs)
    temp_space.add(target_body, target_shape)
    temp_orbs_map[target_orb_data["id"]] = target_body

    # Add other orbs
    for orb_data in all_orbs_data:
        if orb_data["id"] == target_orb_data["id"]: continue
        body = pymunk.Body(mass=1, moment=float('inf'))
        body.position = orb_data["pos"]
        body.velocity = orb_data["vel"]
        shape = pymunk.Circle(body, orb_data["radius"])
        shape.elasticity = 1.0 # TODO: Get from actual orb config
        shape.friction = 0.1   # TODO: Get from actual orb config
        shape.collision_type = 1 # Orb collision type
        temp_space.add(body, shape)
        temp_orbs_map[orb_data["id"]] = body # Store the body for velocity capping
    
    # Main simulation loop (num_steps corresponds to game frames)
    # If PHYSICS_SUBSTEPS is used in the main game, replicate it here.
    # physics_substeps = game_env_params.get("physics_substeps", 1) # Default to 1 if not provided
    # sub_dt = dt_per_simulation_step / physics_substeps
    
    # For now, let's assume game_env_params will include "physics_substeps" matching main game
    # And "game_fps" for calculating sub_dt properly.
    # The current num_steps results in dt_per_simulation_step being 1/GAME_FPS.
    # So, this dt_per_simulation_step IS the main game's frame time.
    
    main_game_physics_substeps = game_env_params.get("physics_substeps", 1) # Get from params, default 1
    actual_sub_dt = dt_per_simulation_step / main_game_physics_substeps

    for _ in range(num_steps): # Each step is one "game frame"
        # Apply velocity cap before stepping physics for this frame
        for b_id, b in temp_orbs_map.items():
            velocity = b.velocity
            speed = velocity.length
            if speed > game_env_params["max_velocity"]:
                b.velocity = velocity.normalized() * game_env_params["max_velocity"]
        
        # Perform physics sub-steps for this "game frame"
        for _ in range(main_game_physics_substeps):
            temp_space.step(actual_sub_dt)

    predicted_pos = temp_orbs_map[target_orb_data["id"]].position
    # print(f"DEBUG PREDICT: Target '{target_orb_data[\"name\"]}', Start: {target_orb_data[\"pos\"]}, End: {predicted_pos}, Vel: {target_orb_data[\"vel\"]}")
    return predicted_pos

if __name__ == "__main__":
    main()