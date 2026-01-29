import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // This test exists to ensure the test runner has something to execute.
  expect(true).toBe(true);
});
