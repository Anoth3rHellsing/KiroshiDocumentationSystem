import { chromium, FullConfig } from '@playwright/test';
import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';

async function globalSetup(config: FullConfig) {
  // Automatically configure the app to bypass the tutorial via settings.json
  const databaseDir = path.join(os.homedir(), 'KiroshiDatabase');

  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  const settingsFile = path.join(databaseDir, 'settings.json');
  fs.writeFileSync(settingsFile, JSON.stringify({ tutorial_completed: true }, null, 2), 'utf-8');
}

export default globalSetup;
