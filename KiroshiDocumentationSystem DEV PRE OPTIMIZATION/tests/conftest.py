import sys
import types
from pathlib import Path


class _DummyHotKeys:
    def __init__(self, mapping):
        self.mapping = mapping

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def join(self):
        return None


keyboard_stub = types.SimpleNamespace(GlobalHotKeys=lambda mapping: _DummyHotKeys(mapping))
sys.modules.setdefault("pynput", types.SimpleNamespace(keyboard=keyboard_stub))
sys.modules["pynput.keyboard"] = keyboard_stub

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
