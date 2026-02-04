import fs from 'fs';
import path from 'path';
import os from 'os';
import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  const databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  const settingsPath = path.join(databaseDir, 'settings.json');
  const settings = {
    "tutorial_completed": true,
    "tutorial_metadata": {
      "completed": true
    }
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Created settings file at ${settingsPath}`);
}

export default globalSetup;
