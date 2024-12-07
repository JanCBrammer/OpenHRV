from PySide6.QtCore import QObject, Signal, QByteArray
from PySide6.QtBluetooth import (
    QBluetoothDeviceDiscoveryAgent,
    QLowEnergyController,
    QLowEnergyService,
    QLowEnergyCharacteristic,
    QBluetoothUuid,
    QBluetoothDeviceInfo,
    QLowEnergyDescriptor,
)
from math import ceil
from typing import Union
from openhrv.utils import get_sensor_address, get_sensor_remote_address
from openhrv.config import COMPATIBLE_SENSORS


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
            self.status_update.emit("Already searching for sensors.")
            return
        self.status_update.emit("Searching for sensors (this might take a while).")
        self.scanner.start()

    def _handle_scan_result(self):
        sensors: list[QBluetoothDeviceInfo] = [
            d
            for d in self.scanner.discoveredDevices()
            if (any(cs in d.name() for cs in COMPATIBLE_SENSORS)) and (d.rssi() <= 0)
        ]  # https://www.mokoblue.com/measures-of-bluetooth-rssi/
        if not sensors:
            self.status_update.emit("Couldn't find sensors.")
            return
        self.sensor_update.emit(sensors)
        self.status_update.emit(f"Found {len(sensors)} sensor(s).")

    def _handle_scan_error(self, error):
        print(error)


class SensorClient(QObject):
    """
    Connect to an ECG sensor that acts as a Bluetooth server / peripheral.
    On Windows, the sensor must already be paired with the machine running
    OpenHRV. Pairing isn't implemented in Qt6.

    In Qt terminology client=central, server=peripheral.
    """

    ibi_update = Signal(object)
    status_update = Signal(str)

    def __init__(self):
        super().__init__()
        self.client: Union[None, QLowEnergyController] = None
        self.hr_service: Union[None, QLowEnergyService] = None
        self.hr_notification: Union[None, QLowEnergyDescriptor] = None
        self.ENABLE_NOTIFICATION: QByteArray = QByteArray.fromHex(b"0100")
        self.DISABLE_NOTIFICATION: QByteArray = QByteArray.fromHex(b"0000")
        self.HR_SERVICE: QBluetoothUuid.ServiceClassUuid = (
            QBluetoothUuid.ServiceClassUuid.HeartRate
        )
        self.HR_CHARACTERISTIC: QBluetoothUuid.CharacteristicType = (
            QBluetoothUuid.CharacteristicType.HeartRateMeasurement
        )

    def _sensor_address(self):
        return get_sensor_remote_address(self.client)

    def connect_client(self, sensor: QBluetoothDeviceInfo):
        if self.client is not None:
            msg = (
                f"Currently connected to sensor at {self._sensor_address()}."
                " Please disconnect before (re-)connecting to (another) sensor."
            )
            self.status_update.emit(msg)
            return
        self.status_update.emit(
            f"Connecting to sensor at {get_sensor_address(sensor)} (this might take a while)."
        )
        self.client = QLowEnergyController.createCentral(sensor)
        self.client.errorOccurred.connect(self._catch_error)
        self.client.connected.connect(self._discover_services)
        self.client.discoveryFinished.connect(self._connect_hr_service)
        self.client.disconnected.connect(self._reset_connection)
        self.client.connectToDevice()

    def disconnect_client(self):
        if self.hr_notification is not None and self.hr_service is not None:
            if not self.hr_notification.isValid():
                return
            print("Unsubscribing from HR service.")
            self.hr_service.writeDescriptor(
                self.hr_notification, self.DISABLE_NOTIFICATION
            )
        if self.client is not None:
            self.status_update.emit(
                f"Disconnecting from sensor at {self._sensor_address()}."
            )
            self.client.disconnectFromDevice()

    def _discover_services(self):
        if self.client is not None:
            self.client.discoverServices()

    def _connect_hr_service(self):
        if self.client is None:
            return
        hr_service: list[QBluetoothUuid] = [
            s for s in self.client.services() if s == self.HR_SERVICE
        ]
        if not hr_service:
            print(f"Couldn't find HR service on {self._sensor_address()}.")
            return
        self.hr_service = self.client.createServiceObject(hr_service[0])
        if not self.hr_service:
            print(
                f"Couldn't establish connection to HR service on {self._sensor_address()}."
            )
            return
        self.hr_service.stateChanged.connect(self._start_hr_notification)
        self.hr_service.characteristicChanged.connect(self._data_handler)
        self.hr_service.discoverDetails()

    def _start_hr_notification(self, state: QLowEnergyService.ServiceState):
        if state != QLowEnergyService.RemoteServiceDiscovered:
            return
        if self.hr_service is None:
            return
        hr_char: QLowEnergyCharacteristic = self.hr_service.characteristic(
            self.HR_CHARACTERISTIC
        )
        if not hr_char.isValid():
            print(f"Couldn't find HR characterictic on {self._sensor_address()}.")
        self.hr_notification = hr_char.descriptor(
            QBluetoothUuid.DescriptorType.ClientCharacteristicConfiguration
        )
        if not self.hr_notification.isValid():
            print("HR characteristic is invalid.")
        self.hr_service.writeDescriptor(self.hr_notification, self.ENABLE_NOTIFICATION)

    def _reset_connection(self):
        print(f"Discarding sensor at {self._sensor_address()}.")
        self._remove_service()
        self._remove_client()

    def _remove_service(self):
        if self.hr_service is None:
            return
        try:
            self.hr_service.deleteLater()
        except Exception as e:
            print(f"Couldn't remove service: {e}")
        finally:
            self.hr_service = None
            self.hr_notification = None

    def _remove_client(self):
        if self.client is None:
            return
        try:
            self.client.disconnected.disconnect()
            self.client.deleteLater()
        except Exception as e:
            print(f"Couldn't remove client: {e}")
        finally:
            self.client = None

    def _catch_error(self, error):
        self.status_update.emit(f"An error occurred: {error}. Disconnecting sensor.")
        self._reset_connection()

    def _data_handler(self, _, data: QByteArray):  # _ is unused but mandatory argument
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
        heart_rate_measurement_bytes: bytes = data.data()

        byte0: int = heart_rate_measurement_bytes[0]
        uint8_format: bool = (byte0 & 1) == 0
        energy_expenditure: bool = ((byte0 >> 3) & 1) == 1
        rr_interval: bool = ((byte0 >> 4) & 1) == 1

        if not rr_interval:
            return

        first_rr_byte: int = 2
        if uint8_format:
            # hr = data[1]
            pass
        else:
            # hr = (data[2] << 8) | data[1] # uint16
            first_rr_byte += 1
        if energy_expenditure:
            # ee = (data[first_rr_byte + 1] << 8) | data[first_rr_byte]
            first_rr_byte += 2

        for i in range(first_rr_byte, len(heart_rate_measurement_bytes), 2):
            ibi: int = (
                heart_rate_measurement_bytes[i + 1] << 8
            ) | heart_rate_measurement_bytes[i]
            # Polar H7, H9, and H10 record IBIs in 1/1024 seconds format.
            # Convert 1/1024 sec format to milliseconds.
            # TODO: move conversion to model and only convert if sensor doesn't
            # transmit data in milliseconds.
            ibi = ceil(ibi / 1024 * 1000)
            self.ibi_update.emit(ibi)
