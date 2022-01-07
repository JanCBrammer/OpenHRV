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
            # transmit data in miliseconds.
            ibi = ceil(ibi / 1024 * 1000)
            self.ibi_update.emit(ibi)
