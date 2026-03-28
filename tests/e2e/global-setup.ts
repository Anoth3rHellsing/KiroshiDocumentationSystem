import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  const dbDir = path.join(os.homedir(), 'KiroshiDatabase');
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }
  const settingsPath = path.join(dbDir, 'settings.json');
  fs.writeFileSync(settingsPath, JSON.stringify({ tutorial_completed: true }));
}

export default globalSetup;
