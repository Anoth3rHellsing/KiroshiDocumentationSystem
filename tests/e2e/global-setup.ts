
import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import os from 'os';

export default async function globalSetup(config: FullConfig) {
  const homeDir = os.homedir();
  const databaseDir = path.join(homeDir, 'KiroshiDatabase');
  const settingsPath = path.join(databaseDir, 'settings.json');

  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  const settings = {
    "tutorial_completed": true,
    "tutorial_metadata": {
      "completed": true
    }
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`Global setup: Wrote settings to ${settingsPath}`);
}
