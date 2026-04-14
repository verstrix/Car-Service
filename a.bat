@echo off
title Car System
cd /d "%~dp0"

if not exist venv (
    py -m venv venv
)

call venv\Scripts\activate

pip install -r requirements.txt

py app.py

pause