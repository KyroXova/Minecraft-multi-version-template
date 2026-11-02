@echo off
python "%~dp0tools\kyro\template.py" gradle %*
exit /b %errorlevel%
