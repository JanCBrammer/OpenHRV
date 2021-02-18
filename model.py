from config import MEANHRV_BUFFER_SIZE, HRV_BUFFER_SIZE, IBI_BUFFER_SIZE
from PySide2.QtCore import QObject, Signal, Slot, Property
import numpy as np
from utils import find_indices_to_average


class Model(QObject):

    # Signals are tuples, with as first element the Redis channel name, and
    # value as second element.
    ibis_buffer_update = Signal(tuple)    # tuple(string, np.ndarray)
    mean_hrv_update = Signal(tuple)    # tuple(string, np.ndarray)
    mac_addresses_update = Signal(tuple)    # tuple(string, list)
    pacer_disk_update = Signal(tuple)    # tuple(string, list)
    pacer_rate_update = Signal(tuple)    # tuple(string, float)
    hrv_target_update = Signal(tuple)    # tuple(string, int)
    biofeedback_update = Signal(tuple)    # tuple(string, float)

    def __init__(self):
        super().__init__()

        self._ibis_buffer = np.array([1000] * IBI_BUFFER_SIZE, dtype=int)
        self._ibis_seconds = np.arange(-IBI_BUFFER_SIZE, 0, dtype=float)
        self._hrv_buffer = np.ones(HRV_BUFFER_SIZE, dtype=int)
        self._mean_hrv_buffer = np.ones(MEANHRV_BUFFER_SIZE, dtype=int)
        self._mean_hrv_seconds = np.arange(-MEANHRV_BUFFER_SIZE, 0, dtype=float)
        self._current_ibi_phase = -1
        self._last_ibi_phase = -1
        self._last_ibi_extreme = 0
        self._mac_addresses = []
        self._breathing_rate = 6.
        self._hrv_mean_window = 15
        self._hrv_target = 200
        self._duration_current_phase = 0

    @Property(object)
    def ibis_buffer(self):
        return self._ibis_buffer

    @Slot(object)
    def set_ibis_buffer(self, value):
        self._ibis_buffer = np.roll(self._ibis_buffer, -1)
        self._ibis_buffer[-1] = value
        self._ibis_seconds = self._ibis_seconds - value / 1000
        self._ibis_seconds = np.roll(self._ibis_seconds, -1)
        self._ibis_seconds[-1] = -value / 1000
        self.ibis_buffer_update.emit(("ibi", self.ibis_buffer))
        self.compute_local_hrv()

    def compute_local_hrv(self):
        self._duration_current_phase += self._ibis_buffer[-1]
        current_ibi_phase = np.sign(self._ibis_buffer[-1] - self._ibis_buffer[-2])    # 1: IBI rises, -1: IBI falls, 0: IBI constant
        if current_ibi_phase == 0:
            return
        if current_ibi_phase == self._last_ibi_phase:
            return

        current_ibi_extreme = self._ibis_buffer[-2]
        local_hrv = abs(self._last_ibi_extreme - current_ibi_extreme)
        self.hrv_buffer = local_hrv
        # potentially enforce constraints on local power here
        print(f"Local HRV: {local_hrv}")

        seconds_current_phase = np.floor(self._duration_current_phase / 1000)
        self._mean_hrv_seconds = self._mean_hrv_seconds - seconds_current_phase
        self._mean_hrv_seconds = np.roll(self._mean_hrv_seconds, -1)
        self._mean_hrv_seconds[-1] = -seconds_current_phase
        self._duration_current_phase = 0

        self._last_ibi_extreme = current_ibi_extreme
        self._last_ibi_phase = current_ibi_phase

    def compute_biofeedback(self, x):
        """Hill equation.

        Biofeedback target (value of x at which half of the maximum reward is
        obtained) is equivalent to K parameter.

        Parameters
        ----------
        x : float
            Input value.

        Returns
        -------
        y : float
            Biofeedback value in the range [0, 1].

        References
        ----------
        [1] https://www.physiologyweb.com/calculators/hill_equation_interactive_graph.html
        [2] https://en.wikipedia.org/wiki/Hill_equation_(biochemistry)
        """
        K = self.hrv_target * .5    # divide by half to make K the value at which maximum reward is obtained
        Vmax = 1    # Upper limit of y values
        n = 3    # Hill coefficient, determines steepness of curve
        y = Vmax * x**n / (K**n + x**n)

        print(f"Biofeedback score: {y}")
        self.biofeedback_update.emit(("biofeedback", y))

    @property
    def hrv_buffer(self):
        return self._hrv_buffer

    @hrv_buffer.setter
    def hrv_buffer(self, value):
        self._hrv_buffer = np.roll(self._hrv_buffer, -1)
        self._hrv_buffer[-1] = value
        average_idcs = find_indices_to_average(self._ibis_seconds[-HRV_BUFFER_SIZE:],
                                               self._hrv_mean_window)
        self.mean_hrv_buffer = self._hrv_buffer[average_idcs].mean()

    @property
    def mean_hrv_buffer(self):
        return self._mean_hrv_buffer

    @mean_hrv_buffer.setter
    def mean_hrv_buffer(self, value):
        self.compute_biofeedback(value)
        self._mean_hrv_buffer = np.roll(self._mean_hrv_buffer, -1)
        self._mean_hrv_buffer[-1] = value
        self.mean_hrv_update.emit(("meanhrv", self._mean_hrv_buffer))
        print(f"Mean HRV: {value}")

    @property
    def ibis_seconds(self):
        return self._ibis_seconds

    @ibis_seconds.setter
    def ibis_seconds(self, value):
        self._ibis_seconds = value

    @property
    def mean_hrv_seconds(self):
        return self._mean_hrv_seconds

    @mean_hrv_seconds.setter
    def mean_hrv_seconds(self, value):
        self._mean_hrv_seconds = value

    @Property(float)
    def breathing_rate(self):
        return self._breathing_rate

    @Slot(float)
    def set_breathing_rate(self, value):
        self._breathing_rate = (value + 8) / 2    # force values into [4, 7], step .5
        self.pacer_rate_update.emit(("pacerrate", self._breathing_rate))

    @Property(int)
    def hrv_target(self):
        return self._hrv_target

    @Slot(int)
    def set_hrv_target(self, value):
        self._hrv_target = value
        self.hrv_target_update.emit(("hrvtarget", value))

    @property
    def pacer_coordinates(self):
        return self._pacer_coordinates

    @pacer_coordinates.setter
    def pacer_coordinates(self, value):
        self._pacer_coordinates = value
        self.pacer_disk_update.emit(("pacercoordinates", value))

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
        self.mac_addresses_update.emit(("sensormacs", self._mac_addresses))
