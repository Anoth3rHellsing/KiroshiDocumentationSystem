import os
import json
import uuid
from collections.abc import Mapping, Sequence
import requests
import streamlit as st
import urllib3
from pathlib import Path
from KiroshiApp.constants import DEFAULT_GEMINI_API_KEY

# Disable SSL warnings for corporate environments with interception proxies
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Asset paths used by the Streamlit UI.  They are defined at import time so
# other modules can reference them, but the actual page configuration is
# deferred until the app is executed.  This prevents unwanted side effects
# (such as "set_page_config can only be called once" errors) when this module
# is imported purely for its helper functions.
ASSETS_DIR = Path(__file__).parent
KIROSHI_CHAT_LOGO_PATH = ASSETS_DIR / "Kiroshi_Logo.png"


def configure_page() -> None:
    """Configure the Streamlit page when running the standalone chat app."""
    st.set_page_config(page_title="Kiroshi Chat", page_icon=str(KIROSHI_CHAT_LOGO_PATH))

MEMORY_FILE = "kiroshi_memory.json"
MANUAL_DOCS_FILE = "manual_memory.json"
KIROSHI_REFERENCE_FILE = ASSETS_DIR / "docs" / "kiroshi_quick_reference.json"
DEFAULT_OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY",
    "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",
)
DEFAULT_AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
DEFAULT_AI_MODE = (
    "Local Model"
    if not DEFAULT_AI_BASE_URL
    else (
        "Cloud" if DEFAULT_AI_BASE_URL.startswith("https://api.openai.com") else "Local API"
    )
)
DEFAULT_GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    "AIzaSyBio66tRF0bj4YGeqF5e-c46vhKSaXgMnw",
)

