import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';

export default async function globalSetup() {
  const dbDir = path.join(os.homedir(), 'KiroshiDatabase');
  fs.mkdirSync(dbDir, { recursive: true });
  fs.writeFileSync(path.join(dbDir, 'settings.json'), JSON.stringify({ tutorial_completed: true }));
}
