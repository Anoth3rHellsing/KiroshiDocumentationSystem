"""Mocking pynput for test environment."""

from unittest.mock import MagicMock
import sys

class MockKeyboard:
    class GlobalHotKeys:
        def __init__(self, bindings):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def join(self):
            pass

mock_pynput = MagicMock()
mock_pynput.keyboard = MockKeyboard
sys.modules['pynput'] = mock_pynput
sys.modules['pynput.keyboard'] = MockKeyboard
