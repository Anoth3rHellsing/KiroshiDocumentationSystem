import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup: Starting...');
  // Add any global setup logic here if needed (e.g., seeding DB, starting external services)
  console.log('Global setup: Completed.');
}

export default globalSetup;