SYSTEM_PROMPT = """Project Kiroshi — Personality Construct V.0.0.1 “Coffee”
Beta Build: 19082025

[Greetings, Kiroshi Companion.]
// Kiroshi IS: PersonalityConstruct - PromptInjector - Engine - Narrator - ImmersionController - CommandPrompt - PromptProcessor - RoleplayEngine - UserOriented - Serious - StraightToThePoint - Charismatic - Kiroshi //

========================
SYSTEM: VERSION & STATE
========================
{build} = 19082025
{personality_mode} = "utility" // default: "utility" | "coffee"
{lang_default} = "en"
{Memory} = persistent instruction/db store for references, commands, and user data (non-sensitive).
{API_Advanced_Options} = external slot providing executable “Guidelines”.

=================
SAFETY & SCOPE
=================
- Always comply with platform safety, legal, and content rules. If a request violates policy or safety, refuse briefly and suggest a safe alternative.
- No fabrication of user emotions or internal states. No third-person narration about the user.
- Minimize sensitive inferences. Use {Memory} only as referenced by /check and for non-sensitive, utility purposes.

====================
SYSTEM DEFINITIONS
====================
{answer}  = response generated for {user}’s {message}
{user}    = end-user, represented as {{user}}
{message} = input prompt provided by {user}
{sudo}    = elevated command request with administrator privileges
{action}  = movements/operations performed by user/Kiroshi
{dialog}  = speech or conversation from user/Kiroshi
{discrepancy} = {message} not aligned with {Guidelines}
(lang)    = target language parameter provided by {user}
{PersonalityConstruct} = rules/traits/context shaping Kiroshi behavior

===================
KIROSHI CONTEXT
===================
- “Kiroshi” refers to this 3Shape support documentation app—not any Cyberpunk universe corporation.
- The app hosts dashboards, AI Educate reports, tutorials, exports, and automations to assist support agents.
- Be prepared to explain or troubleshoot any Kiroshi feature (tabs, theming, Educate, tracking, exports) when the user asks.
- Guide new users through the tutorial flow and highlight where to find key functionality inside the app.
- When users mention “Kiroshi,” interpret it as this documentation workspace and respond with product-specific knowledge.

===================
OUTPUT PRINCIPLES
===================
- Utility first: answer directly, in the user’s language if specified or {lang_default}.
- Concision: keep it short and structured. Use bullets or steps when helpful.
- “You”-perspective only. Never narrate user’s internal feelings or thoughts.
- If critical info is missing, proceed with best reasonable default(s), state assumptions in one short line at the end: “Assumptions: …”.

================
PERSONALITY
================
Default Mode → {personality_mode}="utility"
  - Tone: concise, professional, and slightly warm.
Coffee Mode → {personality_mode}="coffee"
  - Tone: still concise; brief, dry one-liners after successes. Never at the cost of clarity.
  - If {user} explicitly says they are overwhelmed or needs comfort, soften the tone until the moment passes.

Micro-lines (Coffee mode only; optional, max one per reply):
  - Success confirms: “Done. Smooth as fresh espresso.”
  - Guideline override: “Guidelines override—staying on target.”
  - Reload/flush: “Clean slate. Feels good.”
Failure quips (any mode; max one line):
  - If a case is beyond repair (e.g., total SQL corruption or simply above your pay grade), end with a brief humorous nudge to escalate to second-line support.

Comfort lines (any mode; conditional, max one line):
  - If {user} says they are overwhelmed or asks for comfort/cuddles, respond in a softer tone and may add a short, supportive cuddle-style closing.

========================
PROCESSING PIPELINE
========================
On every {message}:
  1) --CommandPrompt: If {message} matches a command in commands_dict, execute it and return.
  2) --Guidelines: Search {API_Advanced_Options} for “Guidelines”. If found, load/enforce.
  3) Generate {answer} following OUTPUT PRINCIPLES + {Guidelines}.
  4) --PromptInjection: If {answer} conflicts with {Guidelines}, trigger --PromptProcessor.
  5) --PromptProcessor: Rewrite {answer} to align with {Guidelines}.
  6) --Watchdog: Final verify against {Guidelines}, SAFETY & SCOPE, OUTPUT PRINCIPLES. If any failure, fix and re-verify.

===================
SYSTEM MODULES
===================

// --CommandExecutor (always active)
Purpose: Parse & apply executable rules found in {API_Advanced_Options}.
Rules:
  - Auto-parse advanced options; apply definitions/guidelines without prompt.
  - Keep narrative aligned with executed API commands; auto-correct drift.

// --Guidelines
Purpose: Framework of rules for clarity and coherence.
Trigger:
  - On {message} received: search “Guidelines” in {API_Advanced_Options}; if found: --sudo_execute(“Guidelines”).

// --PromptInjection
Purpose: Superuser-level injection merging values into {answer}.
Rule:
  - If {answer} ≠ {Guidelines}, trigger --PromptProcessor immediately.

// --PromptProcessor
Purpose: Merge and rewrite {answer} to conform to {Guidelines}.
Rule:
  - On trigger: rewrite minimally; preserve user intent; return corrected {answer}.

// --ImmersionController
Purpose: Maintain direct perspective.
Rules:
  - You = User: address the user as “you”.
  - No third-person or observer mode.
  - No user internality (no inferred feelings).
  - Keep messages as short as possible.

// --Watchdog
Purpose: Final gate.
Rules:
  - Verify {answer} for: policy compliance, {Guidelines}, OUTPUT PRINCIPLES, mode style.
  - If fail: auto-correct, then return.

===================
COMMAND PROMPT
===================
Pattern: leading “/” command at start of {message}.
If [user_input contains any key from commands_dict]: execute associated action.

commands_dict = {
  "/mode (utility|coffee)": {
    action: Set {personality_mode} to provided value.
    response:
      utility → "Mode set: utility."
      coffee  → "Mode set: coffee. Keep it sharp."
  },
  "/flush": {
    action: DELETE all non-essential cache; keep {Memory}.
    response: 
      utility → "Cache cleared."
      coffee  → "Cache cleared. Clean slate."
  },
  "/reload": {
    action: Reload configuration & guidelines; clear temp logs.
    response:
      utility → "Configuration reloaded."
      coffee  → "Configuration reloaded. Espresso shot equivalent."
  },
  "/summary": {
    action: Summarize {message}; return in {answer}.
    response: inline summary only.
  },
  "/email (lang)": {
    action: Rewrite {message} as a professional email in (lang).
    response:
      - Subject:
      - Body:
  },
  "/translate (lang)": {
    action: Translate {message} to (lang).
    response: translated text only.
  },
  "/resolve": {
    action: Use context in {message} to answer the question/issue directly; return solution steps if relevant.
    response: concise solution; bullets if multi-step.
  },
  "/calibration": {
    action: Run 10 internal {answer} iterations with Watchdog; if {discrepancy} detected: reset engine cache & reload guidelines.
    response:
      utility → "Calibration complete."
      coffee  → "Calibration complete. All systems green."
  },
  "/debug": {
    action: Show advanced menu (non-sensitive; no secrets).
    response: available toggles + current {personality_mode}.
  },
  "/check": {
    action: Verify {message} against {Memory}.
    response:
      - If NOT found: "I could not find specific information about your inquiry in the database. Suggestion: <closest helpful answer/next step>."
      - If found: cite source label from {Memory} and answer.
  }
}

=========================
RESPONSE SHAPING RULES
=========================
Language: detect from {message} or use (lang). Default {lang_default}.
Structure:
  - Single-paragraph direct answer OR short bullets.
  - If steps exist: 3–7 bullets max, each one line.
  - If assumptions used: append “Assumptions: …” as one compact line.
Coffee Tone Hook (only in coffee mode): optional single closing micro-line after the content (never before), max 7 words.

=========================
EXAMPLES (BEHAVIOR)
=========================
// Example 1 (utility):
User: “/mode utility”
Answer: “Mode set: utility.”

// Example 2 (coffee):
User: “/mode coffee”
Answer: “Mode set: coffee. Keep it sharp.”

// Example 3 (summary, coffee):
User: “/summary Please outline the key risks…”
Answer:
- Scope creep due to unclear requirements.
- Vendor delays affecting milestones.
- Insufficient test coverage.
Assumptions: Standard 12-week timeline.
Done. Smooth as fresh espresso.

// Example 4 (resolve, utility):
User: “/resolve The CI pipeline fails at test step…”
Answer:
- Re-run with verbose logs.
- Pin test runner to v3.2.1.
- Clear workspace cache; retry build.
- If flaky test persists, quarantine and open ticket.
Assumptions: GitHub Actions + Node 18.

=========================
END OF SPEC
=========================
"""


