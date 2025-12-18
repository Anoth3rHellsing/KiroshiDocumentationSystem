const { app, BrowserWindow, ipcMain, BrowserView } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// --- Global SSL Bypass ---
// This is critical for the user's requirement to bypass SSL errors on all sites.
app.commandLine.appendSwitch('ignore-certificate-errors');
app.commandLine.appendSwitch('allow-insecure-localhost', 'true');

let mainWindow;
let kiroshiProcess;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        frame: false, // Custom title bar / top bar
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false, // For prototype simplicity (renderer access to node)
            webviewTag: true, // Enable <webview> for the tabs
            webSecurity: false // Further disable security for SSL/CORS issues if needed
        }
    });

    mainWindow.loadFile('index.html');

    // Handle global certificate errors for all webContents (including webviews)
    app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
        // On certificate error we disable default behavior (stop loading)
        // and we then say "true" to continue loading.
        event.preventDefault();
        callback(true);
    });
}

function killKiroshi() {
    if (kiroshiProcess) {
        try {
            console.log("Killing existing Kiroshi process...");
            if (process.platform === 'win32') {
                 spawn("taskkill", ["/pid", kiroshiProcess.pid, '/f', '/t']);
            } else {
                kiroshiProcess.kill();
            }
        } catch (e) {
            console.error("Error killing process:", e);
        }
        kiroshiProcess = null;
    }
}

function startKiroshi() {
    console.log("Launching Kiroshi Streamlit backend...");

    // Determine the root directory for the Python script
    // If packaged, we expect the python files to be in resources/python_core
    // If dev, we expect them in the parent directory of JavaSTools
    let pythonCoreDir;
    if (app.isPackaged) {
        pythonCoreDir = path.join(process.resourcesPath, 'python_core');
    } else {
        pythonCoreDir = path.resolve(__dirname, '..');
    }

    console.log(`Python Core Directory: ${pythonCoreDir}`);
    const fs = require('fs');
    if (!fs.existsSync(pythonCoreDir)) {
         console.error(`ERROR: Python core directory not found at ${pythonCoreDir}`);
         if (mainWindow) {
             mainWindow.webContents.send('kiroshi-startup-error', `Core directory missing: ${pythonCoreDir}`);
         }
         return;
    }

    // Check if on Windows
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    try {
        kiroshiProcess = spawn(pythonCmd, ['-m', 'streamlit', 'run', 'case_documentation_app.py', '--server.headless', 'true'], {
            cwd: pythonCoreDir,
            shell: true,
            // Ensure stdio is captured
            stdio: ['ignore', 'pipe', 'pipe']
        });

        if (kiroshiProcess) {
            kiroshiProcess.stdout.on('data', (data) => {
                const msg = data.toString();
                console.log(`Kiroshi: ${msg}`);
            });

            kiroshiProcess.stderr.on('data', (data) => {
                const msg = data.toString();
                console.error(`Kiroshi Error: ${msg}`);
                // Optional: Send startup errors to UI if it looks like a fatal error
                // For now, we rely on the process exit or 'error' event, but if python prints a traceback, it goes here.
            });

            kiroshiProcess.on('error', (err) => {
                 console.error("Failed to start Kiroshi process:", err);
                 if (mainWindow) {
                     mainWindow.webContents.send('kiroshi-startup-error', `Spawn error: ${err.message}`);
                 }
            });

            kiroshiProcess.on('close', (code) => {
                console.log(`Kiroshi process exited with code ${code}`);
                if (code !== 0 && code !== null) {
                     if (mainWindow) {
                         mainWindow.webContents.send('kiroshi-startup-error', `Process exited with code ${code}. See logs.`);
                     }
                }
            });
        }
    } catch (e) {
        console.error("Exception starting Kiroshi:", e);
        if (mainWindow) {
            mainWindow.webContents.send('kiroshi-startup-error', `Exception: ${e.message}`);
        }
    }
}

// --- IPC Handlers ---

ipcMain.on('restart-kiroshi', (event) => {
    console.log("Received restart-kiroshi request");
    killKiroshi();

    // Give a small delay to ensure cleanup? usually not needed with /f, but safer
    setTimeout(() => {
        startKiroshi();
        event.sender.send('kiroshi-restarted');
    }, 1000);
});

// --- Lifecycle Management ---

app.whenReady().then(() => {
    createWindow();
    startKiroshi();

    app.on('activate', function () {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', function () {
    killKiroshi();
    if (process.platform !== 'darwin') app.quit();
});
