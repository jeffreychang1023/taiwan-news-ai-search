# Crawler 系統策略討論

> CTO-CEO First Principles Discussion
> 日期：2026-02-11

---

## 現狀摘要

| Source | 月產量 | Full Scan 進度 | 狀態 |
|--------|--------|---------------|------|
| UDN | ~28,000 | 掃到 2024-08 | 正常 |
| LTN | ~27,000 | 掃到 2021-04 (bug 已修, 從 4.55M 開始) | 已修 |
| CNA | ~9,300 | 掃到 2024-01-19 | 正常但慢 |
| Chinatimes | 未知(估數千) | 掃到 2024-02-18, 只有 247 篇(246 社會版) | 根本性問題 |
| einfo | ~20-30 | ID 233,125 | 低優先小站 |
| ESG BT | ~100-150 | 已完成 | 完成 |
| MOEA | 少量 | 只有 list_page | 無 full scan |

### 已完成的 Bug Fix（本次 Review）

1. LTN start_id 3M → 4.55M（跳過死 ID 區間）
2. LTN max_candidate_urls 3 → 0（LTN 自動 302 redirect，candidate 浪費請求）
3. Chinatimes category 覆蓋（從 1 個擴展到 8 realtimenews + newspapers + opinion）
4. CNA parser aiohttp 相容性修正
5. Per-source DATE_SCAN_MISS_LIMIT（chinatimes 設 500，全域 80 太激進）

---

## 討論議程

1. Chinatimes 策略
2. 整體回填策略與時間範圍
3. 各 Source ROI 分析
4. 系統下一步重心

---

## 討論紀錄

### 1. 產品定位與 Crawler 目的

**產品**：NLWeb 是一個 B2B 知識搜尋平台，服務企業研究人員、知識工作者（記者、公關、教授、研究人員等）— 任何需要寫報告、報導、論文、調查的人。

**Crawler 的角色**：資料供應端。抓取 → 結構化 → chunking → embedding → Qdrant。全文供 reasoning module 推論用，搜尋時不給全文。

**來源選擇策略**：
- 主要台灣新聞來源（UDN、LTN、CNA、Chinatimes 等）
- 小媒體是前期特定 user 的需求（einfo、ESG BT、MOEA）
- **未來目標**：複製 crawling 經驗與架構，替更多 business user 收錄他們工作所需的來源

**資料範圍**：
- 回填目標：**2024-01-01 至今**（CEO 訂定）
- 2024 年以前的資料是測試產物，應打包 archive，不需保留
- 覆蓋率要求：**盡可能接近 100%**

**兩種模式的現況**：
- **Full scan（回填）**：目前主要使用中，但尚未回填完畢
- **Auto（追蹤新文章）**：幾乎沒有真正用過，很多改動只針對 full scan
- **未來**：Crawler 應部署在專用機器上，定期自動跑更新

### 2. 優先順序與部署

**優先順序**：先回填完 → 再上線 auto 模式

**目前運行環境**：
- 跑在 CEO 的個人電腦上
- 常需暫停（做其他事、休眠）→ 這就是為什麼有 pause/resume、dashboard、checkpoint 設計
- CEO 本人頻繁監控，遇到很多問題都即時處理

**未來部署目標**（二選一）：
- 方案 A：一台便宜舊筆電，24/7 跑，產出檔案再搬回主機
- 方案 B：雲端便宜 instance，放著跑

**新 Source 擴展**：
- 時間表：數月到一季後
- 方法：hardcode 即可，一個 source 硬編碼一次能跑兩年資料量，不過分
- 目前 7 個 parser 本質上是同一套 pattern + 各自細節的 hardcode
- 重點是提取 lessons learned，讓下一個 source 更快上手

### 3. 回填策略

**目標**：2024-01-01 至今，接近 100% 覆蓋率
**計畫**：春節期間在 CEO 電腦上所有 source 同時跑

**同時跑的理由**：
- 各 source 完全獨立（不同網站、不同 rate limit、不同 subprocess）
- 遠端難以即時 debug，至少部分 source 能持續有進度
- 監控多條線不困難（有 dashboard）

**需要事前處理的風險**：
- [ ] 關閉電腦自動休眠
- [x] 確認磁碟空間充裕 — C 槽 155GB，足夠
- [ ] **所有 source 驗證**：春節前每個 source 都跑幾小時，確認正常
- [ ] 遠端監控：手機可遠端看電腦，但難操作 CLI → dashboard 要能顯示足夠資訊
- [ ] 雲端備案：研究 GCP e2-micro 部署，需測試部署流程 + 資料同步方案

