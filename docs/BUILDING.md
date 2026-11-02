# 建置與對應來源 / Building and corresponding source

版本：v0.7.0；Windows x64。自有程式碼 AGPL-3.0-only，第三方保留原條款。

## 來源的兩種形式

- Git repository：精簡應用、測試、腳本、文件、鎖定檔、theme 原始素材與小型 Astronomicon 字型及原 OFL 授權。大型歷史封存不進 Git 歷史。
- `OpenBirthChart-0.7.0-source.zip`：相同應用來源，加固定執行資料、完整 regression 封存、審查過的比較來源及 `third_party/sources/` 上游來源封存。另有清單與 SHA-256。不是只提供 GitHub 自動產生的 source ZIP。

Git checkout 的進階驗證需從同版完整來源 ZIP 取出 `regression/` 與 `validation/`。原始封存包含歷史路徑、版本與來源快照，這些是當時證據，不代表目前安裝位置。文章中的歷史證據連結，請在完整來源包內閱讀。

## 從乾淨環境啟動

先安裝 Git 與 uv（https://docs.astral.sh/uv/getting-started/installation/），PowerShell 進入來源根目錄：

```powershell
./setup-desktop.ps1
./launch-desktop.ps1
```

腳本建立 Python 3.12 環境，依 `requirements/desktop.lock` 的版本與 SHA-256 安裝套件，再依三份資料 lock 準備全部核心、時間與桌面資料。已存在資料必須通過雜湊核對；不會無條件覆蓋不同資料。Git 版首次需要網路；完整來源包的資料可直接核對。套件 wheel 安裝仍需取得鎖定版本，不把本機 `.venv` 當成來源。

v0.7.0 參考環境：CPython 3.12.14、LibEphemeris 3.2.2、PySide6-Essentials／shiboken6 6.12.0。完整版本見鎖定檔及 `third-party-sources.lock.json`。需要和歷史數值封存做環境精確核對時，使用該 Python patch 版；換 Python patch 會如實呈現環境差異。

## 測試與 Windows 封裝

```powershell
./.venv-desktop/Scripts/python.exe scripts/run_desktop_tests.py
./.venv-desktop/Scripts/python.exe -m unittest discover -s tests -p 'test_house_number2.py'
./build-desktop.ps1 -ReviewedReference validation/reviewed
./.venv-desktop/Scripts/python.exe scripts/verify_desktop_package.py
```

桌面測試逐模組啟動獨立程序，避免 Qt 視窗生命週期與樣式累積；每個模組都必須通過。以上完整測試需先取得完整來源包的封存。`build-desktop.ps1` 先測試並以預設 12 程序重算六份固定條件，僅允許明示的版本標籤差異，再執行 PyInstaller 和實際 EXE smoke。沒有 `-ReviewedReference` 時仍驗原正式主基準，會如實回報已記錄的 T／閏秒差異，不能靠覆寫基準消除。

產物位於 `dist/OpenBirthChart-0.7.0/`。`verify_desktop_package.py` 核對逐檔雜湊並產生 Windows ZIP／SHA-256。`scripts/prepare_public_release.py` 整理公開來源與完整來源包；上游來源必須先按鎖定清單取得。

## 替換 Qt／修改程式

封裝採目錄形式、動態載入 Qt／PySide6，沒有簽章鎖定或禁止除錯條款。若替換函式庫，須保留相容的 Python／PySide／Qt ABI、DLL 與 plugins；建議修改來源後在自己的環境重新建置整包。完整來源含對應 Qt/PySide/Python 封存及上游建置文件。允許依適用授權進行修改、重新連結及為此除錯，不施加額外限制。

重新從上游來源編譯 Qt／PySide6／Python 需要各自文件指定的編譯器與工具鏈；上述應用建置流程使用鎖定的發行 wheel，不宣稱從原始碼重建每個第三方 binary 可得到逐位元相同結果。

## English

The Git tree contains application/build/test code, pinned manifests, theme assets and the small, unchanged Astronomicon font with its original OFL license. Bundling that font avoids depending on an upstream website that can reject automated downloads. The full source ZIP additionally contains runtime data, immutable regression archives, the reviewed release reference under `validation/reviewed`, and exact upstream archives under `third_party/sources`. Their hashes are in `third-party-sources.lock.json`; these archives retain upstream license texts and build instructions.

On Windows x64 with Git and uv, run `setup-desktop.ps1` then `launch-desktop.ps1`. All runtime data is provisioned and verified, without requiring the old development workspace or Swiss test data. Dependency installation initially needs network access. Existing mismatched data is rejected.

Use the commands above to test/build. For exact historical environment comparison, use Python 3.12.14; changing it is a real environment change. The release gate compares 6606 fixed cases with the explicitly reviewed reference, excluding timings and allowing only the application version field to change. Original baselines remain unchanged.

Qt is dynamically loaded in a directory bundle. Users may replace/rebuild libraries under their licenses, including debugging modifications. ABI compatibility is required; rebuilding the application is recommended. Application builds use pinned upstream wheels; bit-for-bit reproduction of all third-party binaries from source is not claimed.
