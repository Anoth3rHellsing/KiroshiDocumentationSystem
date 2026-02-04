import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  const settingsDir = path.join(os.homedir(), 'KiroshiDatabase');
  const settingsFile = path.join(settingsDir, 'settings.json');

  if (!fs.existsSync(settingsDir)) {
    fs.mkdirSync(settingsDir, { recursive: true });
  }

  const settings = {
    tutorial_completed: true,
    tutorial_metadata: { completed: true }
  };

  fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2));
  console.log(`Global setup: Wrote tutorial completion settings to ${settingsFile}`);
}

export default globalSetup;
