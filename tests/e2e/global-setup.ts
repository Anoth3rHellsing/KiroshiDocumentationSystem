import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

async function globalSetup(config: FullConfig) {
  // Use a temporary directory for testing if not specified, to avoid permission issues
  const dbDir = process.env.KIROSHI_DATABASE_DIR || path.join(process.cwd(), 'temp_db');

  // Ensure the app knows where to look if we are overriding it
  process.env.KIROSHI_DATABASE_DIR = dbDir;

  const settingsPath = path.join(dbDir, 'settings.json');

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settings = {
    tutorial_completed: true,
    enable_holiday_theme: false, // stabilize visual tests
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Global setup: Created settings at ${settingsPath}`);
}

export default globalSetup;
