import { defineConfig } from 'vite';
import { readFileSync } from 'node:fs';
const sourceVersion = readFileSync(new URL('../objectdna/__init__.py', import.meta.url), 'utf8')
  .match(/^__version__ = "([^"]+)"$/m)?.[1];
const frontendVersion = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version;
if (!sourceVersion || frontendVersion.replace('-dev.', '.dev') !== sourceVersion) {
  throw new Error('Frontend and Python source versions must identify the same development generation.');
}
export default defineConfig({
  define: { __OBJECTDNA_VERSION__: JSON.stringify(sourceVersion) },
  server: { proxy: { '/api': 'http://127.0.0.1:8768' } },
  build: { chunkSizeWarningLimit: 650 }
});
