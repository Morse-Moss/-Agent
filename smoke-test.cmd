@echo off
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\smoke-test.ps1" %*
