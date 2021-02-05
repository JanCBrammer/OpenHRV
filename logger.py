import redis
import time
import numpy as np
from config import REDIS_HOST, REDIS_PORT
from PySide2.QtCore import QObject


class RedisPublisher(QObject):

    def __init__(self, model):
        super().__init__()

        self.model = model
        self.redis = redis.Redis(REDIS_HOST, REDIS_PORT)    # connection to server is not established at instantiation, but once first command to server is issued (i.e., first publish() call)

        self.model.ibis_buffer_update.connect(self.publish)
        self.model.mean_hrv_update.connect(self.publish)
        self.model.mac_addresses_update.connect(self.publish)
        self.model.pacer_rate_update.connect(self.publish)
        self.model.hrv_target_update.connect(self.publish)
        self.model.biofeedback_update.connect(self.publish)

    def publish(self, value):
        key, val = value
        if isinstance(val, (list, np.ndarray)):
            val = val[-1]
        if isinstance(val, np.int32):
            val = int(val)
        try:
            self.redis.publish(key, val)
            print(f"publishing {key}, {val}")
        except redis.exceptions.ConnectionError as e:
            print(e)    # client (re)-connects automatically; as soon as server is back up (in case of previous outage) client-server communication resumes

    def set_marker(self, annotation):
        self.redis.publish("eventmarker", annotation)


class RedisLogger(QObject):

    def __init__(self):
        super().__init__()

        self.redis = redis.Redis(REDIS_HOST, REDIS_PORT)
        self.subscription = self.redis.pubsub()
        self.subscription.psubscribe("*")    # subscribe to all channels by matching everything

    def record(self):
        while True:
            message = self.subscription.get_message()
            if message:
                print(f"recording: {message}")
            time.sleep(0.01)
