# engine/game_objects.py
from dataclasses import dataclass, field
import random, pygame, pymunk, math

MAX_ORB_VELOCITY = 1500 # pixels/second, adjust as needed

@dataclass
class Orb:
    name: str
    logo_surface: pygame.Surface         # image ronde
    body: pymunk.Body                    # physique
    shape: pymunk.Circle
    max_hp: int = 7
    hp: int = field(init=False)
    outline_color: tuple[int,int,int] = field(default=(255,255,255)) # Default to white
    heal_effect_active: bool = field(init=False, default=False)
    heal_effect_timer: int = field(init=False, default=0)
    
    # Pickup related states
    is_shielded: bool = field(init=False, default=False) # Renamed from shielded for consistency
    has_saw: 'Saw | None' = field(init=False, default=None)

    def __post_init__(self):
        self.hp = self.max_hp

    def update(self, dt):
        # Heal effect timer
        if self.heal_effect_active:
            self.heal_effect_timer -= 1
            if self.heal_effect_timer <= 0:
                self.heal_effect_active = False

        # Velocity capping
        if self.body: # Ensure body exists
            velocity = self.body.velocity
            speed = velocity.length
            if speed > MAX_ORB_VELOCITY:
                self.body.velocity = velocity.normalized() * MAX_ORB_VELOCITY
                # print(f"DEBUG: Orb {self.name} velocity capped from {speed:.0f} to {MAX_ORB_VELOCITY}")

    def draw(self, screen, offset=(0, 0)):
        x = self.body.position.x + offset[0]
        y = self.body.position.y + offset[1]

        # Draw shield effect first if active, so it's behind the orb
        if self.is_shielded:
            shield_color_outline = (0, 0, 255)  # Blue outline
            shield_color_fill = (100, 100, 255, 77) # Lighter blue fill, 77/255 opacity (~30%)
            # Make shield visually larger
            shield_radius = int(self.shape.radius + 12) # Increased from +6 to +12

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
            # Potentially add a sound effect for shield break here via battle_context
            return

        self.hp = max(0, self.hp - dmg)

    def heal(self, amount=2):
        self.hp = min(self.max_hp, self.hp + amount)
        self.heal_effect_active = True
        self.heal_effect_timer = 10 # Number of frames for the effect

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