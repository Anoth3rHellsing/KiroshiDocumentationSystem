import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  // Determine KiroshiDatabase path
  let databaseDir = '';
  if (process.platform === 'win32') {
    databaseDir = 'C:\\ProgramFiles\\KiroshiDatabase';
  } else {
    databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  }

  // Ensure directory exists
  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  const settingsPath = path.join(databaseDir, 'settings.json');

  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
      completed: true
    }
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Global setup: Wrote tutorial_completed=true to ${settingsPath}`);
}

export default globalSetup;
