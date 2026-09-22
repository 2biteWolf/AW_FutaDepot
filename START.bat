@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "%~dp0AW_FutaDepot.exe" if exist "%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" (
  "%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /win32icon:"%~dp0icon.ico" /r:System.Windows.Forms.dll /out:"%~dp0AW_FutaDepot.exe" "%~dp0launcher.cs" >nul 2>nul
)

if exist "%~dp0AW_FutaDepot.exe" (
  powershell -NoProfile -WindowStyle Hidden -Command "Unblock-File -LiteralPath '%~dp0AW_FutaDepot.exe'" >nul 2>nul
  start "" "%~dp0AW_FutaDepot.exe"
  goto :eof
)

if exist "%~dp0runtime\pythonw.exe" (
  start "" "%~dp0runtime\pythonw.exe" "%~dp0ui.py"
  goto :eof
)

where pyw >nul 2>nul && (start "" pyw -3 "%~dp0ui.py" & goto :eof)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0ui.py" & goto :eof)
where py >nul 2>nul && (start "" py -3 "%~dp0ui.py" & goto :eof)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
  if exist "%%D\pythonw.exe" (
    start "" "%%D\pythonw.exe" "%~dp0ui.py"
    goto :eof
  )
)

python "%~dp0ui.py"
if errorlevel 1 (
  echo Python 3 with Tcl/Tk is required.
  echo winget install Python.Python.3.12
  pause
)
