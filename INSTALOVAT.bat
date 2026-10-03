@echo off
setlocal
cd /d "%~dp0"
title Volebni prehled - instalace
echo ============================================
echo   Volebni prehled - instalace
echo ============================================
echo.

rem Kontrola, ze slozka neni otevrena primo v ZIP archivu
if not exist "pyproject.toml" (
  echo CHYBA: Nenalezen soubor pyproject.toml.
  echo Nejdriv rozbalte cely ZIP archiv a pak spustte INSTALOVAT.bat z rozbalene slozky.
  goto :fail
)

call :find_python
if defined PY goto :have_python

echo Python 3.11 nebo novejsi nebyl nalezen. Pokusim se ho nainstalovat.
where winget >nul 2>nul
if errorlevel 1 goto :manual_python
echo Instaluji Python 3.12 pres winget (muze se objevit okno s dotazem - potvrdte ho)...
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
call :find_python
if defined PY goto :have_python

:manual_python
echo.
echo Python se nepodarilo nainstalovat automaticky.
echo Otevru stranku ke stazeni. Stahnete Python, spustte instalator,
echo ZASKRTNETE "Add python.exe to PATH" a pak spustte INSTALOVAT.bat znovu.
start "" "https://www.python.org/downloads/windows/"
goto :fail

:have_python
echo Pouzivam Python: %PY%
echo.
echo Vytvarim virtualni prostredi...
"%PY%" -m venv .venv
if errorlevel 1 goto :fail
echo Instaluji aplikaci a potrebne knihovny (vyzaduje internet)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :fail

echo.
echo ============================================
echo   Instalace dokoncena.
echo   Aplikaci spustite souborem SPUSTIT.bat
echo ============================================
pause
exit /b 0

:fail
echo.
echo Instalace se nezdarila. Podrobnosti viz NAVOD-INSTALACE.md.
pause
exit /b 1

rem Najde pouzitelny Python >= 3.11 a nastavi promennou PY na jeho cestu
:find_python
set "PY="
for %%C in ("python.exe" "py.exe") do (
  if not defined PY call :try_python %%C
)
for %%V in (313 312 311) do (
  if not defined PY if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" call :try_python "%LocalAppData%\Programs\Python\Python%%V\python.exe"
  if not defined PY if exist "%ProgramFiles%\Python%%V\python.exe" call :try_python "%ProgramFiles%\Python%%V\python.exe"
)
exit /b 0

:try_python
rem Overuje verzi; zaroven vyradi falesny python.exe z Microsoft Store
%~1 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=%~1"
exit /b 0
