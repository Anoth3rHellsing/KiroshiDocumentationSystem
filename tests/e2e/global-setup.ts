import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

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

  try {
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    console.log(`Global setup: Wrote settings to ${settingsPath}`);
  } catch (error) {
    console.error(`Global setup failed to write settings: ${error}`);
  }
}
