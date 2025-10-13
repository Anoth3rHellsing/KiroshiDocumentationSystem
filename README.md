# Kiroshi Documentation System

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](#)
[![Version](https://img.shields.io/badge/version-RC%201.7.2111025-blue)](#)
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
  making it easy to copy into spreadsheets.
- **PDF export** – download a formatted summary of the case with wrapped table text so long values stay within the page.
- **Attachments** – upload screenshots or videos and export everything as a ZIP bundle, with logs placed in a separate `logs/`
  folder.
- **Screenshot capture** – take screenshots directly from the app, name them for context, and include them in the exported ZIP
  under a dedicated `Screenshots/` folder.
- **Real-time autosave** – case data is persisted to `autosave.json` on every interaction to prevent data loss.
- **Save/Load tab** – persist cases to `C:\\ProgramFiles\\KiroshiDatabase` using the case ID, browse recent cases, and reload them directly from the app.
- **Case Dex download** – fetch a Case Dex package for a given case ID and save it as a ZIP file.
- **Case tracking** – enable tracking from the Case tab and store Dell or FedEx status updates in `TrackedCases` for dashboard monitoring; cases may be untracked or closed when finished.
- **GPT-OSS integration (coming soon)** – send prompts directly to GPT-OSS and display the generated response.
- **Kiroshi chat tools** – "Verify" reviews case data for missing details; a separate chat interface offers persistent memory,
  gentle reassurance when you're overwhelmed, and humorous escalation quips. Toggle Sarcasm Mode in Settings when you want the
  assistant to lean into extra wit.
- **Debug tab** – internal diagnostics with a log viewer (last 100 lines) protected by an `admin`/`admin` login.
- **Corporate theme** – default light mode with 3Shape Red accents; switch to dark mode from the Streamlit settings for extended
  sessions.

## Installation

### Automated installation

1. Download the repository ZIP from GitHub.
2. Extract the archive and run **Kiroshi Installer** (`KiroshiInstaller_RC-1-7-2111025.bat`).
3. Launch the app with **Kiroshi Launcher** (`KiroshiLauncher_RC-1-7-2111025.bat`).
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
Major updates such as **RC 1.7.2111025** introduce new requirements and should be applied manually.
To upgrade to these releases, run **Kiroshi Uninstaller** (`KiroshiUninstaller.bat`) and then reinstall using **Kiroshi Installer** (`KiroshiInstaller_RC-1-7-2111025.bat`).

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
   browser just like when running `streamlit run`. Packaged builds listen on
   `http://localhost:8502/`, so adjust any bookmarks or firewall rules that
   referenced the default Streamlit port (`8501`).

The PyInstaller spec bundles the companion `kiroshi_chat.py` module along with
its saved-memory files and logos. This keeps the integrated Kiroshi chat
panel working in the compiled build and prevents `ModuleNotFoundError`
crashes when the executable launches.

If you ever want to rebuild after pulling updates, repeat steps 6 and 7 (you do
not need to reinstall Python or Git).

## Usage

If you used the automated installer, start Kiroshi with the provided **Kiroshi Launcher** (`KiroshiLauncher_RC-1-7-2111025.bat`).

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

Multiple cases can be opened at once via the case tabs displayed at the bottom of the page. Use the **Add Case** tab to spawn a new
blank case and switch between them for multitasking.

Within the *Case* tab, the integrated Kiroshi assistant offers a **Verify** button to highlight missing documentation.

To experiment with the Kiroshi chatbox, run the dedicated script:

```bash
cd /path/to/KiroshiDocumentationSystem
streamlit run kiroshi_chat.py
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
or the controls in the Debug tab. Choose **Cloud** to use OpenAI's service,
**Local API** to point to any OpenAI-compatible server, or **Local Model** to
run a minimal `transformers` pipeline directly. When using a local server, the
`OPENAI_API_KEY` may be left blank.

```bash
export AI_BASE_URL=http://localhost:8000/v1
export OPENAI_API_KEY=""
streamlit run case_documentation_app.py
```

If `AI_BASE_URL` is unset (the "Local Model" option), Kiroshi falls back to a
minimal `transformers` pipeline (install the optional `transformers` and
`torch` packages from `requirements-bored.txt` and supply an available model)
to generate text without making HTTP requests.

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
    Run, C:\\ProgramFiles\\KiroshiLauncher_RC-1-7-2111025.bat
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
    Run, C:\\ProgramFiles\\KiroshiLauncher_RC-1-7-2111025.bat
return

^!2::
    SetEnv, AI_BASE_URL, http://localhost:8000/v1
    SetEnv, OPENAI_API_KEY,
    Run, C:\\ProgramFiles\\KiroshiLauncher_RC-1-7-2111025.bat
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
- **Instaladores incluidos en este repositorio**: Las rutas que apuntan a `KiroshiInstaller_RC-1-7-2111025.bat`, `KiroshiLauncher_RC-1-7-2111025.bat` y carpetas como `C:\\ProgramFiles\\KiroshiDatabase` reflejan los archivos distribuidos junto al proyecto y el comportamiento descrito en este README.
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

