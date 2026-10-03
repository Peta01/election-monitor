@echo off
setlocal
cd /d "%~dp0"
title Volebni prehled - aktualizace
echo ============================================
echo   Volebni prehled - aktualizace
echo ============================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\aktualizovat.ps1"
set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (
  echo Hotovo. Aplikaci spustite souborem SPUSTIT.bat. Sledovane obce i data zustaly zachovany.
) else (
  echo Aktualizace se nezdarila - viz zprava vyse. Stavajici verze zustava funkcni.
)
pause
exit /b %RC%
