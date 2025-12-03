# -*- coding: utf-8 -*-
import logging
import streamlit as st
from typing import List, Dict, Any, Optional
from KiroshiApp.models import CaseData
from kiroshi_chat import invoke_gpt
from KiroshiApp.constants import DEFAULT_OPENAI_API_KEY, DEFAULT_AI_BASE_URL, DEFAULT_GEMINI_API_KEY

def _get_ai_credentials():
    api_key = st.session_state.get("openai_api_key", DEFAULT_OPENAI_API_KEY)
    base_url = st.session_state.get("ai_base_url", DEFAULT_AI_BASE_URL)
    model = st.session_state.get("openai_model", "gpt-4o")
    provider = st.session_state.get("ai_provider", "OpenAI")

    # If Gemini is selected, use Gemini key
    if provider == "Gemini":
        api_key = st.session_state.get("gemini_api_key", DEFAULT_GEMINI_API_KEY)

    return api_key, base_url, model, provider

def run_qa_verify(case: CaseData) -> List[str]:
    """
    Analyzes the case data and returns a list of warnings or missing items.
    """
    warnings = []

    # 1. Mandatory Fields
    if not case.case_id:
        warnings.append("⚠️ Missing Case ID")
    if not case.company_name:
        warnings.append("⚠️ Missing Company Name")
    if not case.brief_description:
        warnings.append("⚠️ Missing Brief Description")
    if not case.description:
        warnings.append("⚠️ Missing Detailed Description")

    # 2. Logic Checks
    if case.root_cause or case.solution:
        # If conclusion started, ensure both are present
        if not case.root_cause:
            warnings.append("⚠️ Solution present but Root Cause is missing")
        if not case.solution:
            warnings.append("⚠️ Root Cause present but Solution is missing")

    # 3. Escalation Checks
    # We can't easily check 'st.session_state.include_escalations' here if passed pure data,
    # but we can check if escalation fields are partially filled.
    if case.straumann or case.esc_name:
        # Likely an escalation
        if not case.esc_email:
             warnings.append("⚠️ Escalation detected: Missing Escalation Email")
        if not case.esc_ph:
             warnings.append("⚠️ Escalation detected: Missing Escalation Phone")

    # 4. Phone/Contact
    if case.caller_name and not case.phone_number:
        warnings.append("ℹ️ Caller Name provided but no Phone Number")

    # 5. Remote Session
    if case.remote_steps and len(case.remote_steps) < 20:
         warnings.append("ℹ️ Remote Steps seem very short. Ensure all actions are documented.")

    if not warnings:
        warnings.append("✅ All QA checks passed! Case looks good.")

    return warnings

def run_ai_autocorrect(text: str) -> str:
    """
    Uses AI to correct grammar and spelling in the provided text.
    """
    if not text:
        return ""

    api_key, base_url, model, provider = _get_ai_credentials()

    prompt = (
        "Correct the grammar and spelling of the following text. "
        "Maintain the technical terminology and professional tone. "
        "Do not add any conversational filler. Just return the corrected text.\n\n"
        f"Text: {text}"
    )

    try:
        from kiroshi_chat import query_kiroshi # Explicit import to be safe
        response = query_kiroshi(prompt, [], api_key, model, base_url, provider=provider)
        return response
    except Exception as e:
        logging.error(f"AI Autocorrect failed: {e}")
        return text  # Fallback to original

def run_summarize(text: str) -> str:
    """
    Uses AI to summarize the provided text.
    """
    if not text:
        return ""

    api_key, base_url, model, provider = _get_ai_credentials()

    prompt = (
        "Summarize the following technical case notes into a concise summary. "
        "Highlight the main issue and key actions taken.\n\n"
        f"Text: {text}"
    )

    try:
        from kiroshi_chat import query_kiroshi # Explicit import
        response = query_kiroshi(prompt, [], api_key, model, base_url, provider=provider)
        return response
    except Exception as e:
        logging.error(f"AI Summarize failed: {e}")
        return f"Error generating summary: {e}"
