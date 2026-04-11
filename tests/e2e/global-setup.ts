import { chromium, FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  const browser = await chromium.launch();
  // We can add any necessary global setup here, but an empty function is enough to satisfy Playwright
  await browser.close();
}

export default globalSetup;
