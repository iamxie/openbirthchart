# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Qt desktop form, timezone feedback, chart and numeric tables."""
from .i18n import tr, localized_zodiac, error_text
from dataclasses import replace,asdict
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError
from PySide6.QtCore import Qt, QDate, QTime, QThread, QTimer, Signal, QSignalBlocker, QSize
from PySide6.QtGui import QColor, QFont, QAction
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,
    QGroupBox,QLabel,QDateEdit,QTimeEdit,QDoubleSpinBox,QSpinBox,QComboBox,QCheckBox,QPushButton,
    QScrollArea,QSplitter,QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,QFileDialog,QMessageBox,
    QAbstractItemView,QCompleter,QSizePolicy,QLineEdit,QMenu,QDialog,QDialogButtonBox,QToolButton,QPlainTextEdit,QFrame,QTabBar,QStackedWidget)
from .model import (BirthInput,ChartEngine,HOUSE_SYSTEMS,ASPECTS,APP_VERSION,
    available_timezones,resolve_local,zodiac_text,calculation_key,display_chart,sorted_aspect_details)
from .chart import ChartWidget,export_chart,font_family
from .aspects import AspectMatrix
from .storage import ProfileStore,validate_profile,DuplicateProfile,default_database_path
from .text import trim_text,report_filename
from .fields import DateField,TimeField,CoordinateField
from .geocoding import GeocodeDialog
from .report import export_html,available_templates
from .theme import apply_theme, dialog_layout, primary
from .dialogs import ExportDialog, LanguageDialog
from .errors import AmbiguousTimeError
from .i18n import LANGUAGES, language
from .help import has_azimuth_notice, azimuth_notice_text, show_azimuth_help
from .house_positions import validate_chart_houses
from .zodiac import zodiac_icon, zodiac_index
from .errors import UserError

ZONE_NAMES={'Asia/Taipei':'台灣／台北','Asia/Tokyo':'日本／東京','Asia/Hong_Kong':'香港',
            'Asia/Shanghai':'中國／上海','Asia/Singapore':'新加坡','Europe/London':'英國／倫敦',
            'America/New_York':'美國／紐約','America/Los_Angeles':'美國／洛杉磯',
            'Europe/Paris':'法國／巴黎','Australia/Sydney':'澳洲／雪梨','Pacific/Auckland':'紐西蘭／奧克蘭','UTC':'UTC'}

class Calculation(QThread):
    succeeded=Signal(dict);failed=Signal(str)
    def __init__(self,birth,orbs,engine=None,parent=None):
        super().__init__(parent);self.birth=birth;self.orbs=orbs;self.engine=engine
    def run(self):
        try:
            if self.engine is None:self.engine=ChartEngine()
            self.succeeded.emit(self.engine.calculate(self.birth,self.orbs))
        except Exception as exc:self.failed.emit(error_text(exc))

