import { type FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup running...');
  // Add any setup steps here if needed
}

export default globalSetup;
