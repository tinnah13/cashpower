#!/usr/bin/env bash
# One-time setup (Mac/Linux/Git Bash). Windows PowerShell: see README.
python -m venv .venv
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
pip install -r requirements.txt
echo "Done. Start the app with:  python run.py"
