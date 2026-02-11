import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  const homeDir = os.homedir();
  const databaseDir = path.join(homeDir, 'KiroshiDatabase');

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
  console.log(`[Global Setup] Wrote tutorial bypass to ${settingsPath}`);
}

export default globalSetup;
