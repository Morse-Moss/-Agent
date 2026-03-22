@echo off
setlocal

C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe --version >nul 2>nul && goto use_py312
C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe --version >nul 2>nul && goto use_py311
G:\Conda\python.exe --version >nul 2>nul && goto use_g_conda
python --version >nul 2>nul && goto use_python
py --version >nul 2>nul && goto use_py_launcher

echo No usable Python executable was found.
exit /b 1

:use_py312
C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe "%~dp0scripts\dev\start_backend.py" %*
exit /b %errorlevel%

:use_py311
C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe "%~dp0scripts\dev\start_backend.py" %*
exit /b %errorlevel%

:use_g_conda
G:\Conda\python.exe "%~dp0scripts\dev\start_backend.py" %*
exit /b %errorlevel%

:use_python
python "%~dp0scripts\dev\start_backend.py" %*
exit /b %errorlevel%

:use_py_launcher
py "%~dp0scripts\dev\start_backend.py" %*
exit /b %errorlevel%
