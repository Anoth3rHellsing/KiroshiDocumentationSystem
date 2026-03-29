import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';

async function globalSetup() {
  const KiroshiDatabase = path.join(os.homedir(), 'KiroshiDatabase');
  fs.mkdirSync(KiroshiDatabase, { recursive: true });

  const settingsPath = path.join(KiroshiDatabase, 'settings.json');
  fs.writeFileSync(settingsPath, JSON.stringify({ tutorial_completed: true }));
}

export default globalSetup;
