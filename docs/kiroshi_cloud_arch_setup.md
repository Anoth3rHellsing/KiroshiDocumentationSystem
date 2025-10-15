# KiroshiCloud Client for Arch Linux

This guide walks through deploying the lightweight **KiroshiCloud** client on
Arch Linux. The client maintains a live SQLite database of every Kiroshi device
you register and exposes a small HTTP API that behaves like a private cloud.
When you follow the optional networking steps you can connect to the service
securely even from a different network – the instructions assume minimal Linux
experience and explain *why* each command is necessary.

The guide is split into four sections:

1. [Prerequisites and environment preparation](#1-prerequisites-and-environment-preparation)
2. [Running the KiroshiCloud service manually](#2-run-the-kiroshicloud-service-manually)
3. [Registering devices and keeping the database live](#3-register-devices-and-keep-the-database-live)
4. [Connecting from other networks](#4-connect-from-other-networks)

---

## 1. Prerequisites and environment preparation

1. **Update Arch** so that the base system and Python packages are current.

   ```bash
   sudo pacman -Syu
   ```

2. **Install Python and runtime dependencies.** The refreshed KiroshiCloud
   stack encrypts device metadata with `cryptography`, serves the Streamlit
   dashboard, and talks to the API with `requests`. Grab the packages from the
   Arch repositories so you do not have to compile them inside the virtual
   environment.

   ```bash
   sudo pacman -S python python-pip python-virtualenv \
     python-cryptography python-requests python-pandas python-streamlit
   ```

3. **Create a dedicated user (optional but recommended).** Running services as a
   non-root account limits the impact of mistakes.

   ```bash
   sudo useradd --system --home /var/lib/kiroshi-cloud --create-home \
     --shell /usr/bin/nologin kiroshi-cloud
   ```

4. **Clone or copy the repository.** If you do not already have the project on
   the machine, place it under `/opt` and adjust ownership so the service user
   can read it.

   ```bash
    sudo mkdir -p /opt/kiroshi
    sudo chown "$USER" /opt/kiroshi
    git clone https://github.com/example/KiroshiDocumentationSystem.git \
      /opt/kiroshi/KiroshiDocumentationSystem
   ```

   If you downloaded a ZIP archive instead of cloning, extract it to
   `/opt/kiroshi/KiroshiDocumentationSystem`.

5. **Create a virtual environment** so that Python dependencies (if you add any
   later) stay isolated.

   ```bash
   cd /opt/kiroshi/KiroshiDocumentationSystem
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   ```

   The secure release bundles a few third-party libraries (Fernet encryption,
   the Streamlit UI, and dataframe helpers). Installing them into the virtual
   environment keeps the system packages untouched and simplifies upgrades.

6. **Create a data directory** that will host the SQLite database. This path is
   configurable; `/var/lib/kiroshi-cloud` matches the service account we created
   earlier.

   ```bash
   sudo mkdir -p /var/lib/kiroshi-cloud
   sudo chown kiroshi-cloud:kiroshi-cloud /var/lib/kiroshi-cloud
   ```

---

## 2. Run the KiroshiCloud service manually

At its core the client is a single Python file. Running it manually lets you
confirm that the database and HTTP API work before you convert it into a
service.

1. **Start the API server.**

   ```bash
   source /opt/kiroshi/KiroshiDocumentationSystem/.venv/bin/activate
   python /opt/kiroshi/KiroshiDocumentationSystem/kiroshi_cloud_client.py \
     --database /var/lib/kiroshi-cloud/kiroshi_cloud.sqlite3 \
     serve --host 0.0.0.0 --port 8050
   ```

   - `--database` points at the path that will hold the SQLite file.
   - `--host 0.0.0.0` allows remote connections on any network interface.
   - `--port 8050` matches the default port used throughout this guide. You may
     change it if another service already uses 8050.

   You should see a message similar to `KiroshiCloud service listening on
   http://0.0.0.0:8050`. On first launch the client generates a Fernet key next
   to the database (for example `/var/lib/kiroshi-cloud/kiroshi_cloud.key`) and
   prints randomly generated default credentials such as:

   ```text
   Default KiroshiCloud credentials created:
     username: admin
     password: X3mB4p7m1KsQ
   ```

   Copy the password — you will need it to authenticate API calls and to sign in
   to the Streamlit UI before rotating the login details.

2. **Open another terminal** and check that the API responds.

   ```bash
   curl http://localhost:8050/health
   curl -u admin:YOUR_PASSWORD http://localhost:8050/devices
   ```

   The first command returns `{"status": "ok"}`. The second requires HTTP Basic
   authentication and returns an empty device list until you register hardware.

3. **Stop the server** with `Ctrl+C` once you are done testing.

### Optional: install as a systemd service

Running the process in a terminal works for demos, but production deployments
should use `systemd` so the service starts automatically after reboots.

1. Create a systemd unit file at `/etc/systemd/system/kiroshi-cloud.service`:

   ```ini
   [Unit]
   Description=KiroshiCloud device registry
   After=network-online.target
   Wants=network-online.target

   [Service]
   User=kiroshi-cloud
   Group=kiroshi-cloud
   WorkingDirectory=/opt/kiroshi/KiroshiDocumentationSystem
   Environment=PATH=/opt/kiroshi/KiroshiDocumentationSystem/.venv/bin:/usr/bin
   ExecStart=/opt/kiroshi/KiroshiDocumentationSystem/.venv/bin/python \
     /opt/kiroshi/KiroshiDocumentationSystem/kiroshi_cloud_client.py \
     --database /var/lib/kiroshi-cloud/kiroshi_cloud.sqlite3 serve --host 0.0.0.0 --port 8050
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```

2. Reload systemd and enable the service:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now kiroshi-cloud.service
   sudo systemctl status kiroshi-cloud.service
   ```

3. Test the API with `curl` again. The service should stay running even if you
   log out of the server.

---

## 3. Register devices and keep the database live

The client provides CLI helpers and HTTP endpoints. Both approaches write to the
same SQLite database, so you can mix and match depending on what is more
convenient for you.

### 3.1 Register a device from the CLI

Use the `register` command to add records manually:

```bash
python kiroshi_cloud_client.py --database /var/lib/kiroshi-cloud/kiroshi_cloud.sqlite3 \
  register --device-id scanner-01 --name "Front Desk Scanner" --model "Kiroshi ScanMate" \
  --owner "Support" --location "HQ" --notes "USB connected to kiosk"
```

### 3.2 Register the current machine automatically

```bash
python kiroshi_cloud_client.py --database /var/lib/kiroshi-cloud/kiroshi_cloud.sqlite3 \
  register-self --device-id kiosk-$(hostname) --owner "Support" --location "HQ"
```

The command collects the hostname, architecture, Python version, and the first
resolvable IP address of the system, then stores it in the database.

### 3.3 Send heartbeats

If you create cron jobs or scripts on remote devices, have them periodically
signal that they are still online:

```bash
python kiroshi_cloud_client.py --database /var/lib/kiroshi-cloud/kiroshi_cloud.sqlite3 \
  heartbeat scanner-01
```

You can schedule the heartbeat every 5 minutes with `systemd` timers or cron.

### 3.4 Use the HTTP API from other tools

The REST endpoints provide JSON responses that are easy to consume. Every call
requires HTTP Basic authentication using the credentials printed when the
service starts.

```bash
curl -X POST http://localhost:8050/devices \
  -u admin:YOUR_PASSWORD \
  -H 'Content-Type: application/json' \
  -d '{
        "device_id": "scanner-02",
        "name": "Second Floor Scanner",
        "location": "Second floor",
        "metadata": {"serial": "SN-7780"}
      }'

curl -u admin:YOUR_PASSWORD http://localhost:8050/devices/scanner-02

# Update the connection policy from a remote script
curl -X POST -u admin:YOUR_PASSWORD \
  http://localhost:8050/connections/scanner-02/block \
  -H 'Content-Type: application/json' \
  -d '{"reason": "Decommissioned"}'

# Delete a device once retired
curl -X DELETE -u admin:YOUR_PASSWORD \
  http://localhost:8050/connections/scanner-02
```

The server replies with the stored JSON record or the updated connection status.
Any tool capable of making authenticated HTTP requests (PowerShell, Node.js,
etc.) can interact with KiroshiCloud.

### 3.5 Manage the cloud from the Streamlit console

The repository now ships with `kiroshi_cloud_ui.py`, a Streamlit interface that
mirrors the Kiroshi desktop styling. It lets you review connections, unblock or
remove devices, rotate credentials, and synchronise the Educate dataset without
touching the CLI.

1. Launch the console on the same machine that runs the API:

   ```bash
   source /opt/kiroshi/KiroshiDocumentationSystem/.venv/bin/activate
   streamlit run /opt/kiroshi/KiroshiDocumentationSystem/kiroshi_cloud_ui.py \
     --server.port 8503
   ```

2. Open `http://localhost:8503` in a browser. Enter the API base URL (for
   example `http://localhost:8050`) and the cloud credentials printed when the
   service started. The overview shows live device status, connection actions,
   and the Tailscale mesh controls.

3. Use the **Educate dataset alignment** panel to push your desktop knowledge
   base into the encrypted cloud store or to pull the remote version back to the
   local `manual_memory.json` used by the desktop assistant.

### 3.6 Inspect the database

```bash
python kiroshi_cloud_client.py --database /var/lib/kiroshi-cloud/kiroshi_cloud.sqlite3 list
```

Use `--format json` to dump raw JSON if you plan to pipe the output into other
programs.

---

## 4. Connect from other networks

Arch installs often sit behind NAT routers or corporate firewalls. The steps
below outline two beginner-friendly ways to reach the service from an external
network. Pick the option that matches your security policies.

### Option A – Tailscale (WireGuard mesh VPN)

Tailscale creates an encrypted mesh network between all your devices. Every
machine receives a stable IP address that you can use to reach the KiroshiCloud
API directly.

1. Install Tailscale:

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --ssh
   ```

   The first command downloads and installs the official package. The second
   command prints a URL; open it in your browser and log in with Google, GitHub,
   or your company SSO.

2. After authentication, run `tailscale ip -4` to view the machine's private
   Tailscale address (for example `100.101.102.103`).

3. On your remote workstation install Tailscale as well, log in to the same
   account, and run:

   ```bash
   curl http://100.101.102.103:8050/devices
   ```

   As long as both machines are online, the connection works even if they sit on
   different physical networks.

   You can also manage the mesh without touching the raw Tailscale CLI by using
   the helper commands bundled with the cloud client:

   ```bash
   python kiroshi_cloud_client.py p2p-status
   python kiroshi_cloud_client.py p2p-connect --auth-key tskey-xxxxxxxxxxxx
   python kiroshi_cloud_client.py p2p-disconnect
   ```

### Option B – SSH reverse tunnel

If you cannot deploy a mesh VPN, an SSH tunnel via a public relay server works
just as well. The idea is to ask the Arch machine to create a tunnel to a
server you control (for example a VPS), exposing port 8050 on the relay.

1. On the relay server, ensure the SSH daemon allows remote port forwarding by
   setting `GatewayPorts yes` in `/etc/ssh/sshd_config` and reloading the
   service (`sudo systemctl reload sshd`).

2. From the Arch machine run:

   ```bash
   ssh -N -R 0.0.0.0:8800:localhost:8050 user@relay.example.com
   ```

   - `-N` keeps the SSH session open without launching a shell.
   - `-R 0.0.0.0:8800:localhost:8050` maps port 8050 on the Arch host to port
     8800 on the relay, listening on all interfaces.

3. Anyone who can reach the relay server can now query the API:

   ```bash
   curl http://relay.example.com:8800/devices
   ```

4. To keep the tunnel online permanently, create a systemd unit and timer:

   ```ini
   # /etc/systemd/system/kiroshi-cloud-tunnel.service
   [Unit]
   Description=Persistent SSH tunnel for KiroshiCloud
   After=network-online.target

   [Service]
   ExecStart=/usr/bin/ssh -N -R 0.0.0.0:8800:localhost:8050 user@relay.example.com
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

   Enable it with `sudo systemctl enable --now kiroshi-cloud-tunnel.service`.

### Firewall reminder

Whether you use Tailscale, SSH, or expose the service directly, make sure the
local firewall allows inbound connections on the chosen port. With `ufw` it
looks like this:

```bash
sudo pacman -S ufw
sudo systemctl enable --now ufw.service
sudo ufw allow 8050/tcp
sudo ufw status
```

### Monitoring tips

- `journalctl -u kiroshi-cloud.service` shows the service logs.
- Use `python kiroshi_cloud_client.py list` periodically to confirm that
  `last_seen` timestamps move forward when your devices send heartbeats.
- Export the database for backups with `sqlite3 /var/lib/kiroshi-cloud/kiroshi_cloud.sqlite3 .dump > backup.sql`.

---

## Appendix – API reference

| Method | Endpoint                     | Description                                      |
| ------ | ---------------------------- | ------------------------------------------------ |
| GET    | `/health`                    | Returns `{ "status": "ok" }` to signal liveness. |
| GET    | `/devices`                   | Lists all registered devices.                     |
| GET    | `/devices/<device_id>`       | Returns a specific device or HTTP 404.            |
| POST   | `/devices`                   | Create or update a device (JSON payload).         |
| POST   | `/devices/<device_id>`       | Alias for update when clients cannot send PUT.    |
| POST   | `/devices/<device_id>/heartbeat` | Updates `last_seen` without changing metadata. |

All responses use JSON and include `Access-Control-Allow-Origin: *`, which makes
the API callable from browser-based dashboards without additional proxying.

