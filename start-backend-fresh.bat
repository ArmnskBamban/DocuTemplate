@echo off
title PraktiKit Backend (3600s TTL)
chcp 65001 >nul
echo.
echo  ==========================================
echo   PraktiKit Backend API - 60min session
echo  ==========================================
echo.
echo  URL: http://127.0.0.1:8000
echo  SESSION_TTL: 3600s (1 jam)
echo.
echo  Menghentikan backend lama...
taskkill /F /FI "WindowTitle eq PraktiKit Backend*" 2>nul
timeout /t 2 /nobreak >nul
echo  Memulai backend baru...
cd /d %~dp0
.venv\Scripts\python.exe -m uvicorn praktikit.api.app:app --host 127.0.0.1 --port 8000
pause