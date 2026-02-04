import { type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Support KIROSHI_DB_DIR environment variable for test isolation.
  // This matches the logic added to case_documentation_app.py.
  let dbDir = process.env.KIROSHI_DB_DIR;

  if (!dbDir) {
      if (os.platform() === 'win32') {
          dbDir = 'C:\\ProgramFiles\\KiroshiDatabase';
      } else {
          dbDir = path.join(os.homedir(), 'KiroshiDatabase');
      }
      console.warn(`[Global Setup] KIROSHI_DB_DIR not set, using default: ${dbDir}. To avoid overwriting user settings, set KIROSHI_DB_DIR.`);
  }

  const settingsPath = path.join(dbDir, 'settings.json');

  if (!fs.existsSync(dbDir)) {
    try {
        fs.mkdirSync(dbDir, { recursive: true });
    } catch (err) {
        console.error(`[Global Setup] Failed to create database directory at ${dbDir}:`, err);
        throw err;
    }
  }

  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
      completed: true
    }
  };

  try {
      fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
      console.log(`[Global Setup] Wrote settings to ${settingsPath}`);
  } catch (err) {
      console.error(`[Global Setup] Failed to write settings to ${settingsPath}:`, err);
      throw err;
  }
}
