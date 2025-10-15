# KiroshiCloud on Windows 10/11 and Windows Server

This guide walks through deploying the KiroshiCloud service and its optional
Streamlit "Control Tower" UI on modern Windows desktops and Windows Server
hosts.  The instructions assume a fresh machine with no prior Python tooling
and highlight the differences between workstation and server scenarios.

> **Audience.** Operators who prefer graphical tooling may follow the
> PowerShell commands verbatim; administrators who already manage Windows
> services can skim the scripted sections and apply their existing
> automation or configuration management platform instead.

## 1. Prerequisites

| Component | Purpose | Notes |
|-----------|---------|-------|
| 64-bit Python 3.10 or newer | Runs the HTTP API and CLI | Grab the official installer from [python.org](https://www.python.org/downloads/). Ensure that "Add python.exe to PATH" is selected. |
| Git (optional) | Clones the repository | Download from [git-scm.com](https://git-scm.com/download/win) or use the Git client that ships with Visual Studio. |
| Visual C++ build tools | Required for cryptography wheels on very old systems | Modern Python distributions bundle the dependency. Windows Server 2016/2019 may require the [Build Tools for Visual Studio 2019](https://visualstudio.microsoft.com/downloads/). |
| [Tailscale](https://tailscale.com/) (optional) | Peer-to-peer mesh without port forwarding | The client is optional. Install if you want the built-in mesh helpers to traverse NAT. |
| Administrator rights | Create the data directory and register a service | Needed once during installation. Day-to-day operation runs as a service account. |

### Recommended directory layout

KiroshiCloud defaults to `%ProgramData%\KiroshiCloud` for its encrypted
SQLite database and Fernet key.  If you prefer a different location set the
`KIROSHI_CLOUD_HOME` environment variable before launching the service.

## 2. Prepare the working tree

1. Open **PowerShell** as an administrator.
2. Clone or download the repository:

   ```powershell
   cd C:\
   git clone https://github.com/<your-account>/KiroshiDocumentationSystem.git
   # Or download the ZIP from GitHub and extract it to C:\KiroshiDocumentationSystem
   cd C:\KiroshiDocumentationSystem
   ```

3. (Optional) Create an isolated virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install the dependencies for both the service and the UI:

   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install streamlit cryptography pandas
   ```

   *Install the [Tailscale for Windows](https://tailscale.com/download/windows) client separately if you plan to orchestrate the mesh from the CLI; the control tower UI remains optional but recommended for day-to-day monitoring.*

## 3. First run and credential bootstrap

Start the API locally to generate the default `admin` credentials:

```powershell
python kiroshi_cloud_client.py serve --host 0.0.0.0 --port 8050
```

The command prints a randomly generated password on first launch.  Copy it to a
secure location; you will use it to sign into the control tower and immediately
rotate the account.

Stop the process once you confirm the database and key file were created under
`%ProgramData%\KiroshiCloud` (or your custom `KIROSHI_CLOUD_HOME`).

## 4. Running KiroshiCloud as a Windows service

### Option A – NSSM (recommended)

[NSSM](https://nssm.cc/) wraps any executable as a Windows service and gives
you a GUI for fine-grained control.

1. Download the latest NSSM ZIP and extract it, e.g. to `C:\nssm`.
2. Register the service:

   ```powershell
   C:\nssm\win64\nssm.exe install KiroshiCloud "C:\KiroshiDocumentationSystem\.venv\Scripts\python.exe" "C:\KiroshiDocumentationSystem\kiroshi_cloud_client.py" serve --host 0.0.0.0 --port 8050
   ```

   Adjust the paths if you did not create a virtual environment. NSSM opens a
   dialog where you can set:

   * **Startup directory:** `C:\KiroshiDocumentationSystem`
   * **I/O redirection (optional):** send stdout/stderr to log files under `%ProgramData%\KiroshiCloud\logs`.

3. Start the service:

   ```powershell
   Start-Service KiroshiCloud
   Get-Service KiroshiCloud
   ```

### Option B – Windows Service using `sc.exe`

If you prefer built-in tooling, create a service that runs a helper batch file:

1. Create `C:\KiroshiDocumentationSystem\run_kiroshi_cloud.bat` with:

   ```bat
   @echo off
   cd /d C:\KiroshiDocumentationSystem
   call .venv\Scripts\activate.bat
   python kiroshi_cloud_client.py serve --host 0.0.0.0 --port 8050
   ```

2. Register the service:

   ```powershell
   sc create KiroshiCloud binPath= "cmd /c C:\KiroshiDocumentationSystem\run_kiroshi_cloud.bat" start= auto
   sc start KiroshiCloud
   ```

   Review `sc query KiroshiCloud` for status and `Get-EventLog -LogName Application -Newest 50` for error output.

## 5. Exposing the API securely

* **Local firewall:** Allow inbound TCP/8050 on the private network profile.
* **Tailscale integration:** After installing the Windows Tailscale client, run
  `tailscale up` once to log in.  From that point the KiroshiCloud CLI can query
  the mesh status and expose the service through your Tailnet without any port
  forwarding.
* **Reverse proxy (optional):** IIS, Caddy, or Nginx for Windows can terminate
  TLS and forward requests to the local service when publishing the API over
  HTTPS.

## 6. Launching the Control Tower UI

The Streamlit UI may run on the same machine or any workstation that reaches
the API.  Activate the same environment and start Streamlit:

```powershell
streamlit run kiroshi_cloud_ui.py --server.port 8501
```

On first load the UI prompts for the admin credentials that the service
bootstrapped.  Use the **Settings → Accounts** tab to rotate the password and
add additional operators.

When hosting the UI on Windows Server behind IIS or Nginx, enable WebSocket
support so Streamlit can push live updates.

## 7. Synchronising the Educate dataset

1. From a desktop that runs the classic Kiroshi app, export the Educate dataset
   (the Streamlit UI exposes dedicated push/pull buttons).
2. On the KiroshiCloud machine run:

   ```powershell
   python kiroshi_cloud_client.py educate import --path C:\path\to\educate.json
   ```

3. Verify the documents via `python kiroshi_cloud_client.py educate list` or the
   Control Tower's "Knowledge" view.

## 8. Updating the installation

1. Stop the `KiroshiCloud` service.
2. Pull the latest code:

   ```powershell
   cd C:\KiroshiDocumentationSystem
   git pull
   pip install -r requirements.txt
   ```

3. Restart the service and confirm `Get-Service KiroshiCloud` shows the `Running`
   state.

## 9. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'cryptography'` | Re-run `pip install -r requirements.txt` from the elevated PowerShell window so the wheel can write to `%ProgramFiles%`. |
| Service starts then stops | Inspect `%ProgramData%\KiroshiCloud\logs` if using NSSM I/O redirection, or check the Application event log for Python tracebacks. Ensure the virtual environment activation path is correct. |
| Streamlit cannot reach the API | Confirm TCP/8050 is open locally, test `Invoke-WebRequest http://localhost:8050/health` from the server, and verify any Tailnet or VPN connectivity before exposing the UI remotely. |
| Tailscale commands fail | Install the Tailscale Windows client and ensure the `tailscale.exe` binary is present on `%PATH%`. |

With these steps Windows administrators receive parity with the Arch Linux
workflow while retaining native service management, firewall configuration, and
mesh networking controls.
