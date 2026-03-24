---
name: Slate by RandomLabs — swarm coding agent
description: RLM-based coding agent with multi-model routing, thread-based parallelism, episodic memory. Watch for Claude Code integration (announced week of 2026-03-13).
type: reference
---

**Slate** by RandomLabs (randomlabs.ai/blog/slate)

- Swarm native coding agent：用 TypeScript DSL 編排大量平行 threads（subagents），context 共享（hive mind）
- Multi-model routing：自動選模型（Opus 策略 / Haiku 執行）
- Episodic memory：自動保留成功 tool calls，剪掉失敗嘗試
- 基於 opencode 架構，計畫支援 Claude Code

**2026-03-13 評估結論**：現在不用，太早。等 Claude Code integration 出來再評估。
**值得借鑑**：multi-model routing 自動化、episodic memory auto-prune、thread context 共享。
**來源**：https://x.com/realmcore_/status/2032146316730778004
