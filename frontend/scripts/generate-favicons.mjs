/**
 * Rasterize frontend/src/assets/logo.svg into the public favicon set.
 * Re-run after redesigning the logo: `npm run generate-favicons`
 *
 * Uses sharp (libvips) — already in the Node/Vite toolchain; no Python cairo stack.
 */
import { mkdir, copyFile, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const logoPath = path.join(root, 'src', 'assets', 'logo.svg')
const publicDir = path.join(root, 'public')
const previewDir = path.join(root, 'scripts', '.preview')

const targets = [
  { file: 'favicon-16x16.png', size: 16 },
  { file: 'favicon-32x32.png', size: 32 },
  { file: 'apple-touch-icon.png', size: 180 },
]

async function main() {
  const svg = await readFile(logoPath)
  await mkdir(publicDir, { recursive: true })
  await mkdir(previewDir, { recursive: true })

  // Scalable favicon for modern browsers (same mark as the source of truth).
  await copyFile(logoPath, path.join(publicDir, 'favicon.svg'))

  for (const { file, size } of targets) {
    await sharp(svg, { density: 384 })
      .resize(size, size, {
        fit: 'contain',
        background: { r: 0, g: 0, b: 0, alpha: 0 },
      })
      .png()
      .toFile(path.join(publicDir, file))
  }

  // Large preview for design review (not shipped).
  await sharp(svg, { density: 384 })
    .resize(512, 512, {
      fit: 'contain',
      background: { r: 247, g: 246, b: 244, alpha: 1 }, // --bg
    })
    .png()
    .toFile(path.join(previewDir, 'logo-preview-512.png'))

  console.log('Wrote favicon.svg, favicon-16x16.png, favicon-32x32.png, apple-touch-icon.png')
  console.log('Wrote scripts/.preview/logo-preview-512.png')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
