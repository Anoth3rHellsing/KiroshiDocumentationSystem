import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  // Add any global setup logic here if needed
  console.log('Global setup starting...');
}

export default globalSetup;
