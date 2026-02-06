import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  // Determine database directory
  let dbDir = process.env.KIROSHI_DATABASE_DIR;
  if (!dbDir) {
    if (process.platform === 'win32') {
      dbDir = 'C:\\ProgramFiles\\KiroshiDatabase';
    } else {
      dbDir = path.join(os.homedir(), 'KiroshiDatabase');
    }
  }

  // Ensure directory exists
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  // Set tutorial_completed to true in settings.json
  const settingsPath = path.join(dbDir, 'settings.json');
  let settings: any = {};
  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
    } catch (e) {
      console.warn('Failed to parse settings.json, creating new one.');
    }
  }

  settings.tutorial_completed = true;

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`Global setup: Tutorial completed set in ${settingsPath}`);
}

export default globalSetup;
