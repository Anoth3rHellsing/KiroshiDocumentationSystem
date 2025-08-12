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

Run the Streamlit app from the repository root:

```bash
streamlit run case_documentation_app.py
```

A browser window will open with tabs for entering case information. The "Download
PDF" button exports a formatted summary, and the attachment section lets you
bundle supporting files.

For API usage, supply an OpenAI API key in the *API* tab before generating an
email.


### Corporate SSL interception

Some enterprise networks intercept HTTPS traffic with a self-signed
certificate, which breaks standard SSL verification. The application now
disables certificate checks for requests to the OpenAI ChatGPT API so it can be
used behind such company proxies. Be aware that this weakens transport security
and should only be enabled in trusted environments.

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