### 4. 各 Source 回填分析

#### UDN — 系統性漏抓問題

**發現**：Auto 模式 ~28,000 篇/月 vs Full scan 最佳月份 ~4,400 篇/月 → **覆蓋率僅 ~15%**

**已爬取分佈**（2024 年以後）：
- 2024-01~02：偏低（1,614 / 2,158）
- 2024-03~08：穩定但偏低（~4,000-4,400）
- 2024-09~2025-10：幾乎空白（14 個月斷層）
- 2025-11~2026-02：~28,000/月（auto 模式，可信 baseline）

**結論**：即使 full scan 表面上「正常運行」的月份，也漏掉了 85% 的文章。

**待調查根因**：
1. 中斷 + resume 縫隙（多次中斷 + 不同版本 backfill）
2. 停止條件太激進（early stop 跳過大段 ID）
3. ID 空間分佈不均觸發 early stop
4. Auto 模式 vs Full scan 邏輯差異（list_page URL vs 逐 ID 掃描）

**結論**：春節前必須調查清楚，否則重跑仍會只有 15% 覆蓋率。

**Dashboard bug**：2024-10 月份資料消失，待修。

**根因分析**：
- **主因（高信心）**：`BLOCKED_CONSECUTIVE_LIMIT=5` 太激進。UDN 57% ID 是 404，連續 5 個 404 機率 ~6%（每 ~17 個 ID 觸發一次停止）。此 bug 已修為 50。
- 次因：多次中斷 + 不同程式碼版本的 resume 不一致
- 次因：SQLite write lock 導致部分記錄遺失

**外部驗證月產量**（indexing-spec.md, 2026-02-11 實測）：
| Source | 月產量 | IDs/月 | Hit Rate |
|--------|--------|--------|----------|
| UDN | ~28,000 | ~65,000 | ~43% |
| LTN | ~27,000 | ~33,000 | ~80% |
| CNA | ~5,700 | ~600 suffix/天 | ~32% |

**行動方案**：用修好的程式碼（BLOCKED_LIMIT=50）重新從 start_id 跑 full scan。Watermark + crawled_ids skip 會跳過已抓到的文章，只補漏洞。

**驗證計畫（春節前必須完成）**：

**Step 1 — 小範圍驗證（1-2 小時）**：
- 挑 2024-09（舊 backfill 只有 735 篇，預期 ~28,000）
- 推算對應 ID 區間，用新程式碼只跑該區間
- 比對結果：接近 28K → 確認修正有效；仍只有幾千 → 根因有誤，需進一步調查

**Step 2 — A/B 對照（若 Step 1 不明確）**：
- BLOCKED_LIMIT=5 vs BLOCKED_LIMIT=50 跑同一段 ID
- 用數據確認差異

**部署備援策略**：GCP + Local 同時跑同一個 source，互為備援。
- 幾 GB 資料，合併成本低
- Indexing pipeline URL 級去重，不怕重複
- 注意：兩邊 crawled_registry SQLite 各自獨立，以實際 TSV 產出為準

#### LTN

**已修 Bug**：
- start_id 3M → 4.55M（3M 是 2019 年，浪費 7-8 天掃不需要的 ID）
- max_candidate_urls 3 → 0（基於 LTN 302 auto-redirect 假設）

**BLOCKED_LIMIT=5 對 LTN 影響小**：80% hit rate，連續 5 個 404 機率僅 0.032%

**未驗證的假設**：
- ⚠️ LTN 302 auto-redirect 行為 — 來自 handoff 文件，未親自測試
- ⚠️ 子網域（health/ec/ent）的文章是否能透過 news.ltn.com.tw URL redirect 存取
- ⚠️ concurrent=12, delay=0.1-0.3s 是否太激進會被 rate limit

**春節前驗證清單**：
- [ ] 手動測試 302 redirect：用錯誤 category URL 打已知文章，確認 redirect 行為
- [ ] 跑 1 萬 ID 小範圍測試，確認 hit rate ~80% 且無異常停止
- [ ] 觀察 rate limiting 跡象

#### CNA

**進度**：僅掃到 2024-01-19（19 天）
**根因**：同 UDN — BLOCKED_LIMIT=5。CNA 68% miss rate，連續 5 個 404 機率 14.5%，平均每 35 個 suffix 停一次。

