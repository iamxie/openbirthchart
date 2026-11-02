# Open BirthChart 0.7.0

繁體中文與英文介面；AGPL-3.0-only，Copyright (C) 2026 OpenBirthChart contributors。

本版加入[天象時間軸](docs/SKY_TIMELINE.md)、共用相位容許度、天象歷史、星盤播放與雙語離線文件匯出。逆行以深棕底白字 R 標示，快轉每次增加 15 fps，最高目標 120 fps；效能不足時放慢，不跳採樣點。

解壓縮整個 Windows x64 ZIP，執行 `OpenBirthChart.exe`，保留 `_internal`。不需另裝 Python 或星曆。來源啟動請用 `setup-desktop.ps1`、`launch-desktop.ps1`。

個人資料與全域設定在 `%USERPROFILE%\Documents\openbirthchart\data.sqlite`，天象結果與播放資料在同資料夾的 `skyhistory.sqlite`，兩者均未加密；與可攜程式資料夾分開。排盤離線，主動使用地址查詢才會傳送地址／API key。

日月只在播放器顯示位置，不參與天象相位與逆行；個人星盤計算規則不變。閏秒不支援排盤，不自動改時間。Polich–Page 無法唯一且連續歸宮時整盤拒絕；Koch 已知未定義狀態保留。

完整功能與限制見 [README](README.md)、[README.en](README.en.md) 及 [v0.7.0 版本說明](docs/releases/v0.7.0.md)。同版完整對應來源為 `OpenBirthChart-0.7.0-source.zip`，包含依賴來源、固定資料與驗證封存；與 Windows ZIP 在 https://github.com/iamxie/openbirthchart/releases/tag/v0.7.0 免費提供。

Build/validation: [BUILDING](docs/BUILDING.md), [VALIDATION](docs/VALIDATION.md), [DEPENDENCY_UPGRADES](docs/DEPENDENCY_UPGRADES.md). License: [LICENSE](LICENSE), [NOTICE](NOTICE.md), [third-party notices](THIRD_PARTY_DESKTOP.md).
