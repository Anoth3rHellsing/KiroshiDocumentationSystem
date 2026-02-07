import { test, expect } from '@playwright/test';

test('sanity check: app loads', async ({ page }) => {
  // Go to the base URL (defaults to http://127.0.0.1:8501 in config)
  await page.goto('/');

  // Wait for the main Streamlit container to appear
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible();

  // Verify the 'Dashboard' tab is present (it's usually a button with role 'tab')
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();

  // Verify a specific element on the Dashboard, like "Tracked Cases"
  // Using .first() to avoid strict mode violations if multiple exist (though ideally should be unique)
  await expect(page.getByText('Tracked Cases', { exact: true }).first()).toBeVisible();
});
