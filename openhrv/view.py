from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QLabel,
    QComboBox,
    QSlider,
    QGroupBox,
    QFormLayout,
    QCheckBox,
    QFileDialog,
    QProgressBar,
    QGridLayout,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QMargins, QSize
from PySide6.QtGui import QIcon, QLinearGradient, QBrush, QGradient, QColor
from PySide6.QtCharts import QChartView, QChart, QSplineSeries, QValueAxis, QAreaSeries
from openhrv.utils import valid_address, valid_path, get_sensor_address
from openhrv.sensor import SensorScanner, SensorClient
from openhrv.logger import Logger
from openhrv.pacer import Pacer
from openhrv.config import (
    breathing_rate_to_tick,
    MEANHRV_BUFFER_SIZE,
    IBI_BUFFER_SIZE,
    MAX_BREATHING_RATE,
    MIN_BREATHING_RATE,
    MIN_HRV_TARGET,
    MAX_HRV_TARGET,
    MIN_PLOT_IBI,
    MAX_PLOT_IBI,
)
from openhrv import resources  # noqa

BLUE = QColor(135, 206, 250)
WHITE = QColor(255, 255, 255)
GREEN = QColor(0, 255, 0)
YELLOW = QColor(255, 255, 0)
RED = QColor(255, 0, 0)


class PacerWidget(QChartView):
    def __init__(self, x_values=None, y_values=None, color=BLUE):
        super().__init__()

        self.setSizePolicy(
            QSizePolicy(
                QSizePolicy.Fixed,  # enforce self.sizeHint by fixing horizontal (width) policy
                QSizePolicy.Preferred,
            )
        )

        self.plot = QChart()
        self.plot.legend().setVisible(False)
        self.plot.setBackgroundRoundness(0)
        self.plot.setMargins(QMargins(0, 0, 0, 0))

        self.disc_circumference_coord = QSplineSeries()
        if x_values is not None and y_values is not None:
            self._instantiate_series(x_values, y_values)
        self.disk = QAreaSeries(self.disc_circumference_coord)
        self.disk.setColor(color)
        self.plot.addSeries(self.disk)

        self.x_axis = QValueAxis()
        self.x_axis.setRange(-1, 1)
        self.x_axis.setVisible(False)
        self.plot.addAxis(self.x_axis, Qt.AlignBottom)
        self.disk.attachAxis(self.x_axis)

        self.y_axis = QValueAxis()
        self.y_axis.setRange(-1, 1)
        self.y_axis.setVisible(False)
        self.plot.addAxis(self.y_axis, Qt.AlignLeft)
        self.disk.attachAxis(self.y_axis)

        self.setChart(self.plot)

    def _instantiate_series(self, x_values, y_values):
        for x, y in zip(x_values, y_values):
            self.disc_circumference_coord.append(x, y)

    def update_series(self, x_values, y_values):
        for i, (x, y) in enumerate(zip(x_values, y_values)):
            self.disc_circumference_coord.replace(i, x, y)

    def sizeHint(self):
        height = self.size().height()
        return QSize(height, height)  # force square aspect ratio

    def resizeEvent(self, event):
        if self.size().width() != self.size().height():
            self.updateGeometry()  # adjusts geometry based on sizeHint
        return super().resizeEvent(event)


