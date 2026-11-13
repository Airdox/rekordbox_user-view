/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
export default {
  packageManager: 'npm',
  testRunner: 'vitest',
  vitest: {
    configFile: 'vitest.config.ts',
    related: true,
  },
  mutate: [
    'src/metadata.ts',
    'src/api.ts',
    'src/camelot-wheel.tsx',
  ],
  reporters: ['progress', 'clear-text', 'json', 'html'],
  jsonReporter: {
    fileName: 'reports/mutation-frontend/stryker-report.json',
  },
  htmlReporter: {
    fileName: 'reports/mutation-frontend/index.html',
  },
  thresholds: {
    high: 97,
    low: 95,
    break: 95,
  },
  tsconfigFile: 'tsconfig.stryker-skip.json',
  ignorePatterns: ['build', 'dist', 'referenzbilder', 'docs', 'public', 'reports', 'release'],
  ignoreStatic: true,
  concurrency: 1,
  timeoutMS: 30000,
}
