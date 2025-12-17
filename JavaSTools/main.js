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

// --- Lifecycle Management ---

app.whenReady().then(() => {
    createWindow();

    // Spawn Kiroshi Streamlit App
    // We assume python is in the path. In a prod app, we'd bundle a python env.
    console.log("Launching Kiroshi Streamlit backend...");

    // We run this from the parent directory of JavaSTools (the repo root)
    const rootDir = path.resolve(__dirname, '..');

    // Check if on Windows
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    kiroshiProcess = spawn(pythonCmd, ['-m', 'streamlit', 'run', 'case_documentation_app.py', '--server.headless', 'true'], {
        cwd: rootDir,
        shell: true
    });

    kiroshiProcess.stdout.on('data', (data) => {
        console.log(`Kiroshi: ${data}`);
    });

    kiroshiProcess.stderr.on('data', (data) => {
        console.error(`Kiroshi Error: ${data}`);
    });

    app.on('activate', function () {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', function () {
    if (kiroshiProcess) {
        // Kill the python process when app closes
        if (process.platform === 'win32') {
             spawn("taskkill", ["/pid", kiroshiProcess.pid, '/f', '/t']);
        } else {
            kiroshiProcess.kill();
        }
    }
    if (process.platform !== 'darwin') app.quit();
});
