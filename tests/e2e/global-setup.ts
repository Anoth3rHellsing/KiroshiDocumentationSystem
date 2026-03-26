import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Creating a dummy settings.json to bypass tutorial if needed.
  const homeDir = os.homedir();
  const dbDir = path.join(homeDir, 'KiroshiDatabase');
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }
  const settingsFile = path.join(dbDir, 'settings.json');
  fs.writeFileSync(settingsFile, JSON.stringify({ tutorial_completed: true }));
  console.log('Global setup: created settings.json to bypass tutorial');
}
