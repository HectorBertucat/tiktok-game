import random
import math

class Camera:
    def __init__(self):
        self.offset = (0.0, 0.0)
        self.shake_amount = 0.0
        self.shake_timer = 0.0

    def shake(self, intensity: float, duration: float):
        """
        Initiates a camera shake.
        :param intensity: The maximum displacement of the shake.
        :param duration: The duration of the shake in seconds.
        """
        self.shake_amount = intensity
        self.shake_timer = duration

    def update(self, dt: float):
        """
        Updates the camera shake effect.
        Call this once per frame.
        :param dt: Delta time in seconds for the current frame.
        """
        if self.shake_timer > 0:
            self.shake_timer -= dt
            if self.shake_timer <= 0:
                self.shake_amount = 0.0
                self.offset = (0.0, 0.0)
            else:
                # Calculate random offset
                offset_x = random.uniform(-self.shake_amount, self.shake_amount)
                offset_y = random.uniform(-self.shake_amount, self.shake_amount)
                self.offset = (offset_x, offset_y)
        else:
            # Ensure offset is reset if timer was already zero or just expired
            self.offset = (0.0, 0.0)


    def get_render_offset(self) -> tuple[float, float]:
        """
        Returns the current camera offset to be applied to rendering.
        """
        return self.offset
