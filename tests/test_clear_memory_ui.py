import sys
from unittest.mock import MagicMock, patch
import pytest

import kiroshi_chat

@patch('kiroshi_chat.st')
def test_clear_memory_confirmation(mock_st):
    # Setup initial state
    session_state = MagicMock()
    session_state.get.side_effect = lambda k, d=None: session_state.__dict__.get(k, d)
    session_state.__contains__ = lambda self, k: k in self.__dict__
    session_state.__setitem__ = lambda self, k, v: setattr(self, k, v)
    session_state.__getitem__ = lambda self, k: getattr(self, k)

    session_state.kiroshi_chat_history = [{'role': 'user', 'content': 'hello'}]
    session_state.confirm_clear_memory = False

    mock_st.session_state = session_state
    mock_st.chat_input.return_value = None

    # 1. Initial render, button is not clicked yet
    mock_st.button.return_value = False
    kiroshi_chat.main()
    assert not mock_st.session_state.get('confirm_clear_memory')

    # 2. User clicks "Clear memory"
    def button_mock(label, *args, **kwargs):
        if label == "Clear memory":
            return True
        return False
    mock_st.button.side_effect = button_mock

    kiroshi_chat.main()
    assert mock_st.session_state.get('confirm_clear_memory') is True
