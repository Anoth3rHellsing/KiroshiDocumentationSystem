# Kiroshi Documentation System

Kiroshi is a Streamlit application for documenting IT support cases. It provides
interactive forms for collecting case details, generating PDF summaries, and
creating email prompts or full e‑mails via the OpenAI ChatGPT API.

## Features

- **Case tab** – capture customer information, notes, and track completion
  progress.
- **Email tab** – generate prompts for different e‑mail templates such as
  customer recaps or escalation notes.
- **Optional hardware tab** – enable with the "Include hardware issue fields" checkbox when a case involves hardware.
- **Notes tab** – scratchpad for temporary notes.
- **Tables tab** – displays each category in an Excel‑style table with a title
  indicating Phonecall or Int plus the current date, making it easy to copy
  into spreadsheets.
- **Timers tab** – run multiple countdown timers (Break, Lunch, Hold, ACW or
  custom) with sound and browser notifications and overdue tracking.
- **Alarms tab** – schedule daily break and lunch reminders, including an
  alert 15 minutes before lunch.
- **PDF export** – download a formatted summary of the case with wrapped table
  text so long values stay within the page.
- **Attachments** – upload screenshots or logs and export everything as a ZIP
  bundle.
- **Real-time autosave** – case data and notes are persisted to `autosave.json`
  on every interaction to prevent data loss.
- **ChatGPT API integration** – send prompts directly to OpenAI and display the
  generated response.
- **A.A.T.O.M. tools** – "Verify" reviews case data for missing details and
  "AI Assistance" auto-fills descriptions; a separate chat interface is also
  available with persistent memory.
- **Debug tab** – internal diagnostics protected by an `admin`/`admin` login.

## Requirements

Install the dependencies from the project directory. If you just cloned or
downloaded the repository, first change into its folder with `cd` and then run
`pip`:

```bash
cd /path/to/KiroshiDocumentationSystem
pip install -r requirements.txt
```

### Windows PATH helper

If the `streamlit` command is not recognized in a Windows terminal, the Python
`Scripts` directory may be missing from your user `PATH`. The following
PowerShell snippet adds it automatically:

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

Run the Streamlit app from the repository root. If you are not already in the
project folder, navigate there first with `cd`:

```bash
cd /path/to/KiroshiDocumentationSystem
streamlit run case_documentation_app.py
```

A browser window will open with tabs for entering case information. The "Download
PDF" button exports a formatted summary, and the attachment section lets you
bundle supporting files. Use the checkbox at the top to toggle hardware tabs and
fields. The *Tables* tab provides a full markdown dump of all case data for easy
copying. An internal *Debug* tab is available after logging in with username and
password `admin`.

Within the *Case* tab, the integrated A.A.T.O.M. assistant offers a **Verify**
button to highlight missing documentation and an **AI Assistance** button that
auto-fills the brief and detailed descriptions based on existing data.

To experiment with the A.A.T.O.M. chatbox, run the dedicated script:

```bash
cd /path/to/KiroshiDocumentationSystem
streamlit run aatom_chat.py
```

The chat history is saved to `atom_memory.json` so conversations persist across
sessions.

For API usage, a placeholder OpenAI API key is prefilled in the *Debug* tab for
demonstration, and GPT-4o is selected by default for fast, high-quality
responses. Replace the key or model with your own settings before generating an
email.


### Corporate SSL interception

Some enterprise networks intercept HTTPS traffic with a self-signed
certificate, which breaks standard SSL verification. The application now
disables certificate checks for requests to the OpenAI ChatGPT API so it can be
used behind such company proxies. Be aware that this weakens transport security
and should only be enabled in trusted environments.


## Build executable

To create a standalone executable, make sure you're in the project directory,
install the dependencies, and run the build script:

```bash
cd /path/to/KiroshiDocumentationSystem
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
