import { FullConfig } from '@playwright/test';
import * as os from 'os';
import * as fs from 'fs';
import * as path from 'path';

async function globalSetup(config: FullConfig) {
  const KiroshiDir = path.join(os.homedir(), 'KiroshiData');
  if (!fs.existsSync(KiroshiDir)) {
    fs.mkdirSync(KiroshiDir, { recursive: true });
  }

  const settingsPath = path.join(KiroshiDir, 'settings.json');
  fs.writeFileSync(settingsPath, JSON.stringify({ tutorial_completed: true }));
}

export default globalSetup;
