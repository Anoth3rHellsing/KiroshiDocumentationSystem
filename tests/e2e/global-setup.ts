import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Determine database directory
  let dbDir = process.env.KIROSHI_DATABASE_DIR;

  if (!dbDir) {
    if (process.platform === 'win32') {
      dbDir = 'C:/ProgramFiles/KiroshiDatabase';
    } else {
      dbDir = path.join(os.homedir(), 'KiroshiDatabase');
    }
  }

  // Ensure directory exists
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  // Path to settings.json
  const settingsPath = path.join(dbDir, 'settings.json');

  let settings: any = {};
  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
    } catch (e) {
      console.warn('Failed to parse existing settings.json, starting fresh.');
    }
  }

  // Bypass tutorial
  settings.tutorial_completed = true;

  // Persist settings
  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`Global setup: tutorial_completed set to true in ${settingsPath}`);
}
