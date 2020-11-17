import asyncio
from PySide2.QtCore import QObject, Signal
from bleak import BleakClient, BleakScanner
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

    ibi_update = Signal(object)

    def __init__(self):
        super().__init__()
        self.ble_client = None
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def start(self, mac):
        self.loop.create_task(self._connect_client(mac))
        self.loop.run_forever()

    def stop(self):
        self.loop.create_task(self._disconnect_client())    # executes as soon as ble_client is idle in between notifications

    async def _connect_client(self, mac):
        self.ble_client = BleakClient(mac)
        print(f"Trying to connect to Polar belt {mac}...")
        await self.ble_client.connect()
        await self.ble_client.is_connected()
        print(f"Connected to Polar belt {mac}.")
        await self.ble_client.start_notify(HR_UUID, self.data_handler)

    async def _disconnect_client(self):
        if self.ble_client is None:
            print("No client.")
            return
        connected = await self.ble_client.is_connected()
        if not connected:
            print("Waiting until client is connected before disconnecting.")
            return
        await self.ble_client.stop_notify(HR_UUID)
        await self.ble_client.disconnect()
        self.ble_client = None
        self.loop.stop()
        print("Disconnected client.")

    def data_handler(self, sender, data):    # sender (UUID) unused but required by Bleak API
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
        # hr = None
        # ibis = []
        # if bytes[0] == 00:
        #     hr = data[1]
        if bytes[0] == 16:
            # hr = data[1]
            for i in range(2, len(bytes), 2):
                ibi = data[i] + 256 * data[i + 1]
                ibi = ceil(ibi / 1024 * 1000)    # convert 1/1024 sec format to milliseconds
        #         ibis.append(ibi)
        # if ibis:
        #     for ibi in ibis:
                print(f"IBI: {ibi}")
                self.ibi_update.emit(ibi)
        # if hr:
        #     print(f"HR: {hr}")
