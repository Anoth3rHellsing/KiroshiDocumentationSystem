import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Ensure KiroshiDatabase/settings.json exists with tutorial completed
  // Respect KIROSHI_DATABASE_DIR env var if set, otherwise default to home
  let dbDir: string;

  if (process.env.KIROSHI_DATABASE_DIR) {
    dbDir = path.resolve(process.env.KIROSHI_DATABASE_DIR);
    console.log(`Global setup: Using configured database directory: ${dbDir}`);
  } else {
    const homeDir = os.homedir();
    dbDir = path.join(homeDir, 'KiroshiDatabase');
    console.log(`Global setup: Using default database directory: ${dbDir}`);
  }

  const settingsPath = path.join(dbDir, 'settings.json');

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
      completed: true,
    },
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Global setup: Wrote tutorial completion settings to ${settingsPath}`);
}
