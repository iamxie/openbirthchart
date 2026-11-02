# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Application-wide aspect rules, independent of personal profiles."""
import math
from .model import ASPECTS
from .errors import UserError


def default_orbs():
    return {angle:orb for angle,_,orb,_,_ in ASPECTS}


def validate_orbs(values):
    if not isinstance(values,dict) or len(values)!=len(default_orbs()) or set(map(str,values))!={str(a) for a in default_orbs()}:
        raise UserError('相位設定不完整。')
    result={}
    for key,value in values.items():
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=15:
            raise UserError('相位容許度需在 0～15 度內。')
        if abs(value*10-round(value*10))>1e-8:
            raise UserError('相位容許度最多一位小數。')
        result[int(key)]=float(value)
    return result


def orb_dialog(values,parent):
    from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QFormLayout,QDoubleSpinBox,QDialogButtonBox
    from .i18n import tr
    from .theme import dialog_layout,primary
    dialog=QDialog(parent);dialog.setWindowTitle(tr('設定 · 相位容許度'))
    layout=QVBoxLayout(dialog);dialog_layout(layout)
    hint=QLabel(tr('個人星盤與天象時間軸共用此設定。天象時間軸使用 0°、90°、120°、180°。'))
    hint.setWordWrap(True);layout.addWidget(hint)
    form=QFormLayout();controls={}
    for angle,name,_,_,_ in ASPECTS:
        spin=QDoubleSpinBox();spin.setRange(0,15);spin.setDecimals(1);spin.setSuffix('°');spin.setValue(values[angle])
        spin.lineEdit().setTextMargins(9,0,0,0)
        controls[angle]=spin;form.addRow(f'{tr(name)} {angle}°',spin)
    layout.addLayout(form)
    buttons=QDialogButtonBox();apply=buttons.addButton(tr('套用'),QDialogButtonBox.ButtonRole.AcceptRole);primary(apply)
    buttons.addButton(tr('取消'),QDialogButtonBox.ButtonRole.RejectRole)
    reset=buttons.addButton(tr('恢復預設值'),QDialogButtonBox.ButtonRole.ResetRole)
    reset.clicked.connect(lambda:[controls[a].setValue(v) for a,v in default_orbs().items()])
    buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
    dialog.resize(440,600)
    return dialog,controls
