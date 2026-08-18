@echo off
title PraktiKit - Launcher
chcp 65001 >nul
echo.
echo  ==========================================
echo   PraktiKit - Smart Report Template Extractor
echo  ==========================================
echo.
echo  Memeriksa apakah backend sudah berjalan...
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8000/health | findstr "200" >nul
if %errorlevel%==0 (
    echo   [OK] Backend sudah aktif di http://127.0.0.1:8000
    set BACKEND_RUNNING=1
) else (
    echo   [..] Backend belum aktif - akan dimulai...
    set BACKEND_RUNNING=0
)

echo  Memeriksa apakah frontend sudah berjalan...
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:3000 | findstr "200" >nul
if %errorlevel%==0 (
    echo   [OK] Frontend sudah aktif di http://localhost:3000
    set FRONTEND_RUNNING=1
) else (
    echo   [..] Frontend belum aktif - akan dimulai...
    set FRONTEND_RUNNING=0
)

echo.
if "%BACKEND_RUNNING%"=="0" (
    echo  Memulai backend (FastAPI) di window baru...
    start "PraktiKit Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn praktikit.api.app:app --host 127.0.0.1 --port 8000"
)
if "%FRONTEND_RUNNING%"=="0" (
    echo  Memulai frontend (Next.js) di window baru...
    start "PraktiKit Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
)

echo.
echo  Menunggu server siap (maks 60 detik)...
set WAITED=0
:wait_backend
if "%BACKEND_RUNNING%"=="1" goto wait_frontend
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8000/health | findstr "200" >nul
if %errorlevel%==0 (
    echo   [OK] Backend siap!
    goto wait_frontend
)
timeout /t 2 /nobreak >nul
set /a WAITED+=2
if %WAITED% geq 60 (
    echo   [WARN] Backend tidak merespon. Periksa window "PraktiKit Backend".
    goto wait_frontend
)
goto wait_backend

:wait_frontend
set WAITED=0
if "%FRONTEND_RUNNING%"=="1" goto done
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:3000 | findstr "200" >nul
if %errorlevel%==0 (
    echo   [OK] Frontend siap!
    goto done
)
timeout /t 2 /nobreak >nul
set /a WAITED+=2
if %WAITED% geq 60 (
    echo   [WARN] Frontend tidak merespon. Periksa window "PraktiKit Frontend".
    goto done
)
goto wait_frontend

:done
echo.
echo  ==========================================
echo   PraktiKit siap digunakan!
echo.
echo   Buka browser:  http://localhost:3000
echo   API docs:      http://localhost:3000/api/docs
echo  ==========================================
echo.
start "" http://localhost:3000
echo  Launcher selesai. Window "PraktiKit Backend" dan "PraktiKit Frontend"
echo  harus TETAP TERBUKA selama Anda memakai PraktiKit.
echo.
pause
