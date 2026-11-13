import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    isolate: false,
    fileParallelism: false,
    include: [
      'tests/frontend/api-metadata.test.ts',
      'tests/frontend/components-wheel.test.tsx',
    ],
    setupFiles: ['tests/frontend/setup.ts'],
  },
})
