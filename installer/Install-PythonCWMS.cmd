@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-PythonCWMS.ps1" %*
set "INSTALL_EXIT_CODE=%ERRORLEVEL%"
if not "%INSTALL_EXIT_CODE%"=="0" (
  echo.
  echo Python CWMS installation failed with exit code %INSTALL_EXIT_CODE%.
  echo Review the error above, then press any key to close this window.
  pause >nul
)
exit /b %INSTALL_EXIT_CODE%
