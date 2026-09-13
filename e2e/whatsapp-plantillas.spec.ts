import { expect, test } from '@playwright/test'
import path from 'path'
import dotenv from 'dotenv'

dotenv.config({ path: path.resolve(__dirname, '../.env.e2e.local') })

const gestorEmail = process.env.E2E_GESTOR_EMAIL || ''
const gestorPassword = process.env.E2E_GESTOR_PASSWORD || ''
const adminEmail = process.env.E2E_ADMIN_EMAIL || ''
const adminPassword = process.env.E2E_ADMIN_PASSWORD || ''

async function enableFlutterSemantics(page: import('@playwright/test').Page) {
  const a11y = page.getByRole('button', { name: /enable accessibility/i })
  try {
    await a11y.click({ timeout: 5_000, force: true })
  } catch {
    // already on
  }
  await page.evaluate(() => {
    const walk = (node: Node | null): boolean => {
      if (!node || node.nodeType !== 1) return false
      const el = node as Element
      if (el.getAttribute?.('aria-label') === 'Enable accessibility') {
        ;(el as HTMLElement).click()
        return true
      }
      const sr = (el as HTMLElement).shadowRoot
      if (sr && walk(sr)) return true
      for (const c of el.children || []) {
        if (walk(c)) return true
      }
      return false
    }
    walk(document.documentElement)
  })
}

async function login(page: import('@playwright/test').Page, email: string, password: string) {
  await page.goto('/')
  await expect(page).toHaveTitle(/recaudo|antcobranzas|gestor/i, { timeout: 60_000 })
  await enableFlutterSemantics(page)
  const emailBox = page.getByRole('textbox', { name: /correo electrónico/i })
  await expect(emailBox).toBeVisible({ timeout: 60_000 })
  await emailBox.click()
  await emailBox.fill(email)
  const passBox = page.getByRole('textbox', { name: /contraseña/i })
  await passBox.click()
  await passBox.fill(password)
  await page.getByRole('button', { name: /iniciar sesión/i }).click()
  await expect(page.getByRole('button', { name: /iniciar sesión/i })).toHaveCount(0, {
    timeout: 60_000,
  })
  await enableFlutterSemantics(page)
}

test.describe('Plantillas WhatsApp', () => {
  test('gestor ve Mensajes WhatsApp en Perfil', async ({ page }) => {
    test.skip(!gestorEmail || !gestorPassword, 'Falta E2E_GESTOR_* en .env.e2e.local')
    await login(page, gestorEmail, gestorPassword)
    await page.getByText(/^Perfil$/i).first().click()
    await enableFlutterSemantics(page)
    await expect(page.getByText(/Mensajes WhatsApp/i).first()).toBeVisible({
      timeout: 30_000,
    })
  })

  test('admin ve Mensajes WhatsApp en Perfil', async ({ page }) => {
    test.skip(!adminEmail || !adminPassword, 'Falta E2E_ADMIN_* en .env.e2e.local')
    await login(page, adminEmail, adminPassword)
    await page.getByText(/^Perfil$/i).first().click()
    await enableFlutterSemantics(page)
    await expect(page.getByText(/Mensajes WhatsApp/i).first()).toBeVisible({
      timeout: 30_000,
    })
  })
})
