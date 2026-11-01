# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Small shared dialogs, using the application's typography and palette."""
from .i18n import tr
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QCheckBox, QDialogButtonBox, QSizePolicy
from .report import available_templates
from .theme import dialog_layout, primary
from .i18n import LANGUAGES


class LanguageDialog(QDialog):
    def __init__(self,selected,parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('介面語言'));self.resize(440,240)
        layout=QVBoxLayout(self);dialog_layout(layout)
        label=QLabel(tr('選擇下次啟動時使用的語言。文件匯出語言可另外選擇。'))
        label.setWordWrap(True);layout.addWidget(label)
        self.languages=QComboBox()
        for code,name in LANGUAGES.items():self.languages.addItem(name,code)
        self.languages.setCurrentIndex(self.languages.findData(selected));layout.addWidget(self.languages)
        buttons=QDialogButtonBox()
        buttons.addButton(tr('取消'),QDialogButtonBox.ButtonRole.RejectRole)
        primary(buttons.addButton(tr('儲存'),QDialogButtonBox.ButtonRole.AcceptRole))
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)


class ExportDialog(QDialog):
    def __init__(self, parent=None, timeline=False, has_selection=False):
        super().__init__(parent)
        self.setWindowTitle(tr('匯出文件'))
        self.resize(560, 490)
        layout = QVBoxLayout(self)
        dialog_layout(layout)
        title = QLabel(tr('匯出文件')); title.setObjectName('dialogTitle'); layout.addWidget(title)
        subtitle = QLabel(tr('單一檔案，可離線閱讀與列印。')); subtitle.setObjectName('hint'); layout.addWidget(subtitle)
        layout.addWidget(QLabel(tr('文件語系／範本')))
        self.templates = QComboBox()
        from .timeline_report import timeline_templates
        for path, label in (timeline_templates() if timeline else available_templates()): self.templates.addItem(label, str(path))
        layout.addWidget(self.templates)
        self.notes = QCheckBox(tr('包含個人備註')); layout.addWidget(self.notes)
        self.notes.setVisible(not timeline)
        self.scope=QComboBox(self)
        self.scope.addItem(tr('全部計算結果（不受畫面篩選影響）'),'all')
        if has_selection:self.scope.addItem(tr('所選事件與同時事件列表'),'selected')
        if timeline:layout.addWidget(self.scope)
        else:self.scope.hide()
        contents = QLabel(tr('時間軸、事件列表、星座歷程與精確成相。所選事件匯出另附重疊事件列表。') if timeline else tr('星盤圖、天體位置、十二宮宮頭位置、相位圖與相位詳細列表。'))
        contents.setObjectName('status'); contents.setWordWrap(True); layout.addWidget(contents)
        hint = QLabel(tr('列印建議：新版 Chrome／Edge、A4 橫向、縮放 100%，關閉瀏覽器頁首頁尾。頁碼僅在列印／PDF 顯示；較長內容會續頁。'))
        hint.setObjectName('hint'); hint.setWordWrap(True); layout.addWidget(hint)
        for label in (contents,hint):label.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Minimum)
        buttons = QDialogButtonBox()
        buttons.addButton(tr('取消'), QDialogButtonBox.ButtonRole.RejectRole)
        primary(buttons.addButton(tr('匯出文件'), QDialogButtonBox.ButtonRole.AcceptRole))
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
