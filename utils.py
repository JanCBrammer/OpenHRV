import re


def valid_mac(mac):
    """Make sure that MAC matches a valid pattern."""

    regex = "[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$"
    valid = re.match(regex, mac.lower())

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
