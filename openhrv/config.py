IBI_BUFFER_SIZE = 60
HRV_BUFFER_SIZE = 10
MEANHRV_BUFFER_SIZE = 120

MIN_BREATHING_RATE = 4
MAX_BREATHING_RATE = 7
def tick_to_breathing_rate(tick):
    return float((tick + 8) / 2)    # scale tick to [4, 7], step .5
def breathing_rate_to_tick(rate):
    return int(rate * 2 - 8)     # scale rate to [0, 6], step 1
