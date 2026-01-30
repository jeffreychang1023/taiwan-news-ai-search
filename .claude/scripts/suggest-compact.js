#!/usr/bin/env node
/**
 * suggest-compact.js
 *
 * 追蹤工具呼叫次數和里程碑完成，在適當時機建議 compact。
 * 由 PostToolUse hook 觸發。
 *
 * v2: 降低門檻、精簡輸出、減少 token 浪費
 */

const fs = require('fs');
const path = require('path');

// 設定（v2: 更積極的門檻）
const FIRST_SUGGESTION_THRESHOLD = 25;  // 原 50 → 25
const REMINDER_INTERVAL = 15;           // 原 25 → 15
const MILESTONE_THRESHOLD = 2;          // 原 3 → 2

// 狀態檔案路徑
const STATE_FILE = path.join(__dirname, '..', 'memory', 'compact-state.json');

function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    }
  } catch (e) { /* 重新初始化 */ }
  return {
    toolCallCount: 0,
    lastSuggestionAt: 0,
    todoWriteCount: 0,
    lastTodoSuggestionAt: 0,
    sessionStart: new Date().toISOString()
  };
}

function saveState(state) {
  const dir = path.dirname(STATE_FILE);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

function main() {
  const args = process.argv.slice(2);

  // --reset: PreCompact 或手動重置
  if (args.includes('--reset')) {
    saveState({
      toolCallCount: 0,
      lastSuggestionAt: 0,
      todoWriteCount: 0,
      lastTodoSuggestionAt: 0,
      sessionStart: new Date().toISOString()
    });
    return;
  }

  // --status: 查看目前狀態
  if (args.includes('--status')) {
    const state = loadState();
    console.log(`[Compact] calls: ${state.toolCallCount}, todos: ${state.todoWriteCount || 0}, since: ${state.sessionStart}`);
    return;
  }

  // --milestone: TodoWrite 呼叫時觸發
  if (args.includes('--milestone')) {
    const state = loadState();
    state.todoWriteCount = (state.todoWriteCount || 0) + 1;
    const sinceLastSuggestion = state.todoWriteCount - (state.lastTodoSuggestionAt || 0);

    if (sinceLastSuggestion >= MILESTONE_THRESHOLD) {
      state.lastTodoSuggestionAt = state.todoWriteCount;
      saveState(state);
      console.log(`[COMPACT] ${state.todoWriteCount} todo updates done. Good time to /compact before moving on.`);
    } else {
      saveState(state);
    }
    return;
  }

  // 正常流程：增加計數
  const state = loadState();
  state.toolCallCount++;

  let shouldSuggest = false;

  if (state.toolCallCount === FIRST_SUGGESTION_THRESHOLD) {
    shouldSuggest = true;
    state.lastSuggestionAt = state.toolCallCount;
  } else if (
    state.toolCallCount > FIRST_SUGGESTION_THRESHOLD &&
    (state.toolCallCount - state.lastSuggestionAt) >= REMINDER_INTERVAL
  ) {
    shouldSuggest = true;
    state.lastSuggestionAt = state.toolCallCount;
  }

  saveState(state);

  if (shouldSuggest) {
    console.log(`[COMPACT] ${state.toolCallCount} tool calls this session. Consider /compact at the next logical breakpoint.`);
  }
}

main();
