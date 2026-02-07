import fs from 'fs';
import path from 'path';
import os from 'os';

async function globalSetup() {
  const isWindows = os.platform() === 'win32';
  let databaseDir = process.env.KIROSHI_DATABASE_DIR;

  if (!databaseDir) {
    if (isWindows) {
      databaseDir = 'C:/ProgramFiles/KiroshiDatabase';
    } else {
      databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
    }
  }

  // Ensure directory exists
  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  const settingsPath = path.join(databaseDir, 'settings.json');
  let settings = {};

  if (fs.existsSync(settingsPath)) {
    try {
      const content = fs.readFileSync(settingsPath, 'utf-8');
      settings = JSON.parse(content);
    } catch (e) {
      console.warn('Failed to parse existing settings.json, starting fresh.');
    }
  }

  // Bypass tutorial
  settings['tutorial_completed'] = true;

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`Global setup: Wrote settings to ${settingsPath}`);
}

export default globalSetup;
