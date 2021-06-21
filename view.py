import pyqtgraph as pg
import asyncio
from utils import valid_address, valid_path
from datetime import datetime
from PySide6.QtWidgets import (QMainWindow, QPushButton, QHBoxLayout,
                               QVBoxLayout, QWidget, QLabel, QComboBox,
                               QSlider, QGroupBox, QFormLayout, QCheckBox,
                               QFileDialog, QProgressBar, QGridLayout)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QIcon, QLinearGradient, QBrush, QGradient
from sensor import SensorScanner, SensorClient
from logger import RedisPublisher, RedisLogger

import resources    # noqa


class ViewSignals(QObject):
    """Cannot be defined on View directly since Signal needs to be defined on
    object that inherits from QObject"""
    annotation = Signal(tuple)
    start_recording = Signal(str)


class View(QMainWindow):

    def __init__(self, model):
        super().__init__()

        self.setWindowTitle("OpenHRV")
        self.setWindowIcon(QIcon(":/logo.png"))

        self.model = model
        self.signals = ViewSignals()

        self.scanner = SensorScanner()
        self.scanner_thread = QThread()
        self.scanner.moveToThread(self.scanner_thread)
        self.scanner.address_update.connect(self.model.set_addresses)
        self.scanner.status_update.connect(self.show_status)

        self.sensor = SensorClient()
        self.sensor_thread = QThread()
        self.sensor.moveToThread(self.sensor_thread)
        self.sensor.ibi_update.connect(self.model.set_ibis_buffer)
        self.sensor.status_update.connect(self.show_status)
        self.sensor_thread.started.connect(self.sensor.run)

        self.redis_publisher = RedisPublisher()
        self.redis_publisher_thread = QThread()
        self.redis_publisher.moveToThread(self.redis_publisher_thread)
        self.model.ibis_buffer_update.connect(self.redis_publisher.publish)
        self.model.mean_hrv_update.connect(self.redis_publisher.publish)
        self.model.addresses_update.connect(self.redis_publisher.publish)
        self.model.pacer_rate_update.connect(self.redis_publisher.publish)
        self.model.hrv_target_update.connect(self.redis_publisher.publish)
        self.model.biofeedback_update.connect(self.redis_publisher.publish)
        self.signals.annotation.connect(self.redis_publisher.publish)
        self.redis_publisher_thread.started.connect(self.redis_publisher.monitor.start)

        self.redis_logger = RedisLogger()
        self.redis_logger_thread = QThread()
        self.redis_logger.moveToThread(self.redis_logger_thread)
        self.redis_logger_thread.finished.connect(self.redis_logger.save_recording)
        self.signals.start_recording.connect(self.redis_logger.start_recording)
        self.redis_logger.recording_status.connect(self.show_recording_status)
        self.redis_logger.status_update.connect(self.show_status)

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

        self.mean_hrv_plot = pg.PlotWidget()
        self.mean_hrv_plot.setBackground("w")
        self.mean_hrv_plot.setLabel("left", "HRV (msec)",
                                **{"font-size": "25px"})
        self.mean_hrv_plot.setLabel("bottom", "Seconds", **{"font-size": "25px"})
        self.mean_hrv_plot.showGrid(y=True)
        self.mean_hrv_plot.setYRange(0, 600, padding=0)
        self.mean_hrv_plot.setMouseEnabled(x=False, y=False)
        colorgrad = QLinearGradient(0, 0, 0, 1)    # horizontal gradient
        colorgrad.setCoordinateMode(QGradient.ObjectMode)
        colorgrad.setColorAt(0, pg.mkColor("g"))
        colorgrad.setColorAt(.5, pg.mkColor("y"))
        colorgrad.setColorAt(1, pg.mkColor("r"))
        brush = QBrush(colorgrad)
        self.mean_hrv_plot.getViewBox().setBackgroundColor(brush)

        self.mean_hrv_signal = pg.PlotCurveItem()
        pen = pg.mkPen(color="w", width=7.5)
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
        self.pacer_rate.setTracking(False)
        self.pacer_rate.setRange(0, 6)    # transformed to bpm [4, 7], step .5 by model
        self.pacer_rate.valueChanged.connect(self.model.set_breathing_rate)
        self.pacer_rate.setSliderPosition(4)    # corresponds to 6 bpm
        self.pacer_label = QLabel(f"Rate: {self.model.breathing_rate}")

        self.pacer_toggle = QCheckBox("Show pacer", self)
        self.pacer_toggle.setChecked(True)
        self.pacer_toggle.stateChanged.connect(self.toggle_pacer)

        self.hrv_target_label = QLabel(f"Target: {self.model.hrv_target}")

        self.hrv_target = QSlider(Qt.Horizontal)
        self.hrv_target.setRange(50, 600)
        self.hrv_target.setSingleStep(10)
        self.hrv_target.valueChanged.connect(self.model.set_hrv_target)
        self.hrv_target.setSliderPosition(self.model.hrv_target)
        self.mean_hrv_plot.setYRange(0, self.model.hrv_target, padding=0)

        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.scanner.scan)

        self.address_menu = QComboBox()

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_sensor)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_sensor)

        self.start_recording_button = QPushButton("Start")
        self.start_recording_button.clicked.connect(self.get_filepath)

        self.save_recording_button = QPushButton("Save")
        self.save_recording_button.clicked.connect(self.redis_logger.save_recording)

        self.annotation = QComboBox()
        self.annotation.setEditable(True)    # user can add custom annotations (edit + enter)
        self.annotation.setDuplicatesEnabled(False)
        self.annotation_button = QPushButton("Annotate")
        self.annotation_button.clicked.connect(self.emit_annotation)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.recording_status_label = QLabel("Status:")
        self.recording_statusbar = QProgressBar()
        self.recording_statusbar.setRange(0, 1)

        self.statusbar = self.statusBar()

        self.vlayout0 = QVBoxLayout(self.central_widget)

        self.hlayout0 = QHBoxLayout()
        self.hlayout0.addWidget(self.ibis_plot, stretch=80)
        self.hlayout0.addWidget(self.pacer_plot, stretch=20)
        self.vlayout0.addLayout(self.hlayout0)

        self.vlayout0.addWidget(self.mean_hrv_plot)

        self.hlayout1 = QHBoxLayout()

        self.device_config = QGridLayout()
        self.device_config.addWidget(self.scan_button, 0, 0)
        self.device_config.addWidget(self.address_menu, 0, 1)
        self.device_config.addWidget(self.connect_button, 1, 0)
        self.device_config.addWidget(self.disconnect_button, 1, 1)
        self.device_panel = QGroupBox("ECG Devices")
        self.device_panel.setLayout(self.device_config)
        self.hlayout1.addWidget(self.device_panel, stretch=25)

        self.hrv_config = QFormLayout()
        self.hrv_config.addRow(self.hrv_target_label, self.hrv_target)
        self.hrv_panel = QGroupBox("HRV Settings")
        self.hrv_panel.setLayout(self.hrv_config)
        self.hlayout1.addWidget(self.hrv_panel, stretch=25)

        self.pacer_config = QFormLayout()
        self.pacer_config.addRow(self.pacer_label, self.pacer_rate)
        self.pacer_config.addRow(self.pacer_toggle)
        self.pacer_panel = QGroupBox("Breathing Pacer")
        self.pacer_panel.setLayout(self.pacer_config)
        self.hlayout1.addWidget(self.pacer_panel, stretch=25)

        self.recording_config = QGridLayout()
        self.recording_config.addWidget(self.start_recording_button, 0, 0)
        self.recording_config.addWidget(self.save_recording_button, 0, 1)
        self.recording_config.addWidget(self.recording_statusbar, 0, 2)
        self.recording_config.addWidget(self.annotation, 1, 0, 1, 2)    # row, column, rowspan, columnspan
        self.recording_config.addWidget(self.annotation_button, 1, 2)
        self.recording_panel = QGroupBox("Recording")
        self.recording_panel.setLayout(self.recording_config)
        self.hlayout1.addWidget(self.recording_panel, stretch=25)

        self.vlayout0.addLayout(self.hlayout1)

        self.model.ibis_buffer_update.connect(self.plot_ibis)
        self.model.mean_hrv_update.connect(self.plot_hrv)
        self.model.addresses_update.connect(self.list_addresses)
        self.model.pacer_disk_update.connect(self.plot_pacer_disk)
        self.model.pacer_rate_update.connect(self.update_pacer_label)
        self.model.hrv_target_update.connect(self.update_hrv_target)

        self.scanner_thread.start()
        self.sensor_thread.start()
        self.redis_publisher_thread.start()
        self.redis_logger_thread.start()

    def closeEvent(self, event):
        """Properly shut down all threads."""
        print("Closing threads...")
        self.scanner_thread.quit()
        self.scanner_thread.wait()

        self.sensor_thread.quit()    # since quit() only works if the thread has a running event loop...
        self.sensor.loop.call_soon_threadsafe(self.sensor.stop)    # ...the event loop must only be stopped AFTER quit() has been called!
        self.sensor_thread.wait()

        self.redis_publisher_thread.quit()
        self.redis_publisher_thread.wait()

        self.redis_logger_thread.quit()
        self.redis_logger_thread.wait()

    def get_filepath(self):
        current_time = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        default_file_name = f"sub-?_day-?_task-?_time-{current_time}.tsv"    # question marks are invalid characters for file names on Windows and hence force user to specify file name
        file_path = QFileDialog.getSaveFileName(None, "Create file",
                                                default_file_name,
                                                options=QFileDialog.DontUseNativeDialog)[0]    # native file dialog not reliable on Windows (most likely COM issues)
        if not file_path:    # user cancelled or closed file dialog
            return
        if not valid_path(file_path):
            self.show_status("File path is invalid or exists already.")
            return
        self.signals.start_recording.emit(file_path)

    def connect_sensor(self):
        if not self.address_menu.currentText():
            return
        address = self.address_menu.currentText().split(",")[1].strip()    # discard device name
        if not valid_address(address):
            print(f"Invalid sensor address: {address}.")
            return
        asyncio.run_coroutine_threadsafe(self.sensor.connect_client(address),
                                         self.sensor.loop)

    def disconnect_sensor(self):
        self.sensor.loop.call_soon_threadsafe(self.sensor.disconnect_client)

    def plot_ibis(self, ibis):
        self.ibis_signal.setData(self.model.ibis_seconds, ibis[1])

    def plot_hrv(self, hrv):
        self.mean_hrv_signal.setData(self.model.mean_hrv_seconds, hrv[1])

    def list_addresses(self, addresses):
        self.address_menu.clear()
        self.address_menu.addItems(addresses[1])

    def plot_pacer_disk(self, coordinates):
        self.pacer_disc.setData(*coordinates[1])

    def update_pacer_label(self, rate):
        self.pacer_label.setText(f"Rate: {rate[1]}")

    def update_hrv_target(self, target):
        self.mean_hrv_plot.setYRange(0, target[1], padding=0)
        self.hrv_target_label.setText(f"Target: {target[1]}")

    def toggle_pacer(self):
        visible = self.pacer_plot.isVisible()
        self.pacer_plot.setVisible(not visible)

    def show_recording_status(self, status):
        self.recording_statusbar.setRange(0, status)    # indicates busy state if progress is 0

    def show_status(self, status):
        if status == "clear_message":
            self.statusbar.clearMessage()
            return
        self.statusbar.showMessage(status, 0)

    def emit_annotation(self):
        self.signals.annotation.emit(("eventmarker", self.annotation.currentText()))
