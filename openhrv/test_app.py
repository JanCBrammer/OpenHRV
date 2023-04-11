from PySide6.QtCore import QObject, Signal, QTimer
from random import randrange, randint
import uuid
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
    status_update = Signal(object)

    def __init__(self):
        super().__init__()

        self.timer = QTimer()
        self.timer.setInterval(1000)
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
        self.ibi_update.emit(randrange(700, 1400))


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
