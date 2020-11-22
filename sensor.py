import asyncio
from PySide2.QtCore import QObject, Signal
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from math import ceil
from config import HR_UUID


class SensorScanner(QObject):

    mac_update = Signal(object)

    def __init__(self):
        super().__init__()
        self.scanner = BleakScanner()

    async def _scan(self):
        devices = await self.scanner.discover()
        polar_devices = [d for d in devices if "Polar" in str(d)]
        self.mac_update.emit(polar_devices)

    def scan(self):
        print("Searching for sensors...")
        asyncio.run(self._scan())


class SensorClient(QObject):
    """Stay connected to the current MAC.

    Perpetually trying to reconnect to the current MAC after external or
    internal disconnection.

    external disconnection:
        - sensor lost skin contact
        - BLE out of range

    internal disconnection:
        - other parts of the application actively request disconnection
    """

    ibi_update = Signal(object)

    def __init__(self):
        super().__init__()
        self._ble_client = None
        self._connected = False
        self._mac = None
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def run(self):
        self.loop.run_forever()

    async def set_mac(self, mac):
        if mac == self._mac:
            print(f"Already connected to {mac} or currently reconnecting.")
            return
        self._mac = mac
        await self._reconnect()

    async def _connect(self):
        """Perpetually try to connect to current MAC."""
        while not self._connected:
            try:
                print(f"Connecting to {self._mac}")
                self._ble_client = BleakClient(self._mac,
                                               disconnected_callback=self._on_disconnect)
                await self._ble_client.connect()    # potential exceptions: BleakError (device not found), asyncio TimeoutError
                self._connected = await self._ble_client.is_connected()
            except (BleakError, asyncio.exceptions.TimeoutError) as error:
                print(error)
                print("Retrying...")
        print(f"Starting notification for {self._mac}.")
        await self._ble_client.start_notify(HR_UUID, self._data_handler)

    def _on_disconnect(self, client):    # client unused but mandatory positional argument
        """Try to (re-)connect to current MAC in case of disconnection.

        Called in the event of external or internal disconnection of the BLE
        client.
        """
        print("Reconnecting...")
        self._connected = False
        self._ble_client = None    # not strictly necessary to reset to None
        self.loop.create_task(self._connect())

    async def _reconnect(self):
        """Handle internal disconnection."""
        print("Internal reconnection request.")
        if self._connected:
            await self._ble_client.stop_notify(HR_UUID)
            print("Shut down notification.")
            await self._ble_client.disconnect()    # triggers _on_disconnect()
            print("Disconnected client.")
        else:    # True on the initial call
            print("Client already disconnected.")
            self._on_disconnect(self._ble_client)

    def _data_handler(self, caller, data):    # caller (UUID) unused but mandatory positional argument
        """
        IMPORTANT: Polar H10 (H9) records IBIs in 1/1024 seconds format, i.e.
        not milliseconds!

        data has up to 6 bytes:
        byte 1: flags
            00 = only HR
            16 = HR and IBI(s)
        byte 2: HR
        byte 3 and 4: IBI1
        byte 5 and 6: IBI2 (if present)
        byte 7 and 8: IBI3 (if present)
        etc.
        Polar H10 Heart Rate Characteristics
        (UUID: 00002a37-0000-1000-8000-00805f9b34fb):
            + Energy expenditure is not transmitted
            + HR only transmitted as uint8, no need to check if HR is
              transmitted as uint8 or uint16 (necessary for bpm > 255)
        Acceleration and raw ECG only available via Polar SDK
        """
        bytes = list(data)
        if bytes[0] == 16:
            for i in range(2, len(bytes), 2):
                ibi = data[i] + 256 * data[i + 1]
                ibi = ceil(ibi / 1024 * 1000)    # convert 1/1024 sec format to milliseconds
                print(f"IBI: {ibi}")
                self.ibi_update.emit(ibi)
