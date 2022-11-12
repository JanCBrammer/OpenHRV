from config import (tick_to_breathing_rate, MEANHRV_BUFFER_SIZE,
                    HRV_BUFFER_SIZE, IBI_BUFFER_SIZE, MAX_BREATHING_RATE,
                    HRV_MEAN_WINDOW)
from PySide6.QtCore import QObject, Signal, Slot
import numpy as np
from utils import find_indices_to_average


class Model(QObject):

    # Signal format is (name, value).
    ibis_buffer_update = Signal(tuple)    # tuple(string, tuple(np.array, np.array))
    mean_hrv_update = Signal(tuple)    # tuple(string, tuple(np.array, np.array))
    addresses_update = Signal(tuple)    # tuple(string, list)
    pacer_rate_update = Signal(tuple)    # tuple(string, float)
    hrv_target_update = Signal(tuple)    # tuple(string, int)

    def __init__(self):
        super().__init__()

        self.ibis_buffer = np.full(IBI_BUFFER_SIZE, 1000, dtype=int)
        self.ibis_seconds = np.arange(-IBI_BUFFER_SIZE, 0, dtype=float)
        self.mean_hrv_buffer = np.full(MEANHRV_BUFFER_SIZE, -1, dtype=int)
        self.mean_hrv_seconds = np.arange(-MEANHRV_BUFFER_SIZE, 0, dtype=float)
        self.sensors = []
        self.breathing_rate = float(MAX_BREATHING_RATE)
        self.hrv_target = 200

        self._hrv_buffer = np.full(HRV_BUFFER_SIZE, -1, dtype=int)
        self._last_ibi_phase = -1
        self._last_ibi_extreme = 0
        self._duration_current_phase = 0

    @Slot(object)
    def update_ibis_buffer(self, value):
        self.update_ibis_seconds(value)
        self.ibis_buffer = np.roll(self.ibis_buffer, -1)
        self.ibis_buffer[-1] = self.validate_ibi(value)
        self.ibis_buffer_update.emit(("InterBeatInterval", (self.ibis_seconds, self.ibis_buffer)))
        self.compute_local_hrv()

    @Slot(float)
    def update_breathing_rate(self, value):
        self.breathing_rate = tick_to_breathing_rate(value)
        self.pacer_rate_update.emit(("PacerRate", self.breathing_rate))

    @Slot(int)
    def update_hrv_target(self, value):
        self.hrv_target = value
        self.hrv_target_update.emit(("HrvTarget", value))

    @Slot(object)
    def update_sensors(self, sensors):
        self.sensors = sensors
        self.addresses_update.emit(("Sensors",
                                    [f"{s.name()}, {s.address().toString()}"
                                     for s in sensors]))

    def validate_ibi(self, value):
        """ Replace IBIs corresponding to instantaneous heart rate of more than
        220, or less than 30 beats per minute with local median."""
        if value < 273 or value > 2000:
            print(f"Correcting invalid IBI: {value}")
            return np.median(self.ibis_buffer[-11:])
        return value

    def compute_local_hrv(self):
        self._duration_current_phase += self.ibis_buffer[-1]
        current_ibi_phase = np.sign(self.ibis_buffer[-1] - self.ibis_buffer[-2])    # 1: IBI rises, -1: IBI falls, 0: IBI constant
        if current_ibi_phase == 0:
            return
        if current_ibi_phase == self._last_ibi_phase:
            return

        current_ibi_extreme = self.ibis_buffer[-2]
        local_hrv = abs(self._last_ibi_extreme - current_ibi_extreme)
        self.update_hrv_buffer(local_hrv)

        seconds_current_phase = np.ceil(self._duration_current_phase / 1000)
        self.update_mean_hrv_seconds(seconds_current_phase)
        self._duration_current_phase = 0

        self._last_ibi_extreme = current_ibi_extreme
        self._last_ibi_phase = current_ibi_phase

    def update_hrv_buffer(self, value):
        if self._hrv_buffer[0] != -1:    # wait until buffer is full
            threshold = np.amax(self._hrv_buffer) * 4
            if value > threshold:    # correct hrv values that considerably exceed threshold
                print(f"Correcting outlier HRV {value} to {threshold}")
                value = threshold
        self._hrv_buffer = np.roll(self._hrv_buffer, -1)
        self._hrv_buffer[-1] = value
        average_idcs = find_indices_to_average(self.ibis_seconds[-HRV_BUFFER_SIZE:],
                                               HRV_MEAN_WINDOW)
        self.update_mean_hrv_buffer(self._hrv_buffer[average_idcs].mean())

    def update_mean_hrv_buffer(self, value):
        self.mean_hrv_buffer = np.roll(self.mean_hrv_buffer, -1)
        self.mean_hrv_buffer[-1] = value
        self.mean_hrv_update.emit(("MeanHrv", (self.mean_hrv_seconds,
                                               self.mean_hrv_buffer)))

    def update_ibis_seconds(self, value):
        self.ibis_seconds = self.ibis_seconds - value / 1000
        self.ibis_seconds = np.roll(self.ibis_seconds, -1)
        self.ibis_seconds[-1] = 0

    def update_mean_hrv_seconds(self, value):
        self.mean_hrv_seconds = self.mean_hrv_seconds - value
        self.mean_hrv_seconds = np.roll(self.mean_hrv_seconds, -1)
        self.mean_hrv_seconds[-1] = 0
