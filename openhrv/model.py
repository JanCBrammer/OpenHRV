import statistics
import math
from collections import namedtuple, deque
from itertools import islice
from PySide6.QtCore import QObject, Signal, Slot
from openhrv.utils import compute_mean_hrv, get_sensor_address, sign
from openhrv.config import (
    tick_to_breathing_rate,
    MEANHRV_BUFFER_SIZE,
    HRV_BUFFER_SIZE,
    IBI_BUFFER_SIZE,
    MAX_BREATHING_RATE,
    MIN_IBI,
    MAX_IBI,
    IBI_MEDIAN_WINDOW,
    MIN_HRV_TARGET,
    MAX_HRV_TARGET,
)


NamedSignal = namedtuple("NamedSignal", "name value")


class Model(QObject):
    ibis_buffer_update = Signal(NamedSignal)
    mean_hrv_update = Signal(NamedSignal)
    addresses_update = Signal(NamedSignal)
    pacer_rate_update = Signal(NamedSignal)
    hrv_target_update = Signal(NamedSignal)

    def __init__(self):
        super().__init__()
        # Once a bounded length deque is full, when new items are added,
        # a corresponding number of items are discarded from the opposite end.
        self.ibis_buffer: deque[int] = deque([1000] * IBI_BUFFER_SIZE, IBI_BUFFER_SIZE)
        self.ibis_seconds: deque[float] = deque(
            map(float, range(-IBI_BUFFER_SIZE, 0)), IBI_BUFFER_SIZE
        )
        self.mean_hrv_buffer: deque[float] = deque(
            [-1] * MEANHRV_BUFFER_SIZE, MEANHRV_BUFFER_SIZE
        )
        self.mean_hrv_seconds: deque[float] = deque(
            map(float, range(-MEANHRV_BUFFER_SIZE, 0)), MEANHRV_BUFFER_SIZE
        )
        self._hrv_buffer: deque[int] = deque([-1] * HRV_BUFFER_SIZE, HRV_BUFFER_SIZE)

        self.sensors = []
        self.breathing_rate = float(MAX_BREATHING_RATE)
        self.hrv_target = int((MIN_HRV_TARGET + MAX_HRV_TARGET) / 2)
        self._last_ibi_phase = -1
        self._last_ibi_extreme = 0
        self._duration_current_phase = 0

    @Slot(object)
    def update_ibis_buffer(self, value):
        self.update_ibis_seconds(value)
        self.ibis_buffer.append(self.validate_ibi(value))
        self.ibis_buffer_update.emit(
            NamedSignal("InterBeatInterval", (self.ibis_seconds, self.ibis_buffer))
        )
        self.compute_local_hrv()

    @Slot(float)
    def update_breathing_rate(self, value):
        self.breathing_rate = tick_to_breathing_rate(value)
        self.pacer_rate_update.emit(NamedSignal("PacerRate", self.breathing_rate))

    @Slot(int)
    def update_hrv_target(self, value):
        self.hrv_target = value
        self.hrv_target_update.emit(NamedSignal("HrvTarget", value))

    @Slot(object)
    def update_sensors(self, sensors):
        self.sensors = sensors
        self.addresses_update.emit(
            NamedSignal(
                "Sensors", [f"{s.name()}, {get_sensor_address(s)}" for s in sensors]
            )
        )

    def validate_ibi(self, value):
        if value < MIN_IBI or value > MAX_IBI:
            print(f"Correcting invalid IBI: {value}")
            return statistics.median(
                islice(
                    self.ibis_buffer, len(self.ibis_buffer) - IBI_MEDIAN_WINDOW, None
                )
            )
        return value

    def compute_local_hrv(self):
        self._duration_current_phase += self.ibis_buffer[-1]
        # 1: IBI rises, -1: IBI falls, 0: IBI constant
        current_ibi_phase = sign(self.ibis_buffer[-1] - self.ibis_buffer[-2])
        if current_ibi_phase == 0:
            return
        if current_ibi_phase == self._last_ibi_phase:
            return

        current_ibi_extreme = self.ibis_buffer[-2]
        local_hrv = abs(self._last_ibi_extreme - current_ibi_extreme)
        self.update_hrv_buffer(local_hrv)

        seconds_current_phase = math.ceil(self._duration_current_phase / 1000)
        self.update_mean_hrv_seconds(seconds_current_phase)
        self._duration_current_phase = 0

        self._last_ibi_extreme = current_ibi_extreme
        self._last_ibi_phase = current_ibi_phase

    def update_hrv_buffer(self, value):
        if not self._hrv_buffer[0]:
            return  # wait until buffer is full
        threshold = max(map(abs, self._hrv_buffer)) * 4
        if value > threshold:
            print(f"Correcting outlier HRV {value} to {threshold}")
            value = threshold
        self._hrv_buffer.append(value)
        self.update_mean_hrv_buffer()

    def update_mean_hrv_buffer(self):
        self.mean_hrv_buffer.append(
            compute_mean_hrv(self.ibis_seconds, self._hrv_buffer)
        )
        self.mean_hrv_update.emit(
            NamedSignal("MeanHrv", (self.mean_hrv_seconds, self.mean_hrv_buffer))
        )

    def update_ibis_seconds(self, value):
        self.ibis_seconds = deque(
            [i - value / 1000 for i in self.ibis_seconds], IBI_BUFFER_SIZE
        )
        self.ibis_seconds.append(0.0)

    def update_mean_hrv_seconds(self, value):
        self.mean_hrv_seconds = deque(
            [i - value for i in self.mean_hrv_seconds], MEANHRV_BUFFER_SIZE
        )
        self.mean_hrv_seconds.append(0.0)
