import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  const isWindows = os.platform() === 'win32';
  let databaseDir;

  if (isWindows) {
    // Usually C:/ProgramFiles/KiroshiDatabase but we might not have permissions in CI?
    // The app defaults to home dir on non-Windows.
    // In the CI environment (likely Linux), it uses home.
    databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  } else {
    databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  }

  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  const settingsPath = path.join(databaseDir, 'settings.json');
  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
      completed: true,
    },
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Global setup: Wrote tutorial completion settings to ${settingsPath}`);
}
