# run-e2e-loop.ps1
# E2E 驗證 loop — 每輪全新 session，自動重置 checklist，保留 findings
#
# 使用方式：
#   .\run-e2e-loop.ps1
#
# 停止條件：
#   1. Agent 寫入 tests/e2e-loop-status.txt 內容為 ALL_CLEAR（連續全 PASS + 0 open issues）
#   2. 手動 Ctrl+C
#
# 前提：
#   1. claude CLI 已安裝且可用
#   2. Python 3.11 venv 在 myenv311/
#   3. Chrome 已安裝（Chrome DevTools MCP 會自動啟動）

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) { $ProjectRoot = Get-Location }

$StatusFile = Join-Path $ProjectRoot "tests\e2e-loop-status.txt"
$Round = 0

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " NLWeb E2E Verification Loop" -ForegroundColor Cyan
Write-Host " Stop: ALL_CLEAR or Ctrl+C" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Clean up status file from previous run
if (Test-Path $StatusFile) {
    Remove-Item $StatusFile
    Write-Host "Cleared previous status file." -ForegroundColor Gray
}

while ($true) {
    $Round++
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host ""
    Write-Host "=== Round $Round | $Timestamp ===" -ForegroundColor Yellow

    # Step 1: Reset checklist (preserves execution log + findings)
    Write-Host "[1/3] Resetting checklist (preserving history)..." -ForegroundColor Gray
    & python "$ProjectRoot\tests\reset_checklist.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to reset checklist" -ForegroundColor Red
        Start-Sleep -Seconds 5
        continue
    }

    # Step 2: Run claude with the e2e loop prompt
    Write-Host "[2/3] Starting claude session..." -ForegroundColor Gray
    $Prompt = Get-Content "$ProjectRoot\tests\e2e-loop-prompt.md" -Raw -Encoding UTF8

    # claude -p = print mode (non-interactive, exits when done)
    # --dangerously-skip-permissions = auto-accept all tool permissions
    claude -p $Prompt --dangerously-skip-permissions

    $ExitCode = $LASTEXITCODE
    $EndTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "Round $Round finished at $EndTime (exit code: $ExitCode)" -ForegroundColor Yellow

    # Step 3: Check stop condition
    Write-Host "[3/3] Checking stop condition..." -ForegroundColor Gray
    if (Test-Path $StatusFile) {
        $Status = (Get-Content $StatusFile -Raw).Trim()
        if ($Status -eq "ALL_CLEAR") {
            Write-Host "" -ForegroundColor Green
            Write-Host "========================================" -ForegroundColor Green
            Write-Host " ALL_CLEAR after Round $Round" -ForegroundColor Green
            Write-Host " All 31 tests PASS, 0 open issues." -ForegroundColor Green
            Write-Host " Loop stopped." -ForegroundColor Green
            Write-Host "========================================" -ForegroundColor Green
            break
        }
    }

    # Brief pause before next round
    Write-Host "Next round in 10 seconds... (Ctrl+C to stop)" -ForegroundColor Gray
    Start-Sleep -Seconds 10
}
