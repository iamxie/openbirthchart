<!-- language:zh-TW -->
# Polich–Page 宮頭倒置：為什麼停止排盤，並請你更換宮位制？

更新日期：2026-10-31；封裝註記更新於 2026-11-01。本文說明 Open BirthChart 的排盤政策；中英文錯誤說明已隨 0.6.6 封裝，原版 0.6.5 EXE／ZIP 不含此修正。本文仍為獨立文章，尚未接入桌面說明或匯出附錄。

2026-11-01 補充：本篇五個宮頭交錯拒絕維持不變。新程式也會檢查宮頭之間的連續映射及每個天體的唯一性；參見[精確宮頭殘差、連續幾何與個別天體多解](polich-page-unique-placement.md)。不能由十二宮頭順序正常推論所有歸宮都唯一。

選擇 Polich–Page（又稱 Topocentric）時，某些高緯度地點與時間會算出順序交錯的宮頭。這時雖然有十二個角度數值，卻無法依原來的宮號，把黃道分成十二個連續、不重疊的區域。

**Open BirthChart 會停止這次排盤，說明原因，並請你自行改選其他宮位制。這是預期的保護行為。** 程式不會為了顯示一張星盤而重排宮頭、任意改動出生地，或暗中改用另一套分宮規則。

## 「倒置」有兩種情況，不能混為一談

**整圈反向排列**，是十二宮仍按 1、2、3……12 連續相接，只是繞行方向相反。只要沒有退化、交錯或重疊，仍可以形成有效的一圈。Open BirthChart 已支援符合此條件的 Campanus、Regiomontanus 及 Azimuth；看到宮號順時針排列，不代表必須拒絕。

**宮頭順序交錯**，則是部分宮頭越過相鄰宮頭。沿同一方向走，遇到的可能是第 2 宮頭、第 1 宮頭、第 3 宮頭。把整圈反過來，也無法恢復依宮號連續排列。本文需要更換宮制的「宮頭倒置」，指的是這種情況。

