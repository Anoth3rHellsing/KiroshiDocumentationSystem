import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup...');
  // Add any necessary setup steps here
}

export default globalSetup;
