import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // Wait for the app to load
  await page.goto('/');

  // Wait for the main app container
  await page.waitForSelector('[data-testid="stAppViewContainer"]', { timeout: 30000 });

  // Basic title check (Streamlit apps usually have the filename or configured title)
  // We just check it's not an error page
  const content = await page.content();
  expect(content).not.toContain('Streamlit server failed to start');
});
