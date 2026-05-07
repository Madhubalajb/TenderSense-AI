"""
run.py — Tendra AI Launcher
----------------------------------
Run this file instead of app/main.py to avoid module import errors.

Usage:
    streamlit run run.py

Place this file in your project ROOT:
    tendra-ai/
        run.py          ← this file
        app/
            main.py
            pipeline/
            pages/
            ...
"""

import sys
import os

# Add the project root to Python's path so "from app.xxx import" works
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Now import and run the main app
from app.main import *