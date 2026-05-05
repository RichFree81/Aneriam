@echo off
REM ============================================================
REM  Rebuild cost_control.exe
REM  Just double-click this file. No coding needed.
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo  Rebuilding cost_control.exe ...
echo  (this takes 30-60 seconds — please don't close the window)
echo ============================================================
echo.

python -m PyInstaller --clean --distpath . cost_control.spec

echo.
if exist cost_control.exe (
    echo ============================================================
    echo  DONE. cost_control.exe has been rebuilt.
    echo  You can now double-click cost_control.exe to launch.
    echo ============================================================
) else (
    echo ============================================================
    echo  BUILD FAILED. cost_control.exe was NOT created.
    echo  Scroll up to see the error message.
    echo ============================================================
)
echo.
pause
