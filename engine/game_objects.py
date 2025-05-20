# engine/game_objects.py
from dataclasses import dataclass, field
import random
import pygame, pymunk, math

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

    def draw(self, screen):
        x, y = self.body.position
        radius = int(self.shape.radius)
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