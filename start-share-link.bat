@echo off
title PRIME-Factory Share Link
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0share-link.ps1" %*
echo.
echo   You can close this window anytime.
pause
