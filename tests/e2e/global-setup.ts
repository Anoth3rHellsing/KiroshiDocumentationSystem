import os from 'os';
import fs from 'fs';
import path from 'path';

export default async function globalSetup() {
  const settingsDir = process.platform === 'win32'
    ? path.join(process.env.PROGRAMDATA || 'C:\\ProgramData', 'Kiroshi Documentation', 'KiroshiDatabase')
    : path.join(os.homedir(), 'KiroshiDatabase');

  fs.mkdirSync(settingsDir, { recursive: true });

  const settingsFile = path.join(settingsDir, 'settings.json');
  fs.writeFileSync(settingsFile, JSON.stringify({ tutorial_completed: true }));
}
