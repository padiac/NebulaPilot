@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
start "" pythonw -m nebulapilot.app_gui