**修好後速度估算**：
- 每天 ~600 suffix，實際文章集中在前 200 suffix
- DATE_SCAN_MISS_LIMIT=80 會在 ~280 suffix 跳到隔天（節省時間）
- 730 天 → 估計 1-2 天跑完

**風險**：
- curl_cffi 依賴：雲端 IP 可能更容易被 Cloudflare 封
- CNA Cloudflare 不太激進，BLOCKED_LIMIT=50 + cooldown 120s 應可應對

**⚠️ 重大疑慮：max_suffix=600 可能不夠**：
- CNA parser 程式碼中 skip 了 suffix=5001 的「早安世界」文章
- 如果 suffix 可達 5001+，代表 600 以上可能有整個區間的文章未被掃到
- 外部驗證只 probe 1-600，估算的 5,700 篇/月也可能偏低
- **CNA ID 後 4 碼的編碼邏輯可能不是簡單連續編號**

**春節前必須調查（範圍比預想大）**：

基本假設待驗證：
- [ ] **ID 位數**：程式碼硬性假設 12 位（regex `\d{12}`），是否有 13+ 位的 ID？
- [ ] **Suffix 分佈**：4 位 suffix 空間（0001-9999）內，文章散佈在哪些區段？不只是 1-600
- [ ] **URL pattern**：是否有不走 `/news/{cat}/{id}.aspx` 的文章？

調查方法：
- [ ] 抓 CNA 多個列表頁的所有 href（不做 regex 過濾），看原始資料格式
- [ ] 挑幾天 probe 更大 suffix 範圍（1-9999），確認 hit 分佈
- [ ] 修好後跑幾小時驗證

**情境對應方案**：

| 情境 | Fix | 代價 | Verify |
|------|-----|------|--------|
| A: Suffix 4 位但超過 600 | 調高 max_suffix 或掃特定區段 | 若掃 1-9999 需 ~34 天（太慢），需知道具體分佈 | 新設定跑同一天，比對已知文章數 |
| B: ID 超過 12 位 | 修 regex(`\d{12,14}`)、get_date()、full scan multiplier | 中等工程量 | 修改後重跑 get_latest_id() + probe 新區間 |
| C: 非 `/news/` URL pattern | 額外 list_page 爬取補充 | 最麻煩，無法用 ID 掃描覆蓋 | 比對列表頁 href vs `/news/` pattern |
| D: 一切正常，max ~450-500 | 不用改（600 已有 buffer） | 無 | probe 確認即可 |

#### Chinatimes — 最棘手的 Source

**現狀**：掃到 2024-02-18，247 篇（246 社會版）。月產量未知。

**問題維度（5 個）**：

1. **Category code**：已部分修復（9 candidates），但 max_candidate_urls=4，仍有 4 個 candidate 沒試
2. **月產量完全未知**：WAF 擋住外部驗證，無基準線判斷覆蓋率
3. **Suffix 空間**：6 位 suffix 理論空間 000001-999999，只掃 3500（0.35%）
4. **Request amplification**：每 ID 5 requests × 3500 suffix × 730 天 = 1,280 萬 requests + WAF 風險
5. **真實 WAF blocking**：不同於 UDN/CNA 的 404 誤判，Chinatimes 是真的被 Cloudflare 封

**建議優先順序**：
1. 先搞清楚月產量（Google News / 第三方聚合 / 列表頁）
2. 搞清楚 ID + category 分佈
3. 評估 ROI — 工程成本 vs 資料價值

**CEO 決策**：中時是台灣四大報，不能放棄。從列表頁下手調查。

**列表頁調查計畫**：
- 用 list_page 模式爬 8 個 category 列表頁，盡可能往回翻頁
- 只收集 URL/ID（不 parse 內容），速度快且 WAF 風險低
- 從 URL 統計：suffix 分佈、category 分佈、日均產量、section 比例
- 拿到數據後再決定 full scan 策略

**待確認**：列表頁能翻多深？若只有最近幾天，歷史分佈仍未知

**調查後情境分析**：

| 情境 | 處理方式 | Verify |
|------|---------|--------|
| A: 列表頁翻很深（數月+） | 直接建立月產量基準線 + category/suffix 分佈 | 抽樣 100 篇用 full scan 邏輯確認能抓到 |
| B: 列表頁只翻幾天 | 用近期數據估算，假設歷史分佈相似 | 挑歷史日期 full scan 一天全範圍，比對推算值 |
| C: 列表頁也被 WAF 擋 | Google site search / Wayback Machine / 第三方聚合間接估算 | 多來源交叉比對 |

