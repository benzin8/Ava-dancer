@echo off
setlocal enabledelayedexpansion

python -m pip install --upgrade pip setuptools wheel

if not exist ".venv\" (
    python -m venv venv
)
call venv\Scripts\activate

pip install -r requirements.txt

python main.py
pause