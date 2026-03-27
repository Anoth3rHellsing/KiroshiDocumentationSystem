import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup() {
  const dbDir = path.join(os.homedir(), 'KiroshiDatabase');
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  if (!fs.existsSync(settingsPath)) {
    const defaultSettings = {
      tutorial_completed: true
    };
    fs.writeFileSync(settingsPath, JSON.stringify(defaultSettings, null, 2), 'utf-8');
  } else {
    try {
      const data = fs.readFileSync(settingsPath, 'utf-8');
      const settings = JSON.parse(data);
      if (!settings.tutorial_completed) {
        settings.tutorial_completed = true;
        fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
      }
    } catch (error) {
      console.error('Failed to parse or update settings.json:', error);
    }
  }
}

export default globalSetup;
