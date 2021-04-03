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

    Perpetually try to reconnect to the current MAC after external or internal
    disconnection.

    Notes
    -----
    - external disconnection:
        - sensor lost skin contact
        - sensor out of range

    - internal disconnection:
        - other parts of the application (e.g., View) actively request
        disconnection

    `await this` means "do `this` and wait for it to return". In the meantime,
    if `this` chooses to suspend execution, other tasks which have already
    started elsewhere may run.
    """

    ibi_update = Signal(object)

    def __init__(self):
        super().__init__()
        self._ble_client = None
        self._listening = False
        self._mac = None
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def run(self):
        """Start the (empty) asyncio event loop."""
        self.loop.run_forever()

    async def stop(self):
        """Shut down client before app is closed."""
        try:
            await self._ble_client.stop_notify(HR_UUID)
            print("Shut down notification.")
            self._ble_client.set_disconnected_callback(None)    # deregister disconnection callback to prevent reconnection attempt
            await self._ble_client.disconnect()
            print("Disconnected client.")
        except (Exception, BleakError) as error:
            print(f"Reconnection exception: {error}.")
        self.loop.stop()

    async def reconnect_internal(self, mac):
        """Handle internal disconnection."""
        print("Internal reconnection request.")
        tasks = asyncio.all_tasks(self.loop)
        if len(tasks) > 1:
            # Necessary to ensure sequential execution of reconnection requests.
            # Yes, this contradicts the asynchronous paradigm. However, bleak is
            # currently the only Python package that somewhat reliably works
            # with BLE on Windows. Hence, forcing bleak to play nicely with the
            # otherwise synchronous Qt event loop seems to be an option to
            # prevent severely messed up Sensor state (given my current, limited
            # knowledge of asyncio).
            print("Waiting for current task to finish...")
            return
        self._mac = mac
        try:
            await self._ble_client.stop_notify(HR_UUID)
            print("Shut down notification.")
            self._ble_client.set_disconnected_callback(None)    # deregister disconnection callback to prevent reconnection attempt
            await self._ble_client.disconnect()
            print("Disconnected client.")
        except (Exception, BleakError) as error:
            print(f"Reconnection exception: {error}.")
        await self._connect()

    def _reconnect_external(self, client):
        """Handle external disconnection."""
        self.loop.create_task(self._connect())

    async def _connect(self):
        """Perpetually try to connect to current MAC.

        Handle internal and external disconnections.
        """
        self._ble_client = BleakClient(self._mac,
                                       disconnected_callback=self._reconnect_external)
        print(f"client: {self._ble_client}")
        self._listening = False
        while not self._listening:
            try:
                print(f"Connecting to {self._mac}")
                await self._ble_client.connect()    # potential exceptions: BleakError (device not found), asyncio TimeoutError
                print(f"Starting notification for {self._mac}.")
                await self._ble_client.start_notify(HR_UUID, self._data_handler)
                self._listening = True
            except (BleakError, asyncio.exceptions.TimeoutError, Exception) as error:
                print(f"Connection exception: {error}")
                print("Retrying...")

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