class XYSeriesWidget(QChartView):
    def __init__(self, x_values=None, y_values=None, line_color=BLUE):
        super().__init__()

        self.plot = QChart()
        self.plot.legend().setVisible(False)
        self.plot.setBackgroundRoundness(0)
        self.plot.setMargins(QMargins(0, 0, 0, 0))

        self.time_series = QSplineSeries()
        self.plot.addSeries(self.time_series)
        pen = self.time_series.pen()
        pen.setWidth(4)
        pen.setColor(line_color)
        self.time_series.setPen(pen)
        if x_values is not None and y_values is not None:
            self._instantiate_series(x_values, y_values)

        self.x_axis = QValueAxis()
        self.x_axis.setLabelFormat("%i")
        self.plot.addAxis(self.x_axis, Qt.AlignBottom)
        self.time_series.attachAxis(self.x_axis)

        self.y_axis = QValueAxis()
        self.y_axis.setLabelFormat("%i")
        self.plot.addAxis(self.y_axis, Qt.AlignLeft)
        self.time_series.attachAxis(self.y_axis)

        self.setChart(self.plot)

    def _instantiate_series(self, x_values, y_values):
        for x, y in zip(x_values, y_values):
            self.time_series.append(x, y)

    def update_series(self, x_values, y_values):
        for i, (x, y) in enumerate(zip(x_values, y_values)):
            self.time_series.replace(i, x, y)


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
        self.model.ibis_buffer_update.connect(self.plot_ibis)
        self.model.mean_hrv_update.connect(self.plot_hrv)
        self.model.addresses_update.connect(self.list_addresses)
        self.model.pacer_rate_update.connect(self.update_pacer_label)
        self.model.hrv_target_update.connect(self.update_hrv_target)

        self.signals = ViewSignals()

        self.pacer = Pacer()
        self.pacer_timer = QTimer()
        self.pacer_timer.setInterval(1 / 8 * 1000)  # redraw pacer at 8Hz
        self.pacer_timer.timeout.connect(self.plot_pacer_disk)

        self.scanner = SensorScanner()
        self.scanner.sensor_update.connect(self.model.update_sensors)
        self.scanner.status_update.connect(self.show_status)

        self.sensor = SensorClient()
        self.sensor.ibi_update.connect(self.model.update_ibis_buffer)
        self.sensor.status_update.connect(self.show_status)

        self.logger = Logger()
        self.logger.recording_status.connect(self.show_recording_status)
        self.logger.status_update.connect(self.show_status)
        self.logger_thread = QThread()
        self.logger_thread.finished.connect(self.logger.save_recording)
        self.signals.start_recording.connect(self.logger.start_recording)
        self.logger.moveToThread(self.logger_thread)

        self.model.ibis_buffer_update.connect(self.logger.write_to_file)
        self.model.addresses_update.connect(self.logger.write_to_file)
        self.model.pacer_rate_update.connect(self.logger.write_to_file)
        self.model.hrv_target_update.connect(self.logger.write_to_file)
        self.model.mean_hrv_update.connect(self.logger.write_to_file)
        self.signals.annotation.connect(self.logger.write_to_file)

        self.ibis_widget = XYSeriesWidget(
            self.model.ibis_seconds, self.model.ibis_buffer
        )
        self.ibis_widget.x_axis.setTitleText("Seconds")
        self.ibis_widget.x_axis.setRange(-IBI_BUFFER_SIZE, 0.0)
        self.ibis_widget.x_axis.setTickCount(7)
        self.ibis_widget.x_axis.setTickInterval(10.0)
        self.ibis_widget.y_axis.setTitleText("Inter-Beat-Interval (msec)")
        self.ibis_widget.y_axis.setRange(MIN_PLOT_IBI, MAX_PLOT_IBI)

        self.hrv_widget = XYSeriesWidget(
            self.model.mean_hrv_seconds, self.model.mean_hrv_buffer, WHITE
        )
        self.hrv_widget.x_axis.setTitleText("Seconds")
        self.hrv_widget.x_axis.setRange(-MEANHRV_BUFFER_SIZE, 0)
        self.hrv_widget.y_axis.setTitleText("HRV (msec)")
        self.hrv_widget.y_axis.setRange(0, self.model.hrv_target)
        colorgrad = QLinearGradient(0, 0, 0, 1)  # horizontal gradient
        colorgrad.setCoordinateMode(QGradient.ObjectMode)
        colorgrad.setColorAt(0, GREEN)
        colorgrad.setColorAt(0.6, YELLOW)
        colorgrad.setColorAt(1, RED)
        brush = QBrush(colorgrad)
        self.hrv_widget.plot.setPlotAreaBackgroundBrush(brush)
        self.hrv_widget.plot.setPlotAreaBackgroundVisible(True)

        self.pacer_widget = PacerWidget(*self.pacer.update(self.model.breathing_rate))

        self.pacer_label = QLabel()
        self.pacer_rate = QSlider(Qt.Horizontal)
        self.pacer_rate.setTickPosition(QSlider.TicksBelow)
        self.pacer_rate.setTracking(False)
        self.pacer_rate.setRange(
            breathing_rate_to_tick(MIN_BREATHING_RATE),
            breathing_rate_to_tick(MAX_BREATHING_RATE),
        )
        self.pacer_rate.valueChanged.connect(self.model.update_breathing_rate)
        self.pacer_rate.setValue(breathing_rate_to_tick(MAX_BREATHING_RATE))

        self.pacer_toggle = QCheckBox("Show pacer", self)
        self.pacer_toggle.setChecked(True)
        self.pacer_toggle.stateChanged.connect(self.toggle_pacer)

        self.hrv_target_label = QLabel(f"Target: {self.model.hrv_target}")

        self.hrv_target = QSlider(Qt.Horizontal)
        self.hrv_target.setRange(MIN_HRV_TARGET, MAX_HRV_TARGET)
        self.hrv_target.setSingleStep(10)
        self.hrv_target.valueChanged.connect(self.model.update_hrv_target)
        self.hrv_target.setSliderPosition(self.model.hrv_target)

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
        self.save_recording_button.clicked.connect(self.logger.save_recording)

        self.annotation = QComboBox()
        self.annotation.setEditable(True)
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
        self.hlayout0.addWidget(self.ibis_widget)
        self.hlayout0.addWidget(self.pacer_widget)
        self.vlayout0.addLayout(self.hlayout0, stretch=50)

        self.vlayout0.addWidget(self.hrv_widget, stretch=50)

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
        # row, column, rowspan, columnspan
        self.recording_config.addWidget(self.annotation, 1, 0, 1, 2)
        self.recording_config.addWidget(self.annotation_button, 1, 2)
        self.recording_panel = QGroupBox("Recording")
        self.recording_panel.setLayout(self.recording_config)
        self.hlayout1.addWidget(self.recording_panel, stretch=25)

        self.vlayout0.addLayout(self.hlayout1)

        self.logger_thread.start()
        self.pacer_timer.start()

    def closeEvent(self, event):
        """Shut down all threads."""
        print("Closing threads...")

        self.sensor.disconnect_client()

        self.logger_thread.quit()
        self.logger_thread.wait()

    def get_filepath(self):
        current_time = datetime.now().strftime("%Y-%m-%d-%H-%M")
        default_file_name = f"OpenHRV_{current_time}.csv"
        # native file dialog not reliable on Windows (most likely COM issues)
        file_path = QFileDialog.getSaveFileName(
            None,
            "Create file",
            default_file_name,
            options=QFileDialog.DontUseNativeDialog,
        )[0]
        if not file_path:  # user cancelled or closed file dialog
            return
        if not valid_path(file_path):
            self.show_status("File path is invalid or exists already.")
            return
        self.signals.start_recording.emit(file_path)

    def connect_sensor(self):
        if not self.address_menu.currentText():
            return
        # discard device name
        address = self.address_menu.currentText().split(",")[1].strip()
        if not valid_address(address):
            print(f"Invalid sensor address: {address}.")
            return
        sensor = [s for s in self.model.sensors if get_sensor_address(s) == address]
        self.sensor.connect_client(*sensor)

    def disconnect_sensor(self):
        self.sensor.disconnect_client()

    def plot_ibis(self, ibis):
        self.ibis_widget.update_series(*ibis.value)

    def plot_hrv(self, hrv):
        self.hrv_widget.update_series(*hrv.value)

    def list_addresses(self, addresses):
        self.address_menu.clear()
        self.address_menu.addItems(addresses.value)

    def plot_pacer_disk(self):
        coordinates = self.pacer.update(self.model.breathing_rate)
        self.pacer_widget.update_series(*coordinates)

    def update_pacer_label(self, rate):
        self.pacer_label.setText(f"Rate: {rate.value}")

    def update_hrv_target(self, target):
        self.hrv_widget.y_axis.setRange(0, target.value)
        self.hrv_target_label.setText(f"Target: {target.value}")

    def toggle_pacer(self):
        visible = self.pacer_widget.isVisible()
        self.pacer_widget.setVisible(not visible)

    def show_recording_status(self, status):
        """Indicate busy state if `status` is 0."""
        self.recording_statusbar.setRange(0, status)

    def show_status(self, status, print_to_terminal=True):
        self.statusbar.showMessage(status, 0)
        if print_to_terminal:
            print(status)

    def emit_annotation(self):
        self.signals.annotation.emit(("Annotation", self.annotation.currentText()))
