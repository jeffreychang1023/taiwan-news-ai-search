@echo off
title Indexing Dashboard Server

cd /d "%~dp0"

echo Starting Indexing Dashboard...
echo.

:: Start browser after 2 seconds (in background)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8001"

:: Start the server
python code/python/indexing/dashboard_server.py

:: If server exits, show error before closing
echo.
echo Server stopped. Press any key to close...
pause >nul
