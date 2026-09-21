#!/usr/bin/env python3
"""The report builder lives in engine/report.py, where the app uses it too.

This keeps the command in SKILL.md working from the repository root.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4]))
from engine.report import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
