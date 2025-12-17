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

    // Check if on Windows
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    kiroshiProcess = spawn(pythonCmd, ['-m', 'streamlit', 'run', 'case_documentation_app.py', '--server.headless', 'true'], {
        cwd: pythonCoreDir,
        shell: true
    });

    kiroshiProcess.stdout.on('data', (data) => {
        console.log(`Kiroshi: ${data}`);
    });

    kiroshiProcess.stderr.on('data', (data) => {
        console.error(`Kiroshi Error: ${data}`);
    });
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
