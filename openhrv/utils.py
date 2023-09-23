import re
import platform
import statistics
from pathlib import Path
from collections import deque
from itertools import islice
from openhrv.config import HRV_MEAN_WINDOW, HRV_BUFFER_SIZE


def get_sensor_address(sensor):
    """Return MAC (Windows, Linux) or UUID (macOS)."""
    system = platform.system()
    if system in ["Linux", "Windows"]:
        return sensor.address().toString()
    elif system == "Darwin":
        return sensor.deviceUuid().toString().strip("{}")


def get_sensor_remote_address(sensor):
    """Return MAC (Windows, Linux) or UUID (macOS)."""
    system = platform.system()
    if system in ["Linux", "Windows"]:
        return sensor.remoteAddress().toString()
    elif system == "Darwin":
        return sensor.remoteDeviceUuid().toString().strip("{}")


def valid_address(address):
    """Make sure that MAC (Windows, Linux) or UUID (macOS) is valid."""
    valid = False
    system = platform.system()

    if system in ["Linux", "Windows"]:
        regex = re.compile("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$")
        valid = regex.match(address.lower())
    elif system == "Darwin":
        regex = re.compile(
            "[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$"  # polar uuid not necessarily RFC4122 compliant
        )
        valid = regex.match(address.lower())

    return valid


def valid_path(path):
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


def compute_mean_hrv(seconds: deque[float], hrv: deque[int]) -> float:
    hrv_buffer_seconds = islice(seconds, len(seconds) - HRV_BUFFER_SIZE, None)
    start_idx_mean_window = next(
        (
            i
            for i, second in enumerate(hrv_buffer_seconds)
            if second >= -HRV_MEAN_WINDOW
        ),
        -1,
    )

    return statistics.mean(islice(hrv, start_idx_mean_window, None))


def sign(value: int) -> int:
    if value > 0:
        return 1
    elif value < 0:
        return -1
    return value
