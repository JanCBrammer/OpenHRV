from PySide6.QtCore import QObject, Signal, QTimer
from random import randrange


class MockBluetoothAddress:
    def toString(self):
        return "31:41:59:26:53:58"


class MockSensor:
    def name(self):
        return "MockSensor"

    def address(self):
        return MockBluetoothAddress()


class MockSensorScanner(QObject):
    sensor_update = Signal(object)
    status_update = Signal(str)

    def scan(self):
        polar_sensors = [MockSensor()]
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
            f"Connecting to sensor at {sensor.address().toString()}."
        )
        self.timer.start()

    def disconnect_client(self):
        self.status_update.emit("Disconnecting from sensor.")
        self.timer.stop()

    def simulate_ibi(self):
        self.ibi_update.emit(randrange(700, 1400))


if __name__ == "__main__":
    # Mock classes need to replace their mocked counterparts in namespace before the latter are imported elsewhere
    # (https://stackoverflow.com/questions/3765222/monkey-patch-python-class).
    import sensor

    sensor.SensorClient = MockSensorClient
    sensor.SensorScanner = MockSensorScanner
    from openhrv.app import main

    main()
