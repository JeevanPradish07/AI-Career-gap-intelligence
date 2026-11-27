@echo off
title AI Career Platform — System Server
color 0B
echo.
echo  ================================================
echo   AI Career Skill Gap Intelligence Platform
echo  ================================================
echo.
echo  Starting backend & frontend services...
echo  The web application will open automatically on http://localhost:5173 ...
echo.
cd /d "%~dp0"
python launcher.py
pause

