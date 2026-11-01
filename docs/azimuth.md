<!-- language:zh-TW -->
# Azimuth 宮制與目前的歸宮提示

適用：Open BirthChart 0.6.6，已整合 2026-10-31 起的應用層補丁與黃緯模式。原版 0.6.5 安裝包不含這些修正。

## Azimuth 是什麼？

Azimuth 又稱 Horizon（地平／方位角）宮制，將地平圈分成十二個相隔 30° 的方向，再以通過頭頂 zenith 與腳下 nadir 的垂直大圓和黃道相交，建立宮頭。黃道上各宮不一定等寬；第一宮頭不一定是 ASC。頭頂的 zenith 與占星的 MC 是不同概念。[Astrolog 官方文件](https://www.astrolog.org/ftp/astrolog.htm)

## 為什麼需要校正編號？

本地 LibEphemeris 3.2.2 的宮頭與空間歸宮，使用的編號起點與方向未在所有情況下對齊。例如部分星盤的 MC 位於第十宮頭，原始歸宮座標卻接近 4。另有星盤的 MC 原本正確，但其他宮頭與天體仍需要換算。這不是星體移動了 180°，也不能只按南北半球加減六宮。

目前程式先用十二宮頭驗證空間方向，再將每一個天體的原始歸宮座標換算成同一套宮頭編號，最後才取整數宮號。補丁只在 Open BirthChart 應用層執行；LibEphemeris 未修改。行星實際黃經、黃緯、ASC、MC 與十二宮頭均保留，原始回傳與校正原因也保存於計算紀錄。

## 圖面與宮號怎麼讀？

- 位於黃道上且可確認是第 n 宮頭的點，歸入第 n 宮。這也讓位於第十宮頭的 MC 歸入第十宮。只處理可確認的宮頭浮點殘差，不把所有 .99999 一律進位。
- 新增「歸宮納入天體黃緯」，預設開啟。開啟時使用實際黃緯歸宮，內圈按連續宮位座標在對應宮頭扇區內呈現位置；外緣空心點保留真實黃經。這是宮位位置示意圖，不是天球的等角投影，請從位置表讀取真實星座與度數。相位線連接對應天體，實際相位角度仍由真實黃經計算，以表格為準。
- 關閉時僅將歸宮輸入黃緯設為零，圖面使用黃經輪盤；原始黃經、黃緯、十二宮頭、ASC／MC 座標和宮號均不因開關改變。兩種模式都保留 Azimuth 編號校正；開關不會修復或掩蓋其他宮制的多解問題。舊版沒有此開關的輪盤仍可能出現非零黃緯天體的圖面扇區與空間宮號不同。
- 可形成完整一圈的反向宮頭仍保留原編號與圖面方向，不把宮頭重排成正向。
- 若空間方向退化（例如點在 zenith／nadir），或無法驗證十二宮頭與原始座標的對應，停止排盤並解釋原因。請改選其他適用宮制後重新計算；不自動替換宮制。

## 為什麼與 Swiss 或其他軟體仍可能不同？

封存的 Swiss Ephemeris 2.10.03 在極接近宮頭時可直接回傳宮頭編號，一般點則走另一條方位角路徑。本地對照重現了 MC 為 10、鄰近點卻接近 4 的情形。本補丁統一整張盤的編號後，部分一般天體會與這份 Swiss 參考出現新的宮號差異。這些差異完整保留，不能因座標角差很小而忽略。[Swiss 2.10.03 原始碼](https://github.com/aloistr/swisseph/blob/v2.10.03/swehouse.c)

這是本程式依宮頭一致性採取的處理政策，不宣稱是上游官方修復或占星界公認標準。比較軟體時請記錄版本、相同時間、時區、地點及宮位制，並分開比較宮號和座標。

## 舊資料的提示

原版 0.6.5 曾只把少數 MC 的 `3.999… → 4` 尾數補正，仍保留 4／10 矛盾。舊資料若顯示「存在已知編號差異」，代表該次計算尚未套用本補丁。新計算需要換算編號時會顯示「已依宮頭編號校正」。舊基準與已匯出文件不會被改寫；須以更新後程式重新排盤才會得到新結果。固定案例測試不代表已驗證所有可能輸入。

<!-- language:en-US -->
# Azimuth houses and the current placement notice

Applies to Open BirthChart 0.6.6, which includes the application changes introduced from 2026-10-31 and the house-latitude modes. The original 0.6.5 package does not include these changes.

## What are Azimuth houses?

Azimuth, also called Horizon houses, divides the horizon into twelve directions 30° apart. Vertical great circles through the zenith and nadir intersect the ecliptic to define the cusps. The houses need not have equal zodiac widths, and cusp 1 need not be the ASC. The zenith directly overhead is distinct from the astrological MC. [Astrolog documentation](https://www.astrolog.org/ftp/astrolog.htm)

## Why align the numbering?

In the locally installed LibEphemeris 3.2.2, cusp numbering and spatial placement do not always use the same starting point and direction. For example, an MC on cusp 10 may have a raw house coordinate near 4. Other charts already have a correct MC but still need alignment for other cusps and bodies. No object has moved 180°, and a hemisphere-based shift of six houses is insufficient.

The application validates spatial directions against all twelve cusps, transforms every body's raw house coordinate into that numbering, and only then takes the integer house. LibEphemeris is unchanged. Actual ecliptic longitude and latitude, ASC, MC and all cusps are preserved. Calculation records retain raw returns and correction reasons.

## Reading the wheel and house numbers

- A point on the ecliptic identified as cusp n belongs to house n. An MC on cusp 10 therefore belongs to house 10. Only identified cusp roundoff is corrected; arbitrary .99999 values are not rounded upward.
- The new “Use ecliptic latitude for houses” option is on by default. With it enabled, inner markers map the continuous house coordinate into the corresponding cusp sector; open outer markers retain true longitude. This is a house-position diagram, not an angle-preserving sky projection. Read actual zodiac positions in the position table. Aspect lines connect the corresponding bodies; aspect values still come from true longitudes and must be read in the tables.
- With the option off, only the latitude supplied for house placement is set to zero, and the wheel displays longitude. Actual longitude, latitude, cusps, ASC/MC coordinates and axis house numbers do not change with this option. Azimuth numbering alignment remains active in both modes. This option neither fixes nor hides multiple solutions in other house systems. Older wheels without this option can still show differences between a nonzero-latitude body's longitude sector and spatial house.
- A valid reversed cusp ring retains its original numbering and drawing direction. Cusps are not reordered into a forward ring.
- If spatial direction is undefined, as at the zenith or nadir, or the cusp-to-coordinate mapping cannot be validated, calculation stops with an explanation. Select another suitable house system and recalculate. The application does not switch systems automatically.

## Why can Swiss and other software still differ?

The archived Swiss Ephemeris 2.10.03 reference can return a numbered cusp directly for a point extremely close to it, while ordinary points follow a different azimuth path. Local comparisons reproduced an MC at 10 with neighboring values near 4. Aligning the entire chart introduces new house-number differences for some ordinary bodies against this Swiss reference. All differences are retained; small angular differences do not excuse different house numbers. [Swiss 2.10.03 source](https://github.com/aloistr/swisseph/blob/v2.10.03/swehouse.c)

This is the application's policy for consistency with its numbered cusps, not an official upstream fix or a claim of consensus. Compare house numbers and angular coordinates separately, using documented versions and identical time, time zone, location and house system.

## Notices in older data

Original 0.6.5 only corrected a few MC residuals from `3.999… → 4`, leaving the 4/10 discrepancy. An older chart showing the known-numbering-discrepancy notice has not received this patch. New calculations that require alignment show an aligned-with-cusps notice. Original baselines and exported files remain untouched; recalculate with the updated application to obtain new results. Fixed tests do not establish correctness for every possible input.
