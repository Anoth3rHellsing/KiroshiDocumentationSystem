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
- FedEx tracking email for refurbished devices (second-line mode)
- Replacement wired scanner setup email (second-line mode)
- Replacement Move+ closure email (second-line mode)
- Callback email
- Refurbished scanner/Move+ shipping email (FedEx tracking)
- Custom request email
- Dell escalation email for second-line support (confirm contact details with the customer)

See `dell_escalation_email.md` and `refurbished_scanner_fedex_email.md` for the full templates and required information.

The generated prompt can be copied or sent directly to GPT-OSS to produce the full e‑mail (feature not yet implemented). All templates automatically begin with the customer's name, company, case number, and a short description of the issue for consistent recaps.
The opening lines match the standard EC format:

```
Dear {customer_name} from {company_name},

I hope this email finds you well. I wanted to recap your recent call to our customer service center regarding the case you had about {brief_description}.
This was registered under the ticket {case_id}.
```

### Hardware Issues
Stores PC and scanner hardware details and displays them in copy‑friendly tables.

### Debug
Stores the OpenAI API key and model selection and displays the current session
state for troubleshooting. A nonfunctional placeholder key is preloaded for
demonstration purposes, and GPT-4o is selected by default for quick, high-quality
responses.

## Autosave
Case information is written to an `autosave.json` file after every interaction,
so progress is preserved even if the browser is closed.

## Exports & Attachments

Users can upload log files or screenshots. Clicking **Create ZIP** bundles all
uploaded files along with a `case.json` file that contains the case data.

## Running the App

From the repository root:

```bash
streamlit run case_documentation_app.py
```

Ensure that the dependencies listed in `requirements.txt` are installed.

For optional mini-games or running the local transformers model, install the
extra packages from `requirements-bored.txt`.

## Local model configuration

Kiroshi can talk to any OpenAI-compatible text generation server. Set the
`AI_BASE_URL` environment variable or, in the Debug tab, choose **Cloud** for
OpenAI, **Local API** for a self-hosted server, or **Local Model** to run a
lightweight model directly. When using a self-hosted server, the
`OPENAI_API_KEY` may be left blank.

To run against a local model server exposing an OpenAI-style API:

```bash
export AI_BASE_URL=http://localhost:8000/v1
export OPENAI_API_KEY=""  # no key required for local servers
streamlit run case_documentation_app.py
```

If `AI_BASE_URL` is unset (the "Local Model" option), Kiroshi falls back to a
lightweight `transformers` pipeline (install the `transformers` and `torch`
packages from `requirements-bored.txt` and supply a local model) to generate
responses directly in Python.
