# engine/game_objects.py
from dataclasses import dataclass, field
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