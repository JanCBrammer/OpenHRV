import re
import platform
from pathlib import Path
from collections import namedtuple
from PySide6.QtBluetooth import QBluetoothDeviceInfo


NamedSignal = namedtuple("NamedSignal", "name value")


def get_sensor_address(sensor: QBluetoothDeviceInfo) -> str:
    """Return MAC (Windows, Linux) or UUID (macOS)."""
    system = platform.system()
    sensor_address = ""
    if system in ["Linux", "Windows"]:
        sensor_address = sensor.address().toString()
    elif system == "Darwin":
        sensor_address = sensor.deviceUuid().toString().strip("{}")

    return sensor_address


def get_sensor_remote_address(sensor) -> str:
    """Return MAC (Windows, Linux) or UUID (macOS)."""
    system = platform.system()
    sensor_remote_address = ""
    if system in ["Linux", "Windows"]:
        sensor_remote_address = sensor.remoteAddress().toString()
    elif system == "Darwin":
        sensor_remote_address = sensor.remoteDeviceUuid().toString().strip("{}")

    return sensor_remote_address


def valid_address(address: str) -> bool:
    """Make sure that MAC (Windows, Linux) or UUID (macOS) is valid."""
    system = platform.system()
    regex = ""
    if system in ["Linux", "Windows"]:
        regex = r"[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\1[0-9a-f]{2}){4}$"
    elif system == "Darwin":
        # Allow for any valid UUID
        regex = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

    return bool(re.compile(regex, re.IGNORECASE).match(address))


def valid_path(path: str) -> bool:
    """Make sure that path is valid by OS standards and that a file doesn't
    exist on that path already. No builtin solution for this atm."""
    valid = False
    test_path = Path(path)
    try:
        test_path.touch(exist_ok=False)  # create file
        test_path.unlink()  # remove file (only called if file doesn't exist)
        valid = True
    except OSError:  # path exists or is invalid
        pass

    return valid


def sign(value: int) -> int:
    if value > 0:
        return 1
    elif value < 0:
        return -1
    return value
