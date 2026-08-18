@echo off
title PraktiKit Frontend
chcp 65001 >nul
echo.
echo  ==========================================
echo   PraktiKit Frontend (Next.js)
echo  ==========================================
echo.
echo  URL: http://localhost:3000
echo  Tekan Ctrl+C untuk menghentikan server.
echo.
cd /d %~dp0frontend
npm run dev
pause
