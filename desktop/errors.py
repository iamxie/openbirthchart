# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Structured user-facing failures; source values stay independent of UI language."""

class UserError(ValueError):
    def __init__(self, source, **values):
        self.source=source
        self.values=values
        super().__init__(source)

    def __str__(self):
        return self.source.format(**self.values)


class AmbiguousTimeError(UserError):
    def __init__(self):
        super().__init__('這個鐘點在當天出現兩次，請選擇「第一次」或「第二次」。')
