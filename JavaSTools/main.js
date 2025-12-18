const { app, BrowserWindow, ipcMain, BrowserView } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// --- Global SSL Bypass ---
// This is critical for the user's requirement to bypass SSL errors on all sites.
app.commandLine.appendSwitch('ignore-certificate-errors');
app.commandLine.appendSwitch('allow-insecure-localhost', 'true');

let mainWindow;
let kiroshiProcess;
let logFilePath;

// Setup File Logging for Launcher Debugging
function logToFile(message) {
    try {
        if (!logFilePath) {
            // Lazy load path to ensure app is ready enough (though usually safe)
            logFilePath = path.join(app.getPath('userData'), 'launcher_debug.log');
        }
        const timestamp = new Date().toISOString();
        const logLine = `[${timestamp}] ${message}\n`;
        fs.appendFileSync(logFilePath, logLine);
    } catch (err) {
        console.error("Failed to write to log file:", err);
    }
}

// Log initial startup info
try {
    logToFile("--- Kiroshi Launcher Session Started ---");
    logToFile(`App Path: ${app.getAppPath()}`);
    logToFile(`Resources Path: ${process.resourcesPath}`);
} catch (e) {
    console.error("Initial logging failed:", e);
}

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
            logToFile("Killing existing Kiroshi process...");
            console.log("Killing existing Kiroshi process...");
            if (process.platform === 'win32') {
                 spawn("taskkill", ["/pid", kiroshiProcess.pid, '/f', '/t']);
            } else {
                kiroshiProcess.kill();
            }
        } catch (e) {
            logToFile(`Error killing process: ${e.message}`);
            console.error("Error killing process:", e);
        }
        kiroshiProcess = null;
    }
}

function startKiroshi() {
    console.log("Launching Kiroshi Streamlit backend...");
    logToFile("Launching Kiroshi Streamlit backend...");

    // Determine the root directory for the Python script
    // If packaged, we expect the python files to be in resources/python_core
    // If dev, we expect them in the parent directory of JavaSTools
    let pythonCoreDir;
    if (app.isPackaged) {
        pythonCoreDir = path.join(process.resourcesPath, 'python_core');
    } else {
        pythonCoreDir = path.resolve(__dirname, '..');
    }

    logToFile(`Python Core Directory resolved to: ${pythonCoreDir}`);
    console.log(`Python Core Directory: ${pythonCoreDir}`);

    if (!fs.existsSync(pythonCoreDir)) {
         const errorMsg = `ERROR: Python core directory not found at ${pythonCoreDir}`;
         logToFile(errorMsg);
         console.error(errorMsg);
         if (mainWindow) {
             mainWindow.webContents.send('kiroshi-startup-error', `Core directory missing: ${pythonCoreDir}`);
         }
         return;
    }

    // Check if on Windows
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    logToFile(`Python Command: ${pythonCmd}`);

    try {
        logToFile("Spawning python process...");
        kiroshiProcess = spawn(pythonCmd, ['-m', 'streamlit', 'run', 'case_documentation_app.py', '--server.headless', 'true'], {
            cwd: pythonCoreDir,
            shell: true,
            // Ensure stdio is captured
            stdio: ['ignore', 'pipe', 'pipe']
        });

        if (kiroshiProcess.pid) {
             logToFile(`Process spawned. PID: ${kiroshiProcess.pid}`);
        } else {
             logToFile("Process spawn failed (no PID).");
        }

        let stderrBuffer = "";

        if (kiroshiProcess) {
            kiroshiProcess.stdout.on('data', (data) => {
                const msg = data.toString();
                console.log(`Kiroshi: ${msg}`);
                // Optional: log first few lines to verify startup
                if (msg.includes("http://localhost")) {
                    logToFile("Streamlit started successfully (url detected).");
                }
            });

            kiroshiProcess.stderr.on('data', (data) => {
                const msg = data.toString();
                stderrBuffer += msg;
                // Limit buffer size to avoid memory issues if it spews
                if (stderrBuffer.length > 5000) stderrBuffer = stderrBuffer.substring(stderrBuffer.length - 5000);

                console.error(`Kiroshi Error: ${msg}`);
                logToFile(`STDERR: ${msg.trim()}`);
            });

            kiroshiProcess.on('error', (err) => {
                 const errorMsg = `Failed to start Kiroshi process: ${err.message}`;
                 logToFile(errorMsg);
                 console.error(errorMsg);
                 if (mainWindow) {
                     mainWindow.webContents.send('kiroshi-startup-error', `Spawn error: ${err.message}`);
                 }
            });

            kiroshiProcess.on('close', (code) => {
                const exitMsg = `Kiroshi process exited with code ${code}`;
                logToFile(exitMsg);
                console.log(exitMsg);

                if (code !== 0 && code !== null) {
                     let userMsg = `Process exited with code ${code}.`;
                     if (stderrBuffer) {
                         // Clean up the error message for display
                         // Grab the last meaningful line
                         const lines = stderrBuffer.trim().split('\n');
                         const lastLine = lines[lines.length - 1];
                         userMsg += ` Error: ${lastLine}`;
                     } else {
                         userMsg += " See launcher_debug.log for details.";
                     }

                     if (mainWindow) {
                         mainWindow.webContents.send('kiroshi-startup-error', userMsg);
                     }
                }
            });
        }
    } catch (e) {
        logToFile(`Exception starting Kiroshi: ${e.message}`);
        console.error("Exception starting Kiroshi:", e);
        if (mainWindow) {
            mainWindow.webContents.send('kiroshi-startup-error', `Exception: ${e.message}`);
        }
    }
}

// --- IPC Handlers ---

ipcMain.on('restart-kiroshi', (event) => {
    logToFile("Received restart-kiroshi request");
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
