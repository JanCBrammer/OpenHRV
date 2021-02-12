import redis
import threading
import traceback
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
        except redis.exceptions.ConnectionError as e:
            print(e)    # client (re)-connects automatically; as soon as server is back up (in case of previous outage) client-server communication resumes


class RedisLogger(QObject):

    def __init__(self):
        super().__init__()

        self.redis = redis.Redis(REDIS_HOST, REDIS_PORT)
        self.subscription = self.redis.pubsub()    # PubSub instance has no connection to Redis server yet at instantiation
        self.subscription_thread = None
        self.wfile = None

        threading.excepthook = self._handle_redis_exceptions

    def start_recording(self):
        subscribed = self._subscribe()
        if not subscribed:
            return
        # TODO: make sure to not open multiple files (i.e., only write to a single file at once)
        self.wfile = open("redisDataDummy.txt", "a+")
        self.subscription_thread = self.subscription.run_in_thread(sleep_time=0.001)     # Redis connection exceptions are handled with excepthook
        print("Started recording.")

    def save_recording(self):
        if self.wfile:
            print("Saving recording.")
            self.wfile.close()
            self.wfile = None
        self._close_subscription_thread()

    def shutdown(self):
        """Only called when application is closed."""
        if not self.subscription_thread:
            return
        print("Shutting down RedisLogger.")
        self.subscription.punsubscribe()
        self.save_recording()

    def _close_subscription_thread(self):
        if not self.subscription_thread:
            return
        print("Closing subscription thread.")
        self.subscription_thread.stop()
        self.subscription_thread = None
        self.subscription.close()    # terminates connection to Redis server

    def _handle_redis_exceptions(self, args):
        print(f"PubSub thread interrupted: \n {traceback.print_tb(args.exc_traceback)}")
        self.save_recording()

    def _subscribe(self):
        # TODO: make sure to not re-subscribe
        subscribed = False
        try:
            self.subscription.psubscribe(**{"*": self._write_to_file})    # subscribe to all channels by matching everything; instantiates connection to Redis server
            subscribed = True
        except redis.exceptions.ConnectionError as e:
            print("Couldn't subscribe.")
            print(e)
        return subscribed

    def _write_to_file(self, data):
        print(f"Logging: {data}.")
        if not self.wfile:
            return
        self.wfile.write(str(data["data"]))
        self.wfile.write("\n")
