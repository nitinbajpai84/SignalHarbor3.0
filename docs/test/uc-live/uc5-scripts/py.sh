#!/bin/sh
# Run a UC5 script with the repo's interpreter (Git Bash). Usage: sh docs/test/uc-live/uc5-scripts/py.sh <script.py> [args]
cd "$(dirname "$0")" && MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 TMP=/d/Temp TEMP=/d/Temp "${UC5_PY:-/c/Users/Nitin/Python Projects/Investment Doc Extraction/files/venv/Scripts/python.exe}" "$@"
