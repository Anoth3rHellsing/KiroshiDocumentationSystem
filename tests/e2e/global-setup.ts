import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  // Determine database directory
  // Prioritize environment variable for safety/CI configuration
  let dbDir = process.env.KIROSHI_DATABASE_DIR;

  if (!dbDir) {
    if (process.platform === 'win32') {
      dbDir = 'C:\\ProgramFiles\\KiroshiDatabase';
    } else {
      dbDir = path.join(os.homedir(), 'KiroshiDatabase');
    }
  }

  // Ensure directory exists
  try {
    if (!fs.existsSync(dbDir)) {
      fs.mkdirSync(dbDir, { recursive: true });
    }
  } catch (error) {
    console.warn(`Global setup: Unable to create database directory at ${dbDir}. Check permissions.`);
    // We continue, as the test might fail later but we don't want to crash setup if possible,
    // though writing settings.json will likely fail next.
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  let settings: any = {};

  if (fs.existsSync(settingsPath)) {
    try {
      const content = fs.readFileSync(settingsPath, 'utf-8');
      if (content.trim()) {
        settings = JSON.parse(content);
      }
    } catch (e) {
      console.error('Failed to parse existing settings.json', e);
    }
  }

  // Bypass tutorial to ensure tests start at dashboard
  settings['tutorial_completed'] = true;

  try {
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
    console.log(`Global setup: Enforced tutorial_completed=true in ${settingsPath}`);
  } catch (error) {
    console.error(`Global setup: Failed to write settings to ${settingsPath}. Tests may fail if tutorial is shown.`, error);
  }
}

export default globalSetup;