極區的地平線、子午線與黃道之間有特殊關係；某些時間，通常稱作 MC 的上中天黃道點甚至仍在地平線下。不同宮制對這些情況有不同定義與處理方式，不能把所有高緯度星盤都視為無效。[Dieter Koch：極區與南半球的占星問題](https://www.astro.com/astrology/in_polar_asc_e.htm)

## 為什麼 Polich–Page 會遇到宮頭交錯？

Polich–Page 的中間宮頭使用不同的「極高」及時角計算。以地理緯度 φ 表示，兩組中間極高分別是 `arctan(tan(φ)/3)` 與 `arctan(2×tan(φ)/3)`，再投影到黃道取得宮頭。它不是先取得四個軸點之間的黃道區間，再保證每個區間內都放入兩個按順序排列的宮頭。[Swiss Ephemeris 一般文件，§6.2.10](https://www.astro.com/swisseph/swisseph.htm)

在某些高緯度與時角組合下，按這些公式分別算出的宮頭會越過彼此。公式仍可能回傳有限角度，但「有十二個數字」與「這十二個邊界可以構成有效分區」是兩件事。

這不是只要多保留幾位小數就能解決的誤差，也不是超過某個固定緯度後所有 Polich–Page 星盤一律失敗。本程式檢查的是該次出生條件實際算出的宮頭排列。

## 一個具體例子

出生條件為挪威 Tromsø，2000-06-07 05:06:58，時區 Europe/Oslo，北緯 69.64890°、東經 18.95508°，選擇 Polich–Page。這個固定案例的前三個宮頭為：

| 宮頭 | 黃經 |
|---|---:|
| 第 1 宮 | 122.641720° |
| 第 2 宮 | 120.371254° |
| 第 3 宮 | 126.724557° |

第 2 宮頭已越過第 1 宮頭，偏差約 **2.270466°**。若硬把第 1 宮到第 2 宮解釋為沿黃經增加方向的區間，第一宮會占約 **357.73°**，幾乎繞完整個黃道，與其他宮重疊；改用反向，其他宮頭又不符合。

固定測試還有以下四個相同城市的例子，時間均為當地時間：1941-07-12 23:25:03、1983-11-19 15:05:31、2004-01-13 08:47:57、2012-08-14 22:57:00。五例的十二段正向弧長合計都是 1080°，反向合計都是 3240°，兩者均不是有效分區要求的 360°。這些數字描述按原始宮號連接的弧長總和，並不是天體繞行了三圈或九圈。[固定案例診斷](../results/numerical/complete-diagnostics-20261031/REPORT.md)

## 為什麼另一套軟體仍然能算？

不同軟體可能採取不同政策：直接提供公式結果、發出警告、要求使用者改選宮制，或改用替代算法。顯示了宮頭與宮號，不足以證明圖面與歸宮定義已經一致。

我們固定使用的 Swiss Ephemeris 2.10.03 對這五例仍回傳 Polich–Page 宮頭，沒有轉用 Porphyry，也沒有把交錯宮頭排序成正常十二宮。相同參數下，LibEphemeris 與 Swiss 的宮頭幾乎完全一致；差別在於 Open BirthChart 另外檢查它們能否形成有效分區。[本機宮頭探測](../results/numerical/complete-diagnostics-20261031/swiss-probes.json)、[Swiss 2.10.03 宮頭實作](https://github.com/aloistr/swisseph/blob/v2.10.03/swehouse.c#L1430)

2020 年，Swiss 作者 Alois Treindl 也曾公開提出 Polich–Page 在高緯度產生不合理宮頭順序的案例；同串討論有人以手算得到相近結果。這是已有公開討論的問題，並非只在本程式出現。[Astrodienst 原始討論，回覆 #67、#73](https://www.astro.com/forarch/pdf/1599069109.pdf)

## 遇到拒絕訊息時，應該怎麼做？

1. **核對出生條件。** 檢查日期、時間、時區、經緯度是否正確。不要為了通過檢查而改動真實出生資料。
2. **改選其他宮位制後重新排盤。** 可選擇程式提示的 Equal（等宮制）或 Whole Sign（整宮制），或其他適合你用途且能在該條件下建立有效分區的宮制。程式不替你自動選擇。
3. **保留實際使用的宮制名稱。** 更換宮制會改變宮頭與歸宮結果；新結果應以新宮制解讀，不能仍稱作 Polich–Page。
4. **不要把失敗當成一張可解讀的星盤。** 排盤失敗時，本次結果不可匯出。若畫面仍留著上一筆成功星盤，那是舊結果，不是本次 Polich–Page 計算成功。

錯誤訊息會說明：

> 此時間／地點的 Polich–Page 宮頭順序交錯或重疊，無法形成連續、不重疊的十二宮，因此停止排盤。請改選其他宮位制（例如 Equal 或 Whole Sign）後重新排盤。

本程式將上述五例的正確預期結果設為**拒絕並解釋原因**，不以「讓它成功出數據」作為修復目標。這項政策只處理無效宮頭排列，不代表所有 Polich–Page 星盤都不能使用，也不代表其他尚待分析的落宮差異已經解決。[拒絕政策測試](../tests/fixtures/polich-rejection-policy.json)

---

<!-- language:en-US -->
# Polich–Page cusp order: why calculation stops and you should choose another house system

Updated: 2026-10-31; package note updated on 2026-11-01. This article describes Open BirthChart's policy. The explanatory Chinese and English errors ship with 0.6.6; the original 0.6.5 EXE/ZIP does not include this change. This remains a standalone article, not yet included in desktop help or exported appendices.

2026-11-01 addition: the five interleaved-cusp refusals remain unchanged. The application now also checks the continuous mapping between cusps and each body's unique placement; see [exact-cusp residuals, continuous geometry and individual ambiguity](polich-page-unique-placement.md). Ordered numbered cusps alone do not establish uniqueness for every point.

For some high-latitude locations and times, Polich–Page (also called Topocentric) produces cusps out of house-number order. Twelve numerical longitudes can exist without defining twelve consecutive, non-overlapping sectors of the zodiac.

**Open BirthChart stops that calculation, explains the reason, and asks you to choose another house system. This rejection is intentional.** It does not reorder the cusps, alter the birthplace, or silently substitute a different method merely to produce a chart.

## A reversed ring and crossed cusp order are different

In a **reversed ring**, houses still follow 1, 2, 3 through 12 consecutively, but in the opposite direction. If the ring is non-degenerate and its sectors do not overlap, it remains usable. Open BirthChart supports such valid reversed rings for Campanus, Regiomontanus and Azimuth. Clockwise numbering alone is not a reason to reject a chart.

With **crossed cusp order**, some cusps pass their neighbours. Moving in one direction may take you past cusp 2, then cusp 1, then cusp 3. Reversing the whole ring does not restore consecutive house numbers. This article's instruction to change systems concerns this second situation.

Polar regions have unusual relationships between the horizon, meridian and ecliptic. At some times, the upper-culminating ecliptic point normally called the MC is still below the horizon. House systems handle these conditions differently; not every high-latitude chart is invalid. [Dieter Koch: Astrology in polar regions and on the southern hemisphere](https://www.astro.com/astrology/in_polar_asc_e.htm)

## Why can Polich–Page cusps cross?

Polich–Page calculates intermediate cusps using different pole heights and hour angles. For geographical latitude φ, the two intermediate pole heights are `arctan(tan(φ)/3)` and `arctan(2×tan(φ)/3)`; projection onto the ecliptic then supplies the cusps. The construction does not first take each ecliptic quadrant between the axes and guarantee that two ordered intermediate cusps lie inside it. [Swiss Ephemeris general documentation, §6.2.10](https://www.astro.com/swisseph/swisseph.htm)

At certain combinations of latitude and sidereal angle, these separately calculated cusps pass one another. The formula can still return finite numbers, but numerical output does not guarantee a valid partition.

Extra decimal places cannot resolve this order reversal. Nor does every Polich–Page chart fail above one universal latitude threshold. The application checks the actual cusp geometry calculated for the supplied conditions.

## A concrete example

Consider Tromsø, Norway, on 2000-06-07 at 05:06:58 local time, Europe/Oslo, latitude 69.64890° N and longitude 18.95508° E, using Polich–Page. The first three cusps in this fixed case are:

| Cusp | Ecliptic longitude |
|---|---:|
| House 1 | 122.641720° |
| House 2 | 120.371254° |
| House 3 | 126.724557° |

Cusp 2 has passed cusp 1 by about **2.270466°**. Treating house 1 as the interval of increasing longitude from cusp 1 to cusp 2 gives it approximately **357.73°**, almost the entire zodiac, overlapping other houses. Choosing the opposite direction makes other cusp pairs inconsistent.

Four further fixed examples use the same city, at these local times: 1941-07-12 23:25:03, 1983-11-19 15:05:31, 2004-01-13 08:47:57 and 2012-08-14 22:57:00. All five have forward arc sums of 1080° and reverse sums of 3240°, rather than the 360° required for a single partition. These are sums of arcs connecting consecutive numbered cusps, not bodies completing three or nine revolutions. [Fixed-case diagnosis](../results/numerical/complete-diagnostics-20261031/REPORT.md)

## Why can another application still return a result?

Applications may return the formula's output, warn, require another system, or substitute an alternative method. Displaying cusps and house numbers does not establish that the wheel and placement definitions agree.

Our fixed reference, Swiss Ephemeris 2.10.03, returns Polich–Page cusps for these five cases without switching to Porphyry or sorting the crossed cusps. With identical parameters, its cusp longitudes and LibEphemeris's are virtually identical. Open BirthChart additionally checks whether the cusps define a valid partition. [Local cusp probes](../results/numerical/complete-diagnostics-20261031/swiss-probes.json), [Swiss 2.10.03 cusp implementation](https://github.com/aloistr/swisseph/blob/v2.10.03/swehouse.c#L1430)

In 2020, Swiss author Alois Treindl publicly raised a high-latitude example with illogical Polich–Page cusp order; a participant obtained similar results by hand. This issue has been discussed publicly and is not unique to this application. [Original Astrodienst discussion, replies #67 and #73](https://www.astro.com/forarch/pdf/1599069109.pdf)

## What should you do when calculation is refused?

1. **Check the birth details.** Verify date, time, time zone and coordinates. Do not alter genuine birth data to bypass the check.
2. **Choose another house system and calculate again.** Options include the suggested Equal or Whole Sign systems, or another system appropriate to your purpose that produces a valid partition for these conditions. The application does not choose for you.
3. **Keep the actual house-system label.** Switching systems changes cusps and placements. Interpret and identify the new chart using the new system, not as Polich–Page.
4. **Do not treat the failed calculation as an available chart.** Export is disabled for the failed calculation. If an earlier successful chart remains visible, it is the previous result, not a successful Polich–Page result for the new request.

The error explains:

> For this time and location, the Polich–Page cusps are out of order or coincide and cannot form twelve consecutive, non-overlapping houses. Chart calculation has stopped. Choose another house system (such as Equal or Whole Sign) and calculate again.

The expected result for these five cases is **rejection with an explanation**, not forced numerical output. This policy concerns invalid cusp geometry; it neither rejects all Polich–Page charts nor resolves other house-placement discrepancies still under investigation. [Rejection-policy tests](../tests/fixtures/polich-rejection-policy.json)
