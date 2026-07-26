import { test, expect } from '@playwright/test'

// All these tests run against the backend with CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS=1
// (see playwright.config.ts webServer.env) - fake/sanitized data only, never real
// credentials or a real ~/.claude / ~/.codex / codex.exe spawn.

test('dashboard loads and shows discovered fake profiles', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle(/Claude & Codex Usage Monitor/)
  await expect(page.getByRole('heading', { name: 'default' }).first()).toBeVisible({
    timeout: 15_000,
  })
  await expect(page.getByRole('heading', { name: 'Codex', exact: true })).toBeVisible({
    timeout: 15_000,
  })
})

test('fake profile with data renders usage bars', async ({ page }) => {
  await page.goto('/')
  // Ensure at least one refresh has happened (scheduler's own startup refresh
  // is delayed by design) so usage data is present, rather than racing it.
  await page.getByTestId('refresh-all-button').click()
  await expect(page.getByTestId('refresh-all-button')).toBeEnabled({ timeout: 15_000 })
  await page.reload()
  await expect(page.getByText('5-hour').first()).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('42%').first()).toBeVisible({ timeout: 15_000 })
})

test('failed/auth-required fake profile displays correctly, not fabricated data', async ({
  page,
}) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'work' })).toBeVisible()
  await page.getByTestId('refresh-all-button').click()
  await expect(page.getByTestId('refresh-all-button')).toBeEnabled({ timeout: 15_000 })
  await page.reload()
  await expect(page.getByText(/authentication required/i)).toBeVisible({ timeout: 15_000 })
})

test('manual refresh-all works', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('refresh-all-button')).toBeVisible({ timeout: 15_000 })
  await page.getByTestId('refresh-all-button').click()
  await expect(page.getByTestId('refresh-all-button')).toBeEnabled({ timeout: 15_000 })
})

test('history range changes update the filter UI', async ({ page }) => {
  await page.goto('/')
  const button30d = page.getByRole('button', { name: '30d' })
  await button30d.click()
  await expect(button30d).toHaveAttribute('aria-pressed', 'true')
})

test('diagnostics drawer opens and shows sanitized fields', async ({ page }) => {
  await page.goto('/')
  await page.getByText('Diagnostics').first().click()
  await expect(page.getByRole('dialog', { name: 'Diagnostics' })).toBeVisible()
  await expect(page.getByText('Config path')).toBeVisible()
})

test('responsive: summary cards remain visible on a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 800 })
  await page.goto('/')
  await expect(page.getByTestId('summary-cards')).toBeVisible()
})
