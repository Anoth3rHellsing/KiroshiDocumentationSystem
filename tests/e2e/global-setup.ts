import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  // Setup code if needed, e.g. checking if server is up
  // For now, we rely on the CI script to start the server.
}

export default globalSetup;
