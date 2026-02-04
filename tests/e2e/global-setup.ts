import fs from 'fs';
import path from 'path';
import { FullConfig } from '@playwright/test';

export default async function globalSetup(config: FullConfig) {
  // Determine the database directory based on OS (simulated for test environment)
  const homeDir = process.env.HOME || process.env.USERPROFILE || '.';
  let dbDir = path.join(homeDir, 'KiroshiDatabase');

  if (process.platform === 'win32') {
      dbDir = 'C:\\ProgramFiles\\KiroshiDatabase';
  }

  // In CI or local test, we might want to use a local path if not running as admin/on windows
  // The app uses Path.home() / "KiroshiDatabase" on non-windows.
  // We'll stick to the home dir version for safety in linux CI.
  if (process.platform !== 'win32') {
      dbDir = path.join(homeDir, 'KiroshiDatabase');
  }

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  const settings = {
    "tutorial_completed": true,
    "tutorial_metadata": { "completed": true }
  };

  try {
      fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
      console.log(`Global setup: Created settings.json at ${settingsPath}`);
  } catch (e) {
      console.error(`Global setup: Failed to create settings.json at ${settingsPath}`, e);
  }
}
