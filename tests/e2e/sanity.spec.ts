import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // This test just ensures the runner has something to execute.
  expect(true).toBe(true);
});
