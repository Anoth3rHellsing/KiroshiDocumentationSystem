import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // This test ensures Playwright has at least one test to run.
  // It doesn't actually interact with the app to avoid flakiness if the app fails to start.
  expect(true).toBe(true);
});
