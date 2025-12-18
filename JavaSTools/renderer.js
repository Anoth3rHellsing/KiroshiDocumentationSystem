const { getKiroshiMessage } = require('./companion_data.js');
const { shell, ipcRenderer } = require('electron');

// --- Launcher Logic ---
const launcherOverlay = document.getElementById('kiroshi-launcher-overlay');
const btnLaunch = document.getElementById('btn-launch-kiroshi');
const statusText = document.getElementById('launcher-status');
const kiroshiView = document.getElementById('view-kiroshi');

btnLaunch.addEventListener('click', () => {
    statusText.innerText = "Killing old processes and restarting Kiroshi Backend...";
    btnLaunch.disabled = true;
    btnLaunch.style.opacity = "0.5";

    // Trigger restart in main process
    ipcRenderer.send('restart-kiroshi');
});

ipcRenderer.on('kiroshi-restarted', () => {
    statusText.innerText = "Backend restarted. Waiting for server...";

    // Wait a bit for Streamlit to actually bind to port
    setTimeout(() => {
        statusText.innerText = "Loading UI...";
        kiroshiView.reload();

        // Hide overlay after a moment (or rely on load event?)
        // Since we can't easily detect 'ready' from http, we'll just hide it
        // and let the user see the loading spinner of the browser/streamlit.
        // But if it fails again, they might need the button.
        // So we will hide it, but if load fails, maybe show it?

        // For now, let's just hide it so they can see the Streamlit 'Please wait...' screen
        launcherOverlay.classList.add('hidden');

        // Re-enable button for next time
        btnLaunch.disabled = false;
        btnLaunch.style.opacity = "1";
        statusText.innerText = "System is ready to launch.";

    }, 3000);
});

// Handle Kiroshi Startup Errors from Main Process
ipcRenderer.on('kiroshi-startup-error', (event, errorMessage) => {
    console.error("Kiroshi Startup Error:", errorMessage);
    launcherOverlay.classList.remove('hidden');

    // Make the error visible to the user
    statusText.innerText = `Startup Error: ${errorMessage}`;
    statusText.style.color = "#ff6b6b"; // Reddish color for error

    // Re-enable button
    btnLaunch.disabled = false;
    btnLaunch.style.opacity = "1";
});

// Optional: Show overlay if webview fails to load?
kiroshiView.addEventListener('did-fail-load', (e) => {
    // Only if it's main frame
    if (e.isMainFrame) {
        console.log("Kiroshi failed to load:", e);
        launcherOverlay.classList.remove('hidden');
        // Do not overwrite specific startup errors if we already showed one
        if (!statusText.innerText.startsWith("Startup Error")) {
             statusText.innerText = "Connection failed. Please launch again.";
             statusText.style.color = "#a5b4fc"; // Reset color
        }
    }
});

// --- Motivational Companion Logic ---
function updateCompanionMessage() {
    const msgObj = getKiroshiMessage();
    const msgElement = document.getElementById('companion-message');
    msgElement.innerText = msgObj.text;

    if (msgObj.type === 'ai') {
        msgElement.style.color = '#a5b4fc'; // Light indigo for AI voice
    } else {
        msgElement.style.color = '#e2e8f0'; // Standard text
    }
}

// Rotate message every 45 seconds (or on click)
setInterval(updateCompanionMessage, 45000);
document.getElementById('companion-message').addEventListener('click', updateCompanionMessage);
updateCompanionMessage(); // Initial load

// --- Tab Management Logic ---
let tabs = [
    { id: 'kiroshi', title: 'Kiroshi System', url: 'http://localhost:8501' }
];
let activeTabId = 'kiroshi';

function switchTab(tabId) {
    activeTabId = tabId;

    // Update Tab UI
    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
    const tabEl = document.getElementById(`tab-${tabId}`);
    if (tabEl) tabEl.classList.add('active');

    // Update Webview Visibility
    document.querySelectorAll('webview').forEach(el => el.classList.remove('active-view'));
    const viewEl = document.getElementById(`view-${tabId}`);
    if (viewEl) viewEl.classList.add('active-view');

    // Hide menu if open
    document.getElementById('new-tab-menu').classList.add('hidden');
}

function addTab(url, title) {
    const tabId = 'tab_' + Date.now();
    const shortTitle = title || new URL(url).hostname;

    tabs.push({ id: tabId, title: shortTitle, url: url });

    // Create Tab Element
    const tabContainer = document.getElementById('dynamic-tabs');
    const tabEl = document.createElement('div');
    tabEl.className = 'tab';
    tabEl.id = `tab-${tabId}`;
    tabEl.innerHTML = `
        <i class="fa-solid fa-globe"></i> ${shortTitle}
        <i class="fa-solid fa-xmark tab-close" onclick="closeTab('${tabId}', event)"></i>
    `;
    tabEl.onclick = () => switchTab(tabId);
    tabContainer.appendChild(tabEl);

    // Create Webview Element
    const contentArea = document.getElementById('content-area');
    const webview = document.createElement('webview');
    webview.id = `view-${tabId}`;
    webview.src = url;
    webview.allowpopups = true;
    // Important: User wants SSL bypass. Main process handles certificate-error globally,
    // but webview might need specific attributes or just rely on the app switch.

    contentArea.appendChild(webview);

    switchTab(tabId);
}

function closeTab(tabId, event) {
    event.stopPropagation(); // Prevent tab switching when closing

    // Remove from array
    tabs = tabs.filter(t => t.id !== tabId);

    // Remove DOM elements
    document.getElementById(`tab-${tabId}`).remove();
    document.getElementById(`view-${tabId}`).remove();

    // If we closed the active tab, switch to the previous one (or Kiroshi)
    if (activeTabId === tabId) {
        const lastTab = tabs[tabs.length - 1];
        switchTab(lastTab ? lastTab.id : 'kiroshi');
    }
}

function showNewTabMenu() {
    const menu = document.getElementById('new-tab-menu');
    menu.classList.toggle('hidden');
}

function addCustomTab() {
    const input = document.getElementById('custom-url');
    let url = input.value.trim();
    if (!url) return;

    if (!url.startsWith('http')) {
        url = 'https://' + url;
    }

    addTab(url);
    input.value = '';
}

// --- Window Controls ---
// Since we set frame: false in main.js, we need custom window controls
// We can use remote or ipcRenderer to control the window.
// For safety in this prototype context without remote module, we'll skip complex IPC for now
// or add basic ones if window.close is blocked.
// Electron 12+ requires IPC for this usually.

document.getElementById('close-btn').addEventListener('click', () => {
    window.close(); // Works if contextIsolation: false is set in main.js
});
document.getElementById('min-btn').addEventListener('click', () => {
    // Requires ipc call usually
    // window.minimize();
});
document.getElementById('max-btn').addEventListener('click', () => {
   // window.maximize();
});
