# 依賴升級流程 / Dependency upgrade procedure

適用 OpenBirthChart v0.6.7 起。LibEphemeris 固定版本與雜湊，不在啟動時自動升級。Git `pull/push` 同步本專案的來源與鎖定檔；套件安裝由 uv 處理，兩者分開。

## 現況

`requirements/core.in` 與 `desktop.in` 均指定 LibEphemeris 3.2.2；`desktop.in` 透過 `-c core.lock` 使用核心約束。`vendor/libephemeris` 是由 `prepare_sources.ps1` 固定 tag／完整 commit 的檢查副本，不是桌面的安裝來源。對它 `git pull` 不會更新桌面套件。

## 每次升級的固定步驟

1. 檢查上游 release notes、修復內容、安全公告、API、授權及資料格式。安全修復優先評估，但不直接追蹤上游 main 或自動合併。
2. 在本專案開獨立升級分支及測試環境，保留現有 lock、資料、正式封存與可用成品。
3. 同步修改 `core.in`／`desktop.in` 的目標精確版本。先用 uv 重新產生 `core.lock`，再產生 `desktop.lock`，皆保留 `--generate-hashes`。只升級目標與必要相依項，審查完整 lock diff。若舊 Kerykeion 約束不相容，要明確處理驗證環境相容性，不能忽略依賴解算錯誤或強制 override。
4. 在新環境以 `uv pip sync --require-hashes` 安裝。更新 `prepare_sources.ps1` 的 tag／完整 commit、第三方來源清單與授權證據；驗證套件版本與檢查來源一致。資料、字型、Swiss 版本先固定，不同因素分開變更。
5. 跑桌面／歸宮測試及主 1200×2、完全 2016×2、邊界 87×2。核心依賴升級即使只升 OpenBirthChart patch，也驗全套；預設每模式 12 程序，各模式依序。保留原始 API、逐筆輸出、版本、環境及原始耗時。
6. 審查所有新差異：修正、退步、不同定義、錯誤類型與來源環境變更分別列出。特別檢查 H 編號與 T 唯一性補丁是否仍需要，避免上游修復後重複補正。不得只放寬容差、覆寫基準或刪除不一致案例來求通過。
7. 確認差異並明確接受後，才另建新版基準；舊基準與原始值繼續保存。舊的嚴格 release gate 會拒絕依賴差異，這是預期行為，不能跳過它冒稱結果相同。
8. 以實際成品驗證啟動、儲存、雙語與匯出；更新版本、變更說明、第三方來源與 SHA-256。合併升級分支後才打 release tag，發佈與該 commit 相符的來源及 binary。

日常純應用小修可依既定政策先跑主基準；此文件要求「核心依賴升級全套」，不是取消原有日常流程。

## 相依方式選擇

優先使用正式 Python 套件＋lock。未發版修正才暫用固定完整 commit 的 Git 依賴，並產生可重建的來源／wheel 及雜湊，不使用浮動 branch。只有需要共同建置上游來源時才考慮 submodule。若必須長期改上游，建立獨立 fork，紀錄變更並在該 fork 管理 origin/upstream；不要把 LibEphemeris 的歷史 merge 進 OpenBirthChart。

若確認升級造成退步，可回到上一個已審查 commit 的 lock 並重建環境，或讓使用者回到上一版完整 ZIP。不要只混換一個 DLL 或直接改 site-packages 而不留下版本紀錄。

## English

Use a pinned released Python package plus hashed locks. Git synchronizes this application's code/locks; uv synchronizes installed dependencies. The vendor checkout is a pinned inspection copy, not the desktop import source.

For an upgrade: review changes/security/licenses; create a branch and isolated environment; update exact requirements and compile core then desktop locks with hashes; review transitive changes; sync a new environment; update source provenance; run all 6606 cases plus application tests with 12 workers per mode; classify every difference; reassess application H/T corrections; accept changes explicitly before creating a new baseline; retain old raw results; test the actual package; publish matching source and binaries from one tag.

Keep Swiss and datasets fixed during the engine comparison. A changed dependency must not pass a gate intended to permit only an application version change. Investigate and document changes rather than weakening thresholds. Security updates are prioritized but not silently auto-merged. Existing release binaries retain their bundled engine until the user installs a newly validated application version.

References: [uv locking/syncing](https://docs.astral.sh/uv/pip/compile/), [Git submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules), [LibEphemeris licensing](https://github.com/g-battaglia/libephemeris/blob/v3.2.2/LICENSING.md).
