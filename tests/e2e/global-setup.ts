import { FullConfig } from '@playwright/test';
import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';

async function globalSetup(config: FullConfig) {
  const dbDir = path.join(os.homedir(), 'KiroshiDatabase');

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  const settings = { "tutorial_completed": true };

  fs.writeFileSync(settingsPath, JSON.stringify(settings));
}

export default globalSetup;
