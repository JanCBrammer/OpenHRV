import statistics
import math
from collections import deque
from itertools import islice
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtBluetooth import QBluetoothDeviceInfo
from openhrv.utils import get_sensor_address, sign, NamedSignal
from openhrv.config import (
    tick_to_breathing_rate,
    HRV_BUFFER_SIZE,
    IBI_BUFFER_SIZE,
    MAX_BREATHING_RATE,
    MIN_IBI,
    MAX_IBI,
    IBI_MEDIAN_WINDOW,
    MIN_HRV_TARGET,
    MAX_HRV_TARGET,
    EWMA_WEIGHT_CURRENT_SAMPLE,
)


class Model(QObject):
    ibis_buffer_update = Signal(NamedSignal)
    hrv_update = Signal(NamedSignal)
    addresses_update = Signal(NamedSignal)
    pacer_rate_update = Signal(NamedSignal)
    hrv_target_update = Signal(NamedSignal)

    def __init__(self):
        super().__init__()
        # Once a bounded length deque is full, when new items are added,
        # a corresponding number of items are discarded from the opposite end.
        self.ibis_buffer: deque[int] = deque([1000] * IBI_BUFFER_SIZE, IBI_BUFFER_SIZE)
        self.ibis_seconds: deque[float] = deque(
            map(float, range(-IBI_BUFFER_SIZE, 1)), IBI_BUFFER_SIZE
        )
        self.hrv_buffer: deque[float] = deque([-1] * HRV_BUFFER_SIZE, HRV_BUFFER_SIZE)
        self.hrv_seconds: deque[float] = deque(
            map(float, range(-HRV_BUFFER_SIZE, 1)), HRV_BUFFER_SIZE
        )

        # Exponentially Weighted Moving Average:
        # - https://en.wikipedia.org/wiki/Moving_average#Exponential_moving_average
        # - https://en.wikipedia.org/wiki/Exponential_smoothing
        # - http://nestedsoftware.com/2018/04/04/exponential-moving-average-on-streaming-data-4hhl.24876.html
        self.ewma_hrv: float = 1.0
        self.sensors: list[QBluetoothDeviceInfo] = []
        self.breathing_rate: float = float(MAX_BREATHING_RATE)
        self.hrv_target: int = math.ceil((MIN_HRV_TARGET + MAX_HRV_TARGET) / 2)
        self._last_ibi_phase: int = -1
        self._last_ibi_extreme: int = 0
        self._duration_current_phase: int = 0

    @Slot(int)
    def update_ibis_buffer(self, ibi: int):
        validated_ibi = self.validate_ibi(ibi)
        self.update_ibis_seconds(validated_ibi / 1000)
        self.ibis_buffer.append(validated_ibi)
        self.ibis_buffer_update.emit(
            NamedSignal("InterBeatInterval", (self.ibis_seconds, self.ibis_buffer))
        )
        self.compute_local_hrv()

    @Slot(int)
    def update_breathing_rate(self, breathing_tick: int):
        self.breathing_rate = tick_to_breathing_rate(breathing_tick)
        self.pacer_rate_update.emit(NamedSignal("PacerRate", self.breathing_rate))

    @Slot(int)
    def update_hrv_target(self, hrv_target: int):
        self.hrv_target = hrv_target
        self.hrv_target_update.emit(NamedSignal("HrvTarget", hrv_target))

    @Slot(object)
    def update_sensors(self, sensors: list[QBluetoothDeviceInfo]):
        self.sensors = sensors
        self.addresses_update.emit(
            NamedSignal(
                "Sensors", [f"{s.name()}, {get_sensor_address(s)}" for s in sensors]
            )
        )

    def validate_ibi(self, ibi: int) -> int:
        validated_ibi: int = ibi
        if ibi < MIN_IBI or ibi > MAX_IBI:
            median_ibi: int = math.ceil(
                statistics.median(
                    islice(
                        self.ibis_buffer,
                        len(self.ibis_buffer) - IBI_MEDIAN_WINDOW,
                        None,
                    )
                )
            )
            if median_ibi < MIN_IBI:
                validated_ibi = MIN_IBI
            elif median_ibi > MAX_IBI:
                validated_ibi = MAX_IBI
            else:
                validated_ibi = median_ibi
            print(f"Correcting outlier IBI {ibi} to {validated_ibi}")

        return validated_ibi

    def validate_hrv(self, hrv: int) -> int:
        validated_hrv: int = hrv
        if hrv > MAX_HRV_TARGET:
            validated_hrv = min(math.ceil(self.ewma_hrv), MAX_HRV_TARGET)
            print(f"Correcting outlier HRV {hrv} to {validated_hrv}")

        return validated_hrv

    def compute_local_hrv(self):
        """https://doi.org/10.1038/s41598-019-44201-7 (Figure 2)"""
        self._duration_current_phase += self.ibis_buffer[-1]
        # 1: IBI rises, -1: IBI falls, 0: IBI constant
        current_ibi_phase: int = sign(self.ibis_buffer[-1] - self.ibis_buffer[-2])
        if current_ibi_phase == 0:
            return
        if current_ibi_phase == self._last_ibi_phase:
            return

        current_ibi_extreme: int = self.ibis_buffer[-2]
        local_hrv: int = abs(self._last_ibi_extreme - current_ibi_extreme)
        self.update_hrv_buffer(local_hrv)

        seconds_current_phase: float = self._duration_current_phase / 1000
        self.update_hrv_seconds(seconds_current_phase)
        self._duration_current_phase = 0

        self._last_ibi_extreme = current_ibi_extreme
        self._last_ibi_phase = current_ibi_phase

    def update_hrv_buffer(self, local_hrv: int):
        self.ewma_hrv = (
            EWMA_WEIGHT_CURRENT_SAMPLE * self.validate_hrv(local_hrv)
            + (1 - EWMA_WEIGHT_CURRENT_SAMPLE) * self.ewma_hrv
        )

        self.hrv_buffer.append(self.ewma_hrv)
        self.hrv_update.emit(
            NamedSignal("HeartRateVariability", (self.hrv_seconds, self.hrv_buffer))
        )

    def update_ibis_seconds(self, seconds: float):
        self.ibis_seconds = deque(
            [i - seconds for i in self.ibis_seconds], IBI_BUFFER_SIZE
        )
        self.ibis_seconds.append(0.0)

    def update_hrv_seconds(self, seconds: float):
        self.hrv_seconds = deque(
            [i - seconds for i in self.hrv_seconds], HRV_BUFFER_SIZE
        )
        self.hrv_seconds.append(0.0)