**Suffix 分佈情境**：
- 都在 3500 以內 → 維持 max_suffix，安心跑
- 超過 3500 → 調高，看是否連續 or 分段

**max_candidate_urls 決策**：
- 列表頁 category 分佈出來後，按頻率排序 candidate
- 前 N 個 candidate 覆蓋 80%+ → N 就夠用
- 分佈均勻 → 增加 candidate 但可降低 max_suffix 控制總請求量

**總請求量公式**：
```
總請求 = 天數 × max_suffix × (1 + max_candidate_urls × miss_rate)
```
若 suffix 可從 3500 降到 1000，candidate 增到 9 也可能更省

#### MOEA（經濟部）

**現狀**：只有 list_page 模式，月產量估算 ~240 篇（未驗證）

**未驗證假設**：
1. ⚠️ 「MOEA 只能 list_page」— news_id 可能是 sequential，但從沒調查過
2. ⚠️ 只爬 `populace`（民眾版）— 可能遺漏 admin 或其他 section
3. ⚠️ 能源署可能有獨立網站（2023 升格），不在 MOEA 列表中
4. ⚠️ list_page 翻頁深度未知 — 可能翻不到 2024-01
5. ⚠️ 240/月未經驗證
6. ⚠️ curl_cffi 必要性 — 政府網站通常不需要

**調查計畫**：
- [ ] 收集列表頁 ID，判斷是否 sequential（→ 能否 full scan）
- [ ] 實際翻到底，測 list_page 深度
- [ ] 檢查能源署是否有獨立新聞頁
- [ ] 檢查 MOEA 其他 section
- [ ] 統計實際月產量
- [ ] 測試是否需要 curl_cffi

**情境分析**：
| 情境 | Fix | Verify |
|------|-----|--------|
| news_id sequential | 加入 FULL_SCAN_CONFIG | 跑一段 ID 確認 hit rate |
| news_id 非 sequential | 靠 list_page，確認翻頁深度夠 | 翻到 2024-01 |
| list_page 翻不到 2024-01 且 ID 非 sequential | 歷史資料無法回填 | 嘗試 sitemap/RSS/Google cache |
| 能源署有獨立網站 | 新增 parser | 評估工程量 vs 資料價值 |

#### einfo（環境資訊中心）

**現狀**：Sequential ID (`/node/{id}`)，concurrent=1, delay=5-10s，hit rate ~6%，月產量估 ~20-30 篇

**未驗證假設**：
1. ⚠️ concurrent=1 — CEO 印象中確實會封鎖，但具體閾值未測（也許 concurrent=2 可以？）
2. ⚠️ Binary search `high=260000` 寫死 — 若最新 ID 超過 260K 會靜默 fallback
3. ⚠️ 6% hit rate — 是「94% 不是文章」還是「parser 漏抓文章」？
4. ⚠️ 月產量 20-30 — 未從外部驗證
5. ⚠️ `default_start_id=230000` 對應日期未確認
6. ⚠️ Drupal 站通常有 RSS — 可能完全不需要 ID 掃描

**調查計畫**：
- [ ] 試打 `/rss.xml`, `/feed`, `/sitemap.xml`
- [ ] 實測 concurrent=3, delay=2s 是否被封
- [ ] 查 node 230,000 的發布日期
- [ ] 查最新 node ID 是否已超過 260,000
- [ ] 統計真實月產量
- [ ] 分析 94% miss 的構成

**情境分析**：
| 情境 | Fix | Verify |
|------|-----|--------|
| 有 RSS | 用 RSS 取得所有 URL，不需 full scan | 比對 RSS vs ID 掃描文章數 |
| concurrent 可提高 | 調高 concurrent + 降低 delay | 跑一段確認不被封 |
| start_id 太早 | 調到 2024-01 對應 ID | 查該 ID 文章日期 |
| binary search high 過時 | 調高或改動態計算 | 確認 get_latest_id 回傳值合理 |
| 月產量遠高於 20-30 | 調查漏抓原因 | 比對 RSS/列表頁文章數 |

#### ESG BusinessToday（今周刊 ESG）

**現狀**：標記「已完成」，月產量估 ~100-150 篇，max_suffix=600

**核心疑慮：「已完成」可能是假象**：
- Hit rate ~2%（98% 是 404）
- BLOCKED_LIMIT=5 時，連續 5 個 404 機率 = 0.98^5 = **90.4%**
- 幾乎不可能在舊設定下完整跑完任何一天
- 100-150/月的估算可能嚴重低估

