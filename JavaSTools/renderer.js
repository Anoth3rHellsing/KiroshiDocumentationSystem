const { getKiroshiMessage } = require('./companion_data.js');
const { shell } = require('electron');

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
