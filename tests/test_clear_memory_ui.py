import pytest
from unittest.mock import patch, MagicMock
import copy

class MockSessionState(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        return None

    def __setattr__(self, name, value):
        self[name] = value

@pytest.fixture
def mock_streamlit():
    with patch("kiroshi_chat.st") as mock_st:
        # Provide a mock session_state dict for test assertions
        mock_st.session_state = MockSessionState()
        # We need mock_st.columns to return a list of two mocks
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_st.columns.return_value = [mock_col1, mock_col2]
        yield mock_st, mock_col1, mock_col2

@patch("kiroshi_chat.save_memory")
@patch("kiroshi_chat.load_memory")
def test_clear_memory_ui_initial_click(mock_load, mock_save, mock_streamlit):
    mock_st, mock_col1, mock_col2 = mock_streamlit

    # Simulate initial click on "Clear memory"
    mock_st.button.side_effect = lambda label, **kwargs: label == "Clear memory"

    import kiroshi_chat
    # Needs to bypass UI setup and just test logic
    with patch("kiroshi_chat.configure_page"):
        with patch("kiroshi_chat.st.chat_input", return_value=None):
            kiroshi_chat.main()

    # The flag should be set to True
    assert kiroshi_chat.st.session_state.get("confirm_clear_memory") is True
    # Save memory should not have been called yet
    mock_save.assert_not_called()
    # Rerun should be triggered
    mock_st.rerun.assert_called()

@patch("kiroshi_chat.save_memory")
@patch("kiroshi_chat.load_memory")
def test_clear_memory_ui_confirm_cancel(mock_load, mock_save, mock_streamlit):
    mock_st, mock_col1, mock_col2 = mock_streamlit

    # State has confirm active
    mock_st.session_state["confirm_clear_memory"] = True

    # Simulate click on "Cancel"
    mock_col1.button.return_value = False
    mock_col2.button.return_value = True

    import kiroshi_chat
    with patch("kiroshi_chat.configure_page"):
        with patch("kiroshi_chat.st.chat_input", return_value=None):
            kiroshi_chat.main()

    # Flag should be reset
    assert kiroshi_chat.st.session_state.get("confirm_clear_memory") is False
    # Data should not be deleted
    mock_save.assert_not_called()
    # Rerun triggered
    mock_st.rerun.assert_called()

@patch("kiroshi_chat.save_memory")
@patch("kiroshi_chat.load_memory")
def test_clear_memory_ui_confirm_yes(mock_load, mock_save, mock_streamlit):
    mock_st, mock_col1, mock_col2 = mock_streamlit

    # State has confirm active
    mock_st.session_state["confirm_clear_memory"] = True

    # Simulate click on "Yes, delete it"
    mock_col1.button.return_value = True
    mock_col2.button.return_value = False

    import kiroshi_chat
    with patch("kiroshi_chat.configure_page"):
        with patch("kiroshi_chat.st.chat_input", return_value=None):
            kiroshi_chat.main()

    # Flag should be reset
    assert kiroshi_chat.st.session_state.get("confirm_clear_memory") is False
    # Memory should be cleared
    assert kiroshi_chat.st.session_state.get("kiroshi_chat_history") == []
    # Save memory called with empty list
    mock_save.assert_called_with([])
    # Rerun triggered
    mock_st.rerun.assert_called()