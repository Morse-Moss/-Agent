@echo off
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\dev\smoke-test.ps1" %*
