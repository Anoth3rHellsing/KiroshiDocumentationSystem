import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

async function globalSetup(config: FullConfig) {
  // Set up environment variables
  // If KIROSHI_DATABASE_DIR is not set, use a temporary directory for tests
  if (!process.env.KIROSHI_DATABASE_DIR) {
      process.env.KIROSHI_DATABASE_DIR = path.resolve('./tests/e2e_temp_db');
  }

  // Ensure the directory exists
  if (!fs.existsSync(process.env.KIROSHI_DATABASE_DIR)) {
    fs.mkdirSync(process.env.KIROSHI_DATABASE_DIR, { recursive: true });
  }

  // Create settings.json with tutorial_completed: true to bypass tutorial
  const settingsPath = path.join(process.env.KIROSHI_DATABASE_DIR, 'settings.json');
  const settings = {
    tutorial_completed: true,
    tutorial_completed_at: new Date().toISOString(),
    tutorial_completion_type: "skip",
    tutorial_metadata: {
        completed: true
    }
  };
  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));

  console.log(`Global setup complete. Database dir: ${process.env.KIROSHI_DATABASE_DIR}`);
}

export default globalSetup;
