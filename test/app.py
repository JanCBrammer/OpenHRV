import math
import time
import uuid
from random import randint
from PySide6.QtCore import QObject, Signal, QTimer
from openhrv.utils import get_sensor_address


class MockBluetoothMac:
    def __init__(self, mac):
        self._mac = mac

    def toString(self):
        return self._mac


class MockBluetoothUuid:
    def __init__(self, uuid):
        self._uuid = uuid

    def toString(self):
        return f"{self._uuid}"


class MockSensor:
    def __init__(self):
        self._mac = MockBluetoothMac(
            ":".join([f"{randint(0, 255):02x}" for _ in range(6)])
        )
        self._uuid = MockBluetoothUuid(uuid.uuid4())
        self._name = "MockSensor"

    def name(self):
        return self._name

    def address(self):
        return self._mac

    def deviceUuid(self):
        return self._uuid


class MockSensorScanner(QObject):
    sensor_update = Signal(object)
    status_update = Signal(str)

    def scan(self):
        polar_sensors = [MockSensor() for _ in range(3)]
        self.sensor_update.emit(polar_sensors)
        self.status_update.emit(f"Found {len(polar_sensors)} sensor(s).")


class MockSensorClient(QObject):
    ibi_update = Signal(object)
    status_update = Signal(str)

    def __init__(self):
        super().__init__()
        # Polar sensor emits a (package of) IBI(s) about every second.
        # Here we "emit" / simulate IBI(s) in quicker succession in order to push the rendering.
        self.mean_ibi = 300
        self.timer = QTimer()
        self.timer.setInterval(self.mean_ibi)
        self.timer.timeout.connect(self.simulate_ibi)

    def connect_client(self, sensor):
        self.status_update.emit(
            f"Connecting to sensor at {get_sensor_address(sensor)}."
        )
        self.timer.start()

    def disconnect_client(self):
        self.status_update.emit("Disconnecting from sensor.")
        self.timer.stop()

    def simulate_ibi(self):
        # IBIs fluctuate at a rate of `breathing_rate`
        # in a sinusoidal pattern around `mean_ibi`,
        # in a range of `range_ibi`.
        breathing_rate = 6
        range_ibi = 40  # HRV must settle at this value
        ibi = self.mean_ibi + (range_ibi / 2) * math.sin(
            2 * math.pi * breathing_rate / 60 * time.time()
        )
        self.ibi_update.emit(ibi)


def main():
    """Mock sensor classes.

    Mock classes need to replace their mocked counterparts in namespace before
    the latter are imported elsewhere:
    https://stackoverflow.com/questions/3765222/monkey-patch-python-class
    """
    from openhrv import sensor  # noqa

    sensor.SensorClient = MockSensorClient
    sensor.SensorScanner = MockSensorScanner

    from openhrv.app import main as mock_main  # noqa

    mock_main()


if __name__ == "__main__":
    main()
