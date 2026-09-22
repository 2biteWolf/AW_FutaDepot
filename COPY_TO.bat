@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo AW_FutaDepot FAST COPY
echo Source: %CD%
echo.
set "DEST="
if not "%~1"=="" set "DEST=%~1"
if "%DEST%"=="" set /p DEST=Paste destination folder and press Enter: 
if "%DEST%"=="" (
  echo empty path
  pause
  exit /b 1
)
if not exist "%DEST%" mkdir "%DEST%"
set "OUT=%DEST%\AW_FutaDepot"
if not exist "%OUT%" mkdir "%OUT%"
echo Copying to %OUT%
robocopy "%CD%" "%OUT%" /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /MT:16 /XO /NFL /NDL /NP /XD __pycache__ .git .iconcache __MACOSX /XF Thumbs.db .DS_Store
set ERR=%ERRORLEVEL%
if %ERR% GEQ 8 (
  echo COPY FAILED code %ERR%
  pause
  exit /b %ERR%
)
echo DONE. Copied to %OUT%
pause
