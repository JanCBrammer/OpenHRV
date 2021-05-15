import numpy as np
import time
from PySide6.QtCore import QTimer, QObject


class Pacer(QObject):

    def __init__(self, model):
        super().__init__()

        self.model = model
        self.timer = QTimer()

        self.refresh_freq = 8
        self.refresh_period = 1 / self.refresh_freq
        self.theta = np.linspace(0, 2 * np.pi, 75)
        self.cos_theta = np.cos(self.theta)
        self.sin_theta = np.sin(self.theta)

    def breathing_pattern(self, t):
        return 0.5 + 0.5 * np.sin(2 * np.pi * self.model.breathing_rate / 60 * t)    # scale such that amplitude fluctuates in [0, 1]

    def start(self):
        self.timer.timeout.connect(self.update_pacer)
        self.timer.setInterval(self.refresh_period * 1000)
        self.timer.start()

    def update_pacer(self):
        """Update radius of pacer disc.

        Make current disk radius a function of real time (i.e., don't
        precompute radii with fixed time interval) in order to compensate for
        jitter or delay in QTimer calls.
        """
        t = time.time()
        radius = self.breathing_pattern(t)
        x = radius * self.cos_theta
        y = radius * self.sin_theta
        self.model.pacer_coordinates = (x, y)