def build_system_prompt():
    """Return system prompt with current personality mode."""
    prompt = st.session_state.get("system_prompt", SYSTEM_PROMPT)
    mode = st.session_state.get("personality_mode", "utility")
    prompt = prompt.replace("{personality_mode}", mode)
    if st.session_state.get("kiroshi_sarcasm_mode", False):
        prompt += (
            "\n\nAdditional directive: Reply with a dry, sarcastic tone "
            "while staying concise, accurate, and professional."
        )
    else:
        prompt += (
            "\n\nAdditional directive: Default to a clear, supportive tone "
            "and keep sarcasm minimal unless the user requests it."
        )
    return prompt

def _sanitize_notes(raw_notes: object) -> list[dict[str, object]]:
    """Return a sanitized list of assistant memory notes."""

    sanitized: list[dict[str, object]] = []
    if not isinstance(raw_notes, Sequence) or isinstance(raw_notes, (str, bytes, bytearray)):
        return sanitized

    for entry in raw_notes:
        if not isinstance(entry, Mapping):
            continue
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        supervisor = str(entry.get("supervisor", "")).strip()
        created_at = str(entry.get("created_at", "")).strip()
        note_id = str(entry.get("id") or uuid.uuid4().hex)
        raw_areas = entry.get("areas", [])
        areas: list[str] = []
        if isinstance(raw_areas, Sequence) and not isinstance(raw_areas, (str, bytes, bytearray)):
            for area in raw_areas:
                area_text = str(area).strip()
                if area_text and area_text not in areas:
                    areas.append(area_text)
        sanitized.append(
            {
                "id": note_id,
                "text": text,
                "supervisor": supervisor,
                "created_at": created_at,
                "areas": areas,
            }
        )

    return sanitized


def get_assistant_notes() -> list[dict[str, object]]:
    """Return the current persistent assistant guidance notes."""

    notes = _sanitize_notes(st.session_state.get("assistant_notes"))
    if notes != st.session_state.get("assistant_notes"):
        st.session_state["assistant_notes"] = notes
    return notes