**未驗證假設**：
1. ⚠️ 「已完成」= 覆蓋率 OK？還是只是 full scan 跑完沒報錯？
2. ⚠️ 100-150/月未從外部獨立驗證
3. ⚠️ max_suffix=600 是否足夠（同 CNA 問題）
4. ⚠️ 14 位 ID 截斷邏輯（截掉後 2 碼）是否正確
5. ⚠️ 5 個分類是否涵蓋所有文章

**調查計畫**：
- [ ] AJAX 模式翻所有分類所有頁，統計 2024-01 至今文章數（建立基準線）
- [ ] 比對 AJAX 發現 vs crawled_registry（確認漏了多少）
- [ ] ~~抓 sitemap.xml 交叉驗證~~ ← sitemap 只到 2021，無法驗證 2024+ 資料
- [ ] **ID 空間共用假設**：拿幾個 ESG 404 的 ID 去今周刊本站 (`businesstoday.com.tw`) 試打
- [ ] 查 14 位 ID 來源與截斷正確性
- [ ] 挑幾天 probe suffix 驗證 max_suffix

**情境分析**：
| 情境 | Fix | Verify |
|------|-----|--------|
| BLOCKED_LIMIT 導致漏抓 | LIMIT=50 重跑 | 比對 AJAX 基準線 |
| 100-150/月是真的 | 不需改 | AJAX 統計確認 |
| max_suffix 不夠 | 調高 | probe 確認 |
| 14 位 ID 截斷有誤 | 修正邏輯 | 用 14 位 ID 打 URL 測試 |
| 有分類外文章 | 增加分類 | 比對首頁 vs 分類文章 |
| ID 空間與今周刊共用 | 2% hit rate 正常，考慮是否爬今周刊本站 | ESG 404 ID 去本站試打 |

**今周刊本站擴展規劃**：

預設先爬 ESG 部分。今周刊本站列為未來可選項。

**調查（在 ESG 驗證過程中順便做）**：
- [ ] 確認 ID 空間是否真的共用：ESG 404 的 ID 去 `businesstoday.com.tw/article/{id}` 試打
- [ ] 如果共用，統計本站 vs ESG 的文章比例（抽樣幾天的 suffix）
- [ ] 本站 URL 結構是否跟 ESG 一樣（`/post/{YYYYMMDDXXXX}`）
- [ ] 本站有無 WAF / anti-bot

**情境分析**：
| 情境 | Fix | Verify |
|------|-----|--------|
| ID 共用，本站結構相同 | 複製 ESG parser，改 base_url + 調整 parse selector | 跑一段 ID，確認 hit rate 從 2% 提升到合理值 |
| ID 共用，本站結構不同 | 寫新 parser，但 full scan 邏輯可複用 | 抽樣 parse 幾篇確認正確 |
| ID 不共用 | 不影響 ESG，本站需獨立調查 ID 格式 | N/A |
| 本站有 WAF | 評估是否值得投入（curl_cffi 或其他方案） | 試打確認 |

**決策時機**：ESG 驗證完成後，根據數據決定是否擴展到本站

### 5. 調查驗證結果（2026-02-11 執行）

> 以下為 6 個並行調查 agent 的實測結果，取代了上方的「假設」。

#### UDN — 策略翻轉：改用 Sitemap 回填

**實測結果**：
- 2024-09 ID 區間抽樣 50 個 → **94% 是 404**（hit rate 僅 **6%**，非預估的 43%）
- BLOCKED_LIMIT=5 下連續 5 個 404 機率 = **73%**（比先前估算的 6% 高得多）
- BLOCKED_LIMIT=50 修正有效（觸發機率降到 4.5%），但 full scan 每月最多 ~6,000 篇（21% 覆蓋）

**顛覆性發現**：UDN ID 空間極度稀疏。Full scan 盲掃 ID 效率極低。

**Sitemap 可行性確認**：
- `https://udn.com/sitemapxml/news/mapindex.xml` → **200 OK**
- 共 1,051 個子 sitemap（回溯到 2020-02）
- 2024-2026 有 **343 個子 sitemap**，每個 ~600KB、~2,885 個 URL
- 預估 2024+ 共 ~99 萬 URL
- 下載成本：343 個請求 × 600KB ≈ **200MB**，**~6 分鐘**即可全部抓完

**結論**：UDN 回填應**改用 sitemap**，而非 full scan。效率提升 5 倍以上。

**✅ 行動項**：
- [ ] 寫 sitemap backfill 腳本（下載 343 子 sitemap → 提取 URL → 去重已爬 → parser 解析）
- [ ] Full scan 降級為「補充」角色（抓 sitemap 遺漏的文章）

