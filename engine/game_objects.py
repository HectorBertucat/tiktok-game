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

    def __post_init__(self):
        self.hp = self.max_hp

    def draw(self, screen, offset=(0, 0)):
        x = self.body.position.x + offset[0]
        y = self.body.position.y + offset[1]
        rect = self.logo_surface.get_rect(center=(x, y))
        screen.blit(self.logo_surface, rect)

    def take_hit(self, dmg=1):
        self.hp = max(0, self.hp - dmg)

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


class Saw:
    def __init__(self, img_surface: pygame.Surface, owner_orb, space,
                 orbit_radius=100, omega_deg=720):
        self.owner = owner_orb
        self.angle = random.uniform(0, 360)
        self.omega = omega_deg                 # °/s
        self.r_orbit = orbit_radius
        self.alive = True

        # sprite préparé 64×64
        self.sprite_orig = pygame.transform.smoothscale(img_surface, (64, 64))
        self.sprite = self.sprite_orig

        # corps « kinematic » car on pilote nous-mêmes la position
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = owner_orb.body.position  # sera déplacé au 1ᵉʳ update
        shape = pymunk.Circle(body, 32)
        shape.collision_type = 2      # 1 = orb, 2 = saw
        shape.saw_ref = self

        space.add(body, shape)
        self.body, self.shape = body, shape

    # --- logique -------
    def update(self, dt):
        self.angle += self.omega * dt
        a = math.radians(self.angle)
        ox, oy = self.owner.body.position
        self.body.position = (ox + self.r_orbit * math.cos(a),
                              oy + self.r_orbit * math.sin(a))
        # rotation visuelle inverse (pour paraître tourner)
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