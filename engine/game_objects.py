# engine/game_objects.py
from dataclasses import dataclass, field
import random, pygame, pymunk, math, time

MAX_ORB_VELOCITY = 500 # pixels/second, reduced for better control and slower gameplay
HP_ANIMATION_DURATION = 0.3 # seconds for the HP change animation

@dataclass
class Orb:
    name: str
    logo_surface: pygame.Surface         # image ronde
    body: pymunk.Body                    # physique
    shape: pymunk.Circle
    max_hp: int = 7
    hp: int = field(init=False)
    outline_color: tuple[int,int,int] = field(default=(255,255,255)) # Default to white
    # heal_effect_active: bool = field(init=False, default=False) # old simple heal flash
    # heal_effect_timer: int = field(init=False, default=0) # old simple heal flash
    
    # Pickup related states
    is_shielded: bool = field(init=False, default=False)
    has_saw: 'Saw | None' = field(init=False, default=None)

    # HP Animation State
    previous_hp: int = field(init=False) # HP at the start of the previous frame
    hp_animation_timer: float = field(init=False, default=0.0)
    hp_at_animation_start: int = field(init=False, default=0)
    hp_target_for_animation: int = field(init=False, default=0)
    # is_gaining_hp_animation: bool = field(init=False, default=False) # Can be inferred from hp_target vs hp_at_start
    
    # Size Animation State
    base_radius: float = field(init=False, default=0.0)  # Original radius before size changes
    current_radius: float = field(init=False, default=0.0)  # Current animated radius
    target_radius: float = field(init=False, default=0.0)  # Target radius for animation
    size_animation_timer: float = field(init=False, default=0.0)
    size_animation_duration: float = field(init=False, default=0.5)  # 0.5 second animation
    
    # Image scaling
    original_logo_surface: pygame.Surface = field(init=False, default=None)  # Original unscaled logo
    scaled_logo_surface: pygame.Surface = field(init=False, default=None)   # Currently scaled logo
    
    # AI Director callback for health change tracking
    health_change_callback: callable = field(init=False, default=None)
    shield_loss_callback: callable = field(init=False, default=None)

    def __post_init__(self):
        self.hp = self.max_hp
        self.previous_hp = self.max_hp # Initialize previous_hp
        self.hp_at_animation_start = self.max_hp
        self.hp_target_for_animation = self.max_hp
        # Size animation will be initialized when attach_shape is called

    def update(self, dt):
        # Update HP animation timer
        if self.hp_animation_timer > 0:
            self.hp_animation_timer -= dt
            if self.hp_animation_timer < 0:
                self.hp_animation_timer = 0
                # Animation finished, ensure current hp is the target (should already be)
                # self.hp = self.hp_target_for_animation # This should be done by take_hit/heal
        
        # Update size animation
        if self.size_animation_timer > 0:
            self.size_animation_timer -= dt
            if self.size_animation_timer < 0:
                self.size_animation_timer = 0
            
            # Interpolate radius based on animation progress
            progress = 1.0 - (self.size_animation_timer / self.size_animation_duration)
            # Smooth easing function
            progress = progress * progress * (3.0 - 2.0 * progress)  # Smoothstep
            
            start_radius = self.current_radius if hasattr(self, 'current_radius') else self.base_radius
            new_radius = start_radius + (self.target_radius - start_radius) * progress
            
            # Only update if radius changed significantly (avoid constant recreation)
            current_r = getattr(self, 'current_radius', self.base_radius)
            if abs(new_radius - current_r) > 0.5:
                self.current_radius = new_radius
                
                # Recreate physics shape with new radius (pymunk circles are immutable)
                if self.shape and self.body and hasattr(self, '_space') and self._space:
                    try:
                        # Remove old shape
                        self._space.remove(self.shape)
                        
                        # Create new shape with updated radius
                        new_shape = pymunk.Circle(self.body, self.current_radius)
                        new_shape.elasticity = self.shape.elasticity
                        new_shape.friction = self.shape.friction
                        new_shape.collision_type = self.shape.collision_type
                        new_shape.orb_ref = self
                        
                        # Add new shape to space
                        self._space.add(new_shape)
                        
                        # Update reference
                        self.shape = new_shape
                        
                        # Update scaled logo surface
                        self._update_scaled_logo()
                    except Exception as e:
                        print(f"Warning: Failed to update orb {self.name} radius: {e}")
                        # Fallback: just update the visual radius
                        self.current_radius = new_radius
                        self._update_scaled_logo()
            else:
                self.current_radius = new_radius
                self._update_scaled_logo()

        # Velocity capping with blade speed reduction
        if self.body: 
            velocity = self.body.velocity
            speed = velocity.length
            
            # Apply blade speed reduction if orb has a saw equipped
            max_velocity = MAX_ORB_VELOCITY
            if self.has_saw:
                max_velocity = MAX_ORB_VELOCITY * 2  # 50% slower when blade equipped
            
            if speed > max_velocity:
                self.body.velocity = velocity.normalized() * max_velocity
        
        # Update previous_hp at the end of the update, before next frame's input processing
        # This is crucial for renderer to correctly diff current vs previous visual state
        # self.previous_hp = self.hp # This should be set in the main loop AFTER rendering for correct diff

    def draw(self, screen, offset=(0, 0)):
        x = self.body.position.x + offset[0]
        y = self.body.position.y + offset[1]

        # Create neon glow effect with multiple layers
        # Use current_radius for visual effects to match physics
        base_radius = int(self.current_radius if hasattr(self, 'current_radius') else self.shape.radius)
        
        # Outer glow layers (largest to smallest)
        glow_layers = [
            (base_radius + 40, (*self.outline_color, 15)),   # Outermost glow
            (base_radius + 25, (*self.outline_color, 30)),   # Middle glow
            (base_radius + 15, (*self.outline_color, 50)),   # Inner glow
        ]
        
        # Draw glow layers
        for glow_radius, glow_color in glow_layers:
            glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surface, glow_color, (glow_radius, glow_radius), glow_radius)
            screen.blit(glow_surface, (int(x - glow_radius), int(y - glow_radius)))

        # Draw shield with enhanced neon effect if active
        if self.is_shielded:
            shield_base_radius = base_radius + 35
            
            # Shield glow layers
            shield_glow_layers = [
                (shield_base_radius + 20, (0, 255, 255, 25)),    # Cyan outer glow
                (shield_base_radius + 10, (0, 200, 255, 50)),    # Cyan middle glow
                (shield_base_radius + 5, (100, 150, 255, 80)),   # Blue inner glow
            ]
            
            for shield_radius, shield_color in shield_glow_layers:
                shield_surface = pygame.Surface((shield_radius * 2, shield_radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(shield_surface, shield_color, (shield_radius, shield_radius), shield_radius)
                screen.blit(shield_surface, (int(x - shield_radius), int(y - shield_radius)))
            
            # Shield border with pulsing effect
            pulse = abs(math.sin(time.time() * 4)) * 0.3 + 0.7  # Pulse between 0.7 and 1.0
            shield_border_color = (int(0 * pulse), int(255 * pulse), int(255 * pulse))
            pygame.draw.circle(screen, shield_border_color, (int(x), int(y)), shield_base_radius, width=4)
            
        # Draw main orb outline with enhanced neon effect
        outline_radius = base_radius + 8
        
        # Multiple outline layers for neon effect
        outline_layers = [
            (outline_radius + 3, (*self.outline_color, 180)),  # Outer outline
            (outline_radius, (*self.outline_color, 255)),      # Main outline
        ]
        
        for out_radius, out_color in outline_layers:
            # Create surface for alpha blending
            outline_surface = pygame.Surface((out_radius * 2, out_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(outline_surface, out_color, (out_radius, out_radius), out_radius, width=6)
            screen.blit(outline_surface, (int(x - out_radius), int(y - out_radius)))

        # Add inner shadow/depth to the orb
        inner_shadow_surface = pygame.Surface((base_radius * 2, base_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(inner_shadow_surface, (0, 0, 0, 30), (base_radius, base_radius), base_radius - 5)
        screen.blit(inner_shadow_surface, (int(x - base_radius), int(y - base_radius)))

        # Draw logo with subtle glow
        logo_glow_surface = pygame.Surface((base_radius * 2, base_radius * 2), pygame.SRCALPHA)
        # Add a subtle white glow behind the logo
        pygame.draw.circle(logo_glow_surface, (255, 255, 255, 40), (base_radius, base_radius), base_radius - 10)
        screen.blit(logo_glow_surface, (int(x - base_radius), int(y - base_radius)))
        
        # Draw scaled logo on top of everything
        logo_to_draw = self.scaled_logo_surface if hasattr(self, 'scaled_logo_surface') and self.scaled_logo_surface else self.logo_surface
        rect = logo_to_draw.get_rect(center=(x, y))
        screen.blit(logo_to_draw, rect)

        # Saw is drawn in the main loop if active, not here directly from orb
        # Bomb is instant, not drawn as equipped

    def take_hit(self, dmg=1):
        if self.is_shielded:
            self.is_shielded = False
            print(f"{self.name} shield blocked a hit!")
            # Call shield loss callback if available
            if self.shield_loss_callback:
                self.shield_loss_callback()
            # Here, you could also trigger a specific "shield block" animation if desired
            # For now, no HP change means no HP animation
            return

        if self.hp <= 0: # Already dead, no further damage or animation
            return

        old_hp_for_animation = self.hp
        new_hp = max(0, self.hp - dmg)
        
        if new_hp != old_hp_for_animation: # Only animate if HP actually changed
            self.hp = new_hp # Update actual HP
            self.hp_at_animation_start = old_hp_for_animation
            self.hp_target_for_animation = new_hp
            self.hp_animation_timer = HP_ANIMATION_DURATION
            # self.is_gaining_hp_animation = False # Redundant, target < start implies loss
            print(f"DEBUG: {self.name} took hit. HP: {old_hp_for_animation} -> {new_hp}. Anim timer: {self.hp_animation_timer}")
            
            # Notify AI Director of health change
            if self.health_change_callback:
                import time
                self.health_change_callback(self.name, old_hp_for_animation, new_hp, time.time(), "damage")
            
            # Trigger size reduction animation (7% smaller per HP lost)
            self._animate_size_for_hp_change()

    def heal(self, amount=1): # Default heal amount to 1 as per recent changes
        if self.hp >= self.max_hp: # Already full, no heal or animation
            return

        old_hp_for_animation = self.hp
        new_hp = min(self.max_hp, self.hp + amount)

        if new_hp != old_hp_for_animation: # Only animate if HP actually changed
            self.hp = new_hp # Update actual HP
            self.hp_at_animation_start = old_hp_for_animation
            self.hp_target_for_animation = new_hp
            self.hp_animation_timer = HP_ANIMATION_DURATION
            # self.is_gaining_hp_animation = True # Redundant, target > start implies gain
            print(f"DEBUG: {self.name} healed. HP: {old_hp_for_animation} -> {new_hp}. Anim timer: {self.hp_animation_timer}")
            
            # Notify AI Director of health change
            if self.health_change_callback:
                import time
                self.health_change_callback(self.name, old_hp_for_animation, new_hp, time.time(), "heal")
            
            # Trigger size increase animation (7% larger per HP gained)
            self._animate_size_for_hp_change()
        # The old heal_effect_active and heal_effect_timer are removed
        # The new HP bar animation will serve as the visual feedback.
    
    def _animate_size_for_hp_change(self):
        """Animate orb size based on current HP (7% change per HP point)"""
        if not hasattr(self, 'base_radius') or self.base_radius == 0:
            return
        
        # Calculate target radius: 7% reduction per missing HP
        hp_ratio = self.hp / self.max_hp
        size_multiplier = 1.0 - (1.0 - hp_ratio) * 0.07 * self.max_hp  # 7% per HP point
        self.target_radius = self.base_radius * size_multiplier
        
        # Start animation
        self.size_animation_timer = self.size_animation_duration
        print(f"DEBUG: {self.name} size animation: {self.current_radius:.1f} -> {self.target_radius:.1f} (HP: {self.hp}/{self.max_hp})")
    
    def _update_scaled_logo(self):
        """Update the scaled logo surface based on current radius"""
        if self.original_logo_surface and hasattr(self, 'base_radius') and self.base_radius > 0:
            # Calculate scale factor based on radius change
            scale_factor = self.current_radius / self.base_radius
            new_size = int(self.base_radius * 2 * scale_factor)
            
            if new_size > 0:
                self.scaled_logo_surface = pygame.transform.smoothscale(
                    self.original_logo_surface, (new_size, new_size)
                )
            else:
                self.scaled_logo_surface = self.original_logo_surface

    def attach_shape(self, space, radius):
        """Crée le body + shape et lie la shape à self (pour collisions)."""
        body = pymunk.Body(mass=1, moment=10_000)
        body.position = random.randint(150, 650), random.randint(150, 650)
        body.velocity = random.choice([(250,150), (-200,230), (200,-220)])

        shape = pymunk.Circle(body, radius)
        shape.elasticity = 1.2  # Increased bounce for more dynamic collisions
        shape.collision_type = 1          # <- on tag toutes les orbs = 1
        shape.orb_ref = self              # <- pour savoir qui est touché

        space.add(body, shape)
        self.body, self.shape = body, shape
        self._space = space  # Store space reference for size updates
        
        # Initialize size animation values
        self.base_radius = radius
        self.current_radius = radius
        self.target_radius = radius
        
        # Store original logo and create initial scaled version
        self.original_logo_surface = self.logo_surface.copy()
        self.scaled_logo_surface = self.logo_surface.copy()

    def destroy(self, space):
        self.alive = False
        space.remove(self.body, self.shape)
        self.body = None
        self.shape = None

class Pickup:
    """
    Objet au sol qu'un orb peut ramasser.
    kind: 'saw', 'heart', 'shield', 'bomb'
    """

    def __init__(self, kind, img_surface, pos, space, radius=20):
        self.kind = kind
        sprite_diameter = int(radius * 2)
        self.sprite = pygame.transform.smoothscale(img_surface, (sprite_diameter, sprite_diameter))
        
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pos
        shape = pymunk.Circle(body, radius)
        shape.collision_type = 3 # Collision type for pickups
        shape.pickup_ref = self
        space.add(body, shape)
        self.body, self.shape = body, shape
        self.alive = True
        
        self.is_active = True

    def draw(self, screen, offset=(0, 0)):
        if not self.alive:
            return
        
        x, y = self.body.position
        center_x, center_y = x + offset[0], y + offset[1]
        
        # Enhanced neon glow effects for pickups based on type
        pulse = abs(math.sin(time.time() * 3)) * 0.4 + 0.6  # Pulse between 0.6 and 1.0
        
        # Define glow colors based on pickup type
        glow_colors = {
            'heart': (255, 100, 100),    # Red glow for hearts
            'shield': (100, 200, 255),   # Blue glow for shields 
            'saw': (255, 200, 0),        # Yellow glow for saws
            'bomb': (255, 150, 0),       # Orange glow for bombs
            'blade': (200, 100, 255),    # Purple glow for blades
            'ice': (150, 255, 255),      # Cyan glow for ice
            'fire': (255, 80, 0)         # Red-orange glow for fire
        }
        
        base_glow_color = glow_colors.get(self.kind, (255, 255, 255))  # Default white
        
        # Multi-layered glow effect
        radius = self.shape.radius
        for i in range(4):
            glow_radius = radius + (25 - i * 5)
            alpha = int((80 - i * 15) * pulse)
            glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surface, (*base_glow_color, alpha), 
                             (glow_radius, glow_radius), glow_radius)
            screen.blit(glow_surface, (int(center_x - glow_radius), int(center_y - glow_radius)), 
                      special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Draw main sprite
        rect = self.sprite.get_rect(center=(center_x, center_y))
        screen.blit(self.sprite, rect)
        
        # Add highlight ring
        highlight_color = tuple(min(255, c + 100) for c in base_glow_color)
        pygame.draw.circle(screen, highlight_color, (int(center_x), int(center_y)), 
                         int(radius + 5), 3)

    def destroy(self, space):
        self.alive = False
        if self.body in space.bodies:
            space.remove(self.body)
        if self.shape in space.shapes:
            space.remove(self.shape)
        # Make sure references are cleared to help GC if necessary, though Python handles most.
        self.body = None
        self.shape = None

class Saw:
    """
    Scie attachée (centrée) sur son owner. Rayon > orb → dépasse visuellement.
    """
    def __init__(self, img_surface, owner_orb, space,
                 omega_deg=360):
        self.owner: Orb = owner_orb # Type hint for clarity
        self.angle = 0
        self.omega = omega_deg
        self.alive = True
        self.space = space # Store space reference for destroy method

        # Dynamically scale saw based on owner orb's radius
        # Example: Saw diameter is 2.5 times the orb's radius
        orb_radius = self.owner.shape.radius 
        scale_px = int(orb_radius * 2.5) 

        self.sprite_orig = pygame.transform.smoothscale(img_surface,
                                                        (scale_px, scale_px))
        self.sprite = self.sprite_orig

        r = scale_px // 2
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = owner_orb.body.position
        shape = pymunk.Circle(body, r)
        shape.collision_type = 2 # Collision type for saws
        shape.sensor = True  # Make saw a sensor to avoid physics interference
        shape.saw_ref = self
        space.add(body, shape)
        self.body, self.shape = body, shape

    def update(self, dt):
        # tourne en place, suit l'orb
        if not self.owner or self.owner.hp <= 0 or not self.alive:
            if self.alive: # If alive but owner gone, destroy self
                print(f"DEBUG: Saw owner {self.owner.name if self.owner else 'Unknown'} is gone or dead. Self-destructing saw.")
                self.destroy() # Call self.destroy without space arg if space is stored
            return

        self.angle += self.omega * dt
        self.body.position = self.owner.body.position
        # Since saw is now a sensor, we can safely match velocity for accurate collision detection
        self.body.velocity = self.owner.body.velocity
        self.sprite = pygame.transform.rotate(self.sprite_orig, -self.angle)

    def draw(self, screen, offset=(0, 0)):
        if not self.alive or not self.owner or self.owner.hp <= 0:
            return
        
        x, y = self.body.position
        center_x, center_y = x + offset[0], y + offset[1]
        
        # Enhanced neon glow effect for spinning saw
        spin_glow = abs(math.sin(self.angle * 0.1)) * 0.3 + 0.7  # Spin-based glow
        
        # Saw glow colors (dangerous orange-red)
        saw_glow_color = (255, 100, 0)  # Orange-red
        
        # Multi-layered spinning glow
        radius = self.shape.radius
        for i in range(5):
            glow_radius = radius + (30 - i * 6)
            alpha = int((100 - i * 15) * spin_glow)
            glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surface, (*saw_glow_color, alpha), 
                             (glow_radius, glow_radius), glow_radius)
            screen.blit(glow_surface, (int(center_x - glow_radius), int(center_y - glow_radius)), 
                      special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Draw main sprite
        rect = self.sprite.get_rect(center=(center_x, center_y))
        screen.blit(self.sprite, rect)
        
        # Add spinning highlight effects
        highlight_intensity = abs(math.sin(self.angle * 0.05)) * 100 + 155
        highlight_color = (255, int(highlight_intensity), 0)
        pygame.draw.circle(screen, highlight_color, (int(center_x), int(center_y)), 
                         int(radius + 8), 4)

    def destroy(self): # Removed space argument, use self.space
        if not self.alive: return # Already destroyed
        self.alive = False
        print(f"DEBUG: Destroying saw for owner {self.owner.name if self.owner else 'Unknown'}.")
        if self.body and self.body in self.space.bodies:
            self.space.remove(self.body)
        if self.shape and self.shape in self.space.shapes:
            self.space.remove(self.shape)
        
        if self.owner and self.owner.has_saw == self:
            self.owner.has_saw = None
            print(f"DEBUG: Cleared has_saw for orb {self.owner.name}")

        self.body, self.shape, self.owner, self.space = None, None, None, None