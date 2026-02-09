import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup: E2E environment ready.');
}

export default globalSetup;
