# Kiroshi Documentation System

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](#)
[![Version](https://img.shields.io/badge/version-1.5.2%20Beta%20Build%20932025-blue)](#)
[![Coverage](https://img.shields.io/badge/coverage-active-brightgreen)](#)
[![Updates](https://img.shields.io/badge/updates-daily-blue)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Kiroshi is a Streamlit application for documenting IT support cases. It provides interactive forms for collecting case details,
generating PDF summaries, and creating email prompts or full emails via the OpenAI ChatGPT API.

Coverage is actively tracked and the project receives daily updates.

## Demo

![Kiroshi UI Demo](docs/demo.png)
*Replace `docs/demo.png` with an actual screenshot or GIF demonstrating the interface.*

## Features

- **Case tab** – capture customer information, notes, and track completion progress.
- **2nd Line Mode Dashboard** – when 2nd Line mode is enabled, monitor active Dell and FedEx tracked cases, browse recent tracked files, and load or untrack any case directly from the tracking tables.
- **Email tab** – generate prompts for different e‑mail templates such as customer recaps, escalation notes, or a flexible custom request. Every template automatically opens with the customer's name, company, case number, and a brief issue summary.
- **Optional hardware tab** – enable with the "Include hardware issue fields" checkbox when a case involves hardware.
- **Notes tab** – scratchpad for temporary notes.
- **Tables tab** – displays each category in an Excel‑style table with a title indicating Phonecall or Int plus the current date,
  making it easy to copy into spreadsheets.
- **PDF export** – download a formatted summary of the case with wrapped table text so long values stay within the page.
- **Attachments** – upload screenshots or videos and export everything as a ZIP bundle, with logs placed in a separate `logs/`
  folder.
- **Screenshot capture** – take screenshots directly from the app, name them for context, and include them in the exported ZIP
  under a dedicated `Screenshots/` folder.
- **Real-time autosave** – case data and notes are persisted to `autosave.json` on every interaction to prevent data loss.
- **Save/Load tab** – persist cases to `C:\\ProgramFiles\\KiroshiDatabase` using the case ID, browse recent cases, and reload them directly from the app.
- **Case tracking** – enable tracking from the Case tab and store Dell or FedEx status updates in `TrackedCases` for dashboard monitoring; cases may be untracked or closed when finished.
- **ChatGPT API integration** – send prompts directly to OpenAI and display the generated response.
- **A.A.T.O.M. tools** – "Verify" reviews case data for missing details; a separate chat interface offers persistent memory,
  gentle reassurance when you're overwhelmed, and humorous escalation quips.
- **Debug tab** – internal diagnostics with a log viewer (last 100 lines) protected by an `admin`/`admin` login.
- **Corporate theme** – default light mode with 3Shape Red accents; switch to dark mode from the Streamlit settings for extended
  sessions.

## Installation

### Automated installation

1. Download the repository ZIP from GitHub.
2. Extract the archive and run **Kiroshi Installer** (`KiroshiInstaller_1-5-2.bat`).
3. Launch the app with **Kiroshi Launcher** (`KiroshiLauncher_1-5-2.bat`).
4. To uninstall, run **Kiroshi Uninstaller** (`KiroshiUninstaller.bat`).

### Manual installation

Install the dependencies from the project directory. If you just cloned or downloaded the repository, first change into its folder
with `cd` and then run `pip`:

```bash
cd /path/to/KiroshiDocumentationSystem
pip install -r requirements.txt
```

### Windows PATH helper

If the `streamlit` command is not recognized in a Windows terminal, the Python `Scripts` directory may be missing from your user
`PATH`. The following PowerShell snippet adds it automatically:

```powershell
# Detect the Scripts folder for the current Python
$scriptsPath = (python -m site --user-site) -replace "site-packages", "Scripts"

if (Test-Path $scriptsPath) {
    Write-Host "Detected Scripts path: $scriptsPath"
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$scriptsPath*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$scriptsPath", "User")
        Write-Host "Scripts path added to user PATH."
    } else {
        Write-Host "Scripts path already in user PATH."
    }
} else {
    Write-Host "Scripts folder not found. Is Python installed?"
}
```

After running the script, close and reopen the terminal, then verify with:

```powershell
streamlit --version
```

## Usage

If you used the automated installer, start Kiroshi with the provided **Kiroshi Launcher** (`KiroshiLauncher_1-5-2.bat`).

For manual runs from source, execute the Streamlit app from the repository root. If you are not already in the project folder,
navigate there first with `cd`:

```bash
cd /path/to/KiroshiDocumentationSystem
streamlit run case_documentation_app.py
```

Alternatively, use the provided wrapper script:

```bash
python run_app.py
```

This helper sets up the correct Streamlit arguments and is the entry point used when packaging the project into an executable.

A browser window will open with tabs for entering case information. The "Download PDF" button exports a formatted summary, and the
attachment section lets you bundle supporting files. Use the checkbox at the top to toggle hardware tabs and fields. The *Tables*
tab provides a full markdown dump of all case data for easy copying. An internal *Debug* tab is available after logging in with
username and password `admin`.

Within the *Case* tab, the integrated A.A.T.O.M. assistant offers a **Verify** button to highlight missing documentation.

To experiment with the A.A.T.O.M. chatbox, run the dedicated script:

```bash
cd /path/to/KiroshiDocumentationSystem
streamlit run aatom_chat.py
```

The chat history is saved to `atom_memory.json` so conversations persist across sessions.

For API usage, a placeholder OpenAI API key is prefilled in the *Debug* tab for demonstration, and GPT-4o is selected by default
for fast, high-quality responses. Replace the key or model with your own settings before generating an email.

### Configuration

Copy the example configuration to a new `config.json` file and edit it to match your environment. The application reads options
such as your OpenAI API key from this file.

```bash
cp config.example.json config.json
# then open config.json and update the values
```

The backend endpoint is configurable via the `AI_BASE_URL` environment variable
or the "AI Base URL" field in the Debug tab. By default it targets OpenAI's
service, but you can point it at any OpenAI-compatible server. When using a
local server, the `OPENAI_API_KEY` may be left blank.

```bash
export AI_BASE_URL=http://localhost:8000/v1
export OPENAI_API_KEY=""
streamlit run case_documentation_app.py
```

If `AI_BASE_URL` is unset, Kiroshi falls back to a minimal `transformers`
pipeline (requires the `transformers` package and an available model) to
generate text without making HTTP requests.

### Corporate SSL interception

Some enterprise networks intercept HTTPS traffic with a self-signed certificate, which breaks standard SSL verification. The
application disables certificate checks for requests to the OpenAI ChatGPT API so it can be used behind such company proxies. Be
aware that this weakens transport security and should only be enabled in trusted environments.

## Build executable

To create a standalone executable, make sure you're in the project directory, install the dependencies, and run the build script:

```bash
cd /path/to/KiroshiDocumentationSystem
pip install -r requirements.txt
./build.sh
```

The resulting binary will be placed in the `dist/` directory. The script bundles the `run_app.py` entry point so the executable
launches the Streamlit interface directly.

## Documentation

See the [`docs/`](docs/README.md) directory for a more detailed explanation of how data is structured and how each tab operates.

## Contributing

Contributions are welcome! To propose a change:

1. Fork the repository and create your feature branch.
2. Commit your changes and open a pull request.
3. For bugs or feature requests, please open an issue describing the problem or proposal.

For questions, reach out by filing an issue or contacting the maintainers directly.

## License

This project is licensed under the terms of the MIT License. See [LICENSE](LICENSE) for details.

## Useful Links

- [Documentation](docs/README.md)
- [Issue Tracker](https://github.com/your-org/KiroshiDocumentationSystem/issues)
- [Streamlit](https://streamlit.io)

