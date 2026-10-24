@echo off
cd /d "%~dp0"
python control_panel.py
if errorlevel 1 pause