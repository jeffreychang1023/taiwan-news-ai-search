---
name: 部署與資安教訓
description: VPS、Docker、SSH、資安加固相關的除錯經驗。部署或資安相關除錯時必讀。
type: feedback
---

> 通用除錯哲學（Silent fail 防範、API 重試等）見 `lessons-general.md`。遭遇未知成因 Bug 時，優先閱讀 general。

## Zoe 工作模式

### Hetzner cloud-init drop-in config 覆蓋 sshd_config — SSH password login 靜默失敗
**問題**：Hetzner Cloud 建立 Ubuntu 伺服器時若選了 SSH key，cloud-init 會在 `/etc/ssh/sshd_config.d/` 放 drop-in config 設定 `PermitRootLogin prohibit-password`。直接 `sed` 修改主 `/etc/ssh/sshd_config` 無效，因 `sshd_config.d/*.conf` 優先級更高。結果：password auth 被 server advertise 為可用（SSH handshake 列出 `publickey,password`），但所有密碼都被拒絕。非常難 debug，因為 `grep PasswordAuthentication /etc/ssh/sshd_config` 顯示 yes，表面上一切正常。
**解決方案**：建立高優先級 drop-in 覆蓋：`echo 'PermitRootLogin yes' > /etc/ssh/sshd_config.d/99-root.conf && systemctl restart ssh`。**通則：Ubuntu 24.04+ 的 SSH 設定分散在 `sshd_config` + `sshd_config.d/*.conf`，修改 SSH 行為必須檢查所有 config 來源。cloud-init 的 drop-in 是最常見的「看不到的覆蓋」。**
**附註**：Ubuntu 的 SSH service 名稱是 `ssh` 不是 `sshd`（`systemctl restart ssh`，不是 `systemctl restart sshd`）。
**信心**：高（實際踩坑，3 次密碼嘗試 + 2 次 config 修改才定位）
**檔案**：N/A（VPS 系統層）
**日期**：2026-03-05

### Docker volume 掛載重設 ownership — container 重建後 /data 權限 denied
**問題**：NLWeb container 用 `user: nlweb` 運行，`/data` 目錄由 Docker named volume 掛載。每次 `docker-compose down && up` 重建 container，volume mount 點的 ownership 重設為 `root:root`。analytics 模組嘗試建立 `/data/analytics` 目錄時 `PermissionError`。搜尋 API 回傳 `{"error": true}` 但無明確錯誤訊息（被 except 吞掉），需查 container logs 才能定位。
**解決方案**：docker-compose.yml 改為 `user: root`（開發/demo 環境可接受）。Production 應用 entrypoint script 做 `chown`。**通則：Docker named volume 的初始 ownership 取決於 image 內的目錄結構，重建 container 不保留 runtime 的 chown 結果。需要持久權限的目錄應在 Dockerfile 中 `mkdir + chown`。**
**信心**：高（兩次踩坑：第一次 /data，第二次 /data/analytics）
**檔案**：VPS docker-compose.yml [問 CEO 取得路徑]
**日期**：2026-03-05

### Docker image 內嵌靜態檔案 — 修改不生效需 volume mount 覆蓋
**問題**：`Dockerfile` 用 `COPY . /app` 將所有檔案（含 `static/`）bake 進 image。在 VPS host 上修改 `static/news-search.js`（修復 crypto.randomUUID polyfill）後，container 內仍用 build 時的舊版。CEO 看到的依然是壞掉的前端。
**解決方案**：docker-compose.yml 加入 `volumes: - ./static:/app/static`，讓 host 的 static 目錄覆蓋 image 內嵌版本。修改後即時生效（加上瀏覽器 hard refresh）。**通則：需要頻繁修改的檔案（前端 JS/CSS、config）不應只靠 COPY 嵌入，應用 volume mount 做 overlay。開發/部署流程要區分「build 時固定」vs「runtime 可變」。**
**信心**：高
**檔案**：VPS docker-compose.yml [問 CEO 取得路徑]
**日期**：2026-03-05

### ~~SSH stdout 被靜默吞掉~~ **已推翻 (2026-03-09) — 惡意軟體症狀，非正常 VPS 行為**
**原結論**：VPS 的 `/etc/ld.so.preload` 載入 `libprocesshider.so` 是「Hetzner cloud image 預裝」，需要 `ssh -tt` 才能正常操作。
**推翻**：`libprocesshider.so` 是惡意軟體植入的（隱藏挖礦進程），不是 Hetzner 預裝。VPS 在開通後很快被暴力破解入侵（因開放了密碼登入）。`.bashrc` 第一行 `exit 0`（非互動 session 直接退出）、`crontab` 函數覆寫（隱藏惡意 cron）、`/var/tmp/apt.log` + `~/.bash_logout` 惡意程式每分鐘執行 — 全部是入侵痕跡。
**正確認知**：乾淨的 Hetzner VPS 不會有這些問題。ssh、scp、sftp 在乾淨 OS 上正常運作，不需要 `-tt`。
**信心**：高（crontab 惡意條目、libprocesshider.so、.bashrc 篡改全部確認）
**日期**：2026-03-09（推翻 2026-03-07 記錄）

