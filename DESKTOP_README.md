# Open BirthChart 0.7.0-dev

本分支為天象時間軸開發版，未合併主線、未公開發佈。請參閱 [功能與限制](docs/SKY_TIMELINE.md)。來源啟動使用本 checkout 的 `launch-desktop.ps1`；下方 0.6.7 發佈紀錄是已公開舊版，並不包含新時間軸。

v0.6.7 已在 GitHub 公開發佈。繁體中文與英文介面；AGPL-3.0-only，Copyright (C) 2026 OpenBirthChart contributors。

解壓縮整個 Windows x64 ZIP，執行 `OpenBirthChart.exe`。不要只複製 EXE；不需另裝 Python 或星曆。來源啟動請用 `setup-desktop.ps1`、`launch-desktop.ps1`。本版包含無效宮號攔截、英文星座圖示統一及離線「關於與授權」。

個人資料存在 `%USERPROFILE%\Documents\openbirthchart\data.sqlite`，未加密；與可攜程式資料夾分開。排盤離線，主動使用地址查詢才會連到 geocode.maps.co 並傳送地址／API key。請保管本地資料庫。

閏秒不支援排盤，不自動改時間。Polich–Page 無法唯一且連續歸宮時整盤拒絕；Koch 已知未定義狀態保留。完整功能與限制見 [README](README.md)，英文見 [README.en](README.en.md)。

同版完整對應來源為 `OpenBirthChart-0.6.7-source.zip`，包含依賴來源、固定資料與驗證封存；與 Windows ZIP 在 https://github.com/iamxie/openbirthchart/releases/tag/v0.6.7 免費提供。

Build/validation: [BUILDING](docs/BUILDING.md), [VALIDATION](docs/VALIDATION.md), [DEPENDENCY_UPGRADES](docs/DEPENDENCY_UPGRADES.md). License: [LICENSE](LICENSE), [NOTICE](NOTICE.md), [third-party notices](THIRD_PARTY_DESKTOP.md).
