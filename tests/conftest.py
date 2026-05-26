"""Project-level pytest configuration."""
import sys
import os

# Ensure the project root is on sys.path so `from main import ...` works
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
