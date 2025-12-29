"""
Pytest configuration and shared fixtures.
"""
import sys
from pathlib import Path

# Add the parent directory to the Python path
# This allows imports to find trivia_bot module
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))