import redis
import numpy as np
from config import REDIS_HOST, REDIS_PORT
from PySide2.QtCore import QObject, Signal, Slot, Property
from functools import wraps


redis_host = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)


def publish_to_redis(func):
    @wraps(func)
    def publish_attribute(model, attribute):
        func(model, attribute)
        if isinstance(attribute, np.ndarray):
            attribute = float(attribute[-1])
        redis_host.set("custom_key", attribute)
    return publish_attribute


class Model(QObject):

    # Costum signals.
    ibis_buffer_update = Signal(object)
    hrv_buffer_update = Signal(object)
    mac_addresses_update = Signal(object)
    pacer_disk_update = Signal(object)
    pacer_rate_update = Signal(object)

    def __init__(self):
        super().__init__()

        self._ibis_buffer = np.ones(60, dtype=int) * 1000
        self._seconds = np.linspace(-sum(self._ibis_buffer) / 1000, 0, 60)
        self._hrv_buffer = np.ones(5, dtype=int)
        self._current_ibi_phase = -1
        self._last_ibi_phase = -1
        self._last_ibi_extreme = 0
        self._mac_addresses = []
        self._breathing_rate = 6

    @Property(object)
    def ibis_buffer(self):
        return self._ibis_buffer

    @Slot(object)
    def set_ibis_buffer(self, value):
        self._ibis_buffer = np.roll(self._ibis_buffer, -1)
        self._ibis_buffer[-1] = value
        self.compute_local_hrv()
        self._seconds = np.linspace(-sum(self._ibis_buffer) / 1000, 0,
                                    self._ibis_buffer.size)
        self.ibis_buffer_update.emit(self.ibis_buffer)

    def compute_local_hrv(self):
        current_ibi_phase = np.sign(self._ibis_buffer[-1] - self._ibis_buffer[-2])    # 1: IBI rises, -1: IBI falls, 0: IBI constant
        if current_ibi_phase == 0:
            return
        if current_ibi_phase != self._last_ibi_phase:

            current_ibi_extreme = self._ibis_buffer[-2]
            local_hrv = abs(self._last_ibi_extreme - current_ibi_extreme)

            # potentially enforce constraints on local power here
            print(f"Local hrv: {local_hrv}!")

            updated_hrv_buffer = self.hrv_buffer
            updated_hrv_buffer = np.roll(updated_hrv_buffer, -1)
            updated_hrv_buffer[-1] = local_hrv
            self.hrv_buffer = updated_hrv_buffer

            self._last_ibi_extreme = current_ibi_extreme
            self._last_ibi_phase = current_ibi_phase

    @property
    def hrv_buffer(self):
        return self._hrv_buffer

    @hrv_buffer.setter
    # @publish_to_redis
    def hrv_buffer(self, value):
        self._hrv_buffer = value
        self.hrv_buffer_update.emit(value)

    @property
    def seconds(self):
        return self._seconds

    @seconds.setter
    def seconds(self, value):
        self._seconds = value

    @Property(int)
    def breathing_rate(self):
        return self._breathing_rate

    @Slot(int)
    # @publish_to_redis
    def set_breathing_rate(self, value):
        self._breathing_rate = value
        self.pacer_rate_update.emit(value)

    @property
    def pacer_coordinates(self):
        return self._pacer_coordinates

    @pacer_coordinates.setter
    def pacer_coordinates(self, value):
        self._pacer_coordinates = value
        self.pacer_disk_update.emit(value)

    @property
    def current_ibi_phase(self):
        return self._current_ibi_phase

    @current_ibi_phase.setter
    def current_ibi_phase(self, value):
        self._current_ibi_phase = value

    @property
    def last_ibi_phase(self):
        return self._last_ibi_phase

    @last_ibi_phase.setter
    def last_ibi_phase(self, value):
        self._last_ibi_phase = value

    @property
    def last_ibi_extreme(self):
        return self._last_ibi_extreme

    @last_ibi_extreme.setter
    def last_ibi_extreme(self, value):
        self._last_ibi_extreme = value

    @Property(object)
    def mac_addresses(self):
        return self._mac_addresses

    @Slot(object)
    def set_mac_addresses(self, value):
        mac_addresses = [v.address for v in value]
        if not mac_addresses:
            mac_addresses = ["None found!"]
        self._mac_addresses = mac_addresses
        self.mac_addresses_update.emit(self._mac_addresses)
