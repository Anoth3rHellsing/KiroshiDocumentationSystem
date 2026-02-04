import fs from 'fs';
import path from 'path';
import { FullConfig } from '@playwright/test';

export default async function globalSetup(config: FullConfig) {
  const home = process.env.HOME || process.env.USERPROFILE || '.';
  const dbDir = path.join(home, 'KiroshiDatabase');

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  // Write settings to bypass tutorial
  fs.writeFileSync(settingsPath, JSON.stringify({
    "tutorial_completed": true,
    "tutorial_metadata": {
        "completed": true,
        "visited": []
    }
  }, null, 2));
  console.log(`Global setup: wrote settings to ${settingsPath}`);
}
