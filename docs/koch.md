<!-- language:zh-TW -->
# Koch 宮位制：為什麼有時無法排盤，或無法判定落宮？

更新日期：2026-10-30。程式行為與測試數據以 Open BirthChart 0.6.5 為準。

選擇 Koch 宮位制後，軟體可能無法建立十二宮，也可能畫得出星盤，卻將某顆天體的宮位標成「未定義」。這兩種結果發生在不同的計算步驟，需要分開理解。

## Koch 是怎樣劃分宮位的？

Koch 是一種以時間與當地地平線為基礎的分宮方法，又稱「出生地宮位制」（Geburtsorthäusersystem）。它不把黃道直接分成十二個相等的 30° 區間。

可以從第十一、十二宮的構造理解它：取出生時 MC 所在的黃道點，考慮該點從升起到上中天所經過的時間，將這段時間三等分，再取相應時刻升起的黃道位置來建立宮頭。這是簡化說明，並非完整計算公式。[Swiss Ephemeris 一般文件，§6.2.2](https://www.astro.com/swisseph/swisseph.htm)

**宮頭**是各宮的邊界；**歸宮**則是判定一個天體屬於哪一宮。算出了邊界，不代表後續每一顆天體都一定能取得有效宮號。

## 第一種情況：無法建立標準 Koch 十二宮

Koch 的標準宮頭構造在極區有適用限制，約為南、北緯 66.5° 以外；這不是全球任意地點都能使用的分宮方法。有些軟體遇到此情況會改用另一種宮制，例如 Astrolog 的文件明載會轉用 Porphyry。**能畫出圓盤，不代表最後使用的仍是 Koch**，應查看實際宮制與警告。[Astrolog 官方文件，Koch houses](https://www.astrolog.org/ftp/astrolog.htm)

Open BirthChart 0.6.5 遇到上游的極圈錯誤或宮頭計算警示時，會停止該次排盤，提示改選 Equal 或 Whole Sign；不把替代宮制的宮頭當成 Koch 結果交付。[目前計算流程](../desktop/model.py)

## 第二種情況：宮頭算得出來，個別天體卻無法歸宮

這種情況也會出現在極圈以外。Swiss 官方文件說明，Koch 歸宮函式可能回傳 `0`，表示計算無法完成；高赤緯、落在繞極區域的天體是其中一類情況。赤緯是相對天球赤道的位置，與相對黃道的「黃緯」不同。[Swiss Ephemeris 程式介面文件，House position of a planet](https://www.astro.com/swisseph/swephprg.htm)

也不能反過來把每個 `0` 都解釋為「這顆天體永不升落」。Swiss 2.10.03 的 Koch 實作還會檢查計算比例的有效範圍；超出範圍時，同樣可能回傳 `0`。判讀某一筆失敗的具體原因，需要檢查該筆輸入與運算條件。[Swiss 2.10.03 原始碼，Koch 分支](https://github.com/aloistr/swisseph/blob/v2.10.03/swehouse.c)

這裡的 `0` **不是第零宮，也不是可以四捨五入成第一宮的尾數**。它表示此計算沒有提供可使用的 Koch 落宮結果。

## 我們實際遇到的例子

Open BirthChart 的 1,200 張固定主案例中，**86 張採用 Koch**。在 LibEphemeris 3.2.2 與 Swiss Ephemeris 2.10.03 的對照中，有 **23 張、32 個天體點**同時無法取得有效宮號；兩邊原始回傳均為 `0`。這是固定測試樣本的結果，不是所有出生資料的失敗機率。[完整對照報告](../results/numerical/release-0.6.5/swiss-comparison/REPORT.md)

例如以下案例：

| 項目 | 條件或結果 |
|---|---|
| 案例編號 | `main-1935-12` |
| 地點 | 智利・蓬塔阿雷納斯（Punta Arenas） |
| 當地日期時間 | 1935-12-29 03:47:17 |
| 時區 | `America/Punta_Arenas`，依封存時區資料換算 |
| 座標 | 南緯 53.16282°、西經 70.90922° |
| 宮制 | Koch |
| 十二宮頭 | 可以建立 |
| 月亮的歸宮 | LibEphemeris 與 Swiss 都回傳 `0` |

這個城市不在極圈內。月亮的天體位置仍有計算結果，也可以畫在圓盤上；缺少的是有效的 Koch 宮號。因此，**看得到月亮，不等於已經完成月亮的 Koch 歸宮**。[逐筆對照資料](../results/numerical/release-0.6.5/swiss-comparison/exceptions.csv)

## 遇到這種情況，可以怎麼做？

1. **先核對輸入。** 確認出生時間、時區、經緯度及宮制；不要為了讓軟體通過而任意改動真實資料。
2. **保留「未定義」的意義。** 天體的星座度數仍可閱讀，但不要把空白宮號補成某一宮，也不要把圓盤上的投影位置當成已成功算出的空間歸宮結果。
3. **需要完整落宮時，可自行改選宮制。** 本程式提示的選項是 Equal 或 Whole Sign。改選後屬於另一套分宮規則，應明確記錄，不能繼續稱為 Koch 星盤。
4. **比較軟體時，同時核對設定與警告。** 若另一套軟體能顯示宮號，還需確認是否改用了替代宮制或不同歸宮方法；單憑「有數字」不能判定哪一方正確。

在 Open BirthChart 0.6.5，已知的 Koch `0` 會保留原始回傳，顯示為「未定義／Undefined」。程式不把天體黃緯改成零來取得答案，也不把它當成浮點尾數補正。[歸宮處理](../desktop/house_positions.py)

以上說明涵蓋已知的 Koch 限制；其他排盤失敗仍可能來自輸入、資料或程式問題，需要分別查明。它也不同於 Azimuth 中「已有兩個互相衝突的宮號」的問題，不能以同一種原因概括。

---

<!-- language:en-US -->
# Koch houses: why can a chart or a house placement be unavailable?

Updated: 2026-10-30. Application behavior and test results refer to Open BirthChart 0.6.5.

After selecting Koch, software may be unable to construct the twelve houses. Alternatively, it may draw the chart but mark an individual body's house as “Undefined.” These outcomes arise at different calculation stages.

## How does Koch divide the houses?

Koch, also called the birthplace house system (Geburtsorthäusersystem), uses time and the local horizon rather than twelve equal 30° zodiac intervals.

For an introductory example, consider the ecliptic point at the birth MC. Divide its rising-to-culmination interval into thirds and use the ecliptic positions rising at the corresponding times to construct cusps 11 and 12. This is a simplified account, not a complete algorithm. [Swiss Ephemeris general documentation, §6.2.2](https://www.astro.com/swisseph/swisseph.htm)

**Cusps** define house boundaries. **Placement** assigns a body to a house. Obtaining the boundaries does not guarantee a valid placement for every body.

## Situation one: standard Koch cusps cannot be constructed

Standard Koch construction has polar limitations, roughly beyond 66.5° north or south. Some applications substitute another system: Astrolog documents a switch to Porphyry. **A displayed wheel therefore does not guarantee that Koch was used.** Check the actual system and warnings. [Astrolog documentation, Koch houses](https://www.astrolog.org/ftp/astrolog.htm)

When the upstream calculation reports a polar-circle error or a cusp warning, Open BirthChart 0.6.5 stops that calculation and suggests Equal or Whole Sign. It does not present fallback cusps as Koch results. [Current calculation flow](../desktop/model.py)

## Situation two: cusps exist, but a body cannot be assigned a house

This can occur outside the polar circles. Swiss documents a Koch return value of `0` when placement cannot be computed; high-declination bodies in circumpolar regions are one example. Declination is measured from the celestial equator, whereas ecliptic latitude is measured from the ecliptic. [Swiss programming interface, House position of a planet](https://www.astro.com/swisseph/swephprg.htm)

However, not every `0` means that the body never rises or sets. Swiss 2.10.03 also checks whether the calculated Koch fraction lies within its valid range and can return `0` when it does not. Diagnosing a particular failure requires its inputs and calculation conditions. [Swiss 2.10.03 source, Koch branch](https://github.com/aloistr/swisseph/blob/v2.10.03/swehouse.c)

This `0` means **no usable Koch placement was returned**. It is neither “house zero” nor a small residual to round up to house one.

## An example from our fixed cases

Of Open BirthChart's 1,200 fixed main charts, **86 use Koch**. Comparing LibEphemeris 3.2.2 with Swiss Ephemeris 2.10.03, **23 charts contain 32 body placements** for which both engines return `0`. These are results for this test sample, not an estimated failure rate for all births. [Full comparison report](../results/numerical/release-0.6.5/swiss-comparison/REPORT.md)

| Item | Input or result |
|---|---|
| Case ID | `main-1935-12` |
| Location | Punta Arenas, Chile |
| Local date and time | 1935-12-29 03:47:17 |
| Time zone | `America/Punta_Arenas`, using the archived time-zone data |
| Coordinates | 53.16282° S, 70.90922° W |
| House system | Koch |
| Twelve cusps | Available |
| Moon's house placement | Both LibEphemeris and Swiss return `0` |

The city is outside the polar circles. The Moon's celestial position remains available and can be drawn on the wheel; its Koch house number is unavailable. **Seeing the Moon on a chart is not proof that its Koch placement was calculated successfully.** [Individual comparison records](../results/numerical/release-0.6.5/swiss-comparison/exceptions.csv)

## What can you do?

1. **Check the inputs.** Confirm the birth time, time zone, coordinates and house system. Do not alter genuine birth information merely to make a calculation succeed.
2. **Respect an undefined result.** You can still read the body's zodiac position, but do not fill in a missing house number or treat its plotted projection as a successfully calculated spatial placement.
3. **Choose another system if you need complete placements.** The application's suggested alternatives are Equal and Whole Sign. Record the change: a chart calculated under another system is no longer a Koch chart.
4. **Compare settings and warnings as well as numbers.** If another application supplies a placement, check for a fallback system or a different placement method. The presence of a number alone does not establish correctness.

Open BirthChart 0.6.5 retains the original Koch `0` and displays “Undefined.” It neither replaces the body's ecliptic latitude with zero to obtain an answer nor treats this result as numerical roundoff. [Placement handling](../desktop/house_positions.py)

These are known Koch limitations. Other calculation failures can involve inputs, data or software and need separate investigation. They also differ from the conflicting house numbers found in Azimuth; the two problems should not be given the same explanation.
