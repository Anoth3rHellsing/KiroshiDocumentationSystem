import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  console.log('Running global setup...');

  // Determine database directory (mimic logic from python app)
  let dbDir = process.env.KIROSHI_DATABASE_DIR;
  if (!dbDir) {
    if (os.platform() === 'win32') {
      dbDir = 'C:/ProgramFiles/KiroshiDatabase';
    } else {
      dbDir = path.join(os.homedir(), 'KiroshiDatabase');
    }
  }

  // Ensure directory exists
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  let settings: any = {};

  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
    } catch (e) {
      console.warn('Failed to parse existing settings.json', e);
    }
  }

  // Bypass tutorial
  settings.tutorial_completed = true;
  settings.tutorial_completed_at = new Date().toISOString();
  settings.tutorial_completion_type = 'automated_test';

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`Global setup complete. Settings updated at ${settingsPath}`);
}