### VPS Docker 容器無法連外 — iptables NAT masquerade 規則遺失
**問題**：VPS 上的 Docker 容器（nlweb-app）無法連線到外部 API（OpenRouter embedding）。錯誤訊息：`[Errno 101] Network is unreachable`。VPS host 本身可以連外（Python urllib 測試拿到 403），但容器內完全不行。搜尋時 OpenRouter embedding 30 秒 timeout → `ValueError: All endpoint searches failed` → 使用者看到空結果。
**根因**：`iptables -t nat -L POSTROUTING` 顯示 chain 完全為空 — 沒有 MASQUERADE 規則。Docker 正常運作時會自動建立這些規則，但此 VPS 上不知何故遺失（可能是 Hetzner cloud-init、手動 iptables flush、或 Docker daemon 重啟後未恢復）。沒有 MASQUERADE，容器的 172.18.x.x 私有 IP 封包無法做 NAT 轉換出去。
**解決方案**：手動加 MASQUERADE 規則（具體子網段和 bridge 介面名稱 [問 CEO]）。**待做**：持久化規則（`iptables-save` 或 `iptables-persistent` 套件），否則 VPS 重啟後規則又會丟失。
**診斷路徑**：VPS logs `Embedding request timed out` → 容器內 urllib `Network is unreachable` → host urllib OK (403) → `iptables -t nat -L POSTROUTING` 空 → 加 MASQUERADE → 修復。
**通則**：Docker 容器無法連外時，先檢查 `iptables -t nat -L POSTROUTING` 是否有 MASQUERADE 規則。這是 Docker networking 最基本的依賴，丟失會導致所有容器 outbound 靜默失敗。
**信心**：高（修復後立即驗證搜尋正常）
**檔案**：N/A（VPS 系統層）
**日期**：2026-03-09

### ~~VPS scp/sftp 完全不可用~~ **已推翻 (2026-03-09) — 惡意軟體症狀**
**原結論**：scp/sftp 因 ld.so.preload 無法使用，需用 base64 分塊繞路。
**推翻**：所有 SSH/scp/sftp 異常都是惡意軟體造成的（同上條）。乾淨 VPS 不需要任何 workaround。
**日期**：2026-03-09

### 治症狀不治病因 — scp 壞了就該修 scp，不是花半天繞路
**問題**：VPS 的 scp/sftp 因 `/etc/ld.so.preload` 載入不存在的 `libprocesshider.so` 而失敗。正確做法是花 30 秒查看並清掉 `ld.so.preload` 那行，scp 立刻恢復。實際做法是把「scp 壞了」當成不可改變的環境限制，花大量時間嘗試 pipe、base64 編碼、split 分塊、heredoc 等 workaround。
**教訓**：遇到工具失敗時，第一反應應該是「為什麼壞了？能不能修？」而不是「壞了，換別的方法」。尤其是自己控制的環境（VPS root 權限），幾乎所有基礎工具故障都是可修的。**通則：先問 WHY，不是 HOW to work around。修根因通常比繞路快得多。**
**信心**：高（本次直接踩坑，浪費大量時間）
**日期**：2026-03-09

### crypto.randomUUID() 需要 HTTPS secure context — HTTP 部署前端完全崩潰
**問題**：VPS 部署後透過 HTTP（非 HTTPS）存取前端，`crypto.randomUUID()` 拋出 `TypeError: crypto.randomUUID is not a function`。此 API 只在 secure context（HTTPS 或 localhost）可用。錯誤發生在 `news-search.js:78` 的 session ID 初始化，阻斷所有後續 JS 執行 — 整個搜尋功能完全不能用，按鈕全部無反應。CEO 回報：「前端完全不能點」。
**解決方案**：加入 polyfill：`(typeof crypto.randomUUID === 'function') ? crypto.randomUUID() : ([1e7]+-1e3+...)`，用 `crypto.getRandomValues()` fallback（在所有 context 可用）。永久解決方案：部署 HTTPS（Let's Encrypt + certbot）。**通則：Web Crypto API 中部分方法有 secure context 限制（randomUUID、subtle），部署到非 HTTPS 環境前必須檢查。**
**信心**：高（Chrome DevTools 實測驗證）
**檔案**：`static/news-search.js`
**日期**：2026-03-05

## 資安 (Security)

