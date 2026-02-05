import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  const dbPath = path.join(os.homedir(), 'KiroshiDatabase');
  if (!fs.existsSync(dbPath)) {
    fs.mkdirSync(dbPath, { recursive: true });
  }

  const settingsPath = path.join(dbPath, 'settings.json');
  const settings = {
    "tutorial_completed": true,
    "tutorial_metadata": {
      "completed": true
    }
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`[Global Setup] Wrote tutorial bypass settings to ${settingsPath}`);
}

export default globalSetup;