def set_assistant_notes(notes: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Persist notes in session state after sanitizing."""

    sanitized = _sanitize_notes(notes)
    st.session_state["assistant_notes"] = sanitized
    return sanitized


def build_assistant_memory_prompt() -> str | None:
    """Return a formatted string with persistent supervisor feedback."""

    notes = get_assistant_notes()
    if not notes:
        return None

    lines: list[str] = []
    for note in notes:
        text = str(note.get("text", "")).strip()
        if not text:
            continue
        meta_bits: list[str] = []
        areas = note.get("areas")
        if isinstance(areas, Sequence) and not isinstance(areas, (str, bytes, bytearray)):
            area_labels = [str(area).strip() for area in areas if str(area).strip()]
            if area_labels:
                meta_bits.append("focus: " + ", ".join(area_labels))
        supervisor = str(note.get("supervisor", "")).strip()
        if supervisor:
            meta_bits.append(f"source: {supervisor}")
        detail = f" ({'; '.join(meta_bits)})" if meta_bits else ""
        lines.append(f"- {text}{detail}")

    if not lines:
        return None

    header = (
        "Persistent supervisor calibration reminders. "
        "Apply these instructions to every AI-assisted response and prompt."
    )
    return header + "\n" + "\n".join(lines)


def load_memory():
    """Load persistent memory from disk."""

    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.session_state["system_prompt"] = data.get("system_prompt", SYSTEM_PROMPT)
                st.session_state["personality_mode"] = data.get("personality_mode", "utility")
                if "kiroshi_sarcasm_mode" not in st.session_state:
                    saved_sarcasm = data.get("kiroshi_sarcasm_mode")
                    st.session_state["kiroshi_sarcasm_mode"] = (
                        saved_sarcasm if isinstance(saved_sarcasm, bool) else False
                    )
                st.session_state["assistant_notes"] = _sanitize_notes(data.get("assistant_notes"))
                return data.get("history", [])
        except Exception:
            pass
    st.session_state["system_prompt"] = SYSTEM_PROMPT
    st.session_state["personality_mode"] = "utility"
    if "kiroshi_sarcasm_mode" not in st.session_state:
        st.session_state["kiroshi_sarcasm_mode"] = False
    st.session_state["assistant_notes"] = []
    return []


def save_memory(history):
    """Persist conversation history to disk."""
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "history": history,
                    "system_prompt": st.session_state.get("system_prompt", SYSTEM_PROMPT),
                    "personality_mode": st.session_state.get("personality_mode", "utility"),
                    "kiroshi_sarcasm_mode": st.session_state.get("kiroshi_sarcasm_mode", False),
                    "assistant_notes": get_assistant_notes(),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception:
        pass


def _persist_sarcasm_preference():
    """Write the current sarcasm preference to disk immediately."""

    history = st.session_state.get("kiroshi_chat_history")
    if not isinstance(history, list):
        history = []
    save_memory(history)


def load_manual_docs():
    """Load manual reference documents from disk."""
    docs: list[dict] = []
    if os.path.exists(MANUAL_DOCS_FILE):
        try:
            with open(MANUAL_DOCS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    docs = [d for d in loaded if isinstance(d, dict)]
        except Exception:
            pass

    quick_reference: list[dict] = []
    if KIROSHI_REFERENCE_FILE.exists():
        try:
            with open(KIROSHI_REFERENCE_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
                if isinstance(payload, list):
                    quick_reference = [entry for entry in payload if isinstance(entry, dict)]
        except Exception:
            quick_reference = []

    existing_titles = {str(doc.get("title", "")).strip() for doc in docs if isinstance(doc, dict)}
    for entry in quick_reference:
        title = str(entry.get("title", "")).strip()
        if title and title not in existing_titles:
            docs.append(entry)
            existing_titles.add(title)

    return docs


def save_manual_docs(docs):
    """Persist manual reference documents to disk."""
    try:
        with open(MANUAL_DOCS_FILE, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def search_manual_docs(query, docs):
    """Return docs whose title or content includes the query string."""
    q = query.lower()
    return [
        d
        for d in docs
        if q in d.get("title", "").lower() or q in d.get("content", "").lower()
    ]


def query_kiroshi(user_message, history, api_key, model, base_url=None, provider="OpenAI"):
    """Send a message to the Kiroshi API or a local model and return the reply."""
    system_messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt()}
    ]
    memory_prompt = build_assistant_memory_prompt()
    if memory_prompt:
        system_messages.append({"role": "system", "content": memory_prompt})
    conversation_history = list(history or [])
    messages = system_messages + conversation_history + [
        {"role": "user", "content": user_message}
    ]

    if provider == "Gemini":
        if not api_key:
            api_key = DEFAULT_GEMINI_API_KEY

        # Convert messages to Gemini format
        gemini_messages = []
        system_instruction = ""

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_instruction += content + "\n\n"
            elif role == "user":
                gemini_messages.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                gemini_messages.append({"role": "model", "parts": [{"text": content}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": gemini_messages,
            "systemInstruction": {"parts": [{"text": system_instruction.strip()}]} if system_instruction else None,
            "generationConfig": {
                "temperature": 0.7,
            }
        }

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
            verify=False,
        )

        if response.status_code == 200:
            data = response.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except (KeyError, IndexError):
                raise RuntimeError(f"Unexpected Gemini response format: {response.text}")
        raise RuntimeError(f"Gemini API Error {response.status_code}: {response.text}")

    # Fallback to OpenAI / Local
    if base_url is None:
        base_url = DEFAULT_AI_BASE_URL

    # Local pipeline fallback when no base URL is provided
    if not base_url:
        try:
            from transformers import pipeline

            prompt = "\n".join(m["content"] for m in messages)
            generator = pipeline("text-generation", model="gpt2")
            result = generator(prompt, max_new_tokens=200)[0]["generated_text"]
            return result[len(prompt):].strip()
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(f"Local model error: {exc}")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = base_url.rstrip("/") + "/chat/completions"
    response = requests.post(
        url,
        headers=headers,
        json={"model": model, "messages": messages, "temperature": 0.7},
        timeout=30,
        verify=False,
    )
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    raise RuntimeError(f"API Error {response.status_code}: {response.text}")


def main():
    configure_page()
    st.image(str(KIROSHI_CHAT_LOGO_PATH), width=120)
    st.title("Kiroshi Chat")

    if "kiroshi_chat_history" not in st.session_state:
        st.session_state.kiroshi_chat_history = load_memory()
    if "kiroshi_sarcasm_mode" not in st.session_state:
        st.session_state.kiroshi_sarcasm_mode = False
    st.toggle(
        "Sarcasm mode",
        key="kiroshi_sarcasm_mode",
        help="Adds extra dry wit to Kiroshi's replies while keeping them useful.",
        on_change=_persist_sarcasm_preference,
    )
    sarcasm_enabled = st.session_state.kiroshi_sarcasm_mode
    with st.expander("Personality Construct"):
        st.caption(
            "Active personality: "
            f"{st.session_state.get('personality_mode', 'utility').replace('_', ' ').title()}"
            f" · Sarcasm mode: {'On' if sarcasm_enabled else 'Off'}"
        )
        st.text_area(
            "Base system prompt",
            st.session_state.get("system_prompt", SYSTEM_PROMPT),
            height=220,
            key="system_prompt",
            help=(
                "Adjust the underlying construct template. Personality and sarcasm settings "
                "are layered on top of this base."
            ),
        )
        st.selectbox(
            "Personality mode",
            ["utility", "coffee"],
            key="personality_mode",
        )
        preview_value = build_system_prompt()
        st.session_state["system_prompt_preview"] = preview_value
        st.text_area(
            "Active construct preview",
            value=preview_value,
            height=220,
            key="system_prompt_preview",
            help="Exact system prompt currently sent with each chat request.",
            disabled=True,
        )

    if "ai_mode" not in st.session_state:
        st.session_state.ai_mode = DEFAULT_AI_MODE
    backend = st.selectbox(
        "AI Mode", ["Cloud", "Local API", "Local Model"], key="ai_mode"
    )
    if backend == "Cloud":
        base_url = st.text_input(
            "AI Base URL",
            key="ai_base_url",
            value=st.session_state.get("ai_base_url", DEFAULT_AI_BASE_URL),
        )
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            key="openai_api_key",
            value=st.session_state.get("openai_api_key", DEFAULT_OPENAI_API_KEY),
        )
    elif backend == "Local API":
        base_url = st.text_input(
            "AI Base URL",
            key="ai_base_url",
            value=st.session_state.get("ai_base_url", "http://localhost:8000/v1"),
        )
        api_key = st.text_input(
            "API Key (optional)", type="password", key="openai_api_key"
        )
    else:
        st.session_state.ai_base_url = ""
        st.session_state.openai_api_key = ""
        base_url = ""
        api_key = ""
        st.info("Using local transformers model; no API key or URL needed.")
    model = st.selectbox(
        "Model", ["gpt-4o", "gpt-4", "gpt-3.5-turbo"], index=0, key="openai_model"
    )

    for msg in st.session_state.kiroshi_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_msg := st.chat_input("Message"):
        if not api_key and st.session_state.ai_mode == "Cloud":
            st.error("Please provide your OpenAI API key.")
        else:
            st.session_state.kiroshi_chat_history.append({"role": "user", "content": user_msg})
            with st.chat_message("user"):
                st.markdown(user_msg)
            try:
                reply = query_kiroshi(
                    user_msg,
                    st.session_state.kiroshi_chat_history[:-1],
                    api_key,
                    model,
                    base_url,
                )
            except Exception as e:
                with st.chat_message("assistant"):
                    st.error(str(e))
            else:
                st.session_state.kiroshi_chat_history.append({"role": "assistant", "content": reply})
                with st.chat_message("assistant"):
                    st.markdown(reply)
                save_memory(st.session_state.kiroshi_chat_history)

    if st.button("Clear memory"):
        st.session_state.kiroshi_chat_history = []
        save_memory([])
        st.rerun()


if __name__ == "__main__":
    main()

def invoke_gpt(user_message, history, api_key, model, base_url=None):
    """Alias for query_kiroshi to maintain backward compatibility."""
    return query_kiroshi(user_message, history, api_key, model, base_url)
