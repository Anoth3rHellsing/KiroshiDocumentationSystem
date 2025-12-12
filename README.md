# Kiroshi Documentation System

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](#)
[![Version](https://img.shields.io/badge/version-RC%20141025-blue)](#)
[![Coverage](https://img.shields.io/badge/coverage-active-brightgreen)](#)
[![Updates](https://img.shields.io/badge/updates-daily-blue)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Kiroshi is a Streamlit application for documenting IT support cases. It provides interactive forms for collecting case details,
generating PDF summaries, and creating email prompts or full emails via GPT-OSS (future integration).

Coverage is actively tracked and the project receives daily updates.

## Demo

![Kiroshi UI Demo](docs/demo.png)
*Replace `docs/demo.png` with an actual screenshot or GIF demonstrating the interface.*

## Features

- **Case tab** – capture customer information, notes, and track completion progress.
- **2nd Line Mode Dashboard** – when 2nd Line mode is enabled, monitor active Dell and FedEx tracked cases, browse recent tracked files, and load or untrack any case directly from the tracking tables.
- **Email tab** – generate prompts for different e‑mail templates such as customer recaps, escalation notes, or a flexible custom request. Every template automatically opens with the customer's name, company, case number, and a brief issue summary.
- **Optional hardware tab** – enable with the "Include hardware issue fields" checkbox when a case involves hardware.
- **Tables tab** – displays each category in an Excel‑style table with a title indicating Phonecall or Int plus the current date,
  making it easy to copy into spreadsheets. A global listener also watches for **Ctrl+Alt+1…8** to copy the Build Title,
  Description, Phonecall, Internal Notes, Remote Session, Additional Information, Root Cause & Conclusion tables, or the
  ChatGPT prompt (Email tab) individually (use **Ctrl+Alt+C** if you still need the full bundle) without switching back to the
  Streamlit window. Pick which case feeds those shortcuts via the “Use this case for global clipboard hotkeys” toggle at the top
  of the Tables tab.
- **PDF export** – download a formatted summary of the case with wrapped table text so long values stay within the page.
- **Attachments** – upload screenshots or videos and export everything as a ZIP bundle, with logs placed in a separate `logs/`
  folder.
- **Screenshot capture** – take screenshots directly from the app, name them for context, and include them in the exported ZIP
  under a dedicated `Screenshots/` folder.
- **Real-time autosave** – case data is persisted to `autosave.json` on every interaction to prevent data loss.
- **Save/Load tab** – persist cases to `C:\\ProgramFiles\\KiroshiDatabase` using the case ID, browse recent cases, and reload them directly from the app.
- **Case Dex download** – fetch a Case Dex package for a given case ID and save it as a ZIP file.
- **Case tracking** – enable tracking from the Case tab and store Dell or FedEx status updates in `TrackedCases` for dashboard monitoring; cases may be untracked or closed when finished.
- **Kiroshi Cloud console** – register remote devices, enforce per-tenant credentials, and synchronise the AI Educate knowledge base across Windows and Windows Server workstations through an encrypted management plane.
- **GPT-OSS integration (coming soon)** – send prompts directly to GPT-OSS and display the generated response.
- **Local (Native) AI** – run AI models locally on your device without external dependencies. Kiroshi manages the download and execution of models like Phi-3 (Speed) or Llama 3 (Quality) using your hardware (GPU supported).
- **Kiroshi chat tools** – "Verify" reviews case data for missing details; a separate chat interface offers persistent memory,
  gentle reassurance when you're overwhelmed, and humorous escalation quips. Toggle Sarcasm Mode in Settings when you want the
  assistant to lean into extra wit.
- **Debug tab** – internal diagnostics with a log viewer (last 100 lines) protected by an `admin`/`admin` login.
- **Corporate theme** – default light mode with 3Shape Red accents; switch to dark mode from the Streamlit settings for extended
  sessions.

## Kiroshi Cloud console

The repository now ships with **KiroshiCloud**, a companion Streamlit client that
acts as the management plane for remote Kiroshi workstations. The console keeps a
live, encrypted registry of every authorised device, lets you approve or block
connections in real time, and synchronises the AI Educate knowledge base across
sites without opening ports on edge firewalls.

### Quick start

1. Install the Python requirements as described below (the list now includes
   `cryptography` for the encryption layer).
2. Launch the console with your preferred runner:

   ```bash
   # Browser mode
   streamlit run kiroshi_cloud_client.py

   # Desktop mode
   streamlit-desktop-app run kiroshi_cloud_client.py
   ```

3. Sign in with the default credentials **admin / admin123!**. The first screen
   will warn you that the defaults are active—change them immediately from the
   *Security* tab so the database gains a unique password.
4. Register each Windows or Windows Server host in the *Connections* tab. You
   only need a friendly name, the overlay IP address, and optional notes such as
   the physical site or rack number.

### Overlay network and remote connectivity

Kiroshi Cloud is designed to work through modern mesh VPNs (Tailscale, ZeroTier,
WireGuard hubs, etc.). These tools create outbound peer-to-peer tunnels so you do
not need to configure port forwarding on customer routers.

1. Install the overlay agent on the cloud host and every workstation that runs
   the classic Kiroshi desktop app.
2. Sign in with the same organisation account (or join the same network ID) so
   all machines appear in the shared overlay.
3. Copy the private IP assigned by the overlay (for example 100.x.y.z on
   Tailscale) and use it as the *Device IP* when adding a workstation inside the
   console.
4. After the agent connects, use the **Mark online** button or `ping <overlay-ip>`
   from the cloud host to confirm that the tunnel is reachable.

The **Setup Guide** tab in the Kiroshi Cloud console lets you tailor these
instructions and the recommended overlay provider for your organisation. Any
changes are written back to the encrypted configuration and surface inside the
desktop client so technicians always see the current playbook before linking a
new workstation.

Each device entry exposes a **Generate connection token** action. The token
encodes the device ID and its shared secret. Download or copy the token and paste
it into the desktop app (see below) to pair the workstation with the cloud roster.

### Synchronising with the desktop app

1. Open **Settings → AI & Knowledge** inside Kiroshi.
2. Enable the **Kiroshi Cloud** toggle, enter the updated username and password,
   and paste the connection token generated for that workstation.
3. Click **Validar conexión** to verify the credentials. The app reports the cloud
   status, device count, and last saved timestamp.
4. Use **Subir Educate al cloud** to push the current AI Educate dataset, or
   **Descargar Educate del cloud** to pull the shared snapshot into the desktop
   installation.

The desktop and cloud clients now share the same analytics pipeline, letting
team leads audit recurring causes or high-risk devices from either interface.

### Encryption at rest

All cloud artefacts live under `C:/ProgramFiles/KiroshiCloud` on Windows (or
`~/KiroshiCloud` on other platforms). The console generates a random salt and
derives a Fernet key from your password using PBKDF2, so both the device roster
and the AI Educate dataset remain encrypted at rest. Updating the credentials
from the console transparently re-encrypts the payloads with the new key.

### Troubleshooting for new administrators

* **Forgot to change the defaults:** Sign back in with `admin / admin123!`, open
  the *Security* tab, and rotate the username/password pair. Every workstation
  must then update its credentials in Settings.
* **Overlay agent offline:** Verify the device is authorised in the overlay’s
  admin portal and allow the service through Windows Defender Firewall.
* **Token rejected in Kiroshi:** Regenerate the token in the console to ensure
  you are using the latest shared secret, then paste it again in the desktop app.
* **Dataset out of sync:** From either side, refresh the dataset from the cloud
  and trigger a download so every workstation consumes the same encrypted
  snapshot.

## Installation

### Automated installation

1. Download the repository ZIP from GitHub.
2. Extract the archive and run **Kiroshi Installer** (`KiroshiInstaller_RC-141025.bat`).
3. Launch the app with **Kiroshi Launcher** (`KiroshiLauncher_RC-141025.bat`),
   which now boots the bundled Streamlit Desktop App build.
4. To uninstall, run **Kiroshi Uninstaller** (`KiroshiUninstaller.bat`).

### Manual installation

Install the dependencies from the project directory. If you just cloned or downloaded the repository, first change into its folder
with `cd` and then run `pip`:

```bash
cd /path/to/KiroshiDocumentationSystem
pip install -r requirements.txt
# Optional: install mini-game and local model dependencies
pip install -r requirements-bored.txt
```

### Instalador bash (Linux/macOS)

El repositorio ahora incluye un script de instalación para entornos Unix (`install_kiroshi.sh`). El script borra los archivos previos en la carpeta de destino, copia la versión nueva y, si encuentra un `requirements.txt`, instala automáticamente las dependencias de Python.

```bash
#!/bin/bash

# Variables: ajusta los paths según tus necesidades
INSTALLDIR="/opt/kiroshi_documentation"         # Carpeta de destino final
SRCDIR="$HOME/kiroshi_nueva_version"            # Carpeta con los archivos nuevos
REQFILE="$SRCDIR/requirements.txt"              # Archivo de requisitos pip

echo "--------- Instalador Kiroshi (bash) ---------"

# Borra todo el contenido existente en la carpeta de destino
if [ -d "$INSTALLDIR" ]; then
    echo "Borrando archivos previos en $INSTALLDIR..."
    rm -rf "$INSTALLDIR"/*
else
    mkdir -p "$INSTALLDIR"
fi

# Copia los archivos nuevos
echo "Copiando archivos nuevos desde $SRCDIR..."
cp -r "$SRCDIR"/* "$INSTALLDIR"

# Instala los requisitos de Python
if [ -f "$REQFILE" ]; then
    echo "Instalando dependencias desde $REQFILE..."
    python3 -m pip install -r "$REQFILE"
    echo "Dependencias instaladas correctamente."
else
    echo "No se encontró requirements.txt en $SRCDIR, saltando instalación de dependencias."
fi

echo "Instalación terminada. Kiroshi listo para usar."
```

Cómo usarlo:

1. Copia el script en un archivo (`install_kiroshi.sh`).
2. Edita las variables para que los paths sean correctos en tu entorno.
3. Concede permisos de ejecución: `chmod +x install_kiroshi.sh`.
4. Ejecuta el script: `./install_kiroshi.sh`.

### Instalador batch (Windows)

También se incluye un instalador para Windows (`install_kiroshi.bat`). El script limpia la carpeta de destino, copia los archivos nuevos y, si encuentra un `requirements.txt`, instala las dependencias usando `pip`.

```bat
@echo off
REM ---- Variables: Cambia los paths según tu entorno ----
set INSTALLDIR=C:\ProgramFiles\KiroshiDocumentation
set SRCDIR=%USERPROFILE%\kiroshi_nueva_version
set REQFILE=%SRCDIR%\requirements.txt

echo --------- Instalador Kiroshi (Windows .bat) ---------

REM Borra contenido previo (archivos y carpetas)
if exist "%INSTALLDIR%" (
    echo Borrando archivos previos en "%INSTALLDIR%"...
    del /Q "%INSTALLDIR%\*" 2>nul
    for /d %%i in ("%INSTALLDIR%\*") do rd /s /q "%%i"
) else (
    mkdir "%INSTALLDIR%"
)

REM Copia archivos y carpetas nuevos
echo Copiando archivos nuevos desde "%SRCDIR%"...
xcopy "%SRCDIR%\*" "%INSTALLDIR%\" /E /H /C /Y

REM Instala requisitos de Python
if exist "%REQFILE%" (
    echo Instalando dependencias desde requirements.txt...
    python -m pip install -r "%REQFILE%"
    echo Dependencias instaladas correctamente.
) else (
    echo No se encontró requirements.txt en "%SRCDIR%", saltando instalación de dependencias.
)

echo Instalación terminada. Kiroshi listo para usar.
pause
```

Cómo usarlo:

1. Copia el script en un archivo (`install_kiroshi.bat`).
2. Edita las variables para que las rutas sean correctas en tu entorno.
3. Ejecuta el archivo con doble clic o desde la consola (`install_kiroshi.bat`).


### Streamlit Desktop App runner

Kiroshi now bundles first-class support for the
[Streamlit Desktop App](https://github.com/streamlit/streamlit-desktop).
After installing the project requirements, install the desktop runner and
initialise it once so the helper files are created:

```bash
pip install streamlit-desktop-app
python -m streamlit_desktop_app
```

Launch the desktop experience from the repository root with the standard
Streamlit runner (the desktop helper only exposes a `build` command at the
moment):

```bash
streamlit run case_documentation_app.py
# or
python run_app.py
```

To distribute a self-contained desktop bundle, use the new build command. The
example below generates an executable with the Kiroshi logo and a custom
window title:

```bash
streamlit-desktop-app build case_documentation_app.py \
  --icon Kiroshi_Logo.png \
  --title "Kiroshi Desktop"
```

Use the `--debug` or `--headless` switches to mirror any advanced `streamlit`
arguments you previously passed through `run_app.py` or `streamlit run`.

#### Clipboard integration prerequisites

The clipboard helpers use [`pyperclip`](https://pypi.org/project/pyperclip/) so
that case notes and incident IDs can be moved between Kiroshi and other tools
with a single shortcut. On Windows the bundled backend generally works out of
the box, but environments with hardened clipboard policies might need the
[`pywin32`](https://pypi.org/project/pywin32/) package to expose the Win32 API.
Linux desktops require the `xclip` or `xsel` command-line utilities; most
distributions provide them through the package manager (for example,
`sudo apt install xclip`). Document these prerequisites for field deployments so
support teams can install the correct bridge ahead of time.

#### Global table copy hotkeys

Kiroshi runs a background listener that starts as soon as a case is loaded.
Every time the case state changes, the UI thread calls
`update_hotkey_snapshot(...)` to deep copy the active `CaseSession` and category
map into an isolated container. While the listener is running you can trigger
the following shortcuts from any window:

| Shortcut         | Clipboard payload                         |
| ---------------- | ------------------------------------------ |
| **Ctrl+Alt+1**   | Build Title (HEADER table)                 |
| **Ctrl+Alt+2**   | Description table                          |
| **Ctrl+Alt+3**   | Phonecall table                            |
| **Ctrl+Alt+4**   | Internal Notes table                       |
| **Ctrl+Alt+5**   | Remote Session table                       |
| **Ctrl+Alt+6**   | Additional Information table               |
| **Ctrl+Alt+7**   | Root Cause & Conclusion table              |
| **Ctrl+Alt+8**   | ChatGPT prompt (Email tab)                 |
| **Ctrl+Alt+C**   | Full bundle (all tables, unchanged)        |

Each shortcut converts the stored snapshot into the same plain-text output that
the Tables tab renders and sends it to the operating system clipboard with
`pyperclip.copy`. Because the listener works outside the Streamlit event loop,
the shortcuts can be pressed while another window (for example, a CRM) has
focus. Paste with the standard **Ctrl+V** to drop the selected table into the
target field.

Pick the case that powers these clipboard actions by enabling **Use this case
for global clipboard hotkeys** in the relevant Tables tab. The active choice is
stored in `st.session_state` so reruns keep the listener pointed at the same
case until you toggle a different tab or turn the option off.

#### Troubleshooting: `pyarrow` fails to install on Windows

Streamlit depends on `pyarrow`, which is distributed as a pre-built wheel for
64-bit versions of Python on Windows. If `pip` prints messages such as
`building 'pyarrow.lib' extension` and ends with `Could not build wheels for
pyarrow`, check the temporary build path in the log. A fragment like
`build\lib.win32-3.11` indicates that the interpreter is 32-bit, and no wheel
exists for that architecture. Install a 64-bit build of Python (for example the
default installer from python.org) or recreate your virtual environment with a
64-bit interpreter, then rerun `pip install -r requirements.txt`. Once `pip`
detects a compatible interpreter it will download the official wheel instead of
attempting a source build, and the installation completes successfully.

#### Troubleshooting: `Screenshot capture is unavailable in this environment`

Compiled deployments need at least one screenshot backend bundled with the
executable. The app will attempt `pyautogui`, fall back to Pillow's
`ImageGrab`, and finally use the optional `mss` module for headless-friendly
captures. When building with PyInstaller, include the relevant packages (for
example `--hidden-import pyautogui`, `PIL.ImageGrab`, and `mss`) or install them
in the runtime environment. If advanced region selection reports that Tkinter
is required, add the standard `tkinter` runtime to the build or use the full
screen capture button instead.

### Updating

The `QuickUpdate.bat` script is intended for small incremental patches.
Major updates such as **RC 141025** introduce new requirements and should be applied manually.
To upgrade to these releases, run **Kiroshi Uninstaller** (`KiroshiUninstaller.bat`) and then reinstall using **Kiroshi Installer** (`KiroshiInstaller_RC-141025.bat`).

#### Updating Python dependencies to the newest releases

If you want to test the application with the most recent Python packages (for example to confirm that a new
Streamlit release works with Kiroshi) use the `requirements-latest.txt` manifest that accompanies the regular
`requirements.txt`. The file pins each dependency to the latest version that was available when the manifest
was generated.

From a clean virtual environment run:

```bash
pip install --upgrade pip
pip install -r requirements-latest.txt
```

Using a fresh virtual environment is recommended so that you can quickly revert to the stable `requirements.txt`
set if a bleeding-edge dependency causes issues. To go back to the supported versions, reinstall the standard
requirements in a separate environment or run `pip install -r requirements.txt` again.

#### Customizing update checks

Kiroshi automatically inspects the Git tree when checking for updates so it can
locate `case_documentation_app.py` even if the file lives inside a nested
folder. If your fork keeps the Streamlit entry point in a non-standard
location, export the `KIROSHI_UPDATE_APP_PATHS` environment variable with a
comma-separated list of relative paths (for example, `tools/streamlit` or
`src/app`). The update checker will prefer these overrides before falling back
to the auto-discovery heuristics.

When the update repository is private, configure a personal access token via
`KIROSHI_UPDATE_GITHUB_TOKEN`. The token is only used for the GitHub API calls
that discover the application path, fetch the latest commit metadata, and
download the remote `case_documentation_app.py` source so the version marker
can be inspected. Without this credential GitHub responds with HTTP 404 for
private repositories, which prevents the update panel from determining the
latest available release.

## Python test suite

The repository includes a comprehensive `pytest` suite that exercises autosave
behaviour, attachment handling, PDF exports, update checks, and the built-in
chat tooling. After installing the runtime requirements you only need the test
runner itself:

```bash
pip install -r requirements.txt
pip install pytest
```

Then execute the full suite from the project root:

```bash
pytest
```

The fixtures automatically adjust `PYTHONPATH` for local imports and provide an
in-repo shim for the [`responses`](https://github.com/getsentry/responses)
library, so no additional development dependencies are required. Network calls
are fully mocked, allowing the tests to run without internet connectivity.

## Visual regression testing

The Streamlit UI is covered by Playwright screenshot tests. Each test run
pre-configures the dashboard via the URL query string so we can validate the
base layout, a forced holiday palette, and a darker seasonal palette without
clicking through the Settings panel.

### One-time setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies and Playwright browsers
npm ci
npx playwright install --with-deps chromium
```

### Running the suite locally

```bash
# In a dedicated terminal (browser/server mode required for tests)
streamlit run case_documentation_app.py --server.headless true --server.port 8501

# In a second terminal
npm run test:e2e
```

> The end-to-end tests expect an HTTP server. The Streamlit Desktop App is not
> currently supported for this workflow.

The tests navigate to `http://127.0.0.1:8501/?enable_holiday_theme=…&theme_preview=…`
before the dashboard fully renders, ensuring the desired palette is active for the
first paint. Baseline payloads live under `tests/e2e/baselines/<browser>/*.base64` and
are materialized into PNGs at runtime. Each snapshot is stored as a newline-wrapped
Base64 blob so textual diffs stay manageable when only a portion of the image
changes. A 1% pixel diff ratio is tolerated to account for minor anti-aliasing
differences.

### Approving new baselines

If a legitimate UI change alters the visuals, regenerate the baselines and re-encode
them before committing:

```bash
npm run test:e2e:update
npm run baselines:encode
```

After the run completes, review the refreshed `.base64` blobs in `tests/e2e/baselines/`
and include them in your pull request. CI will automatically upload the HTML report and
the `test-results/` diff directory whenever a comparison fails so reviewers can inspect
the regressions.

## Building the desktop executable

The repository ships with a helper script that drives the PyInstaller build used for the Windows release. Run it
from the project root:

```bash
./build.sh
```

The script bundles `case_documentation_app.py` together with the Streamlit runtime and deposits the compiled
artifacts under `dist/`. The process was last verified with PyInstaller 6.16.0 on Python 3.12.10; PyInstaller may
emit warnings for optional modules such as `langchain`, but they do not prevent the executable from being
generated.

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

## "Compile it for Dummies" guide

If you want a single executable that bundles Python and all dependencies, you
can create one with PyInstaller. The steps below assume you have never done
this before and walk through the entire process from a clean machine.

1. **Install Python (64-bit).** Download the official 64-bit Python installer
   from [python.org](https://www.python.org/downloads/) and ensure "Add Python
   to PATH" is checked during installation.
2. **Install Git (optional but recommended).** Grab
   [Git for Windows](https://git-scm.com/download/win) so you can clone the
   repository instead of downloading ZIP files manually.
3. **Download the project.** Either run
   `git clone https://github.com/<your-account>/KiroshiDocumentationSystem.git`
   or download and extract the ZIP archive from GitHub.
4. **Open a terminal inside the project folder.** On Windows you can use
   *Command Prompt* or *PowerShell* and run `cd` to the extracted folder, for
   example: `cd C:\Users\you\Downloads\KiroshiDocumentationSystem`.
5. **Create (optional) and activate a virtual environment.** This keeps build
   tools separate from the rest of your system:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
   If you already created `.venv` in a previous session, activate the existing
   environment with `.\.venv\Scripts\activate` and skip re-running
   `python -m venv .venv`. Trying to recreate the environment while it is
   active leads Windows to print `Unable to copy ... venvlauncher.exe` because
   the interpreter files are locked by the running shell.
6. **Install the app requirements and PyInstaller.**
   ```powershell
   pip install -r requirements.txt
   pip install pyinstaller
   ```

   If you see `ModuleNotFoundError: No module named 'reportlab'` while running
   the packaged executable, double-check that the build environment installed
   the project's requirements with the command above. PyInstaller copies
   dependencies from the interpreter that executes the build; missing packages
   cannot be retroactively added to an already compiled binary.
7. **Run PyInstaller.** Use the preconfigured spec file that lives in the
   repository root:
   ```powershell
   pyinstaller KiroshiDocumentationSystem.spec
   ```
   This spec mirrors the long one-liner you might type by hand but also guarantees that
   `case_documentation_app.py` ships with the executable, that the theme and
   server configuration in `.streamlit/config.toml` are packaged, and that all of
   Streamlit's data files are collected. On macOS or Linux you can run the same
   command or execute the helper script: `bash build.sh`.
   > **Prefer a custom command?** If you roll your own `pyinstaller` invocation,
   > remember to include the equivalent of `--add-data "case_documentation_app.py;."`
   > (use a colon on macOS/Linux). Without it the packaged app cannot locate the
   > Streamlit entry-point file and will exit with "File does not exist:
   > case_documentation_app.py". If you disable CORS in a custom build, also
   > bundle `.streamlit/config.toml` so `enableXsrfProtection` stays in sync and
   > Streamlit does not print a startup warning.
8. **Wait for the build to finish.** When PyInstaller completes you will find
   the executable in the `dist` folder (for example
   `dist\KiroshiDocumentationSystem.exe`). Copy that file wherever you want to
   run the app.
9. **Launch the executable.** Double-click the file from `dist` or run it from
   a terminal. Streamlit will start and open the Kiroshi interface in your
   browser just like when running `streamlit run`, while providing the same
   native window chrome as `streamlit-desktop-app`. Packaged builds listen on
   `http://localhost:8502/`, so adjust any bookmarks or firewall rules that
   referenced the default Streamlit port (`8501`).

The PyInstaller spec bundles the companion `kiroshi_chat.py` module along with
its saved-memory files and logos. This keeps the integrated Kiroshi chat
panel working in the compiled build and prevents `ModuleNotFoundError`
crashes when the executable launches.

If you ever want to rebuild after pulling updates, repeat steps 6 and 7 (you do
not need to reinstall Python or Git).

## Usage

If you used the automated installer, start Kiroshi with the provided **Kiroshi Launcher** (`KiroshiLauncher_RC-141025.bat`).

For manual runs from source, choose the classic browser runner or the desktop
experience. If you are not already in the project folder, navigate there first
with `cd`:

```bash
cd /path/to/KiroshiDocumentationSystem

# Browser mode
streamlit run case_documentation_app.py

# Desktop mode
streamlit-desktop-app run case_documentation_app.py
```

Alternatively, use the provided wrapper script for browser/server mode:

```bash
python run_app.py
```

This helper sets up the correct Streamlit arguments and is the entry point used when packaging the project into a browser-first
executable.

A browser window will open with tabs for entering case information. The "Download PDF" button exports a formatted summary, and the
attachment section lets you bundle supporting files. Use the checkbox at the top to toggle hardware tabs and fields. The *Tables*
tab provides a full markdown dump of all case data for easy copying. An internal *Debug* tab is available after logging in with
username and password `admin`.

Multiple cases can be opened at once via the case tabs displayed at the bottom of the page. Use the **Add Case** tab to spawn a new
blank case and switch between them for multitasking.

Within the *Case* tab, the integrated Kiroshi assistant offers a **Verify** button to highlight missing documentation.

To experiment with the Kiroshi chatbox, run the dedicated script:

```bash
cd /path/to/KiroshiDocumentationSystem

# Browser mode
streamlit run kiroshi_chat.py

# Desktop mode
streamlit-desktop-app run kiroshi_chat.py
```

The chat history is saved to `kiroshi_memory.json` so conversations persist across sessions.

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
or the controls in the Debug tab. Kiroshi now supports three AI modes:

1.  **Cloud** – Connects to OpenAI's service (requires an API Key).
2.  **Local API** – Connects to any OpenAI-compatible server (e.g., LM Studio, Ollama) running on `http://localhost:8000/v1` (or your custom URL).
3.  **Local (Native)** – Runs the AI engine directly inside Kiroshi using `llama-cpp-python`. No external server apps are required.
    *   **Features:**
        *   **Automatic Download:** Select a profile ("Speed" or "Quality") and Kiroshi will download the necessary GGUF model files from HuggingFace to a local `models/` directory.
        *   **Hardware Acceleration:** Automatically detects and uses your GPU (Nvidia RTX, etc.) for faster inference.
        *   **Offline Capable:** Once the model is downloaded, no internet connection is needed for AI features.

```bash
# Example for Local API mode
export AI_BASE_URL=http://localhost:8000/v1
export OPENAI_API_KEY=""

# Browser mode
streamlit run case_documentation_app.py

# Desktop mode
streamlit-desktop-app run case_documentation_app.py
```

### Corporate SSL interception

Some enterprise networks intercept HTTPS traffic with a self-signed certificate, which breaks standard SSL verification. The application disables certificate checks for requests to GPT-OSS and for the GitHub updater so it can be used behind such company proxies. Be aware that this weakens transport security and should only be enabled in trusted environments.

## Build executable

To create a standalone executable, make sure you're in the project directory, install the dependencies, and run the build script:

```bash
cd /path/to/KiroshiDocumentationSystem
pip install -r requirements.txt
# Optional: install mini-game and local model dependencies
pip install -r requirements-bored.txt
./build.sh
```

The resulting binary will be placed in the `dist/` directory. The script bundles the `run_app.py` entry point so the executable
launches the Streamlit interface directly.

## Documentation

See the [`docs/`](docs/README.md) directory for a more detailed explanation of how data is structured and how each tab operates.

## Tutorial rápido de AutoHotkey

AutoHotkey (AHK) es un lenguaje de scripting para Windows que permite automatizar tareas repetitivas, crear atajos de teclado y construir interfaces simples. A continuación encontrarás una guía básica en español para comenzar a utilizarlo junto con Kiroshi o en tu flujo de trabajo diario.

### 1. Instalación

1. Visita [https://www.autohotkey.com/](https://www.autohotkey.com/) y descarga la versión estable.
2. Ejecuta el instalador y elige **Express Installation** a menos que necesites una configuración personalizada.
3. Una vez instalado, haz clic derecho en el escritorio o en una carpeta y selecciona **Nuevo → Script de AutoHotkey** para crear tu primer script (`.ahk`).

### 2. Primer script

Abre el archivo recién creado con tu editor favorito y pega el siguiente código:

```ahk
; Muestra un mensaje cuando presionas Ctrl + Alt + K
^!k::
    MsgBox, ¡Bienvenido a tu primer script de AutoHotkey!
return
```

Guarda el archivo y haz doble clic para ejecutarlo. Ahora, al pulsar `Ctrl + Alt + K` verás una ventana de mensaje. Para detener el script, busca el icono con una “H” verde en la bandeja del sistema, haz clic derecho y selecciona **Exit**.

### 3. Hotstrings y automatización de texto

Los *hotstrings* permiten expandir abreviaturas. Añade este ejemplo a tu script:

```ahk
::ksaludo::Hola, gracias por contactar con el soporte de Kiroshi. ¿En qué puedo ayudarte hoy?
```

Escribe `ksaludo` en cualquier campo de texto y presiona espacio para que se reemplace automáticamente por el mensaje completo, ideal para respuestas frecuentes.

### 4. Lanzar aplicaciones y abrir archivos

AutoHotkey puede ejecutar programas o abrir documentación clave para tu equipo:

```ahk
; Abre Kiroshi con Win + Shift + K
# +k::
    Run, C:\\ProgramFiles\\KiroshiLauncher_RC-141025.bat
return

; Abre la wiki interna con Win + Alt + D
# !d::
    Run, https://intranet.ejemplo.com/wiki/kiroshi
return
```

### 5. Variables, bucles y lógica básica

Puedes combinar variables y bucles para crear automatizaciones complejas, como tomar notas temporales y guardarlas en archivos:

```ahk
; Guardar texto seleccionado en un archivo de notas
^!n::
    ClipSaved := ClipboardAll
    Send, ^c
    ClipWait, 0.5
    selectedText := Clipboard
    FileAppend, %A_Now% - %selectedText%`n, %A_Desktop%\NotasKiroshi.txt
    Clipboard := ClipSaved
return
```

Este script copia la selección actual con `Ctrl + Alt + N`, guarda la entrada con fecha y hora en el escritorio y restaura el portapapeles original.

### 6. Buenas prácticas y recursos

- Organiza tus scripts en funciones (`MyFunction()`) y usa comentarios (`;`) para explicar cada bloque.
- Carga scripts automáticamente colocando accesos directos en `%AppData%\Microsoft\Windows\Start Menu\Programs\Startup`.
- Consulta la [documentación oficial](https://www.autohotkey.com/docs/) para explorar GUIs, expresiones regulares y automatización avanzada.

Con estas bases, podrás crear atajos personalizados que complementen tu flujo de trabajo con Kiroshi y faciliten la documentación de casos.

### 7. Configuración sugerida para usar AutoHotkey con Kiroshi

Aunque cada equipo adapta Kiroshi a sus necesidades, la siguiente estructura facilita mantener tus automatizaciones en orden:

| Carpeta | Contenido sugerido |
|---------|--------------------|
| `C:\Kiroshi\AHK\` | Scripts `.ahk` oficiales del equipo. |
| `C:\Kiroshi\Shortcuts\` | Accesos directos para lanzar Kiroshi, el chat de Kiroshi y herramientas de soporte. |
| `%AppData%\AutoHotkey\Lib\` | Funciones reutilizables (por ejemplo, manejo de ventanas Streamlit o plantillas de texto). |

Guarda tus scripts firmados en `C:\Kiroshi\AHK\` y crea accesos directos a los que quieras iniciar con Windows en la carpeta *Startup*. Así todos los agentes tendrán la misma convención de rutas y podrás compartir actualizaciones fácilmente.

### 8. Variables de entorno y configuración de Kiroshi

Kiroshi lee la configuración desde `config.json` o desde variables de entorno. Puedes aprovechar AutoHotkey para conmutar perfiles antes de abrir la aplicación:

```ahk
; Cambia entre entornos Cloud / Local antes de lanzar Kiroshi
^!1::
    SetEnv, AI_BASE_URL, https://api.openai.com/v1
    SetEnv, OPENAI_API_KEY, % Clipboard ; asume que copiaste la clave temporal
    Run, C:\\ProgramFiles\\KiroshiLauncher_RC-141025.bat
return

^!2::
    SetEnv, AI_BASE_URL, http://localhost:8000/v1
    SetEnv, OPENAI_API_KEY,
    Run, C:\\ProgramFiles\\KiroshiLauncher_RC-141025.bat
return
```

Estas funciones lanzan Kiroshi con diferentes backends. Si prefieres modificar `config.json`, AutoHotkey puede editarlo directamente mediante `FileRead`, `StrReplace` y `FileDelete`/`FileAppend` para intercambiar valores antes de ejecutar la app.

### 9. Controlar el flujo de trabajo dentro de Kiroshi

Las páginas de Kiroshi se ejecutan en el navegador. Usa comandos `Send` y `ControlClick` para navegar la interfaz sin perder tiempo:

```ahk
; Crear un caso nuevo y preparar un resumen
!+n::
    ; Asume que el navegador ya está enfocado
    Send, ^l
    Sleep, 150
    Send, http://localhost:8501{Enter}
    WinWaitActive, Kiroshi Documentation System
    ; Botón "Add Case"
    Click, 200, 980
    Sleep, 200
    ; Rellenar campos clave
    Send, Cliente Ejemplo{Tab}ACME Corp{Tab}CS-123456{Tab}Problema detectado en impresora 3Shape.
    ; Cambiar a pestaña Email y generar resumen
    Send, ^{PgDn}
    Sleep, 150
    Send, {Tab 3}{Enter}
return
```

Adapta las coordenadas a tu resolución o reemplázalas por `ControlFocus`/`ControlSetText` si trabajas con navegadores compatibles con UI Automation. También puedes combinar `ImageSearch` para detectar botones con íconos personalizados dentro de la aplicación.

### 10. Registrar notas y exportar documentación

Si necesitas guardar notas rápidas mientras atiendes un caso, conecta AutoHotkey con las carpetas de exportación de Kiroshi:

```ahk
; Guardar la última captura exportada por Kiroshi con un nombre legible
#g::
    latest := "C:\\ProgramFiles\\KiroshiDatabase\\Exports\\Screenshots\\"
    FileGetTime, ts, %latest%, M
    FormatTime, pretty, %ts%, yyyy-MM-dd_HH-mm
    FileMove, %latest%\Screenshot.png, %latest%\%pretty%_CasoActual.png, 1
    TrayTip, Kiroshi, Captura renombrada: %pretty%, 2000
return
```

Modifica las rutas a las utilizadas por tu instalación. Este patrón es útil para normalizar nombres antes de adjuntar archivos en correos o cargar evidencia en Case Dex.

Con estas ampliaciones podrás configurar AutoHotkey para lanzar Kiroshi en distintos entornos, automatizar tareas dentro de la interfaz y mantener ordenados tus recursos compartidos.

### 11. ¿De dónde proviene esta información?

Todos los fragmentos del tutorial se elaboraron a partir de fuentes públicas y flujos de trabajo internos habituales:

- **Documentación oficial de AutoHotkey**: La sintaxis y comandos (`MsgBox`, `Send`, `ControlClick`, `FileAppend`, `SetEnv`, etc.) se basan en los manuales publicados en [https://www.autohotkey.com/docs/](https://www.autohotkey.com/docs/).
- **Instaladores incluidos en este repositorio**: Las rutas que apuntan a `KiroshiInstaller_RC-141025.bat`, `KiroshiLauncher_RC-141025.bat` y carpetas como `C:\\ProgramFiles\\KiroshiDatabase` reflejan los archivos distribuidos junto al proyecto y el comportamiento descrito en este README.
- **Convenciones operativas del equipo**: La estructura de carpetas sugerida (`C:\Kiroshi\AHK\`, `%AppData%\AutoHotkey\Lib\`, etc.) recoge las prácticas compartidas con el personal de soporte para mantener scripts versionados y listos para su despliegue en estaciones Windows.
- **Automatizaciones comunes sobre Streamlit/navegadores**: Los ejemplos con coordenadas, uso de `WinWaitActive` o teclas rápidas se derivan de escenarios reales de documentación de casos dentro de Kiroshi y se adaptan según la resolución o el navegador predeterminado.

#### ¿Qué archivos alimentan el script de AutoHotkey generado por Kiroshi?

- Los datos que se vuelcan en cada *hotstring* salen directamente de los casos abiertos en la interfaz. Internamente, Kiroshi construye cada tabla a partir del modelo `CaseData` (campos como `company_name`, `remote_steps`, `solution`, etc.) y de los grupos definidos en el mapa de categorías (`BASE_CATEGORY_MAP`/`HW_CATEGORY_MAP`).
- Cada modificación que haces en la app se guarda automáticamente en `autosave.json`, localizado junto al ejecutable o en el directorio del proyecto si trabajas desde código fuente. Ese JSON conserva el último caso activo y es la referencia que se recupera al reiniciar la herramienta.
- Cuando pulsas la opción **AutoHotkey quick paste**, la aplicación genera un archivo `kiroshi_tables_hotkeys.ahk` dentro de `C:\\ProgramFiles\\KiroshiDatabase\` (o `~/KiroshiDatabase/` en sistemas que no son Windows). No existe un JSON separado para los atajos: el contenido del `.ahk` se escribe a partir de la sesión en memoria y del `autosave.json` más reciente.
- En la misma carpeta `KiroshiDatabase` encontrarás también `recent_cases.json`, `settings.json` y otros respaldos (`autosave_<CASE>.json`) que permiten mantener sincronizados los datos que alimentan el script de AutoHotkey.

Si necesitas adaptar los ejemplos a otra versión de Windows, a un navegador diferente o a rutas personalizadas de Kiroshi, te recomendamos validar cada fragmento con la documentación oficial y los procedimientos internos actualizados.

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

