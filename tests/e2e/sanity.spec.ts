import { test, expect } from '@playwright/test';

test('Sanity check', async ({ page }) => {
  // This is a dummy test to ensure Playwright has something to run.
  // It doesn't actually interact with the app, just asserts true.
  expect(true).toBe(true);
});
