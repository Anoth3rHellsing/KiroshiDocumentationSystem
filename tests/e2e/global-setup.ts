
import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Determine database directory based on OS, matching Python logic
  let databaseDir;
  if (process.platform === 'win32') {
    databaseDir = 'C:/ProgramFiles/KiroshiDatabase';
  } else {
    databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  }

  // Ensure directory exists
  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  // Create or update settings.json to bypass tutorial
  const settingsPath = path.join(databaseDir, 'settings.json');
  let settings: any = {};
  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
    } catch (e) {
      console.warn('Failed to parse existing settings.json, overwriting.');
    }
  }

  // Set tutorial as completed
  settings.tutorial_completed = true;
  // Also set legacy field just in case
  settings.tutorial_completed_at = new Date().toISOString();

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`Global setup: tutorial_completed set to true in ${settingsPath}`);
}
