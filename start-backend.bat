@echo off
title PraktiKit Backend
chcp 65001 >nul
echo.
echo  ==========================================
echo   PraktiKit Backend API (FastAPI)
echo  ==========================================
echo.
echo  URL: http://127.0.0.1:8000
echo  Docs: http://127.0.0.1:8000/docs
echo  Tekan Ctrl+C untuk menghentikan server.
echo.
cd /d %~dp0backend
.venv\Scripts\python.exe -m uvicorn praktikit.api.app:app --host 127.0.0.1 --port 8000
pause
