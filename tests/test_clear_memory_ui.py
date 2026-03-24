import sys
from unittest.mock import MagicMock, patch

# Mock dependencies before importing kiroshi_chat
sys.modules['kiroshi_local_ai'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['urllib3'] = MagicMock()
sys.modules['streamlit'] = MagicMock()

import kiroshi_chat
import streamlit as st

class MockSessionState(dict):
    def __getattr__(self, name):
        return self.get(name)
    def __setattr__(self, name, value):
        self[name] = value

@patch('kiroshi_chat.st')
@patch('kiroshi_chat.save_memory')
def test_clear_memory_requires_confirmation(mock_save_memory, mock_st):
    mock_st.session_state = MockSessionState()
    mock_st.session_state['kiroshi_chat_history'] = [{'role': 'user', 'content': 'test'}]
    mock_st.session_state['confirm_clear_memory'] = False

    mock_st.chat_input.return_value = None

    def button_side_effect(label, **kwargs):
        if label == "Clear memory":
            return True
        return False
    mock_st.button.side_effect = button_side_effect

    kiroshi_chat.main()

    assert mock_st.session_state.confirm_clear_memory is True
    assert len(mock_st.session_state.kiroshi_chat_history) == 1
    mock_save_memory.assert_not_called()

@patch('kiroshi_chat.st')
@patch('kiroshi_chat.save_memory')
def test_clear_memory_confirmed(mock_save_memory, mock_st):
    mock_st.session_state = MockSessionState()
    mock_st.session_state['kiroshi_chat_history'] = [{'role': 'user', 'content': 'test'}]
    mock_st.session_state['confirm_clear_memory'] = True

    mock_st.chat_input.return_value = None

    mock_col1 = MagicMock()
    mock_col2 = MagicMock()
    mock_st.columns.return_value = [mock_col1, mock_col2]

    mock_col1.button.return_value = True
    mock_col2.button.return_value = False

    kiroshi_chat.main()

    assert mock_st.session_state.kiroshi_chat_history == []
    mock_save_memory.assert_called_once_with([])
    assert mock_st.session_state.confirm_clear_memory is False

@patch('kiroshi_chat.st')
@patch('kiroshi_chat.save_memory')
def test_clear_memory_cancelled(mock_save_memory, mock_st):
    mock_st.session_state = MockSessionState()
    mock_st.session_state['kiroshi_chat_history'] = [{'role': 'user', 'content': 'test'}]
    mock_st.session_state['confirm_clear_memory'] = True

    mock_st.chat_input.return_value = None

    mock_col1 = MagicMock()
    mock_col2 = MagicMock()
    mock_st.columns.return_value = [mock_col1, mock_col2]

    mock_col1.button.return_value = False
    mock_col2.button.return_value = True

    kiroshi_chat.main()

    assert len(mock_st.session_state.kiroshi_chat_history) == 1
    mock_save_memory.assert_not_called()
    assert mock_st.session_state.confirm_clear_memory is False
