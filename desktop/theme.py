# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""One warm, accessible palette for the application and its child dialogs."""
from PySide6.QtGui import QColor, QPalette, QFont
from common import ROOT

BACKGROUND = '#f5f0e9'
SURFACE = '#fffdf9'
TEXT = '#47382e'
MUTED = '#756456'
BORDER = '#ded3c6'
ACCENT = '#995434'
SOFT = '#f3e6d8'


def apply_theme(app, family):
    app.setStyle('Fusion')
    app.setFont(QFont(family, 11))
    palette = QPalette()
    for role, value in {
        'Window': BACKGROUND, 'WindowText': TEXT, 'Base': SURFACE,
        'AlternateBase': '#f8f2eb', 'Text': TEXT, 'Button': SURFACE,
        'ButtonText': TEXT, 'Highlight': ACCENT, 'HighlightedText': '#ffffff',
        'ToolTipBase': SURFACE, 'ToolTipText': TEXT, 'Link': ACCENT,
        'PlaceholderText': '#88796c',
    }.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(value))
    for role in ('Text', 'WindowText', 'ButtonText'):
        palette.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, role), QColor('#a89c90'))
    app.setPalette(palette)
    assets = (ROOT / 'data/desktop/theme').as_posix()
    app.setStyleSheet('''
        QWidget { color: @text; }
        QMainWindow, QDialog, QMessageBox, QWidget#settings { background: @background; }
        QFrame#section, QWidget#chartContent, QWidget#matrixContent { background: @surface; }
        QFrame#section { border:1px solid @border; border-radius:9px; }
        QLabel { background:transparent; }
        QLabel#sectionTitle { color:@text; font-weight:600; padding-bottom:4px; }
        QLabel#brandTitle { font-size:18pt; font-weight:600; }
        QLabel#dialogTitle { font-size:15pt; font-weight:600; }
        QLabel#hint { color:@muted; font-size:10pt; }
        QLabel#status { color:@text; background:@soft; padding:9px 12px; border-radius:7px; }
        QLabel#chartTitle { color:@accent; font-size:13pt; font-weight:600; }
        QFrame#houseNotice { background:@soft; border:1px solid @accent; border-radius:7px; }
        QLineEdit, QPlainTextEdit, QDateEdit, QTimeEdit, QComboBox, QDoubleSpinBox, QSpinBox {
            background:@surface; color:@text; border:1px solid @border; border-radius:6px;
            padding:6px 9px; min-height:22px; selection-background-color:@accent; selection-color:white;
        }
        QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
            border:1px solid @accent;
        }
        QLineEdit:disabled, QComboBox:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled {
            color:#a89c90; background:#f1ece5; border-color:#e4dbd1;
        }
        QComboBox { padding-right:28px; }
        QComboBox::drop-down { subcontrol-origin:padding; subcontrol-position:top right; width:26px; border:none; }
        QComboBox::down-arrow { image:url(@assets/down.svg); width:12px; height:12px; }
        QComboBox QAbstractItemView { background:@surface; border:1px solid @border; outline:0; selection-background-color:@soft; selection-color:@text; padding:4px; }
        QComboBox QAbstractItemView::item { min-height:30px; }
        QAbstractSpinBox { padding:6px 26px 6px 9px; }
        QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { subcontrol-origin:border; width:24px; border:0; }
        QAbstractSpinBox::up-button { subcontrol-position:top right; }
        QAbstractSpinBox::down-button { subcontrol-position:bottom right; }
        QAbstractSpinBox::up-arrow { image:url(@assets/up.svg); width:11px; height:11px; }
        QAbstractSpinBox::down-arrow { image:url(@assets/down.svg); width:11px; height:11px; }
        QPushButton, QToolButton#disclosure { min-height:22px; border:1px solid @border; border-radius:7px; padding:6px 13px; background:@surface; color:@text; }
        QPushButton:hover, QToolButton#disclosure:hover { background:@soft; border-color:#bca58f; }
        QPushButton:pressed { background:#ead6c4; }
        QPushButton:focus, QToolButton:focus { border:1px solid @accent; }
        QPushButton#calculate, QPushButton[role="primary"] { background:@accent; color:white; border-color:@accent; font-weight:600; }
        QPushButton#calculate:hover, QPushButton[role="primary"]:hover { background:#824426; }
        QPushButton:disabled { background:#f3eee7; color:#a89c90; border-color:#e4dbd1; }
        QPushButton#calculate:disabled, QPushButton[role="primary"]:disabled { background:#c9ac99; color:#fffdf9; border-color:#c9ac99; }
        QCheckBox { spacing:8px; padding:4px 0; }
        QCheckBox:disabled { color:#a89c90; }
        QCheckBox::indicator, QGroupBox::indicator { width:16px; height:16px; border:1px solid #bca58f; border-radius:4px; background:@surface; }
        QCheckBox::indicator:checked, QGroupBox::indicator:checked { background:@accent; border-color:@accent; image:url(@assets/check.svg); }
        QCheckBox::indicator:disabled { background:#ebe4db; border-color:@border; }
        QGroupBox { border:1px solid @border; border-radius:7px; margin-top:18px; padding:18px 9px 9px; }
        QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; }
        QTabWidget::pane { border:1px solid @border; background:@surface; border-radius:6px; top:-1px; }
        QTabBar::tab { background:transparent; color:@muted; padding:10px 16px; border:0; border-bottom:3px solid transparent; }
        QTabBar::tab:selected { color:@accent; border-bottom:3px solid @accent; font-weight:600; }
        QTabBar::tab:hover { background:@soft; }
        QTableWidget, QListWidget { background:@surface; alternate-background-color:#f8f2eb; color:@text; border:0; gridline-color:@border; selection-background-color:@soft; selection-color:@text; }
        QTableWidget::item { padding:7px 10px; border:0; border-bottom:1px solid @border; }
        QListWidget::item { padding:10px; border-bottom:1px solid @border; }
        QHeaderView { background:@soft; }
        QHeaderView::section { background:@soft; color:@text; font-weight:600; padding:10px; border:0; border-bottom:1px solid @border; }
        QTableCornerButton::section { background:@soft; border:0; }
        QScrollArea { border:0; background:transparent; }
        QScrollBar:vertical { background:transparent; width:10px; margin:2px; }
        QScrollBar::handle:vertical { background:#c8b9aa; border-radius:3px; min-height:30px; }
        QScrollBar:horizontal { background:transparent; height:10px; margin:2px; }
        QScrollBar::handle:horizontal { background:#c8b9aa; border-radius:3px; min-width:30px; }
        QScrollBar::add-line, QScrollBar::sub-line { width:0; height:0; }
        QScrollBar::add-page, QScrollBar::sub-page { background:transparent; }
        QSplitter::handle { background:transparent; width:10px; }
        QSplitter::handle:hover { background:@soft; }
        QToolTip { background:@surface; color:@text; border:1px solid @border; padding:6px; }
        QProgressBar { border:0; background:#e7dace; border-radius:4px; }
        QProgressBar::chunk { background:@accent; border-radius:4px; }
        QMenu { background:@surface; border:1px solid @border; padding:5px; }
        QMenu::item { padding:7px 18px; }
        QMenu::item:selected { background:@soft; }
        QDialogButtonBox { dialogbuttonbox-buttons-have-icons:0; }
    '''.replace('@background', BACKGROUND).replace('@surface', SURFACE).replace('@text', TEXT)
       .replace('@muted', MUTED).replace('@border', BORDER).replace('@accent', ACCENT)
       .replace('@soft', SOFT).replace('@assets', assets))


def primary(button):
    button.setProperty('role', 'primary')


def dialog_layout(layout):
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(14)
