import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  let dbDir = process.env.KIROSHI_DATABASE_DIR;
  if (!dbDir) {
    if (process.platform === 'win32') {
      dbDir = 'C:/ProgramFiles/KiroshiDatabase';
    } else {
      dbDir = path.join(os.homedir(), 'KiroshiDatabase');
    }
  }

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  let settings: any = {};
  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
    } catch (e) {
      console.error('Failed to parse existing settings.json', e);
    }
  }

  // Bypass the onboarding tutorial
  settings.tutorial_completed = true;

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`Global setup: Enforced tutorial_completed=true in ${settingsPath}`);
}

export default globalSetup;
