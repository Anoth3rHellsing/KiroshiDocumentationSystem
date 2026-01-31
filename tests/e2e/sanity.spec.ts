import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // This test merely ensures the test runner finds a test and passes.
  expect(true).toBe(true);
});
