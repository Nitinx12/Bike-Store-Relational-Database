"""Pytest path setup: make the repo root importable so tests can `import main`."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
