@echo off
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\dev\start-frontend.ps1" %*
