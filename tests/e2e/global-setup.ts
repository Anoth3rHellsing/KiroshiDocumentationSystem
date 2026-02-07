import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  // Set up KIROSHI_DATABASE_DIR based on env or defaults
  const dbDir = process.env.KIROSHI_DATABASE_DIR || (
    os.platform() === 'win32'
      ? 'C:\\ProgramFiles\\KiroshiDatabase'
      : path.join(os.homedir(), 'KiroshiDatabase')
  );

  if (!fs.existsSync(dbDir)) {
    try {
      fs.mkdirSync(dbDir, { recursive: true });
    } catch (err) {
      console.warn(`Could not create database directory at ${dbDir}:`, err);
      // Fallback or ignore if permissions fail (e.g. in restricted CI)
      // Ideally we should fail, but let's be robust.
    }
  }

  // Set tutorial_completed to true in settings.json to skip onboarding
  const settingsPath = path.join(dbDir, 'settings.json');
  let settings: any = {};
  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
    } catch (e) {
      console.error('Failed to parse settings.json', e);
    }
  }

  settings.tutorial_completed = true;

  try {
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    console.log('Global setup: Tutorial completed set to true.');
  } catch (err) {
    console.warn('Global setup: Failed to write settings.json:', err);
  }
}

export default globalSetup;
