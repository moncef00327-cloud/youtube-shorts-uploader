@echo off
REM ============================================================
REM مُشغّل مرتفع لـ setup_scheduler.ps1
REM اطلب صلاحيات المسؤول تلقائياً وشغّل سكريبت الجدولة.
REM ============================================================

net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [طلب صلاحيات] إعادة التشغيل كمسؤول...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo [تشغيل] إعداد المهمة المجدولة...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_scheduler.ps1"
pause
