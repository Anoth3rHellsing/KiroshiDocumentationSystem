import * as os from 'os';
import * as path from 'path';

export default async function globalSetup() {
    // This function is required by Playwright config
    // We export a default async function.
    const KiroshiDatabase = path.join(os.homedir(), 'KiroshiDatabase');
    console.log(`Global setup initialized for ${KiroshiDatabase}`);
}
