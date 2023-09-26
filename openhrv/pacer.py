import math
import time
from PySide6.QtCore import QObject


class Pacer(QObject):
    def __init__(self):
        super().__init__()

        n_samples: int = 40
        increment: float = 2 * math.pi / n_samples
        theta: list[float] = [i * increment for i in range(n_samples + 1)]
        self.cos_theta: list[float] = list(map(math.cos, theta))
        self.sin_theta: list[float] = list(map(math.sin, theta))

    def breathing_pattern(self, breathing_rate: float, time: float) -> float:
        """Returns radius of pacer disk.

        Radius is modulated according to sinusoidal breathing pattern
        and scaled between 0 and 1.
        """
        return 0.5 + 0.5 * math.sin(2 * math.pi * breathing_rate / 60 * time)

    def update(self, breathing_rate: float) -> tuple[list[float], list[float]]:
        """Update radius of pacer disc.

        Make current disk radius a function of real time (i.e., don't
        precompute radii with fixed time interval) in order to compensate for
        jitter or delay in QTimer calls.
        """
        radius = self.breathing_pattern(breathing_rate, time.time())
        x: list[float] = [i * radius for i in self.cos_theta]
        y: list[float] = [i * radius for i in self.sin_theta]

        return (x, y)
