import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  const homeDir = os.homedir();
  // Match python logic for linux
  const dbDir = path.join(homeDir, 'KiroshiDatabase');

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  console.log(`[GlobalSetup] Ensuring tutorial is skipped via settings at ${settingsPath}`);

  // Minimal settings to skip tutorial
  const settings = {
    "tutorial_completed": true,
    "tutorial_metadata": {
      "completed": true
    }
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), { encoding: 'utf-8' });
}
