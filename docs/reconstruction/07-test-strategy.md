# 07 — Test, Coverage, Mutation & GUI Verification Strategy

## 1. Test Layers & Targets

1. **Python Backend Unit & Branch Tests** (`tests/test_*.py`):
   - Modules: `keys.py`, `fixtures.py`, `sources.py`, `library.py`, `live.py`, `rekordbox_live.py`, `main.py`, `diagnostics.py`.
   - Verifies: 24 Camelot keys + classical/German notations + wrap-around (`12A->1A`, `1B->12B`); read-only snapshot & SHA-256 invariance before/after all operations; concurrent source modification rejection (`SNAPSHOT_INCONSISTENT`); SQLCipher error paths; schema normalization (`djmdContent`, `OneLibrary`, `export.pdb` mocks); nested `AND`/`OR` filter groups; all 9 operators (`contains`, `eq`, `neq`, `gte`, `lte`, `gt`, `lt`, `range`, `empty`); Unicode folding (`ä/ö/ü/é`); staged facets (`genres`, `keys`, `histogram`, `counts`); multi-stage stable sorting; Pro DJ Link UDP loopback packet replay; multi-media USB/SD slot disambiguation; fader & crossfader gain math; Win32 transport & UIA mocks.
   - Target: >= 90% branch coverage (when `pytest-cov` / `coverage` available) + 100% pass rate in `unittest` / `pytest`.

2. **Combinatorial Stress & Performance Benchmark** (`tests/test_combinatorial_stress.py`, `tests/test_filter_groups.py`):
   - 15,500-track synthetic Rekordbox DB (`tests/generate_synthetic_db.py`).
   - Independent Python reference oracle (pure SQL + Python set operations, never calling `Library.query`).
   - Validates exact ID sets, counts, staged facets, sort orders, and query latency (p95 / max <= 50ms target when NumPy is active; documented baseline in stdlib mode).

3. **Frontend Unit & Component Tests** (`vitest run --coverage`):
   - `api-metadata.test.ts`: formatters, Camelot wheel math, transitions, CSV/M3U8/XML exports, presets storage.
   - `components-wheel.test.tsx`: `KeyBadge`, `Stars`, `MiniWave`, `LiveWaveform` (real vs synthetic badge), `CamelotWheel` click/Ctrl+click/keyboard.
   - `views-table.test.tsx`: `LiveView`, `FilterView` (nested groups + sort designer DnD & Alt+Arrow), `SetView`, `HardwareModal`, `TrackTable` virtualization & context menu.
   - `app.test.tsx`: Full `App` workflows, shortcuts, modals, Escape close, persistence across remount.
   - Target: >= 90% global coverage; 100% on `src/metadata.ts`, `src/api.ts`, `src/camelot-wheel.tsx`.

4. **Electron Main & Preload Tests** (`tests/electron/main.test.mjs`):
   - Security flags (`contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`), IPC whitelist, untrusted senderFrame rejection, worker crash recovery, timeout handling, `cuepoint:revealFile`.

5. **Real Browser E2E & Visual Verification**:
   - Start live full-stack app (`tsx server.ts` on port 3000 with real Python worker) and drive it via headless Chromium (`playwright-cli` / Playwright) across Live-Match, Filter-Studio, Set-Builder, Hardware Modal, Sort Designer, Preset saving, and reload persistence.
   - Capture screenshots in `reports/evidence/reconstruction/` and compare against `referenzbilder/111111.png`.

6. **Mutation Testing**:
   - Python AST mutator (`scripts/mutate_backend.py`) + StrykerJS (`stryker.config.mjs`) where supported by environment; document all generated/killed/survived/equivalent mutants honestly.
