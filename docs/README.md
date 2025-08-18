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
- Internal note for AX coordinators
- Broken scanner questionnaire
- Broken tip questionnaire
- Escalation to second‑line support

The generated prompt can be copied or sent directly to the API tab.

### Hardware Issues
Stores PC and scanner hardware details and displays them in copy‑friendly tables.

### Notes
A simple scratchpad for temporary information.

### API
Allows the prompt from the Email tab to be sent to the OpenAI ChatGPT API. The
response is displayed directly in the UI.

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
