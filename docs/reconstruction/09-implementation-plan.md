# 09 — Implementation Plan & Task Contracts

## Task Contracts

### CP-001 — Phase 1 Reference Analysis & Contracts
- **Owner**: `Architektur-Agent`
- **Status**: `completed`
- **Deliverables**: `docs/reconstruction/01..09.md`
- **Acceptance**: All 9 documents reflect exact commit `88e8bdf66b2d731961924e85494307b7f3572bc0`.

### CP-002 — Core Bootstrap, Diagnostics, Electron & Web Worker Bridge
- **Owner**: `Electron-Agent`
- **Dependencies**: `CP-001`
- **Deliverables**: `backend/diagnostics.py`, `electron/main.cjs`, `electron/preload.cjs`, `server.ts`, `package.json`, `metadata.json`, `index.html`, `vite.config.ts`, `tsconfig.json`
- **Acceptance**: Whitelisted IPC, `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`, structured error classes (`SOURCE_NOT_FOUND` etc.), JSONL stderr diagnostics, persistent Python worker on port 3000.

### CP-003 — Database Integration & Read-Only Snapshot Engine
- **Owner**: `Datenbank-Agent`
- **Dependencies**: `CP-002`
- **Deliverables**: `backend/sources.py`, `backend/fixtures.py`, `tests/generate_synthetic_db.py`
- **Acceptance**: Read-only `rb` snapshot with SHA-256 + WAL/journal + `stat` verification; Master / OneLibrary / Device Library PDB schema normalization; before/after SHA-256 invariance verified.

### CP-004 — Performance Query, Filter, Sort & Camelot Engine
- **Owner**: `Query-Agent`
- **Dependencies**: `CP-003`
- **Deliverables**: `backend/keys.py`, `backend/library.py`
- **Acceptance**: All 24 Camelot keys + classical/German mappings; nested `AND`/`OR` groups; 9 operators; staged facets; multi-stage stable sort; 15,500-track benchmark & oracle parity.

### CP-005 — Live Integration (Pro DJ Link & Local Rekordbox UIA/Transport)
- **Owner**: `Live-Agent`
- **Dependencies**: `CP-003`, `CP-004`
- **Deliverables**: `backend/live.py`, `backend/rekordbox_live.py`, `backend/main.py`
- **Acceptance**: Pro DJ Link UDP 50000/50002 decoder + loopback replay; USB/SD slot disambiguation; fader/crossfader gain math; track identity + BPM/duration matching; Win32 SendInput transport mocks.

### CP-006 — React 19 Frontend UI & Persistence
- **Owner**: `Frontend-Agent`
- **Dependencies**: `CP-002`, `CP-004`
- **Deliverables**: `src/{api.ts,metadata.ts,camelot-wheel.tsx,components.tsx,track-table.tsx,live-view.tsx,filter-view.tsx,set-view.tsx,hardware-modal.tsx,main.tsx,style.css}`
- **Acceptance**: All 3 views (`Live-Match`, `Filter-Studio`, `Set-Builder`), interactive SVG Camelot wheel, virtualized 40px rows, DnD + Alt+Arrow sort designer, real-vs-synthetic waveform labeling, CSV/M3U8/XML exports, localStorage persistence.

### CP-007 — Comprehensive Automated & Real Browser Verification
- **Owner**: `Test-Agent` + `Visual-QA-Agent` + `Security-Agent`
- **Dependencies**: `CP-005`, `CP-006`
- **Deliverables**: `tests/test_*.py`, `tests/electron/main.test.mjs`, `tests/frontend/*.test.*`, `scripts/mutate_backend.py`, `reports/evidence/`
- **Acceptance**: Python unit/readonly/live/combinatorial tests pass; Vitest >= 90% coverage pass; Electron `node:test` pass; live port-3000 headless browser E2E pass with screenshots.

### CP-008 — CI/CD Workflow, Windows Build Spec & Final Reports
- **Owner**: `Build-Agent` + `Review-Agent`
- **Dependencies**: `CP-007`
- **Deliverables**: `.github/workflows/quality-gate.yml`, `scripts/build-backend.ps1`, `scripts/quality_gate.py`, `reports/final/*`
- **Acceptance**: `npm run build` & `npm run lint` clean; CI `win-unpacked` vs portable EXE mismatch resolved; honest final reports generated with explicit `UNVERIFIED_REAL_REKORDBOX` / `BLOCKED` status for Windows-only items.
