import { test, expect } from '@playwright/test';

test('basic pass', async ({ page }) => {
  expect(true).toBe(true);
});
