import { type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Determine database directory (mimic app logic or use env var)
  // App uses ~/KiroshiDatabase by default or KIROSHI_DATABASE_DIR env var
  // In CI, we likely want to set up a clean state.

  let dbDir = process.env.KIROSHI_DATABASE_DIR;
  if (!dbDir) {
      if (os.platform() === 'win32') {
          dbDir = path.join(os.homedir(), 'KiroshiDatabase');
      } else {
          dbDir = path.join(os.homedir(), 'KiroshiDatabase');
      }
  }

  // Ensure directory exists
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');

  // Write settings to bypass tutorial
  const settings = {
    "tutorial_completed": true,
    "tutorial_metadata": {
      "completed": true
    }
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`[Global Setup] Created settings.json at ${settingsPath} to bypass tutorial.`);
}
