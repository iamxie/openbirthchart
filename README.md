# Open BirthChart

[English](README.en.md) · 繁體中文

Windows 西洋占星本命盤桌面程式，使用 LibEphemeris 計算，提供繁體中文／英文介面、十四種宮位制、天體與宮頭表格、相位及離線報告。

**v0.6.7：首次公開發佈候選。** 本地準備完成不代表下方下載已上線。

## 下載與啟動

1. 在 [Releases](https://github.com/iamxie/openbirthchart/releases) 下載 `OpenBirthChart-0.6.7-windows-x64.zip`。
2. 解壓縮整個資料夾，執行 `OpenBirthChart.exe`，不要只移出 EXE。
3. 不需另裝 Python 或星曆；計算資料已隨附。目前提供 Windows x64 封裝，其他系統尚未提供成品。

下載頁同時提供 SHA-256 與 `OpenBirthChart-0.6.7-source.zip`。程式尚未使用程式碼簽章。

## 功能

- 十四種宮位制；可選擇歸宮是否納入天體實際黃緯。
- 本地儲存個人檔案、時區與夏令時間檢查、可調整相位容許度。
- 星盤 PNG／SVG 與自包含 HTML 報告；HTML 可由瀏覽器列印為 PDF。
- 英文星盤與位置表格採一致的星座圖示，保留名稱與度分秒。
- 精確宮頭微小殘差僅在身分與幾何條件成立時補正；無效宮號拒絕排盤及匯出。

## 資料與隱私

個人檔案與設定儲存在 `%USERPROFILE%\Documents\openbirthchart\data.sqlite`，不是安裝資料夾。SQLite 資料庫未加密，可能含姓名、出生資料、備註及設定，備份與分享前請留意。

排盤可離線執行，沒有自動上傳星盤或遙測。主動使用座標查詢時，地址與所填 API key 會送往 geocode.maps.co；API key 會保存在本地資料庫。地圖連結會透過瀏覽器連線。手動輸入經緯度不需 API key。

## 計算範圍與已知限制

- 閏秒輸入不支援排盤，會明確拒絕，保留原輸入時間。
- Polich–Page 幾何多解、折返或無法唯一歸宮時拒絕整盤；Koch 已知個別未定義狀態明示為「未定義」。
- 部分高緯度／退化條件無法排盤。有效的 Campanus／Regiomontanus 反向排列與無效交錯分別處理。
- Azimuth 空間宮號依本程式宮頭定義對齊，部分結果仍與 Swiss 不同，不宣稱所有軟體結果相同。
- 日期、時區及星曆資料有各自有效範圍；不支援的輸入會拒絕，不自動換時間或宮位制。

[宮位制說明文章](docs/README.md) · [驗證方法與已知差異](docs/VALIDATION.md)

## 開發與驗證

在 Windows x64 準備 PowerShell、Git 與 uv，下載來源後執行：

```powershell
./setup-desktop.ps1
./launch-desktop.ps1
```

首次準備需要網路取得鎖定依賴與資料，之後排盤可離線。完整來源包已包含固定執行資料；Git checkout 會由相同固定來源下載並核對 SHA-256。

[建置說明](docs/BUILDING.md) · [依賴升級流程](docs/DEPENDENCY_UPGRADES.md) · [v0.6.7 版本說明](docs/releases/v0.6.7.md)

主 1200、完全 2016、邊界 87 筆案例，各驗實際／零黃緯，預設每模式 12 程序。大型封存與歷史原值放在完整來源包，Git 工作樹保持精簡。Swiss 僅在獨立參考環境交叉驗證，桌面執行不依賴 pyswisseph。

## 授權

Copyright (C) 2026 OpenBirthChart contributors.

自有程式碼採 [AGPL-3.0-only](LICENSE)，不提供保證。第三方元件、字型與資料保留原授權，見 [NOTICE](NOTICE.md)、[第三方說明](THIRD_PARTY_DESKTOP.md) 與隨附 `licenses/`。程式頂端「關於與授權」提供離線法律告知及完整條文。
