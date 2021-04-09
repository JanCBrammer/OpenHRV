import redis
import time
import threading
import traceback
import numpy as np
from datetime import datetime
from pathlib import Path
from config import REDIS_HOST, REDIS_PORT
from PySide2.QtCore import QObject, Signal
from PySide2.QtWidgets import QFileDialog


class RedisPublisher(QObject):

    def __init__(self):
        super().__init__()

        self.redis = redis.Redis(REDIS_HOST, REDIS_PORT)    # connection to server is not established at instantiation, but once first command to server is issued (i.e., first publish() call)
        self.connected = True    # will be set to False in case Redis server is down
        self.monitor = threading.Thread(target=self.wait_for_connection, daemon=True)    # daemon dies as soon as app is shut down, no specific shutdown required

    def wait_for_connection(self):
        while True:
            try:
                self.redis.ping()    # raises if server is down
                self.connected = True
            except redis.exceptions.ConnectionError as e:
                print("Redis server is down.")
                self.connected = False
            time.sleep(5)

    def publish(self, value):
        if not self.connected:
            return    # don't try to connect to server with publish commands while it's down
        key, val = value
        if isinstance(val, (list, np.ndarray)):
            val = val[-1]
        if isinstance(val, np.int32):
            val = int(val)
        try:
            self.redis.publish(key, val)    # tries to establish connection to server
        except redis.exceptions.ConnectionError as e:
            print(e)


class RedisLogger(QObject):

    recording_status = Signal(int)

    def __init__(self):
        super().__init__()

        self.redis = redis.Redis(REDIS_HOST, REDIS_PORT, decode_responses=True)
        self.subscription = self.redis.pubsub()    # PubSub instance has no connection to Redis server yet at instantiation
        self.subscription_thread = None
        self.file = None

        threading.excepthook = self._handle_redis_exceptions

    def start_recording(self):
        subscribed = self._subscribe()
        if not subscribed:
            return
        if self.file:
            print(f"Already writing to a file at {self.file.name}.")
            return
        self.file = self._open_file()    # subscription_thread is already running and starts writing to wfile
        with threading.Lock():    # prevent subscription_thread from writing to file while writing header
            self.file.write("event\tvalue\ttimestamp\n")    # header
        self.recording_status.emit(0)
        print(f"Started recording to {self.file.name}.")

    def save_recording(self):
        """Called in three cases:
        1. User saves recording.
        2. User closes app while recording
        3. Redis server drops out while recording (_handle_redis_exception())
        """
        self._close_file()
        self._close_subscription()

    def _close_subscription(self):
        if not self.subscription_thread:
            return
        print("Closing subscription thread.")
        self.subscription_thread.stop()
        self.subscription_thread = None
        self.subscription.punsubscribe()
        self.subscription.close()    # terminates connection to Redis server

    def _close_file(self):
        if not self.file:
            return
        self.file.close()
        self.recording_status.emit(1)
        print(f"Saved recording at {self.file.name}.")
        self.file = None

    def _handle_redis_exceptions(self, args):
        print(f"PubSub thread interrupted: \n {traceback.print_tb(args.exc_traceback)}")
        self.save_recording()

    def _subscribe(self):
        subscribed = False
        if self.subscription_thread is not None:
            print("Already subscribed.")
            return subscribed    # don't re-subscribe
        try:
            self.subscription.psubscribe(**{"*": self._write_to_file})    # subscribe to all channels by matching everything; instantiates connection to Redis server
            self.subscription_thread = self.subscription.run_in_thread(sleep_time=0.001)     # Redis connection exceptions are handled with threading.excepthook
            subscribed = True
        except redis.exceptions.ConnectionError as e:
            print("Couldn't subscribe.")
            print(e)
        return subscribed

    def _write_to_file(self, data):
        if not self.file:
            return
        print(f"Logging: {data}.")
        if data["type"] != "pmessage":
            return
        key = data["channel"]
        val = data["data"]
        timestamp = datetime.now().isoformat()
        self.file.write(f"{key}\t{val}\t{timestamp}\n")

    @staticmethod
    def _open_file():
        current_time = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        default_file_name = f"sub-?_day-?_task-?_time-{current_time}"
        save_path = QFileDialog.getSaveFileName(None, "Create file",
                                                default_file_name)[0]
        if not save_path:    # user cancelled or closed file dialog
            save_path = str(Path.cwd().joinpath(default_file_name))
        file = open(f"{save_path}.tsv", "a+")
        return file
