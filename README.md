# Kiroshi Documentation System

Kiroshi is a Streamlit application for documenting IT support cases. It provides
interactive forms for collecting case details, generating PDF summaries, and
creating email prompts or full e‑mails via the OpenAI ChatGPT API.

## Features

- **Case tab** – capture customer information, notes, and track completion
  progress.
- **Email tab** – generate prompts for different e‑mail templates such as
  customer recaps or escalation notes.
- **Hardware tab** – record PC and scanner hardware details.
- **Notes tab** – scratchpad for temporary notes.
- **PDF export** – download a formatted summary of the case.
- **Attachments** – upload screenshots or logs and export everything as a ZIP
  bundle.
- **ChatGPT API integration** – send prompts directly to OpenAI and display the
  generated response.

## Requirements

Install the dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the Streamlit app from the repository root:

```bash
streamlit run case_documentation_app.py
```

A browser window will open with tabs for entering case information. The "Download
PDF" button exports a formatted summary, and the attachment section lets you
bundle supporting files.

For API usage, supply an OpenAI API key in the *API* tab before generating an
email.


## Build executable

To create a standalone executable, first install the dependencies and run the build script:

```bash
pip install -r requirements.txt
./build.sh
```

The resulting binary will be placed in the `dist/` directory.

## Documentation

See the [`docs/`](docs/README.md) directory for a more detailed explanation of
how data is structured and how each tab operates.

## License

This project is licensed under the terms of the MIT License. See
[LICENSE](LICENSE) for details.