class MainWindow(QMainWindow):
    def __init__(self,auto_start=True,store=None,prompt_unsaved=True):
        super().__init__();self.setWindowTitle('Open BirthChart · '+APP_VERSION)
        from .legal import show_legal
        self.legal_action=QAction(tr('關於與授權'),self)
        self.legal_action.triggered.connect(lambda:show_legal(self))
        available=QApplication.primaryScreen().availableGeometry()
        self.setMinimumSize(min(920,available.width()),min(540,available.height()-50))
        self.resize(min(1440,available.width()-40),min(900,available.height()-70))
        self.chart=None;self.engine=None;self.worker=None;self.revision=0;self.pending_revision=None
        self.store=store or ProfileStore();self.record_id=None;self.loading=False
        self.prompt_unsaved=prompt_unsaved;self.saved_payload=None
        self.geocode_key=''
        apply_theme(QApplication.instance(),font_family())
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root);layout.setContentsMargins(18,14,18,14)
        header=QHBoxLayout();brand=QHBoxLayout()
        title=QLabel('Open BirthChart');title.setObjectName('brandTitle');brand.addWidget(title)
        self.record_status=QLabel(tr('新增個人檔案'));self.record_status.setObjectName('hint');brand.addSpacing(18);brand.addWidget(self.record_status)
        header.addLayout(brand);header.addStretch()
        self.mode_menu=QToolButton();self.mode_menu.setText(tr('功能'))
        self.mode_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        mode_menu=QMenu(self.mode_menu);self.mode_menu_actions=[]
        for index,title in enumerate((tr('個人星盤'),tr('天象時間軸'))):
            action=mode_menu.addAction(title);action.setCheckable(True);action.setChecked(index==0)
            action.triggered.connect(lambda checked=False,i=index:self.mode_tabs.setCurrentIndex(i))
            self.mode_menu_actions.append(action)
        self.mode_menu.setMenu(mode_menu);self.mode_menu.hide();header.addWidget(self.mode_menu)
        self.language_button=QPushButton('語言 / Language');header.addWidget(self.language_button)
        self.language_button.clicked.connect(self.choose_language)
        self.legal_button=QPushButton(tr('關於與授權'));header.addWidget(self.legal_button)
        self.legal_button.clicked.connect(self.legal_action.trigger)
        self.form_toggle=QPushButton(tr('收合填寫區'));header.addWidget(self.form_toggle);layout.addLayout(header)
        self.mode_tabs=QTabBar();self.mode_tabs.addTab(tr('個人星盤'));self.mode_tabs.addTab(tr('天象時間軸'))
        self.mode_tabs.setExpanding(False);layout.addWidget(self.mode_tabs)
        self.mode_stack=QStackedWidget();layout.addWidget(self.mode_stack,1)
        self.birth_page=QWidget();self.mode_stack.addWidget(self.birth_page)
        self.timeline_page=None
        layout=QVBoxLayout(self.birth_page);layout.setContentsMargins(0,0,0,0)
        self.mode_tabs.currentChanged.connect(self.switch_mode)
        toolbar=QHBoxLayout()
        self.new_button=QPushButton(tr('新增個人檔案'));self.load_button=QPushButton(tr('載入'))
        self.save_button=QPushButton(tr('儲存'));self.calculate_button=QPushButton(tr('排星盤'));self.calculate_button.setObjectName('calculate')
        for button in (self.new_button,self.load_button,self.save_button):toolbar.addWidget(button)
        toolbar.addSpacing(12);toolbar.addWidget(self.calculate_button);toolbar.addStretch()
        self.export_button=QPushButton(tr('匯出文件'))
        toolbar.addWidget(self.export_button);layout.addLayout(toolbar)
        splitter=QSplitter();layout.addWidget(splitter,1)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setMinimumWidth(310);scroll.setMaximumWidth(400);splitter.addWidget(scroll);self.form_scroll=scroll
        splitter.setChildrenCollapsible(False)
        self.form_toggle.clicked.connect(self.toggle_form)
        settings=QWidget();settings.setObjectName('settings');scroll.setWidget(settings)
        left=QVBoxLayout(settings);left.setContentsMargins(0,6,10,16);left.setSpacing(18)
        def hint(text):
            label=QLabel(text);label.setObjectName('hint');label.setWordWrap(True);return label
        def group(title):
            box=QFrame();box.setObjectName('section');box_layout=QVBoxLayout(box)
            box_layout.setContentsMargins(16,16,16,18);box_layout.setSpacing(12)
            heading=QLabel(title);heading.setObjectName('sectionTitle');box_layout.addWidget(heading)
            left.addWidget(box);return box,box_layout
        box,identity=group(tr('01  基本資料'))
        self.name=QLineEdit();self.name.setPlaceholderText(tr('姓名'));self.name.setMaxLength(80)
        self.gender=QComboBox()
        for value in ('男','女'):self.gender.addItem(tr(value),value)
        identity.addWidget(QLabel(tr('姓名')));identity.addWidget(self.name)
        identity.addWidget(QLabel(tr('性別')));identity.addWidget(self.gender)
        identity.addWidget(QLabel(tr('備註（選填）')));self.notes=QPlainTextEdit();self.notes.setPlaceholderText(tr('需要區分相同個人資料時，請填寫備註。'))
        self.notes.setFixedHeight(78);identity.addWidget(self.notes)
        box,birth_layout=group(tr('02  出生時間地點'))
        birth_layout.addWidget(hint(tr('填寫出生當地的鐘錶時間；不確定秒數時可填 00。')))
        self.date=DateField();self.time=TimeField()
        birth_layout.addWidget(QLabel(tr('日期')));birth_layout.addWidget(self.date)
        birth_layout.addWidget(QLabel(tr('時間（時：分：秒）')));birth_layout.addWidget(self.time)
        geo=birth_layout
        geo.addWidget(hint(tr('經緯度與時區分開設定；時區選單不會更改經緯度。')))
        self.lookup_button=QPushButton(tr('用出生地址查座標'));geo.addWidget(self.lookup_button);self.lookup_button.clicked.connect(self.lookup_coordinates)
        self.lon=CoordinateField(180,tr('經度'));self.lat=CoordinateField(89.99999,tr('緯度'))
        self.ew=QComboBox();self.ew.addItems([tr('東經 E'),tr('西經 W')]);self.ns=QComboBox();self.ns.addItems([tr('北緯 N'),tr('南緯 S')])
        f=QFormLayout();f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows);f.setVerticalSpacing(10)
        for label,number,direction in [(tr('經度'),self.lon,self.ew),(tr('緯度'),self.lat,self.ns)]:
            direction.setMinimumWidth(105);direction.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            number.setMinimumWidth(90)
            row=QHBoxLayout();row.addWidget(number,1);row.addWidget(direction);f.addRow(label,row)
        geo.addLayout(f)
        geo.addWidget(hint(tr('輸入十進位度，最多五位小數。查詢座標後，請自行核對下方出生地區時區。')))
        self.zone=QComboBox();self.zone.setEditable(True);self.zone.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.zone.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.zone.setMinimumContentsLength(16);self.zone.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        zones=list(ZONE_NAMES)+[z for z in sorted(available_timezones()) if z not in ZONE_NAMES]
        for zone in zones:self.zone.addItem((tr(ZONE_NAMES[zone])+' · '+zone) if zone in ZONE_NAMES else zone,zone)
        self.zone.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.zone.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        geo.addWidget(QLabel(tr('出生地區時區')));geo.addWidget(self.zone)
        self.time_info=QLabel();self.time_info.setWordWrap(True);self.time_info.setObjectName('status');geo.addWidget(self.time_info)
        self.fold=QComboBox();self.fold.addItem(tr('重複鐘點：請選擇'),None);self.fold.addItem(tr('第一次（較早的時刻）'),0);self.fold.addItem(tr('第二次（較晚的時刻）'),1)
        self.fold.setVisible(False);geo.addWidget(self.fold)
        self.dst_mode=QComboBox();self.dst_mode.addItems([tr('自動依地區與日期判斷'),tr('手動修正夏令時間')]);geo.addWidget(self.dst_mode)
        self.dst=QCheckBox(tr('出生時間使用夏令時間'));geo.addWidget(self.dst)
        self.dst_amount=QSpinBox();self.dst_amount.setRange(-120,180);self.dst_amount.setValue(60);self.dst_amount.setSuffix(tr(' 分鐘'))
        self.dst_amount.setVisible(False);geo.addWidget(self.dst_amount)
        box,options=group(tr('03  星盤設定'))
        self.house=QComboBox()
        for code,name in HOUSE_SYSTEMS.items():self.house.addItem(tr(name),code)
        options.addWidget(QLabel(tr('分宮制')));options.addWidget(self.house)
        options.addWidget(hint(tr('決定十二宮的劃分方式；預設 Placidus。')))
        self.house_latitude=QCheckBox(tr('歸宮納入天體黃緯'));self.house_latitude.setChecked(True)
        options.addWidget(self.house_latitude)
        options.addWidget(hint(tr('開啟：宮位位置圖；關閉：黃經輪盤。切換後請重新排盤，星座與黃經不變。')))
        self.advanced_toggle=QToolButton();self.advanced_toggle.setText(tr('進階顯示設定'));self.advanced_toggle.setObjectName('disclosure')
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.advanced_toggle.setArrowType(Qt.ArrowType.RightArrow);self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        options.addWidget(self.advanced_toggle)
        self.advanced=QWidget();advanced_layout=QVBoxLayout(self.advanced);advanced_layout.setContentsMargins(0,0,0,0)
        options.addWidget(self.advanced);self.advanced.setVisible(False)
        options=advanced_layout
        self.small=QCheckBox(tr('顯示小行星'));self.small.setChecked(True);options.addWidget(self.small)
        options.addWidget(hint(tr('凱龍星、婚神星、智神星、灶神星、穀神星')))
        self.minor=QCheckBox(tr('顯示次要相位'));self.minor.setChecked(True);options.addWidget(self.minor)
        options.addWidget(hint(tr('30°、45°、72°、135°、150°；在圖上以虛線顯示。')))
        options.addWidget(hint(tr('天王星、海王星、冥王星及出生資訊固定顯示。')))
        options.addWidget(hint(tr('容許度採用嚴格預設；勾選下方「自訂相位容許度」即可修改。取消勾選則使用嚴格預設。')))
        self.orb_group=QGroupBox(tr('自訂相位容許度'));self.orb_group.setCheckable(True);self.orb_group.setChecked(False)
        orb_layout=QFormLayout(self.orb_group);self.orb_controls={}
        if language()=='en-US':orb_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        for angle,name,orb,color,minor in ASPECTS:
            spin=QDoubleSpinBox();spin.setRange(0,15);spin.setDecimals(1);spin.setValue(orb);spin.setSuffix('°')
            self.orb_controls[angle]=spin;orb_layout.addRow(f'{tr(name)} {angle}°',spin)
        self.orb_group.setToolTip(tr('容許與理想相位角度相差多少度。這是判定規則，不是計算誤差。'))
        options.addWidget(self.orb_group);left.addStretch()
        self.advanced_toggle.toggled.connect(self.toggle_advanced)
        right=QWidget();right_layout=QVBoxLayout(right);right_layout.setContentsMargins(8,0,0,0);splitter.addWidget(right)
        self.house_notice=QFrame();self.house_notice.setObjectName('houseNotice')
        notice_layout=QVBoxLayout(self.house_notice);notice_layout.setContentsMargins(12,8,12,8);notice_layout.setSpacing(3)
        self.house_notice_label=QLabel(azimuth_notice_text());self.house_notice_label.setWordWrap(True)
        notice_layout.addWidget(self.house_notice_label)
        self.house_notice_help=QPushButton(tr('閱讀 Azimuth 說明'));notice_layout.addWidget(self.house_notice_help,0,Qt.AlignmentFlag.AlignLeft)
        self.house_notice_help.clicked.connect(lambda:show_azimuth_help(self))
        self.house_notice.hide();right_layout.addWidget(self.house_notice)
        self.tabs=QTabWidget();self.wheel=ChartWidget();self.tabs.addTab(self.wheel,tr('星盤圖'))
        self.positions=self.table([tr('天體／點'),tr('黃道位置'),tr('宮位'),tr('運行')]);self.tabs.addTab(self.positions,tr('天體位置'))
        self.houses=self.table([tr('宮位'),tr('宮頭位置')]);self.tabs.addTab(self.houses,tr('十二宮'))
        aspect_tabs=QTabWidget();self.matrix=AspectMatrix();aspect_tabs.addTab(self.matrix,tr('相位圖'))
        self.aspect_table=self.table([tr('天體 A'),tr('天體 B'),tr('相位'),tr('偏離角度'),tr('容許度')]);aspect_tabs.addTab(self.aspect_table,tr('詳細列表'))
        self.tabs.addTab(aspect_tabs,tr('相位'))
        right_layout.addWidget(self.tabs,1);self.status=QLabel(tr('填寫出生資料後按「排星盤」。'));self.status.setWordWrap(True)
        self.status.setObjectName('status');layout.addWidget(self.status)
        self.export_button.setEnabled(False)
        splitter.setSizes([350,1050])
        self.calculate_button.clicked.connect(self.calculate);self.export_button.clicked.connect(self.export)
        self.new_button.clicked.connect(self.new_record);self.load_button.clicked.connect(self.choose_record)
        self.save_button.clicked.connect(lambda:self.save_record())
        self.dst_mode.currentIndexChanged.connect(self.dst_mode_changed)
        for widget,signal in [(self.date,'textChanged'),(self.time,'textChanged'),(self.lon,'textChanged'),(self.lat,'textChanged'),
                              (self.ew,'currentIndexChanged'),(self.ns,'currentIndexChanged'),(self.zone,'editTextChanged'),
                              (self.fold,'currentIndexChanged'),(self.dst_mode,'currentIndexChanged'),(self.dst,'toggled'),
                              (self.dst_amount,'valueChanged'),(self.house,'currentIndexChanged'),(self.house_latitude,'toggled')]:
            getattr(widget,signal).connect(self.changed)
        for widget,signal in [(self.name,'textChanged'),(self.notes,'textChanged'),(self.gender,'currentIndexChanged'),
                              (self.small,'toggled'),(self.minor,'toggled'),(self.orb_group,'toggled')]:
            getattr(widget,signal).connect(self.display_changed)
        for spin in self.orb_controls.values():spin.valueChanged.connect(self.display_changed)
        self.refresh_time()
        self.saved_payload=self.form_snapshot();self.initial_payload=self.form_snapshot()
        for field in (self.name,self.date,self.time,self.lon,self.lat,self.zone.lineEdit()):
            field.editingFinished.connect(lambda w=field:w.setText(trim_text(w.text())))

    def switch_mode(self,index):
        if index==1 and self.timeline_page is None:
            from .timeline_ui import TimelinePage
            self.timeline_page=TimelinePage(self)
            self.mode_stack.addWidget(self.timeline_page)
        self.mode_stack.setCurrentIndex(index)
        self.form_toggle.setVisible(index==0)
        self.record_status.setVisible(index==0)
        for i,action in enumerate(self.mode_menu_actions):action.setChecked(i==index)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'mode_tabs'):
            compact=self.height()<650
            self.mode_tabs.setVisible(not compact)
            self.mode_menu.setVisible(compact)

    def choose_language(self):
        try:selected=self.store.load_ui_language()
        except Exception:
            QMessageBox.warning(self,tr('無法讀取設定'),tr('無法讀取語言設定，請確認本機資料庫可存取。'));return
        dialog=LanguageDialog(selected,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        selected=dialog.languages.currentData()
        try:self.store.save_ui_language(selected)
        except Exception:
            QMessageBox.warning(self,tr('無法儲存設定'),tr('語言設定未能儲存，請確認本機資料庫可寫入。'));return
        QMessageBox.information(self,tr('介面語言'),tr('已儲存。下次啟動將使用 {language}。',language=LANGUAGES[selected]))

    def toggle_form(self):
        visible=not self.form_scroll.isVisible();self.form_scroll.setVisible(visible)
        self.form_toggle.setText(tr('收合填寫區') if visible else tr('展開填寫區'))

    def lookup_coordinates(self):
        try:self.geocode_key=self.store.load_geocode_key()
        except Exception:
            QMessageBox.warning(self,tr('無法讀取設定'),tr('無法從本機資料庫讀取 API key，請確認資料庫可存取。'));return
        dialog=GeocodeDialog(self,self.geocode_key)
        accepted=dialog.exec()==QDialog.DialogCode.Accepted
        self.geocode_key=trim_text(dialog.key.text())
        try:self.store.save_geocode_key(self.geocode_key)
        except Exception:
            QMessageBox.warning(self,tr('無法儲存設定'),tr('API key 未能儲存至本機資料庫，下次開啟時需重新輸入。'))
        if accepted and dialog.coordinates:
            lon,lat=dialog.coordinates
            self.lon.setValue(abs(lon));self.lat.setValue(abs(lat))
            self.ew.setCurrentIndex(int(lon<0));self.ns.setCurrentIndex(int(lat<0))
            self.status.setText(tr('已帶入經緯度。請核對出生地區時區，再按「排星盤」。'))
            self.zone.setFocus()
        dialog.address.clear();dialog.results=[];dialog.list.clear();dialog.key.clear();dialog.deleteLater()

    def table(self,headers):
        table=QTableWidget(0,len(headers));table.verticalHeader().setVisible(False)
        # Multi-line headers retain readable type at narrow window sizes.
        wrapped=[]
        for text in headers:
            lines=['']
            for word in text.split(' '):
                candidate=(lines[-1]+' '+word).strip()
                if lines[-1] and table.fontMetrics().horizontalAdvance(candidate)>100:lines.append(word)
                else:lines[-1]=candidate
            wrapped.append('\n'.join(lines))
        table.setHorizontalHeaderLabels(wrapped)
        for i,text in enumerate(headers):table.horizontalHeaderItem(i).setToolTip(text)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setShowGrid(False);table.setWordWrap(True)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setMinimumSectionSize(40)
        table.horizontalHeader().sectionResized.connect(lambda *_:table.resizeRowsToContents())
        return table

    def input(self):
        zone=trim_text(self.zone.currentText().split(' · ')[-1])
        return BirthInput(local_iso=self.date.date().toString('yyyy-MM-dd')+'T'+self.time.iso_text(),
            zone=zone,longitude=self.lon.value()*(1 if self.ew.currentIndex()==0 else -1),
            latitude=self.lat.value()*(1 if self.ns.currentIndex()==0 else -1),system=self.house.currentData(),
            small_bodies=self.small.isChecked(),minor_aspects=self.minor.isChecked(),fold=self.fold.currentData(),
            house_latitude=self.house_latitude.isChecked(),
            manual_dst=self.dst_mode.currentIndex()==1,dst_enabled=self.dst.isChecked(),dst_minutes=self.dst_amount.value(),
            name=trim_text(self.name.text()),gender=self.gender.currentData(),notes=trim_text(self.notes.toPlainText()))

    def orbs(self):
        return {a:self.orb_controls[a].value() if self.orb_group.isChecked() else default for a,_,default,_,_ in ASPECTS}

    def changed(self,*args):
        if self.loading:return
        self.revision+=1;self.export_button.setEnabled(False)
        if self.chart:self.status.setText(tr('資料已變更，請重新排盤；畫面仍為上一次結果。'))
        self.refresh_time()
        self.update_record_status()

    def toggle_advanced(self,expanded):
        self.advanced.setVisible(expanded)
        self.advanced_toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def display_changed(self,*args):
        if self.loading:return
        self.update_record_status()
        try:
            if self.chart and calculation_key(self.input())==calculation_key(BirthInput(**self.chart['input'])):self.apply_chart(self.chart)
        except ValueError:pass

    def dst_mode_changed(self,index):
        if index==1:
            try:
                resolved=resolve_local(replace(self.time_input(),manual_dst=False))
                self.dst.blockSignals(True);self.dst.setChecked(bool(resolved['dst']));self.dst.blockSignals(False)
                self.dst_amount.blockSignals(True)
                self.dst_amount.setValue(int(resolved['dst'].total_seconds()/60) if resolved['dst'] else 60)
                self.dst_amount.blockSignals(False)
            except (ValueError,KeyError):pass

    def time_input(self):
        return BirthInput(local_iso=self.date.date().toString('yyyy-MM-dd')+'T'+self.time.iso_text(),
            zone=trim_text(self.zone.currentText().split(' · ')[-1]),fold=self.fold.currentData(),
            manual_dst=self.dst_mode.currentIndex()==1,dst_enabled=self.dst.isChecked(),dst_minutes=self.dst_amount.value())

    def refresh_time(self):
        manual=self.dst_mode.currentIndex()==1;self.dst.setEnabled(manual);self.dst_amount.setVisible(manual)
        try:
            birth=self.time_input();resolved=resolve_local(birth)
            self.fold.setVisible(resolved['ambiguous'])
            if not resolved['ambiguous'] and self.fold.currentIndex()!=0:
                self.fold.blockSignals(True);self.fold.setCurrentIndex(0);self.fold.blockSignals(False)
            if not manual:
                self.dst.blockSignals(True);self.dst.setChecked(bool(resolved['dst']));self.dst.blockSignals(False)
            utc=resolved['utc'].strftime('%Y/%m/%d %H:%M:%S')
            daylight=tr('夏令調整 ')+f'{resolved["dst"].total_seconds()/60:g}'+tr(' 分鐘') if resolved['dst'] else tr('未使用夏令時間')
            self.time_info.setText(tr('{p0} · {p1}\n對應 UTC：{p2}', p0=resolved['offset_label'], p1=daylight, p2=utc))
        except Exception as exc:
            if not trim_text(self.date.text()) or not trim_text(self.time.text()):
                self.fold.hide();self.time_info.setText(tr('填妥出生日期與時間後，顯示時差、夏令時間及 UTC。'));return
            text=error_text(exc);self.fold.setVisible(isinstance(exc,AmbiguousTimeError))
            self.time_info.setText(tr('請從清單選擇有效的地區時區。') if isinstance(exc,ZoneInfoNotFoundError) else text)

    def calculate(self):
        if self.worker and self.worker.isRunning():return
        try:birth=self.input();resolve_local(birth)
        except Exception as exc:self.error(error_text(exc));return
        self.calculate_button.setEnabled(False);self.export_button.setEnabled(False)
        self.new_button.setEnabled(False);self.load_button.setEnabled(False)
        self.status.setText(tr('正在計算星盤…'));self.pending_revision=self.revision
        self.worker=Calculation(birth,self.orbs(),self.engine,self)
        self.worker.succeeded.connect(self.apply_chart);self.worker.failed.connect(self.error);self.worker.finished.connect(self.finished)
        self.worker.start()

    def finished(self):
        worker=self.worker;self.engine=worker.engine;self.worker=None
        worker.deleteLater();self.calculate_button.setEnabled(True)
        self.new_button.setEnabled(True);self.load_button.setEnabled(True)

    def apply_chart(self,chart):
        try:validate_chart_houses(chart)
        except UserError as exc:
            self.error(error_text(exc));return
        try:stale=calculation_key(self.input())!=calculation_key(BirthInput(**chart['input']))
        except ValueError:stale=True
        if not stale:chart=display_chart(chart,self.input(),self.orbs())
        self.chart=chart;self.wheel.set_chart(chart)
        self.house_notice.setVisible(has_azimuth_notice(chart))
        self.house_notice_label.setText(azimuth_notice_text(chart))
        self.matrix.set_chart(chart)
        def fill(table,rows):
            table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                for j,value in enumerate(row):table.setItem(i,j,QTableWidgetItem(str(value)))
        fill(self.positions,[(tr(p['name']),localized_zodiac(p['lon']),p['house'] if p['house'] is not None else tr('未定義'),tr('逆行 R') if p['retrograde'] else ('—' if p['speed'] is None else tr('順行'))) for p in chart['points']])
        fill(self.houses,[(tr('第 {p0} 宮', p0=i + 1),localized_zodiac(v)) for i,v in enumerate(chart['cusps'])])
        if language()=='en-US':
            self.positions.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
            for table,longitudes in ((self.positions,[p['lon'] for p in chart['points']]),(self.houses,chart['cusps'])):
                table.setIconSize(QSize(20,20))
                table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
                for row,lon in enumerate(longitudes):
                    item=table.item(row,1);item.setIcon(zodiac_icon(zodiac_index(lon)))
                    item.setToolTip(item.text())
        fill(self.aspect_table,[(tr(a['a']),tr(a['b']),f'{tr(a["name"])} {a["angle"]}°',f'{a["orb"]:.3f}°',f'{a["limit"]:g}°') for a in sorted_aspect_details(chart['aspects'])])
        self.export_button.setEnabled(not stale)
        self.status.setText(tr('資料已變更，請重新排盤；畫面為上一筆計算。') if stale else
            tr('已完成 · {system} · {count} 組相位',system=tr(HOUSE_SYSTEMS[chart['input']['system']]),count=len(chart['aspects']))+
            ('\n'+' '.join(tr(note) for note in chart['notes']) if chart['notes'] else ''))

    def error(self,message):
        # A failed calculation must not leave an exportable previous result,
        # including when a caller invokes export_ready() directly.
        self.chart=None;self.wheel.set_chart(None);self.house_notice.hide()
        self.positions.setRowCount(0);self.houses.setRowCount(0);self.aspect_table.setRowCount(0)
        self.matrix.table.setRowCount(0);self.matrix.table.setColumnCount(0);self.matrix.points=[]
        self.matrix.detail.setText(tr('排盤後即可查看相位。'))
        self.status.setText(tr('無法排盤：')+message);self.export_button.setEnabled(False)
        QMessageBox.warning(self,tr('請確認出生資料'),message)

    def export_ready(self):
        if not self.chart:return False
        try:return calculation_key(self.input())==calculation_key(BirthInput(**self.chart['input']))
        except ValueError:return False

    def export(self):
        if not self.export_ready():
            self.status.setText(tr('請先按「排星盤」，完成後才能匯出文件。'));return
        dialog=ExportDialog(self);templates=dialog.templates;notes=dialog.notes
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        name=report_filename(self.chart['input'])
        directory=default_database_path().parent
        try:directory.mkdir(parents=True,exist_ok=True)
        except OSError:
            QMessageBox.warning(self,tr('無法開啟匯出位置'),tr('無法建立 Documents/openbirthchart 資料夾，請確認資料夾權限。'));return
        path,_=QFileDialog.getSaveFileName(self,tr('儲存星盤文件'),str(directory/name),'HTML (*.html)')
        if path:
            if not path.lower().endswith('.html'):path+='.html'
            try:
                export_html(self.chart,path,include_notes=notes.isChecked(),template_dir=Path(templates.currentData()))
                self.status.setText(tr('已匯出文件：')+path)
            except Exception as exc:QMessageBox.warning(self,tr('無法匯出'),error_text(exc))

    def profile_payload(self):
        return dict(schema=1,input=asdict(self.input()),custom_orbs=self.orb_group.isChecked(),
                    orb_values={str(a):spin.value() for a,spin in self.orb_controls.items()},app_version=APP_VERSION)

    def is_dirty(self):
        return self.saved_payload is not None and self.form_snapshot()!=self.saved_payload

    def form_snapshot(self):
        return dict(text=[trim_text(w.text()) for w in (self.name,self.date,self.time,self.lon,self.lat)],
            notes=trim_text(self.notes.toPlainText()),zone=trim_text(self.zone.currentText().split(' · ')[-1]),
            indices=[w.currentIndex() for w in (self.gender,self.ew,self.ns,self.house,self.fold,self.dst_mode)],
            checks=[w.isChecked() for w in (self.dst,self.small,self.minor,self.orb_group,self.house_latitude)],
            dst_minutes=self.dst_amount.value(),orbs=[w.value() for w in self.orb_controls.values()])

    def update_record_status(self):
        title=trim_text(self.name.text()) or tr('未命名')
        text=f'{title[:16]} · {self.gender.currentText()} · '+(tr('已存檔案') if self.record_id else tr('新檔案'))
        if self.is_dirty():text+=tr(' · 尚未儲存')
        self.record_status.setText(text);self.record_status.setToolTip(str(self.store.path))

    def save_record(self):
        try:
            payload=validate_profile(self.profile_payload())
            try:record_id=self.store.save(payload,self.record_id)
            except DuplicateProfile as duplicate:
                if not self.confirm_duplicate(duplicate,payload):return False
                record_id=self.store.save(payload,self.record_id,confirm_duplicate=True)
        except Exception as exc:
            QMessageBox.warning(self,tr('無法儲存'),error_text(exc));return False
        self.name.setText(payload['input']['name']);self.notes.setPlainText(payload['input']['notes'])
        self.record_id=record_id;self.saved_payload=self.form_snapshot();self.update_record_status()
        self.status.setText(tr('個人檔案已儲存：')+str(self.store.path))
        return True

    def confirm_duplicate(self,error,payload):
        dialog=QDialog(self);dialog.setWindowTitle(tr('發現相同個人資料'));dialog.resize(680,420)
        layout=QVBoxLayout(dialog);dialog_layout(layout);label=QLabel(error_text(error));label.setWordWrap(True);layout.addWidget(label)
        table=self.table([tr('姓名'),tr('性別'),tr('備註'),tr('夏令／重複鐘點差異')]);table.setRowCount(len(error.matches));layout.addWidget(table)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        b=payload['input']
        for i,row in enumerate(error.matches):
            differences=[]
            for key,title in [('manual_dst',tr('修正模式')),('dst_enabled',tr('手動夏令開關')),('dst_minutes',tr('修正分鐘')),('fold',tr('重複鐘點'))]:
                if (key=='fold' or row['manual_dst'] or b['manual_dst']) and row[key]!=b[key]:differences.append(title)
            for j,value in enumerate((row['name'],tr(row['gender']),row['notes'] or tr('（未填）'),'、'.join(differences) or tr('無'))):
                item=QTableWidgetItem(value);item.setToolTip(value);table.setItem(i,j,item)
        table.selectRow(0)
        note=QLabel(tr('本筆備註：')+(b['notes'] or tr('尚未填寫；請返回表單填寫後再儲存。')));note.setWordWrap(True);layout.addWidget(note)
        buttons=QDialogButtonBox();existing=buttons.addButton(tr('載入選取的原檔案'),QDialogButtonBox.ButtonRole.ActionRole)
        proceed=buttons.addButton(tr('依備註區分並儲存'),QDialogButtonBox.ButtonRole.AcceptRole);proceed.setEnabled(bool(b['notes']))
        primary(proceed)
        buttons.addButton(tr('返回編輯'),QDialogButtonBox.ButtonRole.RejectRole);layout.addWidget(buttons)
        selected=[]
        def choose_existing():
            if table.currentRow()>=0:selected.append(error.matches[table.currentRow()]['id']);dialog.reject()
        existing.clicked.connect(choose_existing);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        result=dialog.exec()
        if selected:
            # This choice is explicit; never overwrite the original with the new draft.
            confirm=QMessageBox.question(self,tr('放棄目前修改？'),tr('載入原檔案會放棄目前未儲存的修改。確定要載入嗎？'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
            if confirm==QMessageBox.StandardButton.Yes:
                try:self.restore_profile(self.store.load(selected[0]),selected[0]);self.calculate()
                except Exception as exc:QMessageBox.warning(self,tr('無法載入'),error_text(exc))
            return False
        if result!=QDialog.DialogCode.Accepted:
            self.form_scroll.show();self.form_toggle.setText(tr('收合填寫區'));self.form_scroll.ensureWidgetVisible(self.notes);self.notes.setFocus();return False
        return True

    def confirm_discard(self):
        if not self.prompt_unsaved or not self.is_dirty():return True
        box=QMessageBox(self);box.setWindowTitle(tr('尚未儲存的修改'))
        box.setText(tr('目前的星盤資料尚未儲存。'))
        save=box.addButton(tr('儲存'),QMessageBox.ButtonRole.AcceptRole)
        primary(save)
        discard=box.addButton(tr('不儲存'),QMessageBox.ButtonRole.DestructiveRole)
        cancel=box.addButton(tr('取消'),QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel);box.exec()
        if box.clickedButton()==save:return self.save_record()
        return box.clickedButton()==discard

    def restore_profile(self,payload,record_id=None):
        payload=validate_profile(payload);birth=BirthInput(**payload['input'])
        widgets=[self.name,self.notes,self.gender,self.date,self.time,self.lon,self.lat,self.ew,self.ns,self.zone,
                 self.house,self.fold,self.dst_mode,self.dst,self.dst_amount,self.small,self.minor,self.orb_group,self.house_latitude,
                 *self.orb_controls.values()]
        self.loading=True;blockers=[QSignalBlocker(w) for w in widgets]
        try:
            self.name.setText(birth.name);self.notes.setPlainText(birth.notes);self.gender.setCurrentIndex(self.gender.findData(birth.gender))
            self.date.setDate(QDate.fromString(birth.local_iso[:10],'yyyy-MM-dd'))
            self.time.setTime(QTime.fromString(birth.local_iso[11:],'HH:mm:ss'))
            self.lon.setValue(abs(birth.longitude));self.lat.setValue(abs(birth.latitude))
            self.ew.setCurrentIndex(int(birth.longitude<0));self.ns.setCurrentIndex(int(birth.latitude<0))
            self.zone.setCurrentIndex(self.zone.findData(birth.zone))
            self.house.setCurrentIndex(self.house.findData(birth.system))
            self.house_latitude.setChecked(birth.house_latitude)
            self.fold.setCurrentIndex(self.fold.findData(birth.fold))
            self.dst_mode.setCurrentIndex(int(birth.manual_dst));self.dst.setChecked(birth.dst_enabled)
            self.dst_amount.setValue(birth.dst_minutes);self.small.setChecked(birth.small_bodies)
            self.minor.setChecked(birth.minor_aspects);self.orb_group.setChecked(payload['custom_orbs'])
            for angle,spin in self.orb_controls.items():spin.setValue(payload['orb_values'][str(angle)])
        finally:
            del blockers;self.loading=False
        self.chart=None;self.wheel.set_chart(None);self.house_notice.hide()
        self.positions.setRowCount(0);self.houses.setRowCount(0);self.aspect_table.setRowCount(0)
        self.matrix.table.setRowCount(0);self.matrix.table.setColumnCount(0);self.matrix.points=[]
        self.matrix.detail.setText(tr('排盤後即可查看相位。'))
        self.export_button.setEnabled(False)
        self.refresh_time();self.record_id=record_id;self.saved_payload=self.form_snapshot()
        self.update_record_status();self.status.setText(tr('已載入資料，正在準備星盤。') if record_id else tr('填寫出生資料後按「排星盤」。'))

    def new_record(self):
        if self.worker or not self.confirm_discard():return
        from dataclasses import asdict
        self.restore_profile(dict(schema=1,input=asdict(BirthInput()),custom_orbs=False,
            orb_values={str(a):o for a,_,o,_,_ in ASPECTS},app_version=APP_VERSION))
        self.loading=True
        for field in (self.name,self.date,self.time,self.lon,self.lat):field.clear()
        self.notes.clear();self.loading=False
        self.refresh_time();self.saved_payload=self.form_snapshot();self.update_record_status()
        self.advanced_toggle.setChecked(False)
        self.name.setFocus()

    def load_record(self,record_id):
        if self.worker:return False
        if not self.confirm_discard():return False
        try:payload=self.store.load(record_id)
        except Exception as exc:
            QMessageBox.warning(self,tr('無法載入'),error_text(exc));return False
        self.restore_profile(payload,record_id);self.calculate();return True

    def choose_record(self):
        try:rows=self.store.list()
        except Exception as exc:
            QMessageBox.warning(self,tr('無法開啟資料庫'),error_text(exc));return
        dialog=QDialog(self);dialog.setWindowTitle(tr('載入個人檔案'));dialog.resize(900,520)
        layout=QVBoxLayout(dialog);dialog_layout(layout);search=QLineEdit();search.setPlaceholderText(tr('搜尋姓名、性別、出生日期或備註'));layout.addWidget(search)
        table=self.table([tr('姓名'),tr('性別'),tr('出生時間'),tr('經緯度／時區'),tr('備註'),tr('更新時間')]);table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setMinimumSectionSize(84)
        table.setRowCount(len(rows));layout.addWidget(table)
        from datetime import datetime
        for i,row in enumerate(rows):
            for j,value in enumerate((row['name'],tr(row['gender']),row['local_iso'].replace('T',' '),f'{row["longitude"]:.5f}\n{row["latitude"]:.5f}\n{row["zone"]}',row['notes'],
                datetime.fromisoformat(row['updated_at']).astimezone().strftime('%Y/%m/%d %H:%M'))):
                item=QTableWidgetItem(value);item.setToolTip(value);table.setItem(i,j,item)
        note=QLabel(str(self.store.path) if rows else tr('尚無已儲存的星盤。'));note.setWordWrap(True);layout.addWidget(note)
        buttons=QDialogButtonBox();open_button=buttons.addButton(tr('載入'),QDialogButtonBox.ButtonRole.AcceptRole)
        primary(open_button)
        buttons.addButton(tr('取消'),QDialogButtonBox.ButtonRole.RejectRole);layout.addWidget(buttons)
        def update_selection():
            selected=table.currentRow();open_button.setEnabled(selected>=0 and not table.isRowHidden(selected))
        def filter_rows(text):
            text=trim_text(text)
            for i,row in enumerate(rows):
                table.setRowHidden(i,text.casefold() not in (row['name']+' '+tr(row['gender'])+' '+row['local_iso']+' '+row['notes']).casefold())
            update_selection()
        search.textChanged.connect(filter_rows);table.itemSelectionChanged.connect(update_selection)
        table.cellDoubleClicked.connect(lambda r,c:dialog.accept())
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);open_button.setEnabled(False)
        if dialog.exec()==QDialog.DialogCode.Accepted and table.currentRow()>=0:
            self.load_record(rows[table.currentRow()]['id'])

    def closeEvent(self,event):
        if self.timeline_page is not None and not self.timeline_page.request_close():
            event.ignore();return
        if self.worker and self.worker.isRunning():
            self.status.setText(tr('計算尚未結束，完成後即可關閉。'));event.ignore();return
        if not self.confirm_discard():event.ignore();return
        super().closeEvent(event)