#### LTN — 驗證通過，不需改動

**實測結果**：
- **302 redirect 行為確認** ✅
- `/life/{id}` 可以 redirect 到**所有** category（包括 politics）
- 但 `/politics/{id}` 只能存取政治文章，其他 category 會 404（不對稱行為）
- 目前 primary URL 用 `/life/` → 所有文章只需 **1 個 request**

**結論**：max_candidate_urls=0 安全，**不需任何修改**。

**✅ 行動項**：無

#### CNA — max_suffix 嚴重不足

**實測結果**：
- **ID 固定 12 位** ✅ — regex `\d{12}` 正確，不需修改
- **Category 通用** ✅ — 任意 category URL 都能存取任意文章
- **Suffix 分佈**：
  - 主要密集區：0200-0400（~80% 文章）
  - 特殊專欄：3000+ 系列
  - 早安世界：5001-5004
  - 列表頁最高 suffix = **5004**
- **max_suffix=600 只覆蓋 ~95%**，3000+ 和 5000+ 區段完全漏掉
- **無 Cloudflare 阻擋** — 標準 User-Agent 即可存取

**✅ 行動項**：
- [ ] `max_suffix` 600 → **6000**
- [ ] 擴展 skip 邏輯至 5001-5010（早安世界系列）

#### Chinatimes — 月產量驚人，參數全面不足

**實測結果**：
- **列表頁可存取**（需 curl_cffi 繞 Cloudflare WAF）
- **翻頁深度**：最多 10 頁，僅覆蓋最近 **3 天**
- **月產量 ≈ 10,510 篇**（350 篇/天 × 30 天）— 是 full scan 實測 247 篇的 **42 倍**

**Category 分佈**（1,051 篇去重）：

| Rank | Code | % | 說明 |
|------|------|---|------|
| 1-4 | 260407/260402/260405/260410 | 各 ~19% | 政治/社會/生活/財經 |
| 5 | 260404 | 15.2% | 國際 |
| 6 | 260403 | 5.3% | 體育 |
| 7-8 | 260408/260412 | 2.9%/0.5% | 科技/其他 |

- **Top 4 categories = 76.1%**（不足 80%），**Top 6 = 96.6%**
- **Suffix 範圍 59 ~ 5,121**（3 天內），每天約 1,600 個 suffix

**✅ 行動項**：
- [ ] `max_suffix` 3500 → **6000**
- [ ] `max_candidate_urls` 4 → **6**（達 >95% coverage）
- [ ] `date_scan_miss_limit` 相應提高到 **700**
- [ ] 修正 `get_list_page_config()` URL 格式（用 category code 而非名稱）

#### ESG BusinessToday — 「已完成」確認為假象

**實測結果**：
- **ID 空間獨立** ❌ — 假設被證偽，ESG 和今周刊主站**不共用** ID 空間
- **Hit rate 確認 2.4%**（250 個 ID 命中 6 篇）
  - BLOCKED_LIMIT=5 下，P(5 consecutive 404) = 0.98^5 = **90.4%** — 幾乎無法推進
- **月產量 ≈ 30-40 篇**（非預估的 100-150）
- **Suffix 範圍 11-81**，極度分散
- **AJAX 分類頁全部失效**（301 到首頁），無法用列表頁驗證
- **DATE_SCAN_MISS_LIMIT=80 可能不足**（suffix 可達 81）

**✅ 行動項**：
- [ ] 新增 `date_scan_miss_limit: 150`（for ESG BT）
- [ ] 用 BLOCKED_LIMIT=50 從 2024-01-01 重新 full scan
- [ ] 預期：~25 月 × 35 篇 ≈ **875 篇**

#### MOEA — 可加入 Full Scan

**實測結果**：
- **news_id 完全 sequential** ✅ — 連續 ID 全部可存取
- 最新 ID：121891（2026-02-11）
- 直接用 `news_id` 參數存取，**不需要 ASP.NET ViewState**
- 無效 ID 回 200 但含 `Error/FileNotFound.aspx`（需特殊偵測）
- **能源署獨立網站確認**：`https://www.moeaea.gov.tw`（需進一步調查新聞系統）
- **月產量**：待精確驗證（可能 27-54 篇/月，非 240）

**✅ 行動項**：
- [ ] MOEA 加入 FULL_SCAN_CONFIG（sequential type）
- [ ] 實作無效 ID 偵測（檢查 FileNotFound.aspx）
- [ ] 調查能源署是否有獨立新聞系統

