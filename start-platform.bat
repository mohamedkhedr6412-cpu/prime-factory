@echo off
setlocal EnableExtensions
title PRIME-Factory Launcher

set "PROJECT=C:\Users\MTS\Desktop\graduation project\Github\prime-factory-main"
set "PY=%PROJECT%\venv\Scripts\python.exe"
set "URL=http://127.0.0.1:8050/real"

echo.
echo   PRIME-Factory - starting...
echo.

rem --- 1) Mosquitto broker (Windows service, automatic) ---
sc query mosquitto >nul 2>&1
if errorlevel 1 (
  echo   [!] Mosquitto service not found.
) else (
  sc query mosquitto | findstr /I "STATE.*RUNNING" >nul
  if errorlevel 1 (
    echo   Starting Mosquitto service...
    net start mosquitto >nul 2>&1
    if errorlevel 1 echo   [!] Could not start Mosquitto automatically.
  ) else (
    echo   Mosquitto: already running
  )
)

netstat -ano | findstr ":1883" | findstr "LISTENING" >nul
if errorlevel 1 (
  echo   [!] Port 1883 is not listening.
) else (
  echo   Broker port 1883: OK
)

rem --- 2) Dashboard ---
netstat -ano | findstr ":8050" | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo   Dashboard: already running
  goto OPEN_BROWSER
)

if not exist "%PY%" (
  echo   [!] Python not found:
  echo       %PY%
  pause
  exit /b 1
)

echo   Starting dashboard...
start "PRIME-Factory Dashboard" /MIN /D "%PROJECT%" "%PY%" app.py

set /a TRIES=0
:WAIT_LOOP
netstat -ano | findstr ":8050" | findstr "LISTENING" >nul
if not errorlevel 1 goto OPEN_BROWSER
set /a TRIES+=1
if %TRIES% GEQ 40 goto TIMEOUT
ping -n 2 127.0.0.1 >nul
goto WAIT_LOOP

:TIMEOUT
echo   [!] Dashboard did not become ready in 40 seconds.
echo       Check the "PRIME-Factory Dashboard" window for errors.
pause
exit /b 1

:OPEN_BROWSER
echo   Opening %URL%
start "" "%URL%"
echo.
echo   Done. You can close this window anytime.
echo   To stop the dashboard later, close the minimized
echo   "PRIME-Factory Dashboard" console window.
ping -n 5 127.0.0.1 >nul
endlocal
