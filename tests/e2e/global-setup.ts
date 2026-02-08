import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  // Setup logic if needed, e.g. ensuring server is up
  console.log('Global setup running...');
}

export default globalSetup;
