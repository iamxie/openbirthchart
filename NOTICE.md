# Open BirthChart 0.6.7 — Copyright and license / 著作權與授權

Copyright (C) 2026 OpenBirthChart contributors.

OpenBirthChart 自有程式碼以 **GNU Affero General Public License version 3 only (AGPL-3.0-only)** 發佈。你可以依授權使用、研究、修改及再散布。程式不提供任何保證，包括適售性或特定用途適用性的默示保證。完整條文見隨附 `LICENSE` 或「關於與授權」的 AGPL 頁籤。

OpenBirthChart original code is licensed under **AGPL-3.0-only**. You may use, study, modify and redistribute it under that license. This program comes WITHOUT ANY WARRANTY, including implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. The complete, unmodified license is included in `LICENSE` and in the application's AGPL tab.

This grant covers original code in `desktop/`, `scripts/`, `tests/`, application entry points, build scripts and original templates unless a file identifies another license. Third-party software, fonts and datasets retain their own copyrights/licenses. Historical upstream snapshots are not relicensed by this notice.

自有授權不取代第三方條款。詳見 `THIRD_PARTY_DESKTOP.md` 與 `licenses/`。Qt／PySide6 採開源授權使用；允許依適用授權修改、替換及除錯函式庫，不施加額外逆向工程限制。應用程式可由對應來源重新建置。

## Corresponding source / 對應來源

Repository / 專案位置：https://github.com/iamxie/openbirthchart

Version / 版本：v0.6.7。發佈頁：https://github.com/iamxie/openbirthchart/releases/tag/v0.6.7

The release provides `OpenBirthChart-0.6.7-source.zip`, containing application/build/test sources, pinned runtime data and dependency source archives listed in `third-party-sources.lock.json`. Download it from the same page as the Windows ZIP, at no additional charge.

同版來源 ZIP 包含應用、建置與測試來源、固定執行資料及鎖定依賴來源，與 Windows ZIP 在同一發佈頁免費提供。

Qt/PySide6 and other dependencies are unmodified. Exact versions/source archives are recorded in the source manifest. See `docs/BUILDING.md` for installation and rebuild instructions. Original upstream license texts accompany source archives and the binary distribution.

## Validation / 驗證

The application calculates with LibEphemeris. Swiss Ephemeris / pyswisseph is used separately for cross-validation, not as a desktop runtime dependency. This describes methodology, not certification or endorsement. Known differences are documented; no universal equivalence is claimed.

本程式以 LibEphemeris 計算，Swiss 只供獨立交叉驗證，並非官方認證或背書。個人輸入與匯出內容不會僅因使用本程式而自動套用本程式授權；第三方內容仍適用原有條款。
