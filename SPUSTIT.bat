@echo off
setlocal
cd /d "%~dp0"
title Volebni prehled
if not exist ".venv\Scripts\python.exe" (
  echo Aplikace jeste neni nainstalovana. Spustte nejdriv INSTALOVAT.bat.
  pause
  exit /b 1
)
echo Spoustim Volebni prehled. Prohlizec se otevre automaticky.
echo Toto okno nechte otevrene - zavrenim okna se sledovani zastavi.
echo.
".venv\Scripts\python.exe" -m election_monitor
echo.
echo Aplikace byla ukoncena.
pause
