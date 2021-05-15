import asyncio
from PySide6.QtCore import QObject, Signal
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from math import ceil
from config import HR_UUID


class SensorScanner(QObject):

    address_update = Signal(object)
    status_update = Signal(str)

    def __init__(self):
        super().__init__()
        self.scanner = BleakScanner()

    async def _scan(self):
        devices = await self.scanner.discover()
        polar_devices = [d for d in devices if "Polar" in str(d.name)]
        if not polar_devices:
            self.status_update.emit("Couldn't find sensors.")
            return
        self.address_update.emit(polar_devices)
        self.status_update.emit(f"Found {len(polar_devices)} sensor(s).")

    def scan(self):
        self.status_update.emit("Searching for sensors...")
        asyncio.run(self._scan())


class SensorClient(QObject):
    """(Re-) connect a BLE client to a server at address.

    Notes
    -----
    external disconnection:
    - sensor lost skin contact
    - sensor out of range

    internal disconnection:
    - user requests connection to another sensor

    `await x` means "do `x` and wait for it to return". In the meantime,
    if `x` chooses to suspend execution, other tasks which have already
    started elsewhere may run. Also see [1].

    References
    ----------
    [1] https://hynek.me/articles/waiting-in-asyncio/
    """

    ibi_update = Signal(object)
    status_update = Signal(str)

    def __init__(self):
        super().__init__()
        self._ble_client = None
        self._address = None
        self._listening = False
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def run(self):
        """Start the (empty) asyncio event loop."""
        self.loop.run_forever()

    async def stop(self):
        """Shut down client before app is closed."""
        await self._discard_client()
        self.loop.stop()

    async def connect_client(self, address):
        """Connect to BLE server."""
        if address == self._address:
            self.status_update.emit(f"Already connected to sensor at {address}.")
            return
        await self._discard_client()
        self._address = address
        await self._connect()

    async def _connect(self):
        """Try connecting to current address."""
        self._ble_client = BleakClient(self._address,
                                       disconnected_callback=self._cleanup_external_disconnection)
        self._listening = False
        max_retries = 3
        n_retries = 0
        while not self._listening:
            self.status_update.emit(f"Trying to connect to sensor at {self._address}...")
            if n_retries > max_retries:
                self.status_update.emit(f"Stopped trying to connect to sensor at {self._address} after {max_retries} attempts.")
                await self._discard_client()
                break
            try:
                await self._ble_client.connect()    # potential exceptions: BleakError (device not found), asyncio TimeoutError
                await self._ble_client.start_notify(HR_UUID, self._data_handler)
                self._listening = True
                self.status_update.emit(f"Successfully connected to sensor at {self._address}.")
            except (BleakError, asyncio.exceptions.TimeoutError, Exception) as error:
                print(f"Connection exception: {error}\nRetrying...")
            n_retries += 1


    def _cleanup_external_disconnection(self, client):
        """Handle external disconnection."""
        self.status_update.emit(f"Lost connection to sensor at {self._address}.")
        self.loop.create_task(self._discard_client())

    async def _discard_client(self):
        try:
            self._ble_client.set_disconnected_callback(None)    # deregister disconnection callback
            await self._ble_client.disconnect()
            print("Disconnected client.")
        except (Exception, BleakError) as error:
            print(f"Couldn't disconnect client: {error}.")
        finally:    # runs before try block exits
            self._ble_client = None
            self._address = None
            print("Discarded client.")

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
                self.ibi_update.emit(ibi)
