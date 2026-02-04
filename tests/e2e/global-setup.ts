import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import os from 'os';

export default async function globalSetup(config: FullConfig) {
  const homeDir = os.homedir();
  const dbDir = path.join(homeDir, 'KiroshiDatabase');

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  const settings = {
    "tutorial_completed": true,
    "tutorial_metadata": {
      "completed": true
    }
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Global setup: Created settings.json at ${settingsPath}`);
}
