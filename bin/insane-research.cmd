@echo off
set ROOT=%~dp0..
python "%ROOT%\skills\insane-research\scripts\researchctl.py" %*
exit /b %ERRORLEVEL%
