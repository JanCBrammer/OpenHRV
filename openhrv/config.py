from typing import Final
from math import ceil


IBI_MEDIAN_WINDOW: Final[int] = 11  # samples
EWMA_WEIGHT_CURRENT_SAMPLE: Final[float] = (
    0.1  # set in range [0, 1], 1 being minimal smoothing, see https://en.wikipedia.org/wiki/Exponential_smoothing
)

MIN_BREATHING_RATE: Final[float] = 4.0  # breaths per minute
MAX_BREATHING_RATE: Final[float] = 7.0  # breaths per minute
MIN_HRV_TARGET: Final[int] = 50
MAX_HRV_TARGET: Final[int] = 600
min_heart_rate = 30
max_heart_rate = 220
MIN_IBI: Final[int] = ceil(60_000 / max_heart_rate)
MAX_IBI: Final[int] = ceil(60_000 / min_heart_rate)
MIN_PLOT_IBI: Final[int] = 300
MAX_PLOT_IBI: Final[int] = 1500

# IBI buffer must hold enough samples such that even if IBIs (on average) were
# MIN_IBI long, there'd be enough samples to display for IBI_HISTORY_DURATION seconds.
IBI_HISTORY_DURATION: Final[int] = 60  # seconds
IBI_BUFFER_SIZE: Final[int] = ceil(IBI_HISTORY_DURATION / (MIN_IBI / 1000))  # samples
HRV_HISTORY_DURATION: Final[int] = 120  # seconds
HRV_BUFFER_SIZE: Final[int] = ceil(HRV_HISTORY_DURATION / (MIN_IBI / 1000))  # samples

COMPATIBLE_SENSORS: Final[list[str]] = ["Polar", "Decathlon Dual HR"]


def tick_to_breathing_rate(tick: int) -> float:
    return (tick + 8) / 2  # scale tick to [4, 7], step .5


def breathing_rate_to_tick(rate: float) -> int:
    return ceil(rate * 2 - 8)  # scale rate to [0, 6], step 1
