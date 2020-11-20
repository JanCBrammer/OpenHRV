import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import (QMainWindow, QPushButton, QHBoxLayout,
                               QVBoxLayout, QWidget, QLabel, QComboBox, QSlider)
from PyQt5.QtCore import QRunnable, QThreadPool, Qt, QThread, Signal
from PyQt5.QtGui import QFont, QIcon
from sensor import SensorScanner, SensorClient


class Worker(QRunnable):

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.fn(*self.args, **self.kwargs)


class View(QMainWindow):

    current_mac = Signal(str)

    def __init__(self, model, pacer):
        super().__init__()

        self.setWindowTitle("OpenHRV")
        self.setWindowIcon(QIcon("./logo.png"))
        self.setGeometry(50, 50, 1750, 750)

        self.model = model
        self.pacer = pacer
        self.threadpool = QThreadPool()

        self.scanner = SensorScanner()
        self.scanner.mac_update.connect(self.model.set_mac_addresses)

        self.sensor = SensorClient()
        self.current_mac.connect(self.sensor.start)
        self.sensor.ibi_update.connect(self.model.set_ibis_buffer)

        self.ibis_plot = pg.PlotWidget()
        self.ibis_plot.setBackground("w")
        self.ibis_plot.setLabel("left", "Inter-Beat-Interval (msec)",
                                **{"font-size": "25px"})
        self.ibis_plot.setLabel("bottom", "Seconds", **{"font-size": "25px"})
        self.ibis_plot.showGrid(y=True)
        self.ibis_plot.setYRange(300, 1500, padding=0)
        self.ibis_plot.setMouseEnabled(x=False, y=False)

        self.ibis_signal = pg.PlotCurveItem()
        pen = pg.mkPen(color=(0, 191, 255), width=7.5)
        self.ibis_signal.setPen(pen)
        self.ibis_signal.setData(self.model.seconds, self.model.ibis_buffer)
        self.ibis_plot.addItem(self.ibis_signal)

        self.pacer_plot = pg.PlotWidget()
        self.pacer_plot.setBackground("w")
        self.pacer_plot.setAspectLocked(lock=True, ratio=1)
        self.pacer_plot.setMouseEnabled(x=False, y=False)
        self.pacer_plot.disableAutoRange()
        self.pacer_plot.setXRange(-1, 1, padding=0)
        self.pacer_plot.setYRange(-1, 1, padding=0)
        self.pacer_plot.hideAxis("left")
        self.pacer_plot.hideAxis("bottom")

        self.pacer_disc = pg.PlotCurveItem()
        brush = pg.mkBrush(color=(135, 206, 250))
        self.pacer_disc.setBrush(brush)
        self.pacer_disc.setFillLevel(1)
        self.pacer_plot.addItem(self.pacer_disc)

        self.pacer_rate = QSlider(Qt.Horizontal)
        self.pacer_rate.setRange(3, 10)
        self.pacer_rate.valueChanged.connect(self.model.set_breathing_rate)
        self.pacer_rate.setSliderPosition(self.model.breathing_rate)

        self.pacer_label = QLabel(f"Breathing Rate: {self.model.breathing_rate}")
        self.pacer_label.setFont(QFont("Arial", 25))

        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.scanner.scan)

        self.mac_menu = QComboBox()

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_sensor)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_sensor)

        self.hrv_label = QLabel("Current HRV:")
        self.hrv_label.setFont(QFont("Arial", 25))

        self.hrv_display = QLabel()
        self.hrv_display.setText("0")
        self.hrv_display.setFont(QFont("Arial", 50))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.hlayout0 = QHBoxLayout(self.central_widget)
        self.hlayout1 = QHBoxLayout()
        self.hlayout2 = QHBoxLayout()

        self.vlayout0 = QVBoxLayout()
        self.vlayout1 = QVBoxLayout()

        self.hlayout0.addLayout(self.vlayout0, stretch=75)
        self.hlayout0.addLayout(self.vlayout1, stretch=25)

        self.vlayout0.addWidget(self.ibis_plot)
        self.vlayout0.addLayout(self.hlayout1)
        self.vlayout0.addLayout(self.hlayout2)

        self.hlayout1.addWidget(self.scan_button)
        self.hlayout1.addWidget(self.mac_menu)

        self.hlayout2.addWidget(self.start_button)
        self.hlayout2.addWidget(self.stop_button)
        self.hlayout2.addWidget(self.hrv_label)
        self.hlayout2.addWidget(self.hrv_display)

        self.vlayout1.addWidget(self.pacer_plot, stretch=70)
        self.vlayout1.addWidget(self.pacer_rate, stretch=15)
        self.vlayout1.addWidget(self.pacer_label, stretch=15)

        self.model.ibis_buffer_update.connect(self.plot_ibis)
        self.model.ibis_buffer_update.connect(self.compute_local_hrv)
        self.model.hrv_buffer_update.connect(self.plot_local_hrv)
        self.model.mac_addresses_update.connect(self.list_macs)
        self.model.pacer_disk_update.connect(self.plot_pacer_disk)
        self.model.pacer_rate_update.connect(self.update_pacer_label)

        self.pacer.start()

        self.scanner_thread = QThread(self)
        self.scanner.moveToThread(self.scanner_thread)
        self.scanner_thread.start()

        self.sensor_thread = QThread(self)
        self.sensor.moveToThread(self.sensor_thread)
        self.sensor_thread.start()

    def start_sensor(self):
        if self.sensor.loop.is_running():
            print("Client already running.")
            return
        mac = self.mac_menu.currentText()
        # TODO: return in case of invalid mac
        self.current_mac.emit(mac)    # starts sensor

    def stop_sensor(self):
        if not self.sensor.loop.is_running():
            print("No client running.")
            return
        self.sensor.stop()

    def compute_local_hrv(self, ibis):    # TODO: move to model

        current_ibi_phase = np.sign(ibis[-1] - ibis[-2])    # 1: IBI rises, -1: IBI falls, 0: IBI constant
        if current_ibi_phase == 0:
            return
        if current_ibi_phase != self.model.last_ibi_phase:

            current_ibi_extreme = ibis[-2]
            local_hrv = abs(self.model.last_ibi_extreme - current_ibi_extreme)

            # potentially enforce constraints on local power here
            updated_hrv_buffer = self.model.hrv_buffer    # copy avoids emission of model.hrv_buffer_update
            updated_hrv_buffer = np.roll(updated_hrv_buffer, -1)
            updated_hrv_buffer[-1] = local_hrv
            self.model.hrv_buffer = updated_hrv_buffer

            print(f"Local hrv: {local_hrv}!")

            self.model.last_ibi_extreme = current_ibi_extreme
            self.model.last_ibi_phase = current_ibi_phase

    def plot_ibis(self, ibis):
        self.ibis_signal.setData(self.model.seconds, ibis)

    def plot_local_hrv(self, hrv):
        self.hrv_display.setText(str(hrv[-1]))

    def list_macs(self, macs):
        self.mac_menu.clear()
        self.mac_menu.addItems(macs)

    def plot_pacer_disk(self, coordinates):
        self.pacer_disc.setData(*coordinates)

    def update_pacer_label(self, rate):
        self.pacer_label.setText(f"Breathing Rate: {rate}")