### VPS 開通後幾小時就會被暴力破解 — 資安加固必須在第一次開機時完成
**問題**：Hetzner VPS 開通後開放了密碼登入（因 SSH key 不 match）。結果在數小時內被暴力破解、植入加密貨幣挖礦惡意軟體（TeamTNT 風格）。攻擊者修改了 `.bashrc`（`exit 0` 阻止非互動 session）、覆寫 `crontab` function（隱藏惡意 cron）、植入 `libprocesshider.so`（隱藏挖礦進程）、在 `/var/tmp/apt.log` + `~/.bash_logout` 放挖礦程式每分鐘執行。我們花了數天 debug scp/ssh 異常，最終才發現是入侵，不是環境問題。
**教訓**：
1. **公網 VPS 被掃描的速度比你想像的快** — SSH port 22 + 密碼登入 = 幾小時內被入侵
2. **資安加固不是「設好再說」** — 必須在第一次開機時就完成（用 cloud-init user data）
3. **絕不開密碼登入** — 只用 SSH key + `PasswordAuthentication no`
4. **被入侵的機器不可修復，只能重建** — 你無法確定攻擊者改了什麼。砍掉重建是唯一安全做法
**信心**：高（親身經歷，付出數天代價）
**日期**：2026-03-09

### SSH Key 管理不當的連鎖反應 — 一把錯誤的 key 導致整台 VPS 被入侵
**問題**：建立 VPS 時，提供了不匹配的 SSH public key 給 Hetzner。VPS 開通後 SSH key 認證失敗 → 被迫開啟密碼登入來 debug → 密碼登入暴露在公網 → 被暴力破解 → 整台 VPS 失守。根因追溯：key fingerprint 格式不同（Hetzner 顯示 MD5 `df:93:...`，SSH client 顯示 SHA256 `6pI7zu...`），沒有交叉驗證就以為 key 正確。
**教訓**：
1. **註冊 SSH key 後必須驗證 fingerprint match** — `ssh-keygen -l -E md5 -f ~/.ssh/id_ed25519.pub` 轉換格式比對
2. **SSH key 失敗時，絕對不要退而用密碼登入** — 正確做法是修正 key，不是降級安全等級
3. **一個看似無害的操作錯誤（貼錯 key）可以導致完全失控的連鎖反應**
**信心**：高
**日期**：2026-03-09

### VPS 首次開機安全清單 — cloud-init + Hetzner Cloud Firewall
**問題**：第一次建 VPS 時沒有任何安全加固，SSH port 22 + 密碼登入直接暴露。第二次重建時使用 cloud-init user data，在第一次開機就完成所有安全設定。
**正確做法（已驗證）**：
1. **cloud-init user data**：自訂 SSH port [問 CEO] + 禁密碼 + UFW 防火牆 + fail2ban
2. **Cloud Firewall**（網路層）：只開必要 port [問 CEO]，在封包到達 VPS 前就擋掉。比 host-level UFW 更安全
3. **開機後加固**：`apt upgrade` + `unattended-upgrades`（自動安全更新）+ `chattr +i authorized_keys`（防篡改）
4. **驗證**：`cat /etc/ld.so.preload`（應為空或不存在）、`crontab -l`（應無惡意條目）、`head -1 ~/.bashrc`（不應是 `exit 0`）
**通則**：安全加固的時間窗口是「VPS 開通到第一個惡意掃描到達」之間 — 這可能只有幾分鐘。唯一可靠方案是 cloud-init 在開機時自動完成，不依賴人工操作。
**信心**：高（第二次建 VPS 驗證，所有安全措施在首次 SSH 連入前已生效）
**檔案**：cloud-init 設定檔 [問 CEO 取得路徑和內容]
**日期**：2026-03-09

### 惡意軟體的隱蔽手法 — 看起來正常不代表正常
**問題**：VPS 被入侵後，攻擊者的隱蔽手法讓所有常規檢查都看起來正常：
- `crontab -l` 顯示空（因為 `.bashrc` 定義了覆寫 function，攔截 crontab 指令）
- `ps aux` 看不到挖礦進程（`libprocesshider.so` 透過 `ld.so.preload` 注入所有進程，隱藏特定 process）
- `ssh` 指令結果正常回傳（因為 `.bashrc` 的 `exit 0` 只影響非互動 session，互動 SSH 不受影響）
- scp/sftp 失敗被歸因為「Hetzner 環境問題」（實際是 ld.so.preload 破壞了非互動 SSH subsystem）
**教訓**：
1. **多個「環境怪癖」同時出現 = 很可能是入侵** — 單一怪癖可能是 config 問題，3+ 個同時出現幾乎確定是惡意行為
2. **不能只用被入侵機器自己的工具檢查自己** — `crontab`、`ps` 都已被劫持。需要從外部（如 rescue mode / live CD）檢查
3. **「Hetzner 預裝」不是 ld.so.preload 有內容的合理解釋** — 正常的 cloud image 不會修改 ld.so.preload
**信心**：高
**日期**：2026-03-09
