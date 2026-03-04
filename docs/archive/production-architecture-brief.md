# Production 部署諮詢

## 專案一句話

台灣新聞 AI 搜尋引擎：使用者輸入自然語言 → 從 200 萬篇新聞中語意搜尋 → LLM 生成摘要回答。預計規模成長到千萬篇。

## 目前 Tech Stack

| 元件                   | 技術                       | 用途                                   | 目前部署                                           | 問題                                      |
| -------------------- | ------------------------ | ------------------------------------ | ---------------------------------------------- | --------------------------------------- |
| **Web Server**       | Python aiohttp, Docker   | 處理 query、SSE streaming               | Render Free (512MB RAM, 無GPU, 無磁碟, 15min 閒置休眠) | RAM 和功能限制明顯                             |
| **向量 DB**            | Qdrant                   | 語意搜尋（存 embedding vectors + metadata） | Qdrant Cloud Free (1GB)                        | 目前 5K vectors 測試中；production 需 ~40-60GB |
| **全文 DB**            | SQLite + Zstd 壓縮         | AI 推論時讀取文章全文                         | ❌ 未部署（本地檔案）                                    | Render 無持久化磁碟，SQLite 無法使用               |
| **Analytics DB**     | PostgreSQL               | 查詢日誌、效能監控                            | Neon.tech Free (512MB)                         |                                         |
| **Crawler Registry** | SQLite (717MB)           | 記錄已爬取的 190 萬篇文章                      | 桌機 + GCP VM                                    | 只在 indexing 用，不需上 production server     |
| **Embedding 模型**     | 二選一（見下方）                 | 把文字轉向量，indexing 和 query 都需要          | OpenAI API                                     | 有本地替代方案                                 |
| **LLM**              | OpenAI API (gpt-4o-mini) | 生成 AI 摘要、query 分析、排序                 | OpenAI API                                     |                                         |
| **前端**               | 純 HTML/JS（無框架）           | 搜尋介面                                 | 跟 server 一起 serve                              | 靜態檔，不影響架構決策                             |
| **Crawler/Indexing** | Python scripts           | 爬新聞 + 切 chunk + 生成向量 + 上傳            | 桌機/GCP VM 手動跑                                  | 離線作業，與 production serving 分離            |

## Embedding 模型選擇（影響架構）

Indexing 和 query **必須用同一個模型**，所以這個選擇直接決定 server 需不需要 GPU：

|           | OpenAI API (1536D) | bge-m3 本地推論 (1024D) |
| --------- | ------------------ | ------------------- |
| 需要 GPU    | 不需要                | 需要（模型 2GB）          |
| 費用        | ~$0.02/M tokens    | 免費                  |
| 中文品質      | 中等                 | 優（多語言專用模型）          |
| 本地 E2E 測試 | —                  | ✅ 已驗證通過             |

## 需要建議的問題

**1. Server 放哪裡？**
Render Free 限制太多（無 GPU、無磁碟、512MB RAM）。是繼續用 PaaS，還是搬到 VPS/Cloud VM 自己管？

**2. 向量 DB 怎麼擴展？**
目前 Qdrant Cloud Free 只有 1GB，production 需要 40-60GB。自架 Qdrant的話，要放到哪個CSP的哪個服務/環境好呢？

**3. 全文 DB 怎麼部署？**
200 萬篇文章全文（壓縮後約 5-20GB），目前是本地 SQLite。要改 PostgreSQL、object storage、還是放本地磁碟？

**4. 整體架構建議？**
以上元件的最佳組合方式？有沒有我們沒考慮到的更好選項？

## 規模參考

- 目前：190 萬篇文章，每篇 ~3 chunks = ~570 萬 vectors
- 中期：1,000 萬篇 = ~3,000 萬 vectors
- 每次 query：1 次 embedding + 1 次向量搜尋 + 2-5 次 LLM call
