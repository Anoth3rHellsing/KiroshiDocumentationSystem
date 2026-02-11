import { type FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup...');
  // No special setup required for now
}

export default globalSetup;
