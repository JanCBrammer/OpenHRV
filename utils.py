import re
from pathlib import Path
import platform


def valid_address(address):
    """Make sure that MAC (Windows, Linux) or UUID (macOS) is valid."""
    valid = False
    system = platform.system()

    if system in ["Linux", "Windows"]:    # on MacOS devices are identified by UUID instead of MAC, hence skip the MAC validation
        regex = re.compile("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$")
        valid = regex.match(address.lower())
    elif system == "Darwin":
        regex = re.compile("[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}$")
        valid = regex.match(address.lower())

    return valid

def valid_path(path):
    """Make sure that path is valid by OS standards and that a file doesn't
    exist on that path already. No builtin solution for this atm."""
    valid = False
    test_path = Path(path)

    try:
        test_path.touch(exist_ok=False)    # create file
        test_path.unlink()    # remove file (only called if file doesn't exist)
        valid = True
    except OSError:    # path exists or is invalid
        pass

    return valid

def find_indices_to_average(seconds, mean_window):
    """Identify which elements need to be averaged.

    Find the indices of those seconds that fall within the most recent
    `mean_window` seconds.

    Parameters
    ----------
    seconds : ndarray of float
        Vector of seconds corresponding to sampling moments. Can be sampled
        non-uniformly. The right-most element is the most recent.
    mean_window : float
        Average window in seconds.

    Returns
    -------
    mean_indices : bool
        Boolean indices indicating which elements in `seconds` need to be
        averaged.
    """
    mean_indices = seconds >= -mean_window
    if not sum(mean_indices):
        mean_indices[-1] = True    # make sure that at least one element gets selected
    return mean_indices
