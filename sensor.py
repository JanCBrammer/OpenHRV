import asyncio
from PySide6.QtCore import QObject, Signal
from bleak import BleakClient, BleakScanner
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
    unexpected disconnection:
    - sensor lost skin contact
    - sensor out of range

    user disconnection:
    - user clicks disconnection button

    `await x` means "do `x` and wait for it to return". In the meantime,
    if `x` chooses to suspend execution, other tasks which have already
    started elsewhere may run. Also see [1] and [2].

    References
    ----------
    [1] https://hynek.me/articles/waiting-in-asyncio/
    [2] https://bbc.github.io/cloudfit-public-docs/
    """

    ibi_update = Signal(object)
    status_update = Signal(str)

    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.disconnection_request = asyncio.Event()
        self.client_lock = asyncio.Lock()

    def run(self):
        """Start the (empty) asyncio event loop."""
        self.loop.run_forever()

    def stop(self):
        """Shut down client and asyncio event loop before app is closed."""
        self.disconnect_client()
        self.loop.stop()

    def disconnect_client(self):    # regular subroutines are called from main (GUI) thread with `call_soon_threadsafe`
        """Disconnect from current BLE server."""
        if not self.client_lock.locked():    # early return if no sensor is connected
            print("Currently there is no sensor connected.")
            return
        print("Disconnecting from current sensor.")
        self.disconnection_request.set()
        self.disconnection_request.clear()

    async def connect_client(self, address):    # async methods are called from the main (GUI) thread with `run_coroutine_threadsafe`
        """Connect to BLE server at address."""
        if self.client_lock.locked():    # don't allow new connection while current client is (dis-)connecting or connected
            print("Please disconnect the current sensor and then try to connect again.")
            return
        async with self.client_lock:    # client_lock context exits and releases lock once client is disconnected, either through regular disconnection or failed connection attempt
            print(f"Trying to connect to sensor at {address}...")
            async with BleakClient(address, disconnected_callback=self._reconnect_client) as client:    # __aenter__() calls client.connect() and raises if connection attempt fails
                try:
                    await client.start_notify(HR_UUID, self._data_handler)
                    print(f"Connected to sensor at {client.address}.")
                    await self.disconnection_request.wait()    # block until `disconnection_request` is set
                    client.set_disconnected_callback(None)
                except Exception as e:
                    print(e)

        print(f"Disconnected from sensor at {address}.")

    def _reconnect_client(self, client):
        """Handle unexpected disconnection."""
        print(f"Lost connection to sensor at {client.address}")
        self.loop.call_soon(self.disconnect_client)

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
        Acceleration and raw ECG available via Polar SDK
        """
        bytes = list(data)
        if bytes[0] == 16:
            for i in range(2, len(bytes), 2):
                ibi = data[i] + 256 * data[i + 1]
                ibi = ceil(ibi / 1024 * 1000)    # convert 1/1024 sec format to milliseconds
                self.ibi_update.emit(ibi)
