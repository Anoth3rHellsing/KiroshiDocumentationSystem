import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock dependencies before importing
sys.modules['streamlit'] = MagicMock()
sys.modules['kiroshi_local_ai'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['urllib3'] = MagicMock()

# Since Streamlit uses st.session_state as a dict with attribute access,
# we need a proper mock for it.
class SessionStateMock(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)
    def __setattr__(self, key, value):
        self[key] = value

@pytest.fixture(autouse=True)
def clean_sys_modules():
    """Ensure kiroshi_chat is reloaded correctly for each test."""
    if 'kiroshi_chat' in sys.modules:
        del sys.modules['kiroshi_chat']
    yield

@patch('kiroshi_chat.st.chat_input', return_value=None)
@patch('kiroshi_chat.st.button')
@patch('kiroshi_chat.st.warning')
@patch('kiroshi_chat.st.columns')
@patch('kiroshi_chat.st.rerun')
def test_clear_memory_confirmation_flow(mock_rerun, mock_columns, mock_warning, mock_button, mock_chat_input):
    # Import inside test to ensure mocks are active
    import kiroshi_chat

    # Setup st.session_state mock
    mock_state = SessionStateMock()
    mock_state.kiroshi_chat_history = [{'role': 'user', 'content': 'test'}]
    kiroshi_chat.st.session_state = mock_state

    # First render: confirm_clear_memory is not set, so button("Clear memory") is called.
    # Simulate clicking "Clear memory"
    def button_side_effect(label, **kwargs):
        if label == "Clear memory":
            return True
        return False
    mock_button.side_effect = button_side_effect

    # We patch save_memory to prevent file IO
    with patch('kiroshi_chat.save_memory') as mock_save:
        kiroshi_chat.main()

        # State should be updated to confirm=True
        assert mock_state.get("confirm_clear_memory") is True
        # Original memory should remain
        assert len(mock_state.kiroshi_chat_history) == 1
        # Should rerun
        mock_rerun.assert_called()

    mock_rerun.reset_mock()

    # Second render: confirm_clear_memory is True.
    # We should see warning and columns.
    # Simulate clicking "Yes, delete it"
    mock_col1 = MagicMock()
    mock_col2 = MagicMock()
    mock_columns.return_value = (mock_col1, mock_col2)
    mock_col1.button.return_value = True
    mock_col2.button.return_value = False

    with patch('kiroshi_chat.save_memory') as mock_save:
        kiroshi_chat.main()

        mock_warning.assert_called_with("Are you sure?")
        mock_col1.button.assert_called_with("Yes, delete it")

        # Memory should be cleared
        assert mock_state.kiroshi_chat_history == []
        mock_save.assert_called_with([])

        # confirm should be False
        assert mock_state.get("confirm_clear_memory") is False
        mock_rerun.assert_called()
