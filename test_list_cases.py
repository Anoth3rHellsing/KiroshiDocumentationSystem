import sys
import json
from unittest.mock import MagicMock

# Mock streamlit before importing the app
sys.modules['streamlit'] = MagicMock()
sys.modules['streamlit.components.v1'] = MagicMock()
sys.modules['streamlit.errors'] = MagicMock()
sys.modules['pandas'] = MagicMock()
sys.modules['altair'] = MagicMock()
sys.modules['reportlab'] = MagicMock()
sys.modules['reportlab.lib.pagesizes'] = MagicMock()
sys.modules['reportlab.lib'] = MagicMock()
sys.modules['reportlab.lib.styles'] = MagicMock()
sys.modules['reportlab.platypus'] = MagicMock()
sys.modules['reportlab.graphics.shapes'] = MagicMock()
sys.modules['reportlab.graphics.charts.barcharts'] = MagicMock()
sys.modules['reportlab.graphics.charts.lineplots'] = MagicMock()
sys.modules['reportlab.graphics.widgets.markers'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['pynput'] = MagicMock()
sys.modules['pyperclip'] = MagicMock()
sys.modules['urllib3'] = MagicMock()

# Patch json.dump to avoid serialization errors with MagicMock
original_dump = json.dump
def safe_dump(obj, fp, **kwargs):
    # This mock dump does nothing, effectively ignoring the file write
    pass
json.dump = safe_dump

# Now import the function
from case_documentation_app import list_saved_cases

# Mock _refresh_and_get_cases to return an empty list
import case_documentation_app
case_documentation_app._refresh_and_get_cases = MagicMock(return_value=[])

result = list_saved_cases()
print(f"Result: {result}")
assert result == []
