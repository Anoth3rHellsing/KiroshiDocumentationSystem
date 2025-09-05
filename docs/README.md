# Kiroshi Documentation

This document explains the structure of the application and describes the
functionality provided by each tab.

## Data Model

Case information is stored in a `CaseData` dataclass. Each field belongs to a
logical category (header, description, phone call, internal notes, remote
session, conclusion, PC hardware, and scanner hardware). The UI tracks progress
by computing how many fields in each category are filled in.

## Tabs

### Case
Collects all general information about the support case. A progress bar shows
completion for each category, and the data can be exported as a PDF with
wrapped table text.

### Email
Generates prompts for several e‑mail templates:

- Recap for the customer
- Broken scanner questionnaire
- Broken tip questionnaire
- Callback email
- Custom request email

The generated prompt can be copied or sent directly to the ChatGPT API to produce the full e‑mail. All templates automatically begin with the customer's name, company, case number, and a short description of the issue for consistent recaps.

### Hardware Issues
Stores PC and scanner hardware details and displays them in copy‑friendly tables.

### Notes
A simple scratchpad for temporary information.

### Debug
Stores the OpenAI API key and model selection and displays the current session
state for troubleshooting. A nonfunctional placeholder key is preloaded for
demonstration purposes, and GPT-4o is selected by default for quick, high-quality
responses.

## Autosave
Case information and scratchpad notes are written to an `autosave.json` file
after every interaction, so progress is preserved even if the browser is
closed.

## Exports & Attachments

Users can upload log files or screenshots. Clicking **Create ZIP** bundles all
uploaded files along with a `case.json` file that contains the case data.

## Running the App

From the repository root:

```bash
streamlit run case_documentation_app.py
```

Ensure that the dependencies listed in `requirements.txt` are installed.

## Local model configuration

Kiroshi can talk to any OpenAI-compatible text generation server. Set the
`AI_BASE_URL` environment variable or update the "AI Base URL" field in the
Debug tab to point to your endpoint. When using a self-hosted server, the
`OPENAI_API_KEY` may be left blank.

To run against a local model server exposing an OpenAI-style API:

```bash
export AI_BASE_URL=http://localhost:8000/v1
export OPENAI_API_KEY=""  # no key required for local servers
streamlit run case_documentation_app.py
```

If `AI_BASE_URL` is unset, Kiroshi falls back to a lightweight
`transformers` pipeline (requires the `transformers` package and a local
model) to generate responses directly in Python.