#### einfo — 透過 Wayback Machine 間接調查完成

**連線狀態**：
- 直連全部 timeout（三次嘗試，所有方式失敗）
- DNS 解析成功：IP `139.162.48.207`（Linode 機房）
- **網站仍在運作** — Wayback Machine 2026-02-09 成功快照（200 OK）
- **確認是 Geo-blocking / IP 封鎖**（非網站離線）

**間接調查結果（Wayback Machine + 本地已爬資料）**：
- **無 RSS/Sitemap** — Wayback 快照中無 RSS 連結，常見 URL 全部 302
- **最新 Node ID ≈ 243,007**（2026-02-09 快照）
  - binary search high=260,000 → 安全餘裕 ~17,000，仍可用，建議提高到 270,000
- **月產量**：~318 新 node / 12 天 × 6% 文章比例 ≈ **~48 篇/月**（比原估 20-30 高）
- **default_start_id=230,000**：本地最早檔案 2025-04，ID 對應合理
- **技術棧**：Drupal + jQuery 1.7（舊版）

**✅ 行動項**：
- [ ] 需要台灣 IP 才能爬取（VPN / 雲端部署在台灣機房）
- [ ] binary search high 260,000 → 270,000（增加緩衝）
- [ ] 確認 full scan 在台灣 IP 下能正常連線
- [ ] 無 RSS，必須依賴 sequential ID scanning

---

### 6. 全局總結（調查後更新版）

#### 驗證後的真實覆蓋率

| Source | 月產量 | 調查前狀態 | 調查後結論 | 回填策略 |
|--------|--------|-----------|-----------|---------|
| **UDN** | ~28,000 | 15% 覆蓋 | ID 空間 94% 空洞 | **Sitemap 回填**（非 full scan） |
| **LTN** | ~27,000 | 假設未驗證 | 302 redirect 確認 ✅ | Full scan 維持現狀 |
| **CNA** | ~5,700+ | 只掃 19 天 | suffix 最高 5004 | Full scan + **max_suffix=6000** |
| **Chinatimes** | **~10,510** | 247 篇（0.02%） | 參數全面不足 | Full scan + **大幅調參** |
| **ESG BT** | ~35 | 「已完成」假象 | ID 獨立，2.4% hit rate | Full scan + **miss_limit=150** |
| **MOEA** | ~30-50 | 只有 list_page | news_id sequential | **新增 full scan** |
| **einfo** | ~48 | Geo-blocked | 無 RSS，需台灣 IP | binary search high→270K |

#### 跨 Source 共通發現（驗證後更新）

**1. BLOCKED_LIMIT=5 確認是系統性主因** ✅ verified

| Source | 實測 Miss Rate | P(5 consecutive 404) | 實際影響 |
|--------|---------------|---------------------|---------|
| UDN | **94%** (非 57%) | **73%** | 覆蓋率僅 6%→21% |
| ESG BT | **97.6%** | **90.4%** | 幾乎無法推進 |
| CNA | ~68% | 14.5% | 第 19 天停止 |

**2. max_suffix 假設全面崩潰**

| Source | 原假設 | 實測 | 修正值 |
|--------|--------|------|--------|
| CNA | ≤600 | **5004** | 6000 |
| Chinatimes | ≤3500 | **5121** (3天內) | 6000 |
| ESG BT | ≤600 | 11-81 (OK) | 維持 |

**3. 假設驗證結果一覽**

| 假設 | 結果 | 影響 |
|------|------|------|
| UDN full scan 正常 | ❌ 94% miss rate | 改用 sitemap |
| LTN 302 redirect | ✅ 確認（`/life/` 通吃） | 不改 |
| CNA max_suffix=600 | ❌ 實際到 5004 | 改為 6000 |
| Chinatimes max_suffix=3500 | ❌ 實際到 5121+ | 改為 6000 |
| ESG BT ID 空間共用 | ❌ 完全獨立 | 無法靠主站補充 |
| ESG BT 已完成 | ❌ 假象 | 重跑 |
| MOEA 只能 list_page | ❌ news_id sequential | 加 full scan |
| einfo 穩定可連線 | ❌ connection timeout | 待重試 |

#### 修正行動清單（依優先序）

