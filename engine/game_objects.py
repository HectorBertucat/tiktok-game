# engine/game_objects.py
from dataclasses import dataclass, field
import random, pygame, pymunk, math

MAX_ORB_VELOCITY = 1500 # pixels/second, adjust as needed
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
    
    # AI Director callback for health change tracking
    health_change_callback: callable = field(init=False, default=None)

    def __post_init__(self):
        self.hp = self.max_hp
        self.previous_hp = self.max_hp # Initialize previous_hp
        self.hp_at_animation_start = self.max_hp
        self.hp_target_for_animation = self.max_hp

    def update(self, dt):
        # Update HP animation timer
        if self.hp_animation_timer > 0:
            self.hp_animation_timer -= dt
            if self.hp_animation_timer < 0:
                self.hp_animation_timer = 0
                # Animation finished, ensure current hp is the target (should already be)
                # self.hp = self.hp_target_for_animation # This should be done by take_hit/heal

        # Velocity capping
        if self.body: 
            velocity = self.body.velocity
            speed = velocity.length
            if speed > MAX_ORB_VELOCITY:
                self.body.velocity = velocity.normalized() * MAX_ORB_VELOCITY
        
        # Update previous_hp at the end of the update, before next frame's input processing
        # This is crucial for renderer to correctly diff current vs previous visual state
        # self.previous_hp = self.hp # This should be set in the main loop AFTER rendering for correct diff

    def draw(self, screen, offset=(0, 0)):
        x = self.body.position.x + offset[0]
        y = self.body.position.y + offset[1]

        # Draw shield effect first if active, so it's behind the orb
        if self.is_shielded:
            shield_color_outline = (0, 0, 255)  # Blue outline
            shield_color_fill = (100, 100, 255, 77) # Lighter blue fill, 77/255 opacity (~30%)
            # Make shield visually larger
            shield_radius = int(self.shape.radius + 28) # Increased from +6 to +12

            # Create a temporary surface for alpha blending the shield fill
            shield_surface = pygame.Surface((shield_radius * 2, shield_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(shield_surface, shield_color_fill, (shield_radius, shield_radius), shield_radius)
            screen.blit(shield_surface, (int(x - shield_radius), int(y - shield_radius)))
            
        # Draw outline next
        outline_radius = self.shape.radius + 3 # Slightly larger for outline
        pygame.draw.circle(screen, self.outline_color, (int(x), int(y)), int(outline_radius), width=3)

        # Draw logo on top of everything
        rect = self.logo_surface.get_rect(center=(x, y))
        screen.blit(self.logo_surface, rect)

        # Saw is drawn in the main loop if active, not here directly from orb
        # Bomb is instant, not drawn as equipped

    def take_hit(self, dmg=1):
        if self.is_shielded:
            self.is_shielded = False
            print(f"{self.name} shield blocked a hit!")
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
        # The old heal_effect_active and heal_effect_timer are removed
        # The new HP bar animation will serve as the visual feedback.

    def attach_shape(self, space, radius):
        """Crée le body + shape et lie la shape à self (pour collisions)."""
        body = pymunk.Body(mass=1, moment=10_000)
        body.position = random.randint(150, 650), random.randint(150, 650)
        body.velocity = random.choice([(250,150), (-200,230), (200,-220)])

        shape = pymunk.Circle(body, radius)
        shape.elasticity = 1.0
        shape.collision_type = 1          # <- on tag toutes les orbs = 1
        shape.orb_ref = self              # <- pour savoir qui est touché

        space.add(body, shape)
        self.body, self.shape = body, shape

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
        rect = self.sprite.get_rect(center=(x + offset[0], y + offset[1]))
        screen.blit(self.sprite, rect)

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
                 omega_deg=720):
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
        self.body.velocity = self.owner.body.velocity # Match owner's velocity for better kinematic collisions
        self.sprite = pygame.transform.rotate(self.sprite_orig, -self.angle)

    def draw(self, screen, offset=(0, 0)):
        if not self.alive or not self.owner or self.owner.hp <= 0:
            return
        
        # Current sprite drawing
        x, y = self.body.position
        rect = self.sprite.get_rect(center=(x + offset[0], y + offset[1]))
        screen.blit(self.sprite, rect)

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