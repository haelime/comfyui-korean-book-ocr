@echo off
chcp 65001 >nul
title ComfyUI Korean Book OCR 설치
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_windows.ps1"
echo.
pause
