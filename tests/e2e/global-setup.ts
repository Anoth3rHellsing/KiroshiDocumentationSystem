import { FullConfig } from '@playwright/test';
import { homedir } from 'os';
import { writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';

async function globalSetup(config: FullConfig) {
  // Bypass tutorial to avoid complex UI interactions during basic E2E verification
  const kiroshiDir = join(homedir(), '.kiroshi');
  mkdirSync(kiroshiDir, { recursive: true });
  writeFileSync(join(kiroshiDir, 'settings.json'), JSON.stringify({ tutorial_completed: true }));
}

export default globalSetup;
