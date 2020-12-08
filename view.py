import pyqtgraph as pg
import asyncio
from utils import valid_mac
from PySide2.QtWidgets import (QMainWindow, QPushButton, QHBoxLayout,
                               QVBoxLayout, QWidget, QLabel, QComboBox,
                               QSlider, QSpinBox)
from PySide2.QtCore import Qt, QThread
from PySide2.QtGui import QFont, QIcon
from sensor import SensorScanner, SensorClient


class View(QMainWindow):

    def __init__(self, model, pacer):
        super().__init__()

        self.setWindowTitle("OpenHRV")
        self.setWindowIcon(QIcon("./logo.png"))
        self.setGeometry(50, 50, 1750, 750)

        self.model = model
        self.pacer = pacer

        self.scanner = SensorScanner()
        self.scanner_thread = QThread()
        self.scanner.moveToThread(self.scanner_thread)
        self.scanner.mac_update.connect(self.model.set_mac_addresses)

        self.sensor = SensorClient()
        self.sensor_thread = QThread(self)
        self.sensor.moveToThread(self.sensor_thread)
        self.sensor.ibi_update.connect(self.model.set_ibis_buffer)
        self.sensor_thread.started.connect(self.sensor.run)

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
        self.ibis_signal.setData(self.model.ibis_seconds,
                                 self.model.ibis_buffer)
        self.ibis_plot.addItem(self.ibis_signal)

        self.mean_hrv_plot = pg.PlotWidget()#GradientWidget()
        self.mean_hrv_plot.setBackground("w")
        self.mean_hrv_plot.setLabel("left", "HRV (msec)",
                                **{"font-size": "25px"})
        self.mean_hrv_plot.setLabel("bottom", "Seconds", **{"font-size": "25px"})
        self.mean_hrv_plot.showGrid(y=True)
        self.mean_hrv_plot.setYRange(0, 600, padding=0)
        self.mean_hrv_plot.setMouseEnabled(x=False, y=False)

        self.mean_hrv_signal = pg.PlotCurveItem()
        pen = pg.mkPen(color=(0, 191, 255), width=7.5)
        self.mean_hrv_signal.setPen(pen)
        self.mean_hrv_signal.setData(self.model.mean_hrv_seconds, self.model.mean_hrv_buffer)
        self.mean_hrv_plot.addItem(self.mean_hrv_signal)

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

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_sensor)

        # self.hrv_label = QLabel("Current HRV:")
        # self.hrv_label.setFont(QFont("Arial", 25))

        # self.hrv_display = QLabel()
        # self.hrv_display.setText("0")
        # self.hrv_display.setFont(QFont("Arial", 50))

        self.hrv_smoothwindow_label = QLabel("HRV smoothing window")

        self.hrv_smoothwindow = QSpinBox()
        self.hrv_smoothwindow.setRange(0, 15)
        self.hrv_smoothwindow.setSingleStep(1)
        self.hrv_smoothwindow.setSuffix(" seconds")
        self.hrv_smoothwindow.valueChanged.connect(self.model.set_hrv_mean_window)
        self.hrv_smoothwindow.setValue(self.model.hrv_mean_window)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.vlayout0 = QVBoxLayout(self.central_widget)

        self.hlayout0 = QHBoxLayout()
        self.hlayout0.addWidget(self.ibis_plot, stretch=80)
        self.hlayout0.addWidget(self.pacer_plot, stretch=20)
        self.vlayout0.addLayout(self.hlayout0)

        self.vlayout0.addWidget(self.mean_hrv_plot)

        self.hlayout1 = QHBoxLayout()
        self.hlayout1.addWidget(self.scan_button)
        self.hlayout1.addWidget(self.mac_menu)
        self.hlayout1.addWidget(self.connect_button)
        self.hlayout1.addWidget(self.hrv_smoothwindow_label)
        self.hlayout1.addWidget(self.hrv_smoothwindow)
        self.hlayout1.addWidget(self.pacer_rate)
        self.hlayout1.addWidget(self.pacer_label)
        self.vlayout0.addLayout(self.hlayout1)

        self.model.ibis_buffer_update.connect(self.plot_ibis)
        self.model.mean_hrv_update.connect(self.plot_hrv)
        self.model.mac_addresses_update.connect(self.list_macs)
        self.model.pacer_disk_update.connect(self.plot_pacer_disk)
        self.model.pacer_rate_update.connect(self.update_pacer_label)

        self.pacer.start()
        self.scanner_thread.start()
        self.sensor_thread.start()

    def connect_sensor(self):
        mac = self.mac_menu.currentText()
        if not valid_mac(mac):
            print("Invalid MAC.")
            return
        asyncio.run_coroutine_threadsafe(self.sensor.reconnect_internal(mac),
                                         self.sensor.loop)

    def plot_ibis(self, ibis):
        self.ibis_signal.setData(self.model.ibis_seconds, ibis)

    def plot_hrv(self, hrv):
        self.mean_hrv_signal.setData(self.model.mean_hrv_seconds, hrv)

    def list_macs(self, macs):
        self.mac_menu.clear()
        self.mac_menu.addItems(macs)

    def plot_pacer_disk(self, coordinates):
        self.pacer_disc.setData(*coordinates)

    def update_pacer_label(self, rate):
        self.pacer_label.setText(f"Breathing Rate: {rate}")
