#!/usr/bin/env node
/**
 * Verifica FIREBASE_SERVICE_ACCOUNT_PATH (o GOOGLE_APPLICATION_CREDENTIALS)
 * sin imprimir claves privadas. Uso local — no commitear el JSON.
 *
 *   node scripts/verify-firebase-admin.mjs
 *   set FIREBASE_SERVICE_ACCOUNT_PATH=C:\ruta\service-account.json && node scripts/verify-firebase-admin.mjs
 */
import { readFileSync, existsSync } from 'node:fs'
import { resolve, isAbsolute, basename } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(join(repoRoot, 'electron-app', 'package.json'))

function resolvePath(raw) {
  const p = raw.trim()
  return isAbsolute(p) ? p : resolve(process.cwd(), p)
}

const raw =
  process.env.FIREBASE_SERVICE_ACCOUNT_PATH?.trim() ||
  process.env.GOOGLE_APPLICATION_CREDENTIALS?.trim()

if (!raw) {
  console.error(
    'ERROR: Defina FIREBASE_SERVICE_ACCOUNT_PATH o GOOGLE_APPLICATION_CREDENTIALS.'
  )
  process.exit(1)
}

const path = resolvePath(raw)
if (!existsSync(path)) {
  console.error(`ERROR: No existe el archivo: ${path}`)
  process.exit(1)
}

let sa
try {
  sa = JSON.parse(readFileSync(path, 'utf8'))
} catch (e) {
  console.error('ERROR: JSON inválido:', e instanceof Error ? e.message : e)
  process.exit(1)
}

const projectId = sa.project_id
const clientEmail = sa.client_email
console.log('Archivo:', basename(path))
console.log('project_id:', projectId ?? '(falta)')
console.log('client_email:', clientEmail ?? '(falta)')

if (!projectId || !sa.private_key) {
  console.error('ERROR: El JSON no parece un service account válido.')
  process.exit(1)
}

let admin
try {
  admin = require('firebase-admin')
} catch {
  console.error('ERROR: Ejecute npm install en electron-app primero.')
  process.exit(1)
}

if (!admin.apps.length) {
  admin.initializeApp({
    credential: admin.credential.cert(sa),
    projectId
  })
}

try {
  const res = await admin.auth().listUsers(1)
  console.log('auth.listUsers(1): OK — usuarios en página:', res.users.length)
  console.log('Verificación Firebase Admin completada.')
} catch (e) {
  console.error('ERROR auth.listUsers:', e instanceof Error ? e.message : e)
  process.exit(1)
}
