import { type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  // Ensure KiroshiDatabase directory exists in user's home directory
  const dbDir = path.join(os.homedir(), 'KiroshiDatabase');
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  // Create or update settings.json to bypass tutorial
  const settingsPath = path.join(dbDir, 'settings.json');
  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
      completed: true,
    },
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`[Global Setup] Wrote tutorial bypass settings to ${settingsPath}`);
}

export default globalSetup;
