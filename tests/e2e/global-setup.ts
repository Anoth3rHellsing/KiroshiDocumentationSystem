import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup...');
  // Add any setup steps here if needed, e.g., checking if server is up
}

export default globalSetup;
