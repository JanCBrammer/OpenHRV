from PySide6.QtCore import QObject, Signal, QByteArray
from PySide6.QtBluetooth import (QBluetoothDeviceDiscoveryAgent,
                                 QLowEnergyController, QLowEnergyService,
                                 QBluetoothUuid)
from math import ceil


class SensorScanner(QObject):

    sensor_update = Signal(object)
    status_update = Signal(str)

    def __init__(self):
        super().__init__()
        self.scanner = QBluetoothDeviceDiscoveryAgent()
        self.scanner.finished.connect(self._handle_scan_result)
        self.scanner.errorOccurred.connect(self._handle_scan_error)

    def scan(self):
        if self.scanner.isActive():
            self.status_update.emit("Already searching for sensors...")
            return
        self.status_update.emit("Searching for sensors...")
        self.scanner.start()

    def _handle_scan_result(self):
        polar_sensors = [d for d in self.scanner.discoveredDevices()
                         if "Polar" in str(d.name()) and d.rssi() < 0]    # TODO: comment why rssi needs to be negative
        if not polar_sensors:
            self.status_update.emit("Couldn't find sensors.")
            return
        self.sensor_update.emit(polar_sensors)
        self.status_update.emit(f"Found {len(polar_sensors)} sensor(s).")

    def _handle_scan_error(self, error):
        print(error)


class SensorClient(QObject):
    """
    Connect to a Polar sensor that acts as a Bluetooth server / peripheral.
    On Windows, the sensor must already be paired with the machine running
    OpenHRV. Pairing isn't implemented in Qt6.

    In Qt terminology client=central, server=peripheral.
    """
    ibi_update = Signal(object)
    status_update = Signal(str)

    def __init__(self):
        super().__init__()
        self.client = None
        self.hr_service = None
        self.hr_notification = None
        self.ENABLE_NOTIFICATION = QByteArray.fromHex(b"0100")
        self.DISABLE_NOTIFICATION = QByteArray.fromHex(b"0000")
        self.HR_SERVICE = QBluetoothUuid.ServiceClassUuid.HeartRate
        self.HR_CHARACTERISTIC = QBluetoothUuid.CharacteristicType.HeartRateMeasurement

    def connect_client(self, sensor):
        if self.client:
            print(f"Currently connected to sensor at {self.client.remoteAddress()}.")
            print("Please disconnect before (re-)connecting to (another) sensor.")
            print(self.client.state())
            return
        # self.status_update.emit(f"Connecting to sensor at {sensor.address().toString()}")
        print(f"Connecting to sensor at {sensor.address().toString()}.")
        self.client = QLowEnergyController.createCentral(sensor)
        self.client.errorOccurred.connect(self._catch_error)
        self.client.connected.connect(self._discover_services)
        self.client.discoveryFinished.connect(self._connect_hr_service)
        self.client.disconnected.connect(self._reset_connection)
        self.client.connectToDevice()

    def disconnect_client(self):
        if self.hr_notification and self.hr_service:
            if not self.hr_notification.isValid():
                return
            print("Unsubscribing from HR service.")
            self.hr_service.writeDescriptor(self.hr_notification, self.DISABLE_NOTIFICATION)
        if self.client:
            print(f"Disconnecting from sensor at {self.client.remoteAddress()}")
            self.client.disconnectFromDevice()

    def _discover_services(self):
        self.client.discoverServices()

    def _connect_hr_service(self):
        hr_service = [s for s in self.client.services() if s == self.HR_SERVICE]
        if not hr_service:
            print(f"Couldn't find HR service on {self.client.remoteAddress()}.")
            return
        self.hr_service = self.client.createServiceObject(*hr_service)
        if not self.hr_service:
            print(f"Couldn't establish connection to HR service on {self.client.remoteAddress()}.")
            return
        self.hr_service.stateChanged.connect(self._start_hr_notification)
        self.hr_service.characteristicChanged.connect(self._data_handler)
        self.hr_service.discoverDetails()

    def _start_hr_notification(self, state):
        if state != QLowEnergyService.RemoteServiceDiscovered:
            return
        hr_char = self.hr_service.characteristic(self.HR_CHARACTERISTIC)
        if not hr_char.isValid():
            print("No HR characterictic found.")
        self.hr_notification = hr_char.descriptor(QBluetoothUuid.DescriptorType.ClientCharacteristicConfiguration)
        if not self.hr_notification.isValid():
            print("HR characteristic is invalid.")
        self.hr_service.writeDescriptor(self.hr_notification, self.ENABLE_NOTIFICATION)

    def _reset_connection(self):
        print(f"Discarding sensor at {self.client.remoteAddress()}")
        self._remove_service()
        self._remove_client()

    def _remove_service(self):
        try:
            self.hr_service.deleteLater()
        except Exception as e:
            print(f"Couldn't remove service: {e}")
        finally:
            self.hr_service = None
            self.hr_notification = None

    def _remove_client(self):
        try:
            self.client.disconnected.disconnect()
            self.client.deleteLater()
        except Exception as e:
            print(f"Couldn't remove client: {e}")
        finally:
            self.client = None

    def _catch_error(self, error):
        print(f"An error occurred: {error}")
        self._reset_connection()

    def _data_handler(self, characteristic, data):    # characteristic is unused but mandatory argument
        """
        `data` is formatted according to the
        "GATT Characteristic and Object Type 0x2A37 Heart Rate Measurement"
        which is one of the three characteristics included in the
        "GATT Service 0x180D Heart Rate".

        `data` can include the following bytes:
        - flags
            Always present.
            - bit 0: HR format (uint8 vs. uint16)
            - bit 1, 2: sensor contact status
            - bit 3: energy expenditure status
            - bit 4: RR interval status
        - HR
            Encoded by one or two bytes depending on flags/bit0. One byte is
            always present (uint8). Two bytes (uint16) are necessary to
            represent HR > 255.
        - energy expenditure
            Encoded by 2 bytes. Only present if flags/bit3.
        - inter-beat-intervals (IBIs)
            One IBI is encoded by 2 consecutive bytes. Up to 18 bytes depending
            on presence of uint16 HR format and energy expenditure.
        """
        data = data.data()    # convert from QByteArray to Python bytes

        byte0 = data[0]
        uint8_format = (byte0 & 1) == 0
        energy_expenditure = ((byte0 >> 3) & 1) == 1
        rr_interval = ((byte0 >> 4) & 1) == 1

        if not rr_interval:
            return

        first_rr_byte = 2
        if uint8_format:
            # hr = data[1]
            pass
        else:
            # hr = (data[2] << 8) | data[1] # uint16
            first_rr_byte += 1
        if energy_expenditure:
            # ee = (data[first_rr_byte + 1] << 8) | data[first_rr_byte]
            first_rr_byte += 2

        for i in range(first_rr_byte, len(data), 2):
            ibi = (data[i + 1] << 8) | data[i]
            # Polar H7, H9, and H10 record IBIs in 1/1024 seconds format.
            # Convert 1/1024 sec format to milliseconds.
            # TODO: move conversion to model and only convert if sensor doesn't
            # transmit data in milliseconds.
            ibi = ceil(ibi / 1024 * 1000)
            self.ibi_update.emit(ibi)
