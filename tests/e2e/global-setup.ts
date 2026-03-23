import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  // Bypassing tutorial as mentioned in memory:
  // "Automated UI testing of the initial application state requires bypassing the tutorial by creating a settings.json file with {"tutorial_completed": true} in the configured storage directory (using os.homedir() for cross-platform compatibility)."

  const dbDir = path.join(os.homedir(), 'KiroshiDatabase');
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  try {
    const existing = fs.existsSync(settingsPath) ? JSON.parse(fs.readFileSync(settingsPath, 'utf8')) : {};
    existing.tutorial_completed = true;
    fs.writeFileSync(settingsPath, JSON.stringify(existing, null, 2));
    console.log('Setup: Wrote tutorial_completed=true to settings.json');
  } catch (err) {
    console.error('Setup error writing settings.json:', err);
  }
}

export default globalSetup;
