import json
from datetime import datetime
from pathlib import Path

import serial
from serial.tools import list_ports
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QScrollArea,
    QStackedWidget,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mp2886_registers import (
    FAULT_STATUS_CODES,
    MFR_FAULT_SNAPSHOT_CODES,
    PAGE0_REGISTERS,
    READABLE_PAGE0_REGISTERS,
    REGISTERS_BY_CODE,
    STATUS_FLAG_NAMES,
    description_for,
    interpretation_for,
    status_flags_for,
    telemetry_display_for,
)


DIAGNOSTIC_TABLE_CODES = set(FAULT_STATUS_CODES) | set(MFR_FAULT_SNAPSHOT_CODES) | {
    0x01, 0x1F, 0x21, 0x24, 0x35, 0x36, 0x5E, 0x5F, 0x88, 0xBD, 0xE1, 0xE2,
}

COLOR_GOOD = "#63d8b3"
COLOR_WARNING = "#f0bc65"
COLOR_ERROR = "#ff858b"
PROFILE_FORMAT = "mp2886-page0-profile"
PROFILE_VERSION = 1
PROFILE_EXCLUDED_CODES = frozenset({
    0x00, 0x01, 0x06, 0x13, 0x27, 0x28, 0x29, 0x3A, 0x46, 0x47, 0xBE,
})
PROFILE_REGISTERS = tuple(
    register
    for register in PAGE0_REGISTERS
    if register.can_read and register.can_write and register.code not in PROFILE_EXCLUDED_CODES
)
PROFILE_SIGNATURE_CODES = (0x46, 0x47)
SETTINGS_REGISTERS = tuple(
    register for register in PAGE0_REGISTERS
    if register.can_read and register.can_write and register.code != 0x00
)
MONITOR_REGISTERS = tuple(register for register in PAGE0_REGISTERS if register.access == "r")
CONFIG_NUMERIC_FIELDS = {
    "vboot": (0xBB, 0x01FF, 0, 0.00625, 0xFE00, 0x0000),
    "vmin": (0x1F, 0x01FF, 0, 0.00625, 0xFE00, 0x0000),
    "vmax": (0x24, 0x01FF, 0, 0.00625, 0xFE00, 0x0000),
    "frequency": (0xBD, 0x01FF, 0, 0.01, 0xFE00, 0x0000),
    "vin_on": (0x35, 0x00FF, 0, 0.125, 0xFF00, 0xE800),
    "vin_off": (0x36, 0x00FF, 0, 0.125, 0xFF00, 0xE800),
    "vin_ov_fault": (0x55, 0x00FF, 0, 0.125, 0xFF00, 0xE800),
    "vin_uv_warn": (0x58, 0x00FF, 0, 0.125, 0xFF00, 0xE800),
    "oc_warn": (0x4A, 0x03FF, 0, "current", 0xFC00, 0x0000),
    "ocp_total": (0xEC, 0x007F, 0, "current", 0x8000, 0x0000),
    "temp_warn": (0x51, 0x00FF, 0, 1.0, 0xFF00, 0x0000),
}
CONFIG_CHOICE_FIELDS = {
    "vid_control": (0xE1, 0x0010, ("PWM-VID", "PMBus")),
    "dvid_mode": (0xE2, 0x0001, ("Linear", "R-C filter")),
    "phase_count": (0xE1, 0x0007, ("1-phase DCM", "1-phase CCM", "2-phase", "3-phase", "4-phase", "5-phase", "6-phase", "Code 7 · preserve raw")),
}
CONFIG_READ_CODES = tuple(sorted(
    {0x00, 0x44}
    | {field[0] for field in CONFIG_NUMERIC_FIELDS.values()}
    | {field[0] for field in CONFIG_CHOICE_FIELDS.values()}
))


def _mask_shift(mask):
    return (mask & -mask).bit_length() - 1


STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background: #171c1a;
    color: #e4ece8;
    font-family: "Noto Sans";
    font-size: 9pt;
}
QFrame#statusCard, QGroupBox, QWidget#panel {
    background: #202725;
    border: 1px solid #394440;
    border-radius: 5px;
}
QFrame#deviceSidebar {
    background: #202725;
    border-right: 1px solid #394440;
}
QListWidget {
    background: #151b19;
    color: #e4ece8;
    border: 1px solid #394440;
    border-radius: 4px;
    outline: none;
}
QListWidget::item {
    padding: 8px;
    border-radius: 3px;
}
QListWidget::item:selected {
    background: #285f50;
    color: #ffffff;
}
QLabel#faultIndicator {
    background: #20332d;
    color: #63d8b3;
    border: 1px solid #315244;
    border-radius: 4px;
    padding: 6px 8px;
    font-weight: 700;
}
QLabel#pageTitle {
    color: #f0f5f2;
    font-size: 19pt;
    font-weight: 700;
}
QLabel#eyebrow, QLabel.muted, QLabel#cardNote {
    color: #a1ada8;
}
QLabel#cardTitle {
    color: #aab7b1;
    font-size: 8pt;
    font-weight: 700;
}
QLabel#cardValue {
    color: #e4ece8;
    font-size: 12pt;
    font-weight: 700;
}
QGroupBox {
    margin-top: 8px;
    padding: 9px 8px 7px 8px;
    font-size: 8pt;
    font-weight: 700;
    color: #b5c1bb;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 25px;
    padding: 2px 7px;
    background: #151b19;
    color: #edf4f0;
    border: 1px solid #46534d;
    border-radius: 4px;
    selection-background-color: #287c66;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #58d6b2;
}
QComboBox QAbstractItemView {
    background: #202725;
    color: #e4ece8;
    selection-background-color: #287c66;
    selection-color: #ffffff;
}
QPushButton {
    min-height: 27px;
    padding: 2px 10px;
    background: #2a3330;
    border: 1px solid #424e48;
    border-radius: 4px;
    color: #e2eae6;
    font-weight: 600;
}
QPushButton:hover {
    background: #35413c;
}
QPushButton:pressed {
    background: #3c4b44;
}
QPushButton:disabled {
    color: #78847e;
    background: #222926;
    border-color: #303a35;
}
QPushButton#primaryButton {
    background: #147d67;
    border-color: #238f76;
    color: #ffffff;
}
QPushButton#primaryButton:hover {
    background: #19987c;
}
QPushButton#dangerButton {
    color: #ff9ba0;
    background: #382326;
    border-color: #684047;
}
QPushButton#dangerButton:hover {
    background: #4a2b2e;
}
QCheckBox {
    spacing: 7px;
    color: #dce5e0;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    background: #151b19;
    border: 1px solid #56645d;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    background: #238f76;
    border-color: #58d6b2;
}
QTabWidget::pane {
    border: 1px solid #394440;
    border-radius: 5px;
    background: #202725;
    top: -1px;
}
QTabBar::tab {
    min-width: 90px;
    padding: 8px 14px;
    margin-right: 3px;
    color: #aab6b0;
    background: #252d2a;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    color: #74dfbd;
    background: #202725;
    font-weight: 700;
    border: 1px solid #394440;
    border-bottom-color: #202725;
}
QTableWidget {
    background: #202725;
    alternate-background-color: #252d2a;
    color: #e1e9e5;
    border: none;
    gridline-color: #343e39;
    selection-background-color: #285f50;
    selection-color: #ffffff;
}
QHeaderView::section {
    padding: 6px 7px;
    color: #c1ccc6;
    background: #29322f;
    border: none;
    border-bottom: 1px solid #3d4943;
    font-weight: 700;
}
QPlainTextEdit {
    background: #151b19;
    border: 1px solid #3c4842;
    border-radius: 4px;
    color: #dce5e0;
    selection-background-color: #287c66;
    selection-color: #ffffff;
}
QStatusBar {
    background: #202725;
    color: #aab6b0;
    border-top: 1px solid #394440;
}
QStatusBar::item {
    border: none;
}
QScrollBar:vertical {
    background: #202725;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #46534d;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar:horizontal {
    background: #202725;
    height: 12px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #46534d;
    min-width: 24px;
    border-radius: 5px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
}
"""


class StatusCard(QFrame):
    def __init__(self, title, value, note):
        super().__init__()
        self.setObjectName("statusCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("cardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("cardValue")
        self.note_label = QLabel(note)
        self.note_label.setObjectName("cardNote")
        self.note_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.note_label)

    def set_value(self, value, color=None):
        self.value_label.setText(value)
        self.value_label.setStyleSheet(f"color: {color};" if color else "")

    def set_note(self, note):
        self.note_label.setText(note)


class MP2886Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP2886A | PMBus Workbench")
        self.resize(1280, 820)
        self.setMinimumSize(1050, 690)
        self.port = None
        self.last_scan_addresses = []
        self.pec_supported = False
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(5000)
        self.monitor_timer.timeout.connect(self.refresh_monitor)

        self._build_ui()
        self.refresh_ports()
        self.statusBar().showMessage("Hazır · ESP32-C3 bridge bağlantısı bekleniyor")

    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        sidebar = QFrame()
        sidebar.setObjectName("deviceSidebar")
        sidebar.setFixedWidth(250)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 14, 12, 12)
        side.setSpacing(8)
        title = QLabel("MP2886A")
        title.setObjectName("pageTitle")
        subtitle = QLabel("PMBus POWER MONITOR")
        subtitle.setObjectName("eyebrow")
        side.addWidget(title)
        side.addWidget(subtitle)
        address_title = QLabel("DEVICE ADDRESS")
        address_title.setObjectName("cardTitle")
        side.addWidget(address_title)
        self.device_list = QListWidget()
        self.device_list.setMaximumHeight(150)
        self.device_list.itemClicked.connect(self._select_scanned_address)
        side.addWidget(self.device_list)

        address_row = QHBoxLayout()
        address_row.addWidget(QLabel("7-bit"))
        self.address = QLineEdit("20")
        self.address.setMaximumWidth(70)
        address_row.addWidget(self.address)
        self.scan_button = QPushButton("SCAN")
        self.scan_button.clicked.connect(self.scan_bus)
        address_row.addWidget(self.scan_button, 1)
        side.addLayout(address_row)

        bridge_title = QLabel("USB-I²C BRIDGE")
        bridge_title.setObjectName("cardTitle")
        side.addWidget(bridge_title)
        port_row = QHBoxLayout()
        self.port_box = QComboBox()
        self.refresh_button = QPushButton("↻")
        self.refresh_button.setToolTip("Seri portları yenile")
        self.connect_button = QPushButton("Bağlan")
        self.connect_button.setObjectName("primaryButton")
        self.refresh_button.clicked.connect(self.refresh_ports)
        self.connect_button.clicked.connect(self.toggle_connection)
        port_row.addWidget(self.port_box, 1)
        port_row.addWidget(self.refresh_button)
        side.addLayout(port_row)
        side.addWidget(self.connect_button)

        self.bridge_card = StatusCard("USB bridge", "Bağlı değil", "Seri bağlantı bekleniyor")
        self.target_card = StatusCard("I²C hedef", "Taranmadı", "ACK kimlik doğrulaması değildir")
        self.pec_card = StatusCard("SMBus PEC", "Kapalı", "CRC-8 · polynomial 07h")
        side.addWidget(self.bridge_card)
        side.addWidget(self.target_card)
        side.addWidget(self.pec_card)

        speed_title = QLabel("BUS SPEED")
        speed_title.setObjectName("cardTitle")
        side.addWidget(speed_title)
        speed_row = QHBoxLayout()
        self.frequency = QSpinBox()
        self.frequency.setRange(10000, 1000000)
        self.frequency.setSingleStep(10000)
        self.frequency.setValue(100000)
        self.frequency.setSuffix(" Hz")
        self.frequency_button = QPushButton("Set")
        self.frequency_button.clicked.connect(self.set_frequency)
        speed_row.addWidget(self.frequency, 1)
        speed_row.addWidget(self.frequency_button)
        side.addLayout(speed_row)
        side.addStretch(1)
        root.addWidget(sidebar)

        workspace = QWidget()
        main = QVBoxLayout(workspace)
        main.setContentsMargins(14, 10, 14, 8)
        main.setSpacing(8)
        header = QHBoxLayout()
        header.addWidget(QLabel("MP2886A / CONFIGURATION"))
        header.addStretch(1)
        self.connection_badge = QLabel("●  BRIDGE OFFLINE")
        self.connection_badge.setStyleSheet(f"color: {COLOR_ERROR}; font-weight: 700; padding: 8px 12px;")
        header.addWidget(self.connection_badge)
        main.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_input_tab(), "Input")
        self.tabs.addTab(self._build_diagnostics_tab(), "Protection")
        self.tabs.addTab(self._build_eeprom_tab(), "Advanced")
        self.tabs.addTab(self._build_settings_tab(), "All Settings")
        self.tabs.addTab(self._build_register_tab(), "Register")
        self.tabs.addTab(self._build_monitor_tab(), "Monitor")
        self.tabs.setCurrentIndex(0)
        main.addWidget(self.tabs, 1)

        log_header = QHBoxLayout()
        log_title = QLabel("ACTIVITY")
        log_title.setObjectName("cardTitle")
        log_header.addWidget(log_title)
        log_header.addStretch(1)
        clear_log_button = QPushButton("Clear")
        clear_log_button.clicked.connect(self.clear_log)
        log_header.addWidget(clear_log_button)
        main.addLayout(log_header)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setFixedHeight(72)
        main.addWidget(self.log)
        self.setStatusBar(QStatusBar())
        root.addWidget(workspace, 1)

    def _build_input_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        title = QLabel("OUTPUT CONFIGURATION")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        group = QGroupBox("VOLTAGE / PWM-VID")
        form = QFormLayout(group)
        self.config_widgets = {}
        self._add_config_field(form, "vboot", "Boot voltage · BBh", 0, 3.2, 5, " V")
        self._add_config_field(form, "vmin", "VOUT minimum · 1Fh", 0, 3.2, 5, " V")
        self._add_config_field(form, "vmax", "VOUT maximum · 24h", 0, 3.2, 5, " V")
        self._add_config_field(form, "frequency", "Switching frequency · BDh", 0, 5.11, 2, " MHz")
        self._add_config_choice(form, "phase_count", "Full phase count · E1h", CONFIG_CHOICE_FIELDS["phase_count"][2])
        self._add_config_choice(form, "vid_control", "Voltage control · E1h", ("PWM-VID", "PMBus"))
        self._add_config_choice(form, "dvid_mode", "Boot / DVID slew · E2h", ("Linear", "R-C filter"))
        layout.addWidget(group)

        vin_group = QGroupBox("INPUT VOLTAGE LIMITS")
        vin_form = QFormLayout(vin_group)
        self._add_config_field(vin_form, "vin_on", "VIN_ON · 35h", 0, 31.875, 3, " V")
        self._add_config_field(vin_form, "vin_off", "VIN_OFF · 36h", 0, 31.875, 3, " V")
        self._add_config_field(vin_form, "vin_ov_fault", "VIN over-voltage fault · 55h", 0, 31.875, 3, " V")
        self._add_config_field(vin_form, "vin_uv_warn", "VIN under-voltage warning · 58h", 0, 31.875, 3, " V")
        layout.addWidget(vin_group)

        note = QLabel("VOUT values use 6.25 mV/LSB. PWM frequency uses 10 kHz/LSB. Live values are read from PAGE 0.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        self._add_config_actions(layout)
        return page

    def _add_config_field(self, form, key, label, minimum, maximum, decimals, suffix):
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setSingleStep(0.01 if suffix == " MHz" else 0.00625)
        widget.setSuffix(suffix)
        widget.setEnabled(False)
        form.addRow(label, widget)
        self.config_widgets[key] = widget

    def _add_config_choice(self, form, key, label, choices):
        widget = QComboBox()
        widget.addItems(choices)
        widget.setEnabled(False)
        form.addRow(label, widget)
        self.config_widgets[key] = widget

    def _add_config_actions(self, layout):
        actions = QHBoxLayout()
        self.config_state = QLabel("Bağlantı bekleniyor · değerler okunmadan yazma kapalı")
        self.config_state.setObjectName("muted")
        actions.addWidget(self.config_state, 1)
        self.config_read_button = QPushButton("Mevcut ayarları oku")
        self.config_read_button.clicked.connect(self.read_configuration)
        actions.addWidget(self.config_read_button)
        self.config_update_button = QPushButton("Güncelle")
        self.config_update_button.setObjectName("primaryButton")
        self.config_update_button.setEnabled(False)
        self.config_update_button.clicked.connect(self.update_configuration)
        actions.addWidget(self.config_update_button)
        layout.addLayout(actions)

    def _build_protection_editor(self, layout):
        group = QGroupBox("PROTECTION LIMITS")
        form = QFormLayout(group)
        self._add_config_field(form, "oc_warn", "Output current warning · 4Ah", 0, 2046, 1, " A")
        self._add_config_field(form, "ocp_total", "Total over-current limit · ECh", 0, 254, 1, " A")
        self._add_config_field(form, "temp_warn", "Temperature warning · 51h", 0, 255, 0, " °C")
        otp_note = QLabel("MFR_VTEMP_OT_SET · EAh: VTEMP OTP cutoff register; raw field mapping and board sensor scaling are shown in All Settings.")
        otp_note.setObjectName("muted")
        otp_note.setWordWrap(True)
        form.addRow("Maximum temperature cutoff", otp_note)
        layout.addWidget(group)

    def _build_monitor_tab(self):
        tabs = QTabWidget()
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        actions = QHBoxLayout()
        title = QLabel("LIVE MONITOR")
        title.setObjectName("cardTitle")
        actions.addWidget(title)
        actions.addStretch(1)
        self.monitor_time = QLabel("No sample")
        self.monitor_time.setObjectName("muted")
        actions.addWidget(self.monitor_time)
        self.monitor_auto_checkbox = QCheckBox("Auto · 5 s")
        self.monitor_auto_checkbox.toggled.connect(self._toggle_monitor_timer)
        actions.addWidget(self.monitor_auto_checkbox)
        self.monitor_refresh_button = QPushButton("Refresh")
        self.monitor_refresh_button.setObjectName("primaryButton")
        self.monitor_refresh_button.clicked.connect(self.refresh_monitor)
        actions.addWidget(self.monitor_refresh_button)
        layout.addLayout(actions)

        top = QHBoxLayout()
        power_panel = QGroupBox("POWER STATE / FAULTS")
        power_layout = QVBoxLayout(power_panel)
        self.output_card = StatusCard("Power Good", "UNKNOWN", "STATUS_WORD · 79h bit 11")
        power_layout.addWidget(self.output_card)
        self.monitor_fault_indicators = {}
        fault_grid = QGridLayout()
        fault_flags = (
            ("VIN OV", 0x7C, 7), ("VIN UV", 0x7C, 4),
            ("VOUT OV", 0x7A, 7), ("VOUT UV", 0x7A, 4),
            ("OCP", 0x7B, 7), ("OC ALERT", 0x7B, 5),
            ("OTP", 0x7D, 7), ("OT ALERT", 0x7D, 6),
            ("OP ALERT", 0x7B, 0), ("UV ALERT", 0x7C, 5),
            ("COMMAND", 0x7E, 7), ("EEPROM", 0x7E, 4),
        )
        for index, (name, code, bit) in enumerate(fault_flags):
            indicator = QLabel(name + "  —")
            indicator.setObjectName("faultIndicator")
            self.monitor_fault_indicators[name] = (indicator, code, bit)
            fault_grid.addWidget(indicator, index // 2, index % 2)
        power_layout.addLayout(fault_grid)
        top.addWidget(power_panel, 1)

        metrics_panel = QGroupBox("TELEMETRY")
        metrics = QGridLayout(metrics_panel)
        self.monitor_cards = {}
        telemetry = (
            (0x88, "Input Voltage", "READ_VIN · 88h"),
            (0x97, "Input Power", "READ_PIN · 97h"),
            (0x8B, "Output Voltage", "READ_VOUT · 8Bh"),
            (0x96, "Output Power", "READ_POUT · 96h"),
            (0x8C, "Output Current", "READ_IOUT · 8Ch"),
            (0x8D, "Temperature", "READ_TEMPERATURE · 8Dh"),
            (0x95, "Efficiency", "READ_EFFICIENCY · 95h"),
        )
        for index, (code, name, note) in enumerate(telemetry):
            card = StatusCard(name, "—", note)
            card.value_label.setStyleSheet("font-size: 17pt; font-weight: 700;")
            self.monitor_cards[code] = card
            metrics.addWidget(card, index // 3, index % 3)
        top.addWidget(metrics_panel, 2)
        layout.addLayout(top, 1)

        note = QLabel("Values use MP2886A datasheet scales. Current and power resolution is read from MFR_SYS_CONFIG (44h), bit 3.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        tabs.addTab(page, "Telemetry")
        tabs.addTab(self._build_read_only_monitor_tab(), "Read-only registers")
        return tabs

    def _build_read_only_monitor_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        actions = QHBoxLayout()
        title = QLabel("DATASHEET READ-ONLY PAGE 0 REGISTERS")
        title.setObjectName("cardTitle")
        actions.addWidget(title)
        actions.addStretch(1)
        self.readonly_state = QLabel("Henüz okunmadı")
        self.readonly_state.setObjectName("muted")
        actions.addWidget(self.readonly_state)
        self.readonly_read_button = QPushButton("Read-only kayıtları oku")
        self.readonly_read_button.clicked.connect(self.read_readonly_registers)
        actions.addWidget(self.readonly_read_button)
        layout.addLayout(actions)
        self.readonly_table = self._create_table((
            ("command", "Command", 80),
            ("name", "Register", 220),
            ("width", "Bytes", 55),
            ("value", "Value", 105),
            ("meaning", "Datasheet interpretation", 480),
        ))
        self.readonly_row_by_code = {}
        for register in MONITOR_REGISTERS:
            row = self.readonly_table.rowCount()
            self.readonly_table.insertRow(row)
            self.readonly_row_by_code[register.code] = row
            self._put_table_row(
                self.readonly_table,
                (f"{register.code:02X}h", register.name, register.width, "—", description_for(register)),
                row,
            )
        layout.addWidget(self.readonly_table, 1)
        return page

    def read_readonly_registers(self, show_errors=True):
        try:
            address = self.target()
            page = self._read_page_zero_register(address, 0x00)
            if page != 0:
                raise ValueError(f"Read-only kayıtlar yalnızca PAGE 0'da okunur; cihaz PAGE={page:02X}h.")
            failures = []
            for index, register in enumerate(MONITOR_REGISTERS, start=1):
                row = self.readonly_row_by_code[register.code]
                try:
                    value = self._read_page_zero_register(address, register.code)
                    self._put_table_row(
                        self.readonly_table,
                        (f"{register.code:02X}h", register.name, register.width,
                         f"0x{value:0{register.width * 2}X}", interpretation_for(register, value)),
                        row,
                    )
                except Exception as error:
                    failures.append(register)
                    self._put_table_row(
                        self.readonly_table,
                        (f"{register.code:02X}h", register.name, register.width, "ERROR", str(error)),
                        row,
                    )
                self.statusBar().showMessage(f"Read-only kayıtlar okunuyor: {index}/{len(MONITOR_REGISTERS)}")
                QApplication.processEvents()
            self.readonly_state.setText(f"{len(MONITOR_REGISTERS) - len(failures)}/{len(MONITOR_REGISTERS)} okundu")
            self.log_message(f"Monitor read-only kayıtlar: {len(MONITOR_REGISTERS) - len(failures)}/{len(MONITOR_REGISTERS)} okundu.")
            if failures and show_errors:
                QMessageBox.warning(self, "Monitor kayıtları", f"{len(failures)} read-only register okunamadı.")
            return not failures
        except Exception as error:
            self.readonly_state.setText("Okuma başarısız")
            self.log_message("Read-only monitor read failed: " + str(error))
            if show_errors:
                QMessageBox.warning(self, "Monitor kayıtları okunamadı", str(error))
            return False

    def _toggle_monitor_timer(self, enabled):
        if enabled:
            self.monitor_timer.start()
            self.refresh_monitor()
        else:
            self.monitor_timer.stop()

    def _select_scanned_address(self, item):
        address = item.data(Qt.UserRole)
        if address is not None:
            self.address.setText(address)

    def _config_scale(self, scale, snapshot):
        if scale == "current":
            return 2.0 if snapshot[0x44] & 0x0008 else 1.0
        return scale

    def _set_config_enabled(self, enabled):
        for widget in self.config_widgets.values():
            widget.setEnabled(enabled)
        self.config_update_button.setEnabled(enabled)

    def read_configuration(self, show_errors=True):
        self._set_config_enabled(False)
        self.config_snapshot = None
        try:
            address = self.target()
            page = self._read_page_zero_register(address, 0x00)
            if page != 0:
                raise ValueError(f"Ayarlar için PAGE=00h gerekli; cihaz PAGE={page:02X}h. Sayfa değiştirilmedi.")
            snapshot = {code: self._read_page_zero_register(address, code) for code in CONFIG_READ_CODES if code != 0x00}
            snapshot[0x00] = page

            invalid = []
            for key, (code, mask, shift, scale, fixed_mask, fixed_value) in CONFIG_NUMERIC_FIELDS.items():
                raw = snapshot[code]
                if raw & fixed_mask != fixed_value:
                    invalid.append(f"{code:02X}h sabit/ayrılmış bit biçimi geçersiz")
                    continue
                unit_scale = self._config_scale(scale, snapshot)
                self.config_widgets[key].setValue(((raw & mask) >> shift) * unit_scale)

            for key, (code, mask, choices) in CONFIG_CHOICE_FIELDS.items():
                shift = _mask_shift(mask)
                choice_index = (snapshot[code] & mask) >> shift
                if choice_index >= len(choices):
                    invalid.append(f"{code:02X}h {key} değeri gösterilemiyor")
                else:
                    self.config_widgets[key].setCurrentIndex(choice_index)

            if invalid:
                raise ValueError("; ".join(invalid))
            self.config_snapshot = snapshot
            self._set_config_enabled(True)
            self.config_state.setText("PAGE 0 okundu · düzenlenebilir ayarlar hazır")
            self.log_message("MP2886A configuration read from PAGE 0.")
            return True
        except Exception as error:
            self.config_state.setText("Okuma başarısız · ayarlar yazmaya kapalı")
            self.log_message("Configuration read failed: " + str(error))
            if show_errors:
                QMessageBox.warning(self, "Ayarlar okunamadı", str(error))
            return False

    def update_configuration(self):
        try:
            if not getattr(self, "config_snapshot", None):
                raise ValueError("Önce cihazdaki mevcut ayarları oku.")
            address = self.target()
            page = self._read_page_zero_register(address, 0x00)
            if page != 0:
                raise ValueError(f"Yazma için PAGE=00h gerekli; cihaz PAGE={page:02X}h. Sayfa değiştirilmedi.")
            current = {code: self._read_page_zero_register(address, code) for code in CONFIG_READ_CODES if code != 0x00}
            current[0x00] = page

            desired = {}
            for key, (code, mask, shift, scale, fixed_mask, fixed_value) in CONFIG_NUMERIC_FIELDS.items():
                raw = current[code]
                if raw & fixed_mask != fixed_value:
                    raise ValueError(f"{code:02X}h formatı değişmiş veya geçersiz; yazma iptal edildi.")
                unit_scale = self._config_scale(scale, current)
                encoded = round(self.config_widgets[key].value() / unit_scale)
                if encoded < 0 or encoded > mask >> shift:
                    raise ValueError(f"{key}: değer register alanı dışında.")
                desired[code] = (desired.get(code, raw) & ~mask) | ((encoded << shift) & mask)

            for key, (code, mask, choices) in CONFIG_CHOICE_FIELDS.items():
                shift = _mask_shift(mask)
                encoded = self.config_widgets[key].currentIndex()
                if encoded >= len(choices):
                    raise ValueError(f"{key}: register değeri ayrılmış veya desteklenmiyor.")
                raw = current[code]
                desired[code] = (desired.get(code, raw) & ~mask) | ((encoded << shift) & mask)

            min_voltage = self.config_widgets["vmin"].value()
            max_voltage = self.config_widgets["vmax"].value()
            boot_voltage = self.config_widgets["vboot"].value()
            if min_voltage >= max_voltage:
                raise ValueError("VOUT minimum, VOUT maximum değerinden küçük olmalı.")
            if self.config_widgets["vid_control"].currentIndex() == 0 and not min_voltage <= boot_voltage <= max_voltage:
                raise ValueError("PWM-VID modunda boot voltage, VOUT min/max aralığında olmalı.")
            if self.config_widgets["vin_on"].value() <= self.config_widgets["vin_off"].value():
                raise ValueError("VIN_ON, VIN_OFF değerinden büyük olmalı.")

            changed_codes = [code for code, value in desired.items() if value != current[code]]
            if not changed_codes:
                self.config_state.setText("Değişiklik yok · cihaza yazılmadı")
                return

            summary = "\n".join(
                f"{REGISTERS_BY_CODE[code].name} ({code:02X}h): 0x{current[code]:04X} → 0x{desired[code]:04X}"
                for code in sorted(changed_codes)
            )
            answer = QMessageBox.warning(
                self,
                "MP2886A ayarlarını güncelle",
                "Yalnızca değişen register'lar çalışma belleğine yazılacak.\n"
                "Bu işlem çıkış davranışını değiştirebilir; EEPROM'a kaydetmez.\n\n" + summary,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

            for code in sorted(changed_codes):
                register = REGISTERS_BY_CODE[code]
                operation = "WW" if register.width == 2 else "WB"
                self.request(f"{operation} {address:02X} {code:02X} {desired[code]:04X}")
            for code in sorted(changed_codes):
                actual = self._read_page_zero_register(address, code)
                if actual != desired[code]:
                    raise RuntimeError(f"{code:02X}h readback uyuşmadı: 0x{actual:04X} != 0x{desired[code]:04X}")

            if not self.read_configuration(show_errors=False):
                raise RuntimeError("Yazma readback doğrulandı ancak ayarların tamamı yeniden okunamadı.")
            self.config_state.setText(f"Güncellendi ve doğrulandı · {len(changed_codes)} register")
            self.log_message("Configuration updated and readback verified; EEPROM unchanged.")
        except Exception as error:
            self._set_config_enabled(False)
            self.config_snapshot = None
            self.config_state.setText("Güncelleme başarısız · cihazı yeniden oku")
            self.log_message("Configuration update failed: " + str(error))
            QMessageBox.critical(self, "Ayar güncellenemedi", str(error))

    def read_input_parameters(self):
        return self.read_configuration()

    def refresh_monitor(self):
        if self.port is None:
            self.statusBar().showMessage("Connect the USB-I²C bridge to read live telemetry.", 4000)
            return
        self.monitor_refresh_button.setEnabled(False)
        try:
            address = self.target()
            page = self._read_page_zero_register(address, 0x00)
            if page != 0:
                raise ValueError(f"Monitor requires PAGE=00h; current PAGE={page:02X}h. Page was not changed.")

            status_values = {}
            for code in (0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E):
                try:
                    status_values[code] = self._read_page_zero_register(address, code)
                except Exception:
                    status_values[code] = None

            status_word = status_values.get(0x79)
            if status_word is None:
                self.output_card.set_value("READ ERROR", COLOR_ERROR)
                self.output_card.set_note("STATUS_WORD · 79h")
            else:
                pgood = bool(status_word & (1 << 11))
                self.output_card.set_value("POWER GOOD" if pgood else "NOT READY", COLOR_GOOD if pgood else COLOR_WARNING)
                self.output_card.set_note(f"STATUS_WORD = 0x{status_word:04X} · PGOOD bit 11 = {int(pgood)}")

            try:
                sys_config = self._read_page_zero_register(address, 0x44)
                total_current_half_resolution = bool(sys_config & (1 << 3))
                resolution_error = None
            except Exception as error:
                total_current_half_resolution = None
                resolution_error = str(error)

            for name, (indicator, code, bit) in self.monitor_fault_indicators.items():
                value = status_values.get(code)
                active = value is not None and bool(value & (1 << bit))
                indicator.setText(f"{name}  {'ACTIVE' if active else 'CLEAR' if value is not None else 'N/A'}")
                indicator.setStyleSheet(
                    "color: #ff9ba0; background: #382326; border: 1px solid #684047; border-radius: 4px; padding: 6px 8px; font-weight: 700;"
                    if active else
                    "color: #63d8b3; background: #20332d; border: 1px solid #315244; border-radius: 4px; padding: 6px 8px; font-weight: 700;"
                    if value is not None else
                    "color: #f0bc65; background: #383024; border: 1px solid #5d4b30; border-radius: 4px; padding: 6px 8px; font-weight: 700;"
                )

            for code, card in self.monitor_cards.items():
                register = REGISTERS_BY_CODE[code]
                try:
                    value = self._read_page_zero_register(address, code)
                except Exception as error:
                    card.set_value("READ ERROR", COLOR_ERROR)
                    card.set_note(str(error))
                    continue
                if code in (0x8C, 0x96, 0x97) and total_current_half_resolution is None:
                    card.set_value(f"0x{value:0{register.width * 2}X}", COLOR_WARNING)
                    card.set_note(f"{register.name} · resolution unavailable (44h bit 3): {resolution_error}")
                    continue
                try:
                    display, detail = telemetry_display_for(code, value, total_current_half_resolution)
                    card.set_value(display)
                    card.set_note(detail)
                except ValueError as error:
                    card.set_value("FORMAT ERROR", COLOR_ERROR)
                    card.set_note(str(error))

            self.monitor_time.setText(datetime.now().astimezone().strftime("Updated %H:%M:%S"))
            self.statusBar().showMessage("Live telemetry refreshed", 3000)
        except Exception as error:
            self.statusBar().showMessage("Monitor refresh failed: " + str(error), 6000)
        finally:
            self.monitor_refresh_button.setEnabled(True)

    def _build_register_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(8)

        read_group = QGroupBox("REGISTER İŞLEMİ")
        read_layout = QGridLayout(read_group)
        read_layout.setContentsMargins(8, 9, 8, 7)
        read_layout.setHorizontalSpacing(7)
        read_layout.setVerticalSpacing(6)
        read_layout.addWidget(QLabel("Komut"), 0, 0)
        self.command = QLineEdit("00")
        self.command.setMaximumWidth(72)
        read_layout.addWidget(QLabel("0x"), 0, 1)
        read_layout.addWidget(self.command, 0, 2)
        read_layout.addWidget(QLabel("Veri"), 0, 3)
        self.data = QLineEdit("00")
        self.data.setMaximumWidth(90)
        read_layout.addWidget(QLabel("0x"), 0, 4)
        read_layout.addWidget(self.data, 0, 5)
        self.width_box = QComboBox()
        self.width_box.addItems(("Byte · 8 bit", "Word · 16 bit"))
        self.width_box.setCurrentIndex(1)
        self.width_box.setMaximumWidth(145)
        read_layout.addWidget(self.width_box, 0, 6)
        self.read_button = QPushButton("Oku")
        self.read_button.setObjectName("primaryButton")
        self.read_button.clicked.connect(self.read_value)
        read_layout.addWidget(self.read_button, 0, 7)
        self.write_button = QPushButton("Yaz…")
        self.write_button.setObjectName("dangerButton")
        self.write_button.clicked.connect(self.write_value)
        read_layout.addWidget(self.write_button, 0, 8)
        self.pec_checkbox = QCheckBox("SMBus PEC")
        self.pec_checkbox.toggled.connect(self.set_pec)
        read_layout.addWidget(self.pec_checkbox, 0, 9)

        read_layout.addWidget(QLabel("Datasheet kaydı"), 1, 0, 1, 2)
        self.register_box = QComboBox()
        self.register_box.addItems([f"{register.code:02X}h  {register.name} ({register.access})" for register in PAGE0_REGISTERS])
        self.register_box.setCurrentIndex(-1)
        self.register_box.currentIndexChanged.connect(self.select_register)
        read_layout.addWidget(self.register_box, 1, 2, 1, 5)
        self.read_all_button = QPushButton("Page 0 oku")
        self.read_all_button.clicked.connect(self.read_all_registers)
        read_layout.addWidget(self.read_all_button, 1, 7)
        self.pgood_button = QPushButton("VR / PGOOD")
        self.pgood_button.clicked.connect(self.read_pgood)
        read_layout.addWidget(self.pgood_button, 1, 8)
        layout.addWidget(read_group)

        table_header = QHBoxLayout()
        label = QLabel("REGISTER OKUMALARI")
        label.setObjectName("cardTitle")
        table_header.addWidget(label)
        table_header.addStretch(1)
        self.profile_save_button = QPushButton("Profili kaydet…")
        self.profile_save_button.clicked.connect(self.save_profile)
        table_header.addWidget(self.profile_save_button)
        self.profile_write_button = QPushButton("Dosyadan yaz…")
        self.profile_write_button.setObjectName("dangerButton")
        self.profile_write_button.clicked.connect(self.write_profile_from_file)
        table_header.addWidget(self.profile_write_button)
        clear_button = QPushButton("Listeyi temizle")
        clear_button.clicked.connect(lambda: self.clear_table(self.register_table))
        table_header.addWidget(clear_button)
        layout.addLayout(table_header)
        self.register_table = self._create_table((
            ("code", "Komut", 65),
            ("name", "Register", 170),
            ("access", "Erişim", 60),
            ("bytes", "Byte", 48),
            ("value", "Değer", 100),
            ("meaning", "Açıklama", 340),
        ))
        layout.addWidget(self.register_table, 1)
        return page

    @staticmethod
    def _settings_category(register):
        name = register.name
        if "APS" in name or "PHASE" in name or "LOW_PHASE" in name:
            return "Faz ve faz atlama"
        if name.startswith("VIN_") or "VIN_" in name or "VIN_" in name:
            return "Giriş gerilimi"
        if "OCP" in name or "OVP" in name or "UVP" in name or "WARN_LIMIT" in name or "OT_" in name or "TEMP" in name or "T_ALERT" in name:
            return "Akım / sıcaklık / koruma"
        if name.startswith("VOUT_") or name.startswith("POWER_GOOD_"):
            return "Çıkış gerilimi / Power Good"
        if "PWMVID" in name or "VBOOT" in name or "VID" in name or "PARM_" in name or "_SR" in name:
            return "PWM-VID / açılış / slew"
        if "SLOPE" in name or "LOOP" in name or "DROOP" in name or "OSR" in name or "DC_" in name:
            return "Regülasyon / kompanzasyon"
        if "GAIN" in name or "OFFSET" in name or "SENSE" in name or "CS_" in name or "DIV" in name or "CAL_" in name:
            return "Ölçüm / kalibrasyon"
        if "CONFIG" in name or "EEPROM" in name or "REPORT" in name or "PWD" in name or "PROTECT" in name or "PMBUS" in name or name in {"OPERATION", "WRITE_PROTECT"}:
            return "Sistem / PMBus kontrolü"
        if "FS" in name or "FREQ" in name or "PWM_LIMIT" in name:
            return "Switching / PWM"
        return "Diğer MPS ayarları"

    def _build_settings_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(8)

        heading = QHBoxLayout()
        title = QLabel("MP2886A · TÜM PAGE 0 AYARLARI")
        title.setObjectName("cardTitle")
        heading.addWidget(title)
        heading.addStretch(1)
        self.settings_search = QLineEdit()
        self.settings_search.setPlaceholderText("Ayar / register / komut ara…")
        self.settings_search.setMaximumWidth(260)
        heading.addWidget(self.settings_search)
        layout.addLayout(heading)

        note = QLabel(
            "Ayarlar datasheet işlev gruplarına ayrılmıştır. Ölçeği doğrulanmış alanlar fiziksel birimle; "
            "diğer üretici alanları decimal kodla gösterilir. Bilinen modlar seçenek olarak sunulur."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        actions = QHBoxLayout()
        self.settings_state = QLabel("Bağlantı bekleniyor · register değerleri okunmadı")
        self.settings_state.setObjectName("muted")
        actions.addWidget(self.settings_state, 1)
        self.settings_read_button = QPushButton("Tüm ayarları oku")
        self.settings_read_button.clicked.connect(self.read_all_settings)
        actions.addWidget(self.settings_read_button)
        self.settings_update_button = QPushButton("Değişenleri yaz…")
        self.settings_update_button.setObjectName("primaryButton")
        self.settings_update_button.setEnabled(False)
        self.settings_update_button.clicked.connect(self.update_all_settings)
        actions.addWidget(self.settings_update_button)
        layout.addLayout(actions)

        self.settings_category_tabs = QTabWidget()
        self.settings_widgets = {}
        self.settings_field_rows = {}
        self.settings_info_labels = {}
        self.settings_composite_fields = {}
        self.settings_categories = sorted({self._settings_category(register) for register in SETTINGS_REGISTERS})
        self.settings_category_codes = {category: [] for category in self.settings_categories}
        for category in self.settings_categories:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            form = QFormLayout(content)
            form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            form.setHorizontalSpacing(14)
            form.setVerticalSpacing(8)
            for register in SETTINGS_REGISTERS:
                if self._settings_category(register) != category:
                    continue
                value_row = QWidget()
                value_layout = QHBoxLayout(value_row)
                value_layout.setContentsMargins(0, 0, 0, 0)
                value_layout.setSpacing(10)
                editor = self._make_settings_editor(register)
                editor.setEnabled(False)
                info = QLabel(description_for(register))
                info.setObjectName("muted")
                info.setWordWrap(True)
                value_layout.addWidget(editor)
                value_layout.addWidget(info, 1)
                label = f"{register.name} · {register.code:02X}h · {register.width} byte"
                form.addRow(label, value_row)
                self.settings_widgets[register.code] = editor
                self.settings_field_rows[register.code] = value_row
                self.settings_info_labels[register.code] = info
                self.settings_category_codes[category].append(register.code)
            form.addRow(QWidget())
            scroll.setWidget(content)
            self.settings_category_tabs.addTab(scroll, category)
        self.settings_category_tabs.currentChanged.connect(self._filter_settings)
        self.settings_search.textChanged.connect(self._filter_settings)
        layout.addWidget(self.settings_category_tabs, 1)
        self.settings_snapshot = None
        return page

    def _make_settings_editor(self, register):
        code = register.code
        if code in (0xE1, 0xE2):
            editor = QWidget()
            fields = QHBoxLayout(editor)
            fields.setContentsMargins(0, 0, 0, 0)
            fields.setSpacing(8)
            controls = {}
            if code == 0xE1:
                phase = QComboBox()
                for index, name in enumerate(CONFIG_CHOICE_FIELDS["phase_count"][2]):
                    phase.addItem(name, index)
                voltage_mode = QComboBox()
                voltage_mode.addItem("PWM-VID", 0)
                voltage_mode.addItem("PMBus", 1)
                controls.update(phase=phase, voltage_mode=voltage_mode)
                fields.addWidget(QLabel("Faz"))
                fields.addWidget(phase)
                fields.addWidget(QLabel("Gerilim"))
                fields.addWidget(voltage_mode)
                for key, text in (("aps", "APS"), ("osr", "OSR"), ("balance", "Akım dengeleme")):
                    checkbox = QCheckBox(text)
                    controls[key] = checkbox
                    fields.addWidget(checkbox)
            else:
                slew = QComboBox()
                slew.addItem("Linear", 0)
                slew.addItem("R-C filter", 1)
                boot_source = QComboBox()
                boot_source.addItem("VOUT_COMMAND", 0)
                boot_source.addItem("TSNS/BOOT pini", 1)
                controls.update(slew=slew, boot_source=boot_source)
                fields.addWidget(QLabel("Slew"))
                fields.addWidget(slew)
                fields.addWidget(QLabel("Boot kaynağı"))
                fields.addWidget(boot_source)
            fields.addStretch(1)
            self.settings_composite_fields[code] = controls
            return editor

        if code == 0x01:
            editor = QComboBox()
            for value, label in (
                (0x00, "Hi-Z off"),
                (0x40, "Soft off"),
                (0x80, "Normal on"),
                (0x90, "Margin low"),
                (0xA0, "Margin high"),
            ):
                editor.addItem(label, value)
            return editor

        if code in (0x1F, 0x21, 0x24, 0x25, 0x26, 0x5E, 0x5F, 0xBB):
            editor = QDoubleSpinBox()
            editor.setRange(0.0, 3.19375)
            editor.setDecimals(5)
            editor.setSingleStep(0.00625)
            editor.setSuffix(" V")
            return editor
        if code == 0x23:
            editor = QDoubleSpinBox()
            editor.setRange(-800.0, 793.75)
            editor.setDecimals(2)
            editor.setSingleStep(6.25)
            editor.setSuffix(" mV")
            return editor
        if code in (0x35, 0x36, 0x55, 0x58):
            editor = QDoubleSpinBox()
            editor.setRange(0.0, 31.875)
            editor.setDecimals(3)
            editor.setSingleStep(0.125)
            editor.setSuffix(" V")
            return editor
        if code == 0xBD:
            editor = QDoubleSpinBox()
            editor.setRange(0.0, 5.11)
            editor.setDecimals(2)
            editor.setSingleStep(0.01)
            editor.setSuffix(" MHz")
            return editor
        if code in (0x4A, 0xEC):
            editor = QDoubleSpinBox()
            editor.setRange(0.0, 2046.0 if code == 0x4A else 254.0)
            editor.setDecimals(1)
            editor.setSingleStep(1.0)
            editor.setSuffix(" A")
            return editor
        if code == 0x51:
            editor = QDoubleSpinBox()
            editor.setRange(0.0, 255.0)
            editor.setDecimals(0)
            editor.setSingleStep(1.0)
            editor.setSuffix(" °C")
            return editor

        editor = QSpinBox()
        editor.setRange(0, (1 << (register.width * 8)) - 1)
        editor.setMaximumWidth(180)
        editor.setToolTip("Decimal register code; physical scale/bit meanings are not verified.")
        return editor

    def _settings_value_from_raw(self, register, raw):
        code = register.code
        if code in self.settings_composite_fields:
            controls = self.settings_composite_fields[code]
            if code == 0xE1:
                controls["phase"].setCurrentIndex(raw & 0x07)
                controls["voltage_mode"].setCurrentIndex(1 if raw & 0x10 else 0)
                controls["aps"].setChecked(bool(raw & 0x20))
                controls["osr"].setChecked(bool(raw & 0x40))
                controls["balance"].setChecked(bool(raw & 0x80))
            else:
                controls["slew"].setCurrentIndex(raw & 0x01)
                controls["boot_source"].setCurrentIndex(1 if raw & 0x04 else 0)
            return
        editor = self.settings_widgets[code]
        if code == 0x01:
            index = editor.findData(raw)
            if index < 0:
                editor.addItem("Diğer mevcut mod (değişmeden bırak)", raw)
                index = editor.count() - 1
            editor.setCurrentIndex(index)
        elif code in (0x1F, 0x21, 0x24, 0x25, 0x26, 0x5E, 0x5F, 0xBB):
            editor.setValue((raw & 0x01FF) * 0.00625)
        elif code == 0x23:
            value = raw & 0xFF
            if value & 0x80:
                value -= 0x100
            editor.setValue(value * 6.25)
        elif code in (0x35, 0x36, 0x55, 0x58):
            editor.setValue((raw & 0xFF) * 0.125)
        elif code == 0xBD:
            editor.setValue((raw & 0x01FF) * 0.01)
        elif code in (0x4A, 0xEC):
            if not self.settings_snapshot or 0x44 not in self.settings_snapshot:
                raise ValueError("Akım çözünürlüğü için MFR_SYS_CONFIG (44h) okunamadı; akım limiti düzenlenemez.")
            current_scale = self._settings_current_scale()
            mask = 0x03FF if code == 0x4A else 0x007F
            editor.setRange(0.0, (mask * current_scale))
            editor.setSingleStep(current_scale)
            editor.setValue((raw & mask) * current_scale)
        elif code == 0x51:
            editor.setValue(raw & 0xFF)
        else:
            editor.setValue(raw)

    def _settings_raw_from_editor(self, register, base_value):
        code = register.code
        if code in self.settings_composite_fields:
            controls = self.settings_composite_fields[code]
            if code == 0xE1:
                fields = (
                    (0x0007, controls["phase"].currentData()),
                    (0x0010, controls["voltage_mode"].currentData()),
                    (0x0020, int(controls["aps"].isChecked())),
                    (0x0040, int(controls["osr"].isChecked())),
                    (0x0080, int(controls["balance"].isChecked())),
                )
            else:
                fields = (
                    (0x0001, controls["slew"].currentData()),
                    (0x0004, int(controls["boot_source"].currentData()) << 2),
                )
            value = base_value
            for mask, field_value in fields:
                value = (value & ~mask) | (int(field_value) << (mask & -mask).bit_length() - 1)
            return value

        editor = self.settings_widgets[code]
        if code == 0x01:
            return int(editor.currentData())
        if code in (0x1F, 0x21, 0x24, 0x25, 0x26, 0x5E, 0x5F, 0xBB):
            return (base_value & ~0x01FF) | round(editor.value() / 0.00625)
        if code == 0x23:
            encoded = round(editor.value() / 6.25) & 0xFF
            return (base_value & ~0x00FF) | encoded
        if code in (0x35, 0x36, 0x55, 0x58):
            return 0xE800 | round(editor.value() / 0.125)
        if code == 0xBD:
            return (base_value & ~0x01FF) | round(editor.value() / 0.01)
        if code in (0x4A, 0xEC):
            current_scale = self._settings_current_scale()
            mask = 0x03FF if code == 0x4A else 0x007F
            encoded = round(editor.value() / current_scale)
            if encoded > mask:
                raise ValueError(f"{register.name}: seçilen akım limiti mevcut çözünürlükte register sınırını aşıyor.")
            return (base_value & ~mask) | encoded
        if code == 0x51:
            return (base_value & ~0x00FF) | round(editor.value())
        return editor.value()

    def _settings_current_scale(self, config_value=None):
        if config_value is None:
            snapshot = self.settings_snapshot or {}
            config_value = snapshot.get(0x44, 0)
            config_editor = self.settings_widgets.get(0x44)
            if config_editor is not None and 0x44 in snapshot:
                config_value = config_editor.value()
        return 2.0 if config_value & 0x0008 else 1.0

    def _settings_display_value(self, register, raw, config_value=None):
        code = register.code
        if code == 0x01:
            editor = self.settings_widgets[code]
            index = editor.findData(raw)
            return editor.itemText(index) if index >= 0 else str(raw)
        if code in (0x1F, 0x21, 0x24, 0x25, 0x26, 0x5E, 0x5F, 0xBB):
            return f"{(raw & 0x01FF) * 0.00625:.5f} V"
        if code == 0x23:
            value = raw & 0xFF
            if value & 0x80:
                value -= 0x100
            return f"{value * 6.25:.2f} mV"
        if code in (0x35, 0x36, 0x55, 0x58):
            return f"{(raw & 0xFF) * 0.125:.3f} V"
        if code == 0xBD:
            return f"{(raw & 0x01FF) * 0.01:.2f} MHz"
        if code in (0x4A, 0xEC):
            scale = self._settings_current_scale(config_value)
            mask = 0x03FF if code == 0x4A else 0x007F
            return f"{(raw & mask) * scale:g} A"
        if code == 0x51:
            return f"{raw & 0xFF} °C"
        if code in self.settings_composite_fields:
            return interpretation_for(register, raw)
        return str(raw)

    def _filter_settings(self):
        query = self.settings_search.text().strip().casefold()
        visible_by_category = []
        for category_index, category in enumerate(self.settings_categories):
            visible_codes = []
            for code in self.settings_category_codes[category]:
                register = REGISTERS_BY_CODE[code]
                text = f"{register.code:02X}h {register.name} {description_for(register)}".casefold()
                visible = not query or query in text
                self.settings_field_rows[code].setVisible(visible)
                if visible:
                    visible_codes.append(code)
            visible_by_category.append(bool(visible_codes))
            self.settings_category_tabs.setTabVisible(category_index, bool(visible_codes))
        if self.settings_categories and not visible_by_category[self.settings_category_tabs.currentIndex()]:
            for index, has_visible in enumerate(visible_by_category):
                if has_visible:
                    self.settings_category_tabs.setCurrentIndex(index)
                    break

    def _set_settings_editing_enabled(self, enabled):
        self.settings_update_button.setEnabled(bool(enabled and self.settings_snapshot))
        for code, editor in self.settings_widgets.items():
            editor.setEnabled(bool(enabled and self.settings_snapshot and code in self.settings_snapshot))

    def _set_settings_value(self, register, value, editable=False):
        editor = self.settings_widgets[register.code]
        self._settings_value_from_raw(register, value)
        editor.setEnabled(editable)
        self.settings_info_labels[register.code].setText(interpretation_for(register, value))

    def read_all_settings(self, show_errors=True):
        self.settings_snapshot = None
        self._set_settings_editing_enabled(False)
        try:
            address = self.target()
            page = self._read_page_zero_register(address, 0x00)
            if page != 0:
                raise ValueError(f"Ayarlar yalnızca PAGE 0'da okunur; cihaz PAGE={page:02X}h. Sayfa değiştirilmedi.")

            snapshot = {}
            self.settings_snapshot = snapshot
            failures = []
            total = len(SETTINGS_REGISTERS)
            for index, register in enumerate(SETTINGS_REGISTERS, start=1):
                try:
                    value = self._read_page_zero_register(address, register.code)
                    snapshot[register.code] = value
                    self._set_settings_value(register, value, editable=True)
                except Exception as error:
                    snapshot.pop(register.code, None)
                    failures.append((register, str(error)))
                    self.settings_widgets[register.code].setToolTip(str(error))
                    self.settings_info_labels[register.code].setText("Okuma hatası: " + str(error))
                    self.settings_widgets[register.code].setEnabled(False)
                self.statusBar().showMessage(f"Ayarlar okunuyor: {index}/{total}")
                QApplication.processEvents()

            self.settings_snapshot = snapshot
            self._set_settings_editing_enabled(True)
            self.settings_state.setText(f"{len(snapshot)}/{total} register okundu · {len(failures)} hata")
            self.log_message(f"Ayar editörü PAGE 0: {len(snapshot)}/{total} r/w kayıt okundu; {len(failures)} hata.")
            if failures and show_errors:
                QMessageBox.warning(self, "Ayar okuma tamamlandı", f"{len(snapshot)} kayıt okundu, {len(failures)} okunamadı. Okunan satırlar düzenlenebilir.")
            return not failures
        except Exception as error:
            self.settings_snapshot = None
            self._set_settings_editing_enabled(False)
            self.settings_state.setText("Okuma başarısız · yazma kapalı")
            self.log_message("Full settings read failed: " + str(error))
            if show_errors:
                QMessageBox.warning(self, "Ayarlar okunamadı", str(error))
            return False

    def update_all_settings(self):
        try:
            if not self.settings_snapshot:
                raise ValueError("Önce tüm ayarları cihazdan oku.")
            address = self.target()
            page = self._read_page_zero_register(address, 0x00)
            if page != 0:
                raise ValueError(f"Yazma yalnızca PAGE 0'da yapılır; cihaz PAGE={page:02X}h. Hiçbir register yazılmadı.")

            changes = []
            for register in SETTINGS_REGISTERS:
                if register.code not in self.settings_snapshot:
                    continue
                value = self._settings_raw_from_editor(register, self.settings_snapshot[register.code])
                if value != self.settings_snapshot[register.code]:
                    live = self._read_page_zero_register(address, register.code)
                    if live != self.settings_snapshot[register.code]:
                        raise RuntimeError(f"{register.code:02X}h cihazdaki değer okuma sonrasında değişmiş; yeniden oku.")
                    changes.append((register, value))

            if not changes:
                self.settings_state.setText("Değişiklik yok · cihaza yazılmadı")
                return
            summary = "\n".join(
                f"{register.name}: {self._settings_display_value(register, self.settings_snapshot[register.code], self.settings_snapshot.get(0x44))} → {self._settings_display_value(register, value, self.settings_widgets[0x44].value() if 0x44 in self.settings_widgets else None)}"
                for register, value in changes[:15]
            )
            if len(changes) > 15:
                summary += f"\n… ve {len(changes) - 15} başka register"
            answer = QMessageBox.warning(
                self,
                "Register değişikliklerini uygula",
                f"{len(changes)} değişen PAGE 0 register'ı yazılıp geri okunacak.\n"
                "Bazı MPS alanları doğrudan PWM, koruma, EEPROM veya adres davranışını etkileyebilir. "
                "İşlem EEPROM'a otomatik kaydetmez.\n\n" + summary,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

            changes.sort(key=lambda item: item[0].code == 0xBE)
            verified = []
            for register, value in changes:
                operation = "WW" if register.width == 2 else "WB"
                self.request(f"{operation} {address:02X} {register.code:02X} {value:0{register.width * 2}X}")
                read_address = address
                if register.code == 0xBE and value & 0x80:
                    read_address = value & 0x7F
                    self.address.setText(f"{read_address:02X}")
                    self.last_scan_addresses = []
                actual = self._read_page_zero_register(read_address, register.code)
                if actual != value:
                    raise RuntimeError(f"{register.code:02X}h readback uyuşmadı: 0x{actual:0{register.width * 2}X} != 0x{value:0{register.width * 2}X}")
                verified.append((register, value))

            self.settings_snapshot.update({register.code: value for register, value in verified})
            for register, value in verified:
                self._set_settings_value(register, value, editable=True)
            self.settings_state.setText(f"{len(verified)} register yazıldı ve geri okundu · EEPROM değişmedi")
            self.log_message(f"All Settings: {len(verified)} değişen register yazıldı ve readback doğrulandı.")
        except Exception as error:
            self._set_settings_editing_enabled(False)
            self.settings_snapshot = None
            self.settings_state.setText("Güncelleme başarısız/yarım kalmış olabilir · önce yeniden oku")
            self.log_message("All settings update failed: " + str(error))
            QMessageBox.critical(self, "Ayar güncelleme hatası", str(error))

    def _build_diagnostics_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(8)
        actions = QHBoxLayout()
        title = QLabel("PWM / HATA DURUMU")
        title.setObjectName("cardTitle")
        actions.addWidget(title)
        actions.addStretch(1)
        self.fault_button = QPushButton("Teşhisi çalıştır")
        self.fault_button.setObjectName("primaryButton")
        self.fault_button.clicked.connect(self.read_faults)
        actions.addWidget(self.fault_button)
        self.clear_faults_button = QPushButton("Hata bayraklarını temizle…")
        self.clear_faults_button.setObjectName("dangerButton")
        self.clear_faults_button.clicked.connect(self.clear_faults)
        actions.addWidget(self.clear_faults_button)
        clear_button = QPushButton("Listeyi temizle")
        clear_button.clicked.connect(lambda: self.clear_table(self.diagnostic_table))
        actions.addWidget(clear_button)
        layout.addLayout(actions)
        self.fault_summary = QLabel("Teşhis henüz çalıştırılmadı.")
        self.fault_summary.setObjectName("faultIndicator")
        self.fault_summary.setWordWrap(True)
        layout.addWidget(self.fault_summary)
        self._build_protection_editor(layout)

        splitter = QSplitter(Qt.Vertical)
        self.diagnostic_table = self._create_table((
            ("code", "Komut", 70),
            ("name", "Teşhis kaydı", 200),
            ("value", "Değer", 100),
            ("detail", "Açıklama", 500),
        ))
        splitter.addWidget(self.diagnostic_table)
        self.fault_report = QPlainTextEdit()
        self.fault_report.setReadOnly(True)
        self.fault_report.setPlaceholderText("Teşhis raporu burada görüntülenir.")
        splitter.addWidget(self.fault_report)
        splitter.setSizes([300, 220])
        layout.addWidget(splitter, 1)
        return page

    def _build_eeprom_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        warning = QLabel(
            "EEPROM işlemleri cihazın kalıcı profilini değiştirebilir. "
            "Yalnızca kartına ait doğrulanmış yapılandırmayla devam et."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(f"color: {COLOR_WARNING}; font-weight: 600; padding: 5px;")
        layout.addWidget(warning)

        restore_group = QGroupBox("RESTORE_USER_ALL · 16h")
        restore_layout = QHBoxLayout(restore_group)
        restore_layout.addWidget(QLabel("EEPROM’daki profili çalışma belleğine yükler."), 1)
        restore_button = QPushButton("EEPROM’dan geri yükle…")
        restore_button.setObjectName("dangerButton")
        restore_button.clicked.connect(self.restore_user_all)
        restore_layout.addWidget(restore_button)
        layout.addWidget(restore_group)

        store_group = QGroupBox("STORE_USER_ALL · 15h")
        store_layout = QHBoxLayout(store_group)
        store_layout.addWidget(QLabel("Çalışma belleğindeki ayarları EEPROM’a kalıcı kaydeder."), 1)
        store_button = QPushButton("EEPROM’a kaydet…")
        store_button.setObjectName("dangerButton")
        store_button.clicked.connect(self.store_user_all)
        store_layout.addWidget(store_button)
        layout.addWidget(store_group)
        layout.addStretch(1)
        return page

    @staticmethod
    def _create_table(columns):
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels([column[1] for column in columns])
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(25)
        table.setShowGrid(False)
        header = table.horizontalHeader()
        for index, (_, _, width) in enumerate(columns):
            header.resizeSection(index, width)
        header.setStretchLastSection(True)
        return table

    def log_message(self, message):
        self.log.appendPlainText(f"{datetime.now():%H:%M:%S}  {message}")
        self.statusBar().showMessage(message, 6000)

    def clear_log(self):
        self.log.clear()
        self.statusBar().showMessage("İşlem geçmişi temizlendi", 3000)

    def clear_table(self, table):
        rows = table.rowCount()
        table.setRowCount(0)
        self.log_message(f"Liste temizlendi ({rows} satır).")

    def refresh_ports(self):
        selected = self.port_box.currentText()
        ports = [port.device for port in list_ports.comports()]
        self.port_box.clear()
        self.port_box.addItems(ports)
        if selected in ports:
            self.port_box.setCurrentText(selected)
        elif ports:
            self.port_box.setCurrentIndex(0)
        if not ports:
            self.statusBar().showMessage("Seri port bulunamadı · ESP32-C3 bağlantısını kontrol et")

    def toggle_connection(self):
        if self.port is not None:
            self.close_port()
            return
        port_name = self.port_box.currentText()
        if not port_name:
            QMessageBox.warning(self, "Seri port yok", "ESP32-C3 seri portunu seç.")
            return
        try:
            self.port = serial.Serial(port_name, 115200, timeout=0.25, write_timeout=3)
            while self.port.readline():
                pass
            self.port.timeout = 3
            self.port.reset_input_buffer()
            reply = self.request("PING")
            if not reply.startswith("OK MP2886_BRIDGE"):
                raise RuntimeError("ESP32 bridge yanıt vermedi: " + reply)
            self.pec_supported = reply.endswith(" 2")
            if self.pec_supported:
                self.pec_checkbox.setEnabled(True)
                self.request("PEC ON" if self.pec_checkbox.isChecked() else "PEC OFF")
                self.pec_card.set_value("Açık" if self.pec_checkbox.isChecked() else "Kapalı", COLOR_WARNING)
                self.pec_card.set_note("CRC-8 · polynomial 07h")
            else:
                self.pec_checkbox.setChecked(False)
                self.pec_checkbox.setEnabled(False)
                self.pec_card.set_value("Firmware eski", COLOR_WARNING)
                self.pec_card.set_note("PEC için bridge v2 gerekli")
            self.connect_button.setText("Bağlantıyı kes")
            self.connect_button.setObjectName("dangerButton")
            self.connect_button.style().unpolish(self.connect_button)
            self.connect_button.style().polish(self.connect_button)
            self.connection_badge.setText("●  BRIDGE ONLINE")
            self.connection_badge.setStyleSheet(f"color: {COLOR_GOOD}; font-weight: 700; padding: 8px 12px;")
            self.bridge_card.set_value("Bağlı", COLOR_GOOD)
            self.bridge_card.set_note(port_name)
            self.target_card.set_value("Taranmadı")
            self.log_message("ESP32-C3 bridge bağlandı.")
            self.read_configuration(show_errors=False)
            self.read_all_settings(show_errors=False)
            self.read_readonly_registers(show_errors=False)
        except Exception as error:
            self.close_port()
            QMessageBox.critical(self, "Bağlantı hatası", str(error))

    def close_port(self):
        self.monitor_timer.stop()
        self.monitor_auto_checkbox.setChecked(False)
        if hasattr(self, "config_widgets"):
            self._set_config_enabled(False)
            self.config_snapshot = None
            self.config_state.setText("Bağlantı bekleniyor · değerler okunmadan yazma kapalı")
        if hasattr(self, "settings_table"):
            self.settings_snapshot = None
            self._set_settings_editing_enabled(False)
            self.settings_state.setText("Bağlantı bekleniyor · register değerleri okunmadı")
        if self.port is not None:
            self.port.close()
            self.port = None
        self.connect_button.setText("Bağlan")
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.style().unpolish(self.connect_button)
        self.connect_button.style().polish(self.connect_button)
        self.connection_badge.setText("●  BRIDGE OFFLINE")
        self.connection_badge.setStyleSheet(f"color: {COLOR_ERROR}; font-weight: 700; padding: 8px 12px;")
        self.bridge_card.set_value("Bağlı değil", COLOR_ERROR)
        self.bridge_card.set_note("Seri bağlantı bekleniyor")
        self.target_card.set_value("Taranmadı")
        self.last_scan_addresses = []
        self.pec_supported = False
        self.pec_checkbox.setEnabled(True)

    def closeEvent(self, event):
        self.close_port()
        event.accept()

    def request(self, command):
        if self.port is None:
            raise RuntimeError("Önce ESP32-C3 bridge’e bağlan.")
        self.port.reset_input_buffer()
        self.port.write((command + "\n").encode("ascii"))
        response = self.port.readline().decode("ascii", errors="replace").strip()
        if not response:
            raise TimeoutError("ESP32 yanıt vermedi.")
        if response.startswith("ERR"):
            raise RuntimeError(response)
        return response

    @staticmethod
    def parse_hex(field, label, maximum):
        try:
            value = int(field.text().strip().lower().removeprefix("0x"), 16)
        except ValueError as error:
            raise ValueError(label + " hexadecimal olmalı.") from error
        if value < 0 or value > maximum:
            raise ValueError(label + " aralık dışında.")
        return value

    def target(self):
        address = self.parse_hex(self.address, "Adres", 0x77)
        if address < 0x03:
            raise ValueError("7-bit adres 03h ile 77h arasında olmalı.")
        if self.last_scan_addresses and f"{address:02X}" not in self.last_scan_addresses:
            found = ", ".join("0x" + item for item in self.last_scan_addresses)
            raise ValueError(
                f"Seçili hedef 0x{address:02X} son I²C taramasında yanıt vermedi. "
                f"Yanıt veren adresler: {found}."
            )
        return address

    def scan_bus(self):
        try:
            response = self.request("SCAN")
            devices = response[3:] if response.startswith("OK ") else response
            addresses = [item.strip().upper().removeprefix("0X") for item in devices.split(",") if item.strip() and item.strip() != "NONE"]
            self.last_scan_addresses = addresses
            self.device_list.clear()
            for value in addresses:
                item = QListWidgetItem(f"0x{value}")
                item.setData(Qt.UserRole, value)
                self.device_list.addItem(item)
            if addresses:
                selected = self.address.text().strip().upper().removeprefix("0X")
                matched = selected in addresses
                if matched:
                    self.device_list.setCurrentRow(addresses.index(selected))
                self.target_card.set_value("ACK alındı" if matched else "Hedef yok", COLOR_GOOD if matched else COLOR_ERROR)
                summary = ", ".join("0x" + value for value in addresses)
                self.target_card.set_note("Yanıt veren: " + summary)
                self.log_message("I²C tarama yanıtı: " + summary)
            else:
                empty = QListWidgetItem("No devices found")
                empty.setFlags(empty.flags() & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable)
                self.device_list.addItem(empty)
                self.target_card.set_value("Yanıt yok", COLOR_ERROR)
                self.target_card.set_note("I²C hattında ACK alınmadı")
                self.log_message("I²C taraması tamamlandı: yanıt veren adres yok.")
        except Exception as error:
            self.target_card.set_value("Tarama hatası", COLOR_ERROR)
            QMessageBox.critical(self, "Tarama hatası", str(error))

    def set_frequency(self):
        try:
            response = self.request("FREQ " + str(self.frequency.value()))
            self.log_message(f"I²C saati {self.frequency.value()} Hz ({response})")
        except Exception as error:
            QMessageBox.critical(self, "Saat ayarı", str(error))

    def select_register(self, index):
        if index < 0:
            return
        register = PAGE0_REGISTERS[index]
        self.command.setText(f"{register.code:02X}")
        self.width_box.setCurrentIndex(0 if register.width == 1 else 1)

    def _put_table_row(self, table, values, row=None):
        if row is None:
            row = table.rowCount()
            table.insertRow(row)
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, column, item)
        return row

    def _show_register_value(self, register, value):
        full_row = (
            f"{register.code:02X}h",
            register.name,
            register.access,
            str(register.width),
            f"0x{value:0{register.width * 2}X}",
            interpretation_for(register, value),
        )
        if register.code in DIAGNOSTIC_TABLE_CODES:
            table = self.diagnostic_table
            values = (full_row[0], full_row[1], full_row[4], full_row[5])
        else:
            table = self.register_table
            values = full_row
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is not None and item.text() == full_row[0]:
                self._put_table_row(table, values, row)
                return
        self._put_table_row(table, values)

    def _show_register_error(self, register, error):
        if register.code in DIAGNOSTIC_TABLE_CODES:
            table = self.diagnostic_table
            values = (f"{register.code:02X}h", register.name, "OKUNAMADI", error)
        else:
            table = self.register_table
            values = (f"{register.code:02X}h", register.name, register.access, str(register.width), "OKUNAMADI", error)
        self._put_table_row(table, values)

    def read_all_registers(self):
        self.read_all_button.setEnabled(False)
        try:
            address = self.target()
            page_response = self.request(f"RB {address:02X} 00")
            current_page = int(page_response.split()[1], 16)
            if current_page != 0:
                raise ValueError(f"MP2886A şu an PAGE={current_page:02X}h. PAGE değiştirilmedi; önce cihazı güvenli şekilde PAGE 0'a al.")

            self.clear_table(self.register_table)
            completed = 0
            failures = []
            for register in READABLE_PAGE0_REGISTERS:
                if register.code == 0x00:
                    value = current_page
                    response_parts = page_response.split()
                else:
                    operation = "RB" if register.width == 1 else "RW"
                    try:
                        response = self.request(f"{operation} {address:02X} {register.code:02X}")
                        response_parts = response.split()
                        value = int(response_parts[1], 16)
                    except Exception as error:
                        failures.append((register, str(error)))
                        self._show_register_error(register, str(error))
                        QApplication.processEvents()
                        continue
                self._show_register_value(register, value)
                completed += 1
                if self.pec_checkbox.isChecked() and "PEC_OK" in response_parts:
                    self.pec_card.set_value("Son okuma: PASS", COLOR_GOOD)
                    self.pec_card.set_note("CRC-8 doğrulandı")
                QApplication.processEvents()

            self.log_message(
                f"PAGE 0 toplu okuma: {completed}/{len(READABLE_PAGE0_REGISTERS)} kayıt okundu; "
                f"{len(failures)} kayıt okunamadı."
            )
            if failures:
                QMessageBox.warning(
                    self,
                    "Toplu okuma tamamlandı",
                    f"{completed} kayıt okundu, {len(failures)} kayıt okunamadı. Başarısız satırlar tabloda.",
                )
        except Exception as error:
            QMessageBox.critical(self, "Page 0 okuma hatası", str(error))
        finally:
            self.read_all_button.setEnabled(True)

    def save_profile(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "MP2886A profilini kaydet",
            "mp2886a-profile.json",
            "JSON profili (*.json)",
        )
        if not file_name:
            return

        self.setEnabled(False)
        try:
            address = self.target()
            page = self._read_page_zero_register(address, 0x00)
            if page != 0:
                raise ValueError(f"Profil yalnızca PAGE=00h'da okunur; cihaz şu an PAGE={page:02X}h. Sayfa değiştirilmedi.")

            entries = []
            failures = []
            total = len(PROFILE_REGISTERS)
            for index, register in enumerate(PROFILE_REGISTERS, start=1):
                operation = "RB" if register.width == 1 else "RW"
                try:
                    response = self.request(f"{operation} {address:02X} {register.code:02X}")
                    parts = response.split()
                    if len(parts) < 2 or parts[0] != "OK":
                        raise RuntimeError("Geçersiz bridge yanıtı: " + response)
                    value = int(parts[1], 16)
                    if value >= 1 << (register.width * 8):
                        raise ValueError("Yanıt register genişliğini aşıyor.")
                    entries.append({
                        "command": f"{register.code:02X}",
                        "name": register.name,
                        "width": register.width,
                        "value": f"0x{value:0{register.width * 2}X}",
                    })
                    self._show_register_value(register, value)
                except Exception as error:
                    failures.append(f"{register.code:02X}h {register.name}: {error}")
                self.statusBar().showMessage(f"Profil okunuyor: {index}/{total}")
                QApplication.processEvents()

            if failures:
                sample = "\n".join(failures[:8])
                extra = f"\n… ve {len(failures) - 8} başka hata" if len(failures) > 8 else ""
                raise RuntimeError(
                    f"Profil eksik olduğu için dosya kaydedilmedi ({len(failures)} okuma hatası):\n{sample}{extra}"
                )

            signature = {}
            for code in PROFILE_SIGNATURE_CODES:
                register = REGISTERS_BY_CODE[code]
                value = self._read_page_zero_register(address, code)
                signature[f"{code:02X}"] = f"0x{value:0{register.width * 2}X}"

            profile = {
                "format": PROFILE_FORMAT,
                "version": PROFILE_VERSION,
                "device": "MP2886A",
                "page": 0,
                "source_address": f"{address:02X}",
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "signature": signature,
                "registers": entries,
            }
            destination = Path(file_name)
            if destination.suffix.lower() != ".json":
                destination = destination.with_suffix(".json")
            destination.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.log_message(f"Profil kaydedildi: {destination} ({len(entries)} ayar)")
            QMessageBox.information(
                self,
                "Profil kaydedildi",
                f"{len(entries)} okunabilir ayar {destination} dosyasına kaydedildi.\n\n"
                "PAGE, OPERATION, koruma/EEPROM kontrolleri, kimlik ve PMBus adresi profile dahil edilmedi.",
            )
        except Exception as error:
            QMessageBox.critical(self, "Profil okunamadı", str(error))
        finally:
            self.setEnabled(True)

    @staticmethod
    def _validate_profile_document(profile):
        if not isinstance(profile, dict):
            raise ValueError("JSON kökü bir nesne olmalı.")
        if profile.get("format") != PROFILE_FORMAT or profile.get("version") != PROFILE_VERSION:
            raise ValueError("Bu MP2886A profil biçimi veya sürümü desteklenmiyor.")
        if profile.get("device") != "MP2886A" or profile.get("page") != 0:
            raise ValueError("Dosya MP2886A Page 0 profili değil.")

        allowed = {register.code: register for register in PROFILE_REGISTERS}
        raw_entries = profile.get("registers")
        if not isinstance(raw_entries, list) or not raw_entries:
            raise ValueError("Profildə uygulanabilir register bulunamadı.")

        entries = []
        seen = set()
        for entry in raw_entries:
            if not isinstance(entry, dict):
                raise ValueError("Register girdisi nesne biçiminde olmalı.")
            command = entry.get("command")
            if not isinstance(command, str) or len(command) != 2 or any(char not in "0123456789abcdefABCDEF" for char in command):
                raise ValueError("Register komutu iki basamaklı hexadecimal olmalı.")
            code = int(command, 16)
            register = allowed.get(code)
            if register is None:
                raise ValueError(f"{code:02X}h profilden yazmaya izin verilen bir register değil.")
            if code in seen:
                raise ValueError(f"{code:02X}h profilde birden fazla kez bulunuyor.")
            if entry.get("name") != register.name or type(entry.get("width")) is not int or entry["width"] != register.width:
                raise ValueError(f"{code:02X}h register adı veya byte genişliği katalogla uyuşmuyor.")
            raw_value = entry.get("value")
            if not isinstance(raw_value, str):
                raise ValueError(f"{code:02X}h değeri hexadecimal metin olmalı.")
            digits = raw_value.strip().lower().removeprefix("0x")
            if not digits or len(digits) > register.width * 2 or any(char not in "0123456789abcdef" for char in digits):
                raise ValueError(f"{code:02X}h değeri {register.width} byte aralığında hexadecimal olmalı.")
            value = int(digits, 16)
            entries.append((register, value))
            seen.add(code)

        signature = profile.get("signature")
        if not isinstance(signature, dict) or set(signature) != {f"{code:02X}" for code in PROFILE_SIGNATURE_CODES}:
            raise ValueError("Profilin CONFIG_ID / CONFIG_REV_MPS kimlik bilgileri eksik.")
        parsed_signature = {}
        for code in PROFILE_SIGNATURE_CODES:
            register = REGISTERS_BY_CODE[code]
            raw_value = signature.get(f"{code:02X}")
            if not isinstance(raw_value, str):
                raise ValueError(f"{register.name} kimliği hexadecimal metin olmalı.")
            digits = raw_value.strip().lower().removeprefix("0x")
            if not digits or len(digits) > register.width * 2 or any(char not in "0123456789abcdef" for char in digits):
                raise ValueError(f"{register.name} kimliği hexadecimal biçimde değil.")
            parsed_signature[code] = int(digits, 16)
        return entries, parsed_signature

    def write_profile_from_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Yazılacak MP2886A profilini seç",
            "",
            "JSON profili (*.json)",
        )
        if not file_name:
            return

        try:
            source = Path(file_name)
            if source.stat().st_size > 1_000_000:
                raise ValueError("Profil dosyası 1 MB sınırını aşıyor.")
            profile = json.loads(source.read_text(encoding="utf-8"))
            entries, signature = self._validate_profile_document(profile)
            address = self.target()
            page = self._read_page_zero_register(address, 0x00)
            if page != 0:
                raise ValueError(f"Profil yalnızca PAGE=00h'a yazılır; cihaz şu an PAGE={page:02X}h. Sayfa değiştirilmedi.")

            for code, expected in signature.items():
                actual = self._read_page_zero_register(address, code)
                if actual != expected:
                    register = REGISTERS_BY_CODE[code]
                    raise ValueError(
                        f"{register.name} eşleşmiyor: dosya 0x{expected:04X}, cihaz 0x{actual:04X}. "
                        "Farklı MP2886A yapılandırmasına ait profil uygulanmadı."
                    )

            source_address = profile.get("source_address", "bilinmiyor")
            answer = QMessageBox.warning(
                self,
                "Profili cihaza yaz",
                f"{source.name}: {len(entries)} ayar 0x{address:02X} adresine sırayla yazılacak.\n"
                f"Profil kaynak adresi: 0x{source_address}. CONFIG_ID ve revizyon eşleşti.\n\n"
                "Yalnızca aynı anakart/VR yapılandırmasına ait olduğundan eminsen devam et. "
                "İşlem çalışma belleğini değiştirir; hata olursa önceki yazmalar geri alınamaz. "
                "EEPROM'a otomatik kaydetmez.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        except Exception as error:
            QMessageBox.critical(self, "Profil uygulanamadı", str(error))
            return

        verified = 0
        failed_register = None
        failure = None
        self.setEnabled(False)
        try:
            total = len(entries)
            for index, (register, value) in enumerate(entries, start=1):
                failed_register = register
                operation = "WB" if register.width == 1 else "WW"
                self.request(f"{operation} {address:02X} {register.code:02X} {value:04X}")
                read_operation = "RB" if register.width == 1 else "RW"
                response = self.request(f"{read_operation} {address:02X} {register.code:02X}")
                parts = response.split()
                if len(parts) < 2 or int(parts[1], 16) != value:
                    raise RuntimeError(f"Yazma sonrası doğrulama başarısız: {response}")
                verified += 1
                self._show_register_value(register, value)
                self.statusBar().showMessage(f"Profil yazılıyor ve doğrulanıyor: {index}/{total}")
                QApplication.processEvents()
        except Exception as error:
            failure = error
        finally:
            self.setEnabled(True)

        if failure is not None:
            self.log_message(f"Profil kısmen uygulandı: {verified}/{len(entries)} doğrulandı; hata {failed_register.code:02X}h.")
            QMessageBox.critical(
                self,
                "Profil kısmen uygulandı",
                f"{verified}/{len(entries)} yazma doğrulandı. {failed_register.code:02X}h {failed_register.name} sırasında hata: {failure}\n\n"
                "Önceki yazmalar geri alınmadı; cihazı yeniden okuyup durumunu kontrol et.",
            )
            return

        self.log_message(f"Profil uygulandı: {verified} register yazıldı ve okuma ile doğrulandı; EEPROM değiştirilmedi.")
        QMessageBox.information(
            self,
            "Profil uygulandı",
            f"{verified} ayar yazıldı ve geri okunarak doğrulandı. Değerler çalışma belleğinde; EEPROM'a kaydedilmedi.",
        )

    def set_pec(self, enabled):
        if self.port is None:
            if enabled:
                self.pec_checkbox.blockSignals(True)
                self.pec_checkbox.setChecked(False)
                self.pec_checkbox.blockSignals(False)
            self.pec_card.set_value("Kapalı", COLOR_WARNING)
            return
        if not self.pec_supported:
            self.pec_checkbox.blockSignals(True)
            self.pec_checkbox.setChecked(False)
            self.pec_checkbox.blockSignals(False)
            return
        try:
            self.request("PEC ON" if enabled else "PEC OFF")
            self.pec_card.set_value("Açık · bekliyor" if enabled else "Kapalı", COLOR_WARNING)
            self.pec_card.set_note("İlk başarılı okumada doğrulanacak" if enabled else "CRC-8 · polynomial 07h")
            self.log_message("SMBus PEC " + ("açıldı" if enabled else "kapatıldı") + ".")
        except Exception as error:
            self.pec_checkbox.blockSignals(True)
            self.pec_checkbox.setChecked(not enabled)
            self.pec_checkbox.blockSignals(False)
            QMessageBox.critical(self, "PEC ayarı", str(error))

    def read_pgood(self):
        try:
            address = self.target()
            response = self.request(f"RW {address:02X} 79")
            parts = response.split()
            status_word = int(parts[1], 16)
            status_byte = self._read_page_zero_register(address, 0x78)
            warnings = self._status_word_warnings(status_word, status_byte)
            if warnings:
                self.output_card.set_value("Status uyumsuz", COLOR_ERROR)
                self.output_card.set_note("; ".join(warnings))
                self.log_message("STATUS_WORD güvenilir değil: " + "; ".join(warnings))
                return
            pgood_bit = (status_word >> 11) & 1
            self.output_card.set_value(f"POWER_GOOD B11={pgood_bit}")
            self.output_card.set_note(f"STATUS_WORD=0x{status_word:04X}; fiziksel pin ölçümü değil")
            self.target_card.set_value("Yanıt alındı", COLOR_GOOD)
            self.log_message(f"STATUS_WORD 79h: 0x{status_word:04X}; POWER_GOOD bit 11={pgood_bit}")
            if self.pec_checkbox.isChecked() and "PEC_OK" in parts:
                self.pec_card.set_value("Son okuma: PASS", COLOR_GOOD)
                self.pec_card.set_note("STATUS_WORD PEC CRC-8 doğrulandı")
        except Exception as error:
            self.output_card.set_value("Okunamadı", COLOR_ERROR)
            self.output_card.set_note("STATUS_WORD 79h yanıtı alınamadı")
            if "PEC_MISMATCH" in str(error) or "PEC_BYTE_MISSING" in str(error):
                self.pec_card.set_value("PEC hatası", COLOR_ERROR)
                self.pec_card.set_note(str(error))
            QMessageBox.critical(self, "PGOOD okuma hatası", str(error))

    def _read_page_zero_register(self, address, code):
        register = REGISTERS_BY_CODE[code]
        operation = "RB" if register.width == 1 else "RW"
        response = self.request(f"{operation} {address:02X} {code:02X}")
        return int(response.split()[1], 16)

    @staticmethod
    def _status_word_warnings(status_word, status_byte):
        warnings = []
        if status_word & 0xFF != status_byte:
            warnings.append(f"STATUS_WORD alt byte 0x{status_word & 0xFF:02X}, STATUS_BYTE 0x{status_byte:02X}; eşleşmeli")
        if status_word & 0x0600:
            warnings.append("STATUS_WORD ayrılmış bit 10:9 set")
        if status_byte & 0x81:
            warnings.append("STATUS_BYTE ayrılmış bit 7 veya 0 set")
        return warnings

    def read_faults(self):
        try:
            address = self.target()
            page = self._read_page_zero_register(address, 0x00)
            if page != 0:
                raise ValueError(f"Teşhis için PAGE=00h gerekli; cihaz şu an PAGE={page:02X}h. Sayfa değiştirilmedi.")

            report = ["MP2886A PWM / HATA TEŞHİSİ", "PAGE 0: canlı ve latch edilmiş status kayıtları"]
            active_flags = []
            read_failures = []
            nonzero_snapshots = False
            snapshot_values = []
            status_values = {}
            self.diagnostic_table.setRowCount(0)
            for code in FAULT_STATUS_CODES:
                register = REGISTERS_BY_CODE[code]
                try:
                    value = self._read_page_zero_register(address, code)
                    status_values[code] = value
                    self._show_register_value(register, value)
                    names = status_flags_for(code, value)
                    report.append(f"{code:02X}h {register.name} = 0x{value:0{register.width * 2}X}")
                    if names:
                        report.extend(f"  - {name}" for name in names)
                        if code not in (0x78, 0x79):
                            active_flags.extend(
                                (code, bit, name)
                                for bit, name in STATUS_FLAG_NAMES[code].items()
                                if value & (1 << bit) and not (code == 0x7E and bit == 3)
                            )
                    else:
                        report.append("  - Tanımlı hata bayrağı set değil")
                except Exception as error:
                    read_failures.append(f"{code:02X}h {register.name}: {error}")
                    report.append(f"{code:02X}h {register.name}: OKUNAMADI ({error})")

            status_byte = status_values.get(0x78)
            status_word = status_values.get(0x79)
            status_word_valid = True
            if status_byte is not None and status_word is not None:
                status_warnings = self._status_word_warnings(status_word, status_byte)
                if status_warnings:
                    status_word_valid = False
                    report.extend(("", "STATUS VERİ BÜTÜNLÜĞÜ UYARISI:"))
                    report.extend(f"  - {warning}" for warning in status_warnings)

            report.extend(("", "MPS ÜRETİCİ FAULT SNAPSHOT (ham hexadecimal):"))
            for code in MFR_FAULT_SNAPSHOT_CODES:
                register = REGISTERS_BY_CODE[code]
                try:
                    value = self._read_page_zero_register(address, code)
                    self._show_register_value(register, value)
                    nonzero_snapshots = nonzero_snapshots or bool(value)
                    if value:
                        snapshot_values.append((code, value))
                    suffix = " — sıfır değil; bit kodları çözülmüyor" if value else " — sıfır"
                    report.append(f"{code:02X}h {register.name} = 0x{value:04X}{suffix}")
                except Exception as error:
                    read_failures.append(f"{code:02X}h {register.name}: {error}")
                    report.append(f"{code:02X}h {register.name}: OKUNAMADI ({error})")

            profile_codes = (0x01, 0x1F, 0x21, 0x24, 0x35, 0x36, 0x5E, 0x5F, 0x88, 0xBD, 0xE1, 0xE2)
            report.extend(("", "PWM İÇİN MEVCUT PROFİL DEĞERLERİ (yazılmaz):"))
            profile_values = {}
            for code in profile_codes:
                register = REGISTERS_BY_CODE[code]
                try:
                    value = self._read_page_zero_register(address, code)
                    profile_values[code] = value
                    self._show_register_value(register, value)
                    report.append(f"{code:02X}h {register.name} = 0x{value:0{register.width * 2}X} — {interpretation_for(register, value)}")
                except Exception as error:
                    read_failures.append(f"{code:02X}h {register.name}: {error}")
                    report.append(f"{code:02X}h {register.name}: OKUNAMADI ({error})")

            operation = profile_values.get(0x01)
            if operation is not None and operation & 0xC0 != 0x80:
                report.append("BAŞLATMA NOTU: OPERATION Hi-Z/soft-off kodunda; çıkış çalışması istenmiyor.")
            input_voltage = profile_values.get(0x88)
            vin_on = profile_values.get(0x35)
            if input_voltage is not None and vin_on is not None:
                vin_measurement_valid = input_voltage & 0xFC00 == 0xEC00
                vin_threshold_valid = vin_on & 0xFF00 == 0xE800
                if not vin_measurement_valid or not vin_threshold_valid:
                    report.append("BAŞLATMA NOTU: READ_VIN veya VIN_ON sabit bit alanı datasheet formatına uymuyor; VIN karşılaştırması güvenilir değil.")
                else:
                    measured_vin = (input_voltage & 0x03FF) * 0.03125
                    startup_threshold = (vin_on & 0xFF) * 0.125
                    if measured_vin < startup_threshold:
                        report.append(f"BAŞLATMA NOTU: READ_VIN {measured_vin:.3f} V, VIN_ON {startup_threshold:.3f} V altında; soft-start başlamayabilir.")
            if status_word_valid and status_word is not None and not (status_word & (1 << 11)):
                report.append("BAŞLATMA NOTU: POWER_GOOD henüz set değil; VOUT eşiği veya PG_DELAY tamamlanmamış olabilir.")

            report.extend(("", "VIN_ON/VIN_OFF giriş beslemesi eşikleridir; VOUT_MIN/COMMAND/MAX kartın VR profiline uymalıdır."))
            report.append("PWM çıkışı için anakart EN, güç katı ve PWMVID/BOOT pin bağlantıları da gerekir.")
            report.append("Güvenli profil bilinmeden ayar yazılmaz. Latch bayrağı fiziksel neden sürüyorsa yeniden set olur.")
            if nonzero_snapshots:
                report.append("MPS fault snapshot sıfır değil; ham değerleri ayrıca inceleyin.")
            if read_failures:
                report.append(f"\nOkuma hatası: {len(read_failures)} kayıt okunamadı; tablodaki satırlara bakın.")
            elif active_flags or nonzero_snapshots:
                report.append("\nSONUÇ: Arıza bayrakları veya üretici snapshot değerleri incelenmeli.")
            else:
                report.append("\nSONUÇ: Okunabilen status kayıtlarında tanımlı arıza bayrağı yok.")

            dialog = "\n".join(report)
            self.fault_report.setPlainText(dialog)
            if active_flags:
                active_lines = [f"{code:02X}h · bit {bit} · {name}" for code, bit, name in active_flags]
                summary_lines = [f"AKTİF DURUM BAYRAKLARI ({len(active_flags)})", *active_lines]
                summary_lines.extend(f"MPS SNAPSHOT {code:02X}h = 0x{value:04X}" for code, value in snapshot_values)
                self.fault_summary.setText("\n".join(summary_lines))
                self.fault_summary.setStyleSheet(
                    "color: #ffb1b5; background: #382326; border: 1px solid #a44e59; "
                    "border-radius: 4px; padding: 8px 10px; font-weight: 700;"
                )
                flag_log = "; ".join(active_lines)
            else:
                if snapshot_values:
                    summary_lines = ["MPS FAULT SNAPSHOT SIFIR DEĞİL; ham değerler:"]
                    summary_lines.extend(f"{code:02X}h = 0x{value:04X}" for code, value in snapshot_values)
                    self.fault_summary.setText("\n".join(summary_lines))
                    self.fault_summary.setStyleSheet(
                        "color: #ffb1b5; background: #382326; border: 1px solid #a44e59; "
                        "border-radius: 4px; padding: 8px 10px; font-weight: 700;"
                    )
                    flag_log = "; ".join(f"snapshot {code:02X}h=0x{value:04X}" for code, value in snapshot_values)
                elif read_failures:
                    self.fault_summary.setText(f"DURUM BELİRLENEMEDİ · {len(read_failures)} register okunamadı")
                    self.fault_summary.setStyleSheet(
                        "color: #f0bc65; background: #383024; border: 1px solid #5d4b30; "
                        "border-radius: 4px; padding: 8px 10px; font-weight: 700;"
                    )
                    flag_log = f"durum belirsiz; {len(read_failures)} kayıt okunamadı"
                else:
                    self.fault_summary.setText("AKTİF STATUS BAYRAĞI YOK")
                    self.fault_summary.setStyleSheet(
                        "color: #63d8b3; background: #20332d; border: 1px solid #315244; "
                        "border-radius: 4px; padding: 8px 10px; font-weight: 700;"
                    )
                    flag_log = "arıza bayrağı görülmedi"
            self.log_message(f"PWM / hata teşhisi tamamlandı; {flag_log}.")
            if active_flags or nonzero_snapshots or read_failures:
                QMessageBox.warning(self, "PWM / hata teşhisi", dialog)
        except Exception as error:
            QMessageBox.critical(self, "PWM / hata teşhisi yapılamadı", str(error))

    def clear_faults(self):
        try:
            address = self.target()
            page = self._read_page_zero_register(address, 0x00)
            if page != 0:
                raise ValueError(f"CLEAR_FAULTS yalnızca PAGE 0'da gönderilir; mevcut PAGE={page:02X}h. Sayfa değiştirilmedi.")
            answer = QMessageBox.question(
                self,
                "Hata bayraklarını temizle",
                "CLEAR_FAULTS (03h) latch edilmiş status bayraklarını temizler. Fiziksel nedeni gidermez. Devam edilsin mi?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            response = self.request(f"CMD {address:02X} 03")
            self.log_message(f"CLEAR_FAULTS 03h gönderildi: {response}")
            QMessageBox.information(self, "Temizleme gönderildi", "Komut gönderildi. Teşhis sekmesinden durumu tekrar oku.")
        except Exception as error:
            QMessageBox.critical(self, "Hata bayrakları temizlenemedi", str(error))

    def read_value(self):
        try:
            address = self.target()
            command = self.parse_hex(self.command, "Komut", 0xFF)
            register = REGISTERS_BY_CODE.get(command)
            if register is not None and not register.can_read:
                raise ValueError(f"{register.name} datasheet'e göre okunabilir değil ({register.access}).")
            word = register.width == 2 if register is not None else self.width_box.currentIndex() == 1
            operation = "RW" if word else "RB"
            response = self.request(f"{operation} {address:02X} {command:02X}")
            parts = response.split()
            value = parts[1]
            self.data.setText(value)
            self.target_card.set_value("Yanıt alındı", COLOR_GOOD)
            self.log_message(f"{'Word' if word else 'Byte'} okuma: 0x{address:02X} / komut 0x{command:02X} → 0x{value}")
            if register is not None:
                self._show_register_value(register, int(value, 16))
            if self.pec_checkbox.isChecked() and "PEC_OK" in parts:
                self.pec_card.set_value("Son okuma: PASS", COLOR_GOOD)
                self.pec_card.set_note("CRC-8 doğrulandı")
        except Exception as error:
            if "PEC_MISMATCH" in str(error) or "PEC_BYTE_MISSING" in str(error):
                self.pec_card.set_value("PEC hatası", COLOR_ERROR)
                self.pec_card.set_note(str(error))
            QMessageBox.critical(self, "Okuma hatası", str(error))

    def write_value(self):
        try:
            address = self.target()
            command = self.parse_hex(self.command, "Komut", 0xFF)
            word = self.width_box.currentIndex() == 1
            value = self.parse_hex(self.data, "Değer", 0xFFFF if word else 0xFF)
            operation = "WW" if word else "WB"
            answer = QMessageBox.warning(
                self,
                "Register yazma onayı",
                f"0x{address:02X} adresine {command:02X}h komutuyla 0x{value:04X} yazılacak. Yanlış VR ayarı donanıma zarar verebilir.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            response = self.request(f"{operation} {address:02X} {command:02X} {value:04X}")
            self.target_card.set_value("Yazma yanıtı alındı", COLOR_GOOD)
            self.log_message(f"{'Word' if word else 'Byte'} yazma: 0x{address:02X} / {command:02X}h / 0x{value:04X} ({response})")
            if self.pec_checkbox.isChecked() and "PEC_TX_ACK" in response:
                self.pec_card.set_value("TX ACK", COLOR_GOOD)
                self.pec_card.set_note("Cihaz PEC baytını ACK etti; okuma doğrulaması değildir")
        except Exception as error:
            QMessageBox.critical(self, "Yazma hatası", str(error))

    def restore_user_all(self):
        try:
            address = self.target()
            answer = QMessageBox.warning(
                self,
                "EEPROM geri yükleme",
                f"0x{address:02X} adresindeki cihaz EEPROM’dan çalışma belleğine geri yüklenecek. Devam edilsin mi?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            response = self.request(f"CMD {address:02X} 16")
            self.log_message(f"RESTORE_USER_ALL 16h: {response}")
        except Exception as error:
            QMessageBox.critical(self, "Geri yükleme hatası", str(error))

    def store_user_all(self):
        try:
            address = self.target()
            answer = QMessageBox.warning(
                self,
                "EEPROM’a kalıcı yazma",
                f"0x{address:02X} adresindeki ayarlar EEPROM’a kalıcı kaydedilecek. Doğrulanmış profil olduğundan emin ol. Devam edilsin mi?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            response = self.request(f"CMD {address:02X} 15")
            self.log_message(f"STORE_USER_ALL 15h: {response}")
        except Exception as error:
            QMessageBox.critical(self, "EEPROM yazma hatası", str(error))


def main():
    application = QApplication([])
    application.setStyle("Fusion")
    application.setStyleSheet(STYLESHEET)
    window = MP2886Window()
    window.show()
    return application.exec_()


if __name__ == "__main__":
    main()
