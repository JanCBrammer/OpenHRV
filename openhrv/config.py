from typing import Final
from math import ceil

IBI_BUFFER_SIZE: Final[int] = 60  # samples
HRV_BUFFER_SIZE: Final[int] = 10  # samples
MEANHRV_BUFFER_SIZE: Final[int] = 120  # samples

HRV_MEAN_WINDOW: Final[float] = 15.0  # seconds
IBI_MEDIAN_WINDOW: Final[int] = 11  # samples

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


def tick_to_breathing_rate(tick: int) -> float:
    return (tick + 8) / 2  # scale tick to [4, 7], step .5


def breathing_rate_to_tick(rate: float) -> int:
    return ceil(rate * 2 - 8)  # scale rate to [0, 6], step 1