**P0 — 立即修改參數**
- [x] CNA `max_suffix` 600 → 6000 ✅ (2026-02-11 executed)
- [x] Chinatimes `max_suffix` 3500 → 6000 ✅
- [x] Chinatimes `max_candidate_urls` 4 → 6 ✅
- [x] Chinatimes `date_scan_miss_limit` 500 → 700 ✅
- [x] ESG BT `date_scan_miss_limit` → 150 ✅

**P1 — 新增功能**
- [ ] UDN sitemap backfill 腳本（待實作，full scan 已暫停）
- [x] MOEA full scan 支援 ✅ — `get_url()` fallback direct URL + FULL_SCAN_CONFIG + OVERRIDES

**P2 — 驗證與補充**
- [x] einfo binary search high 260,000 → 270,000 ✅
- [ ] einfo 需台灣 IP 才能爬取（Geo-blocked）— 爬蟲暫停
- [x] CNA skip 邏輯擴展到 5001-5010 ✅
- [ ] MOEA 能源署獨立網站調查
- [ ] Chinatimes `get_list_page_config()` URL 格式修正

#### 春節執行計畫（調查後更新版）

**Pre-CNY Checklist**：
- [x] ~~Tier 1 驗證全部完成~~ ✅ UDN / LTN / CNA 已驗證
- [x] ~~Tier 2 調查取得初步數據~~ ✅ Chinatimes / ESG BT 已調查
- [ ] **P0 參數修改全部完成**
- [ ] **UDN sitemap backfill 腳本完成**
- [ ] 關閉電腦自動休眠
- [ ] 所有 source 各跑幾小時 dry run
- [ ] GCP e2-micro 部署測試（備案）

**CNY 執行**：
- **UDN**：sitemap backfill（~6 分鐘下載，數小時解析）
- **LTN**：full scan 維持現狀（hit rate 80%，效率最高）
- **CNA**：full scan with max_suffix=6000（估計 1-2 天完成）
- **Chinatimes**：full scan with 新參數（最大挑戰，需密切監控 WAF）
- **ESG BT**：full scan with miss_limit=150（預期 ~875 篇總量）
- **MOEA**：full scan 如果已實作
- 手機遠端監控 dashboard

**Post-CNY**：
- 各 source 覆蓋率檢查
- einfo 重新調查
- MOEA 能源署擴展評估
- Auto mode 部署規劃

---

*會議結束：2026-02-11*
*調查驗證完成：2026-02-11*

---

### 7. 執行報告（2026-02-11 實施）

#### 已完成的程式碼修改

| 檔案 | 修改內容 |
|------|---------|
| `engine.py` FULL_SCAN_CONFIG | CNA max_suffix 600→6000, Chinatimes max_suffix 3500→6000 + miss_limit 500→700, ESG BT miss_limit=150, **MOEA 新增** (sequential, start_id=110K) |
| `settings.py` FULL_SCAN_OVERRIDES | Chinatimes max_candidate_urls 4→6, **MOEA 新增** (concurrent=5, delay 0.5-1.5s) |
| `moea_parser.py` get_url() | 新增 direct URL fallback: `News.aspx?news_id={id}` (原本只有 cache lookup, full scan 時回 None) |
| `cna_parser.py` get_latest_id() | skip 邏輯從 `endswith('5001')` 擴展為 `5001 <= suffix <= 5010` |
| `einfo_parser.py` _binary_search | high 260000 → 270000 |
| `dashboard_api.py` FULL_SCAN_CONFIG | 新增 MOEA (sequential, start=110K, end=122K), einfo end_id 260K→270K |

#### 爬蟲啟動狀態

| Source | 狀態 | 說明 |
|--------|------|------|
| **LTN** | 🟢 Running | full scan 維持，302 redirect 已驗證 |
| **CNA** | 🟢 Running | max_suffix=6000，覆蓋 3000+ 和 5000+ 區段 |
| **Chinatimes** | 🟢 Running | max_suffix=6000, candidate=6, miss_limit=700 |
| **ESG BT** | 🟢 Running | miss_limit=150，重新掃描 |
| **MOEA** | 🟢 Running | 首次 full scan，sequential 110K→122K |
| **UDN** | ⏸️ Stopped | 94% 空洞 ID，改用 sitemap 回填（待實作） |
| **einfo** | ⏸️ Stopped | Geo-blocked，需台灣 IP |

#### 待辦項目

- [ ] UDN sitemap backfill 腳本（高優先）
- [ ] einfo 台灣 IP 部署方案
- [ ] MOEA 能源署獨立網站調查
- [ ] Chinatimes `get_list_page_config()` URL 格式修正
- [ ] 各 source 跑幾小時後檢查進度與覆蓋率

