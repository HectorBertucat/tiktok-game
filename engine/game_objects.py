# engine/game_objects.py
from dataclasses import dataclass, field
import random, pygame, pymunk, math

@dataclass
class Orb:
    name: str
    logo_surface: pygame.Surface         # image ronde
    body: pymunk.Body                    # physique
    shape: pymunk.Circle
    max_hp: int = 6
    hp: int = field(init=False)
    outline_color: tuple[int,int,int] = field(default=(255,255,255)) # Default to white
    heal_effect_active: bool = field(init=False, default=False)
    heal_effect_timer: int = field(init=False, default=0)

    def __post_init__(self):
        self.hp = self.max_hp

    def draw(self, screen, offset=(0, 0)):
        x = self.body.position.x + offset[0]
        y = self.body.position.y + offset[1]

        # Draw outline first
        outline_radius = self.shape.radius + 3 # Slightly larger for outline
        pygame.draw.circle(screen, self.outline_color, (int(x), int(y)), int(outline_radius), width=3)

        # Draw logo on top
        rect = self.logo_surface.get_rect(center=(x, y))
        screen.blit(self.logo_surface, rect)

    def take_hit(self, dmg=1):
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


class Pickup:
    """
    Objet au sol qu'un orb peut ramasser.
    kind: 'saw', 'heart', etc.
    """
    def __init__(self, kind, img_surface, pos, space):
        self.kind = kind
        self.sprite = pygame.transform.smoothscale(img_surface, (40, 40))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pos
        shape = pymunk.Circle(body, 20)
        shape.collision_type = 3
        shape.pickup_ref = self
        space.add(body, shape)
        self.body, self.shape = body, shape
        self.alive = True

    def draw(self, screen, offset=(0, 0)):
        if not self.alive:
            return
        x, y = self.body.position
        rect = self.sprite.get_rect(center=(x + offset[0], y + offset[1]))
        screen.blit(self.sprite, rect)

    def destroy(self, space):
        self.alive = False
        space.remove(self.body, self.shape)

class Saw:
    """
    Scie attachée (centrée) sur son owner. Rayon > orb → dépasse visuellement.
    """
    def __init__(self, img_surface, owner_orb, space,
                 scale_px=150, omega_deg=720):
        self.owner = owner_orb
        self.angle = 0
        self.omega = omega_deg
        self.alive = True

        self.sprite_orig = pygame.transform.smoothscale(img_surface,
                                                        (scale_px, scale_px))
        self.sprite = self.sprite_orig

        r = scale_px // 2
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = owner_orb.body.position
        shape = pymunk.Circle(body, r)
        shape.collision_type = 2
        shape.saw_ref = self
        space.add(body, shape)
        self.body, self.shape = body, shape

    def update(self, dt):
        # tourne en place, suit l'orb
        self.angle += self.omega * dt
        self.body.position = self.owner.body.position
        self.sprite = pygame.transform.rotate(self.sprite_orig, -self.angle)

    def draw(self, screen, offset=(0, 0)):
        if not self.alive:
            return
        x, y = self.body.position
        rect = self.sprite.get_rect(center=(x + offset[0], y + offset[1]))
        screen.blit(self.sprite, rect)

    def destroy(self, space):
        self.alive = False
        space.remove(self.body, self.shape)
        # on pourrait déclencher un petit effet ici