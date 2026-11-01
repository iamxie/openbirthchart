# Desktop interface translations

The first release supports `zh-TW` (default) and `en-US`. Use **語言 / Language**
in the main window. The preference is stored as `ui_language` in the existing
SQLite `app_settings` table and takes effect on the next launch. It is separate
from profile data and the report template selected for each export.

`desktop_en_US.ts` is the editable Qt Linguist translation catalog;
`desktop_en_US.qm` is the compiled runtime catalog. Traditional Chinese uses the
source messages, plus Qt's `qtbase_zh_TW.qm` for standard Qt controls. Native OS
file dialogs may continue to follow the operating system language.

From the project root:

```powershell
.venv-desktop/Scripts/python.exe scripts/build_translations.py --update
# Translate unfinished entries in desktop_en_US.ts with Qt Linguist or an XML editor.
.venv-desktop/Scripts/python.exe scripts/build_translations.py
```

The build validates missing translations and Python format placeholders before
calling Qt's bundled `lrelease`. Extraction recognizes literal calls to `tr()`
and `UserError()`, and includes canonical domain strings in model/storage/window
modules. Dynamic values require an inventory entry; do not translate complete
user-generated strings. Preserve placeholders and their format specifications.
The catalog's location attributes link messages to their source code.

`OpenBirthChart` is the UI/domain context; `BodyShort` contains compact celestial
labels. The bilingual language button and language self-names stay recognizable
in either interface. Personal names, notes, IANA zone IDs and geocoding result
addresses are not translated. Dates, coordinate input and numeric precision
retain the documented formats; changing UI language does not change locale
parsing, location, time zone or chart calculations.

Canonical chart names and legacy stored gender values remain stable. Translate
them only at presentation boundaries. `UserError` carries source text and format
values without importing Qt; `error_text()` translates it in the UI. Branch on
exception types (for example `AmbiguousTimeError`), never translated text.

HTML templates remain in `templates/report/`. The i18n tests compare domain
terminology with the English report and check both report languages under both
interfaces. Keep those terms synchronized when editing translations.

Run desktop tests and `scripts/check_desktop_layout.py --language en-US` (also
`zh-TW`), plus `scripts/check_i18n_ui.py`, before packaging. Check the actual
frozen application: a source run alone does not prove the catalogs were bundled.
