# Third-party software, fonts and data / 第三方元件

OpenBirthChart v0.6.7 original code: AGPL-3.0-only, Copyright (C) 2026 OpenBirthChart contributors. This does not replace third-party copyrights or licenses. Original texts are preserved in `licenses/` and the corresponding source archives.

## Runtime and build components

| Component | Pinned version | Upstream terms / scope |
| --- | --- | --- |
| LibEphemeris | 3.2.2 | AGPL-3.0-only; original licensing, notices and adapted-file attributions retained |
| PySide6-Essentials / shiboken6 | 6.12.0 | LGPL-3.0-only / applicable upstream GPL alternatives; unmodified, dynamically loaded |
| Qt Core / Gui / Network / Widgets / SVG | 6.12.0 | Applicable Qt open-source terms; bundled third-party notices retained |
| CPython | 3.12.14 | PSF license and included third-party notices |
| NumPy | 2.5.4 | BSD-3-Clause and bundled component terms (OpenBLAS and others) |
| PyERFA | 2.0.1.5 | BSD-3-Clause; ERFA/SOFA provenance in upstream notices |
| Skyfield / jplephem / sgp4 | 1.55 / 2.24 / 2.27 | MIT |
| skyfield-data | 7.0.0 | Package MIT; upstream data provenance retained |
| tzdata | 2026.5 | Apache-2.0 package; IANA database terms retained |
| zstandard | 0.25.0 | BSD-3-Clause and upstream bundled terms |
| certifi | 2026.10.23 | MPL-2.0; unmodified source supplied |
| PyInstaller | 6.22.3 | GPL with bootloader distribution exception; exact source/exception retained |
| Other packaging dependencies | See locks | Exact versions and all available notices in `licenses/components.json` |

Inventory includes build dependencies as well as runtime dependencies; their presence in the inventory does not mean every module is loaded by the application. PySide6-Essentials provides the Qt modules actually collected; Qt Addons are not installed. Source archives include qtbase, qtsvg, qttools, qttranslations and pyside-setup, with their upstream build instructions and third-party texts.

Qt DLLs and plugins are shipped as separate files. Users may modify/replace/rebuild applicable components and debug those changes under the license. Build and replacement instructions are in `docs/BUILDING.md` in the package. Do not apply an EULA that prohibits those freedoms.

## Fonts and data

- Noto Sans TC: original unmodified font, SIL OFL 1.1. Full text: `licenses/NotoSansTC-OFL.txt`.
- Astronomicon: Copyright (c) 2021 Roberto Corona; SIL OFL 1.1, Reserved Font Name Astronomicon. Full text: `licenses/Astronomicon-OFL.txt`. Original font is bundled unchanged; charts and English position tables render glyph outlines. HTML/SVG uses paths and does not require a remote font.
- JPL DE440s: fixed original JPL planetary ephemeris; source URL and SHA-256 in `data-sources.lock.json`. Preserve JPL provenance; no affiliation or endorsement is claimed.
- LibEphemeris data-v4 LEB2: upstream JPL-derived tables, original manifest/checksums retained; URLs and hashes in `desktop-data-sources.lock.json`. Generation source is in the LibEphemeris source archive; OpenBirthChart does not modify these files.
- IERS EOP and leap seconds: fixed Astropy IERS data redistribution, original wheel, data ReadMe and license retained. Exact artifact/URLs in `time-data-sources.lock.json`; attribution in `licenses/astropy-iers-data`.

## Swiss validation only

pyswisseph 2.10.3.2 is installed in an independent reference environment under AGPL v3. Swiss Ephemeris offers AGPL or its Professional License; this project uses the open-source route. Reference versions/data hashes and numerical differences remain in validation records. Swiss runtime modules and `.se1` files are not included in the desktop binary bundle. The comparison is not certification or endorsement.

## Corresponding sources

`third-party-sources.lock.json` gives exact archives, upstream URLs and SHA-256. The complete `OpenBirthChart-0.6.7-source.zip` contains these archives under `third_party/sources/`. Publish it beside the Windows ZIP; upstream links alone do not replace this release's source distribution. Components are unmodified. License metadata is an index; the complete upstream texts govern.

Sources: [LibEphemeris v3.2.2](https://github.com/g-battaglia/libephemeris/tree/v3.2.2), [Qt obligations](https://www.qt.io/development/open-source-lgpl-obligations), [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html), [OFL FAQ](https://openfontlicense.org/ofl-faq/), [Swiss license](https://github.com/aloistr/swisseph/blob/master/LICENSE).

## 中文摘要

本版保留第三方原授權與著作權，主程式 AGPL 不會取代字型、Qt 或資料條款。實際套件版本與來源已固定，依賴沒有因 v0.6.7 升級。完整來源包附上鎖定的上游來源及原始通知，Windows 包附授權文本，並提供離線法律告知。Swiss 僅供獨立驗證，相關說明保留。主程式與第三方修改／重新建置方式見建置文件。
