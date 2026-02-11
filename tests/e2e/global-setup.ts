import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup starting...');
  // Add any global setup logic here if needed in the future
  console.log('Global setup completed.');
}

export default globalSetup;
