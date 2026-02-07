import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Determine database directory
  let dbDir = process.env.KIROSHI_DATABASE_DIR;
  if (!dbDir) {
    if (process.platform === 'win32') {
      dbDir = 'C:/ProgramFiles/KiroshiDatabase';
    } else {
      dbDir = path.join(os.homedir(), 'KiroshiDatabase');
    }
  }

  // Ensure directory exists
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  // Create settings.json with tutorial completed
  const settingsPath = path.join(dbDir, 'settings.json');
  const settings = {
    tutorial_completed: true,
    frutiger_aero_mode: false,
    dark_mode_enabled: false
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Global setup: Created settings.json at ${settingsPath}`);
}
