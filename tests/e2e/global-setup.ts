
import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup...');
  // Add any global setup logic here if needed
}

export default globalSetup;
