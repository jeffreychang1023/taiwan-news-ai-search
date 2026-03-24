---
name: VPS 部署與基礎設施狀態
description: Hetzner VPS、Docker、CI/CD、資安設定的當前狀態。部署或 VPS 相關工作時讀取。
type: project
---

## Infra Migration Progress (2026-03-12 更新)

**Phase 1: Local Validation** — 完成
- S1: Qwen3-4B INT8 OK (4.4GB VRAM, 10.7 chunks/sec)
- S2: PostgreSQL Docker OK (PG17 + pgvector + pg_bigm)

**Phase 2: Code Migration** — 完成（committed as `58f82e0`）

**Phase 3: Deploy to Hetzner VPS** — 完成（2026-03-12）
- **新 VPS**: IP **95.217.153.63**, SSH port **2222**, Ubuntu 24.04 ARM64 (CAX31, 16GB RAM)
- **舊 VPS** 77.42.69.120 已刪除（被入侵）
- Docker 3 containers: nlweb-postgres + nlweb-app + nlweb-nginx
- twdubao.com + HTTPS + Cloudflare Origin Certificate (15yr) + SSL Full (strict)
- 資安加固：cloud-init（SSH 2222 + 禁密碼）+ UFW + fail2ban + Hetzner Cloud Firewall + chattr +i authorized_keys
- 部署檔案：`docker-compose.production.yml`、`nginx.conf`、`infra/cloud-init.yaml`
- **CI/CD**: GitHub Actions（`.github/workflows/deploy.yml`）push to main → SSH deploy → Docker rebuild → LINE 通知
- **VPS git repo**: 已從 SCP 模式改為 git（`git init` + `remote add` + `fetch` + `reset --hard`）
- **待做**：全量 indexing 後 pg_dump/pg_restore → 關閉舊服務（Render/Qdrant Cloud/Neon）
