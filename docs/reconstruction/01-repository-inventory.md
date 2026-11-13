# 01 — Repository Inventory (Airdox/iste-rekordbox · Cuepoint)

## 1. Fixed Reference Snapshot

| Field | Value |
|---|---|
| **Repository URL** | `https://github.com/Airdox/iste-rekordbox` |
| **Project Name** | `Cuepoint` (`cuepoint-library`) |
| **Reference Version** | `1.1.0` (`package.json`) |
| **Fixed Commit SHA** | `88e8bdf66b2d731961924e85494307b7f3572bc0` |
| **Branch** | `main` |
| **Commit Date** | `2026-11-13 00:00:07 +0100` |
| **Commit Message** | `test: add frontend unit tests for api and metadata helpers` |

## 2. Locked Dependency Versions

### Node.js (`package.json`)
- **Runtime Dependencies**:
  - `@fontsource/ibm-plex-mono`: `^5.2.7`
  - `@fontsource/inter`: `^5.2.8`
  - `@tanstack/react-table`: `^8.21.3`
  - `@tanstack/react-virtual`: `^3.13.23`
  - `lucide-react`: `^0.468.0`
  - `react`: `^19.2.0`
  - `react-dom`: `^19.2.0`
- **Dev Dependencies**:
  - `@playwright/test`: `^1.57.0`
  - `@stryker-mutator/core`: `^10.1.1`
  - `@stryker-mutator/vitest-runner`: `^10.1.1`
  - `@tailwindcss/vite`: `^4.1.0`
  - `@testing-library/jest-dom`: `^7.0.1`
  - `@testing-library/react`: `^16.3.3`
  - `@testing-library/user-event`: `^14.6.10`
  - `@types/react`: `^19.2.0`
  - `@types/react-dom`: `^19.2.0`
  - `@vitest/coverage-v8`: `^5.1.0`
  - `c8`: `^12.0.0`
  - `electron`: `^45.3.1`
  - `electron-builder`: `^26.0.0`
  - `jsdom`: `^31.0.0`
  - `tailwindcss`: `^4.1.0`
  - `typescript`: `~5.9.3`
  - `vite`: `^7.2.0`
  - `vitest`: `^5.1.0`

### Python (`requirements.txt` / `requirements-dev.txt`)
- `pyrekordbox==0.5.0`
- `rekordbox-pdb @ https://codeload.github.com/fragmede/rekordbox-pdb/zip/ee3bac2f22ca11a5ce61eea35f8cb951c246eaef`
- `psutil==7.2.2`
- `comtypes==1.5.0` (`sys_platform == "win32"`)
- Dev: `pytest>=8.3,<10`, `pytest-cov>=5.0`, `coverage[toml]>=7.6`, `ruff>=0.7`, `pyinstaller==6.22.3`
- Implicitly imported by `backend/library.py` via `pyrekordbox`: `numpy`, `sqlcipher3`, `construct`

## 3. Complete Reference File Tree (15,456 LOC)

- `.github/workflows/quality-gate.yml` — 6-stage Windows CI/CD & Quality Gate
- `README.md` — Usage, read-only architecture, dev/test commands
- `package.json`, `package-lock.json`, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`
- `tsconfig.json`, `vite.config.ts`, `vitest.config.ts`, `stryker.config.mjs`, `index.html`
- `backend/`:
  - `fixtures.py` (76 lines) — Synthetic 15,500-track generator & SQLite schema writer
  - `keys.py` (43 lines) — Camelot normalization (`camelot`) & harmonic circle (`compatible`)
  - `sources.py` (210 lines) — Read-only snapshot, SHA-256 verification, SQLCipher, Master/OneLibrary/PDB readers
  - `library.py` (642 lines) — In-memory SQLite + NumPy boolean mask & sort engine, facets, recommendations, ANLZ waveform parser
  - `live.py` (152 lines) — Pro DJ Link UDP 50000/50002 interface discovery, status decoder, announcement builder
  - `rekordbox_live.py` (604 lines) — Win32 UI Automation deck/fader reader & Win32 SendInput transport
  - `main.py` (242 lines) — JSON-RPC stdio dispatcher & `Core` anchor/matching coordinator
- `electron/`:
  - `main.cjs` (163 lines) — Electron main process, Python worker lifecycle, IPC whitelist, file dialogs, persistence
  - `preload.cjs` (8 lines) — `contextBridge` exposing `window.cuepoint`
- `src/`:
  - `api.ts` (230 lines) — TypeScript types, IPC wrapper, Camelot helpers, CSV/M3U8/Rekordbox XML exporters
  - `metadata.ts` (105 lines) — 18 metadata fields, 7 UI operators, 3 built-in presets, custom preset localStorage
  - `camelot-wheel.tsx` (115 lines) — Interactive 24-segment SVG Camelot wheel
  - `components.tsx` (112 lines) — `KeyBadge`, `Stars`, `MiniWave`, `LiveWaveform`, `Empty`, `Modal`
  - `track-table.tsx` (343 lines) — `@tanstack/react-table` + `@tanstack/react-virtual` (40px rows, 33px header)
  - `live-view.tsx` (509 lines) — Live-Match 3-pane workspace
  - `filter-view.tsx` (711 lines) — Filter-Studio 3-pane workspace with nested groups & sort cascade
  - `set-view.tsx` (283 lines) — Set-Builder workspace with transitions & exports
  - `hardware-modal.tsx` (366 lines) — Pro DJ Link / Deck radar / USB media binding modal
  - `main.tsx` (1600 lines) — Root `App` state coordinator, window bar, topnav, livebar, sidenav, modals
  - `style.css` (1753 lines) — Complete dark studio CSS theme
- `scripts/`:
  - `build-backend.ps1`, `inspect_rekordbox_uia.py`, `mutate_backend.py`, `quality_gate.py`
- `tests/`:
  - `generate_synthetic_db.py`, `profile_query_breakdown.py`, `test_backend_coverage.py`, `test_combinatorial_stress.py`, `test_filter_groups.py`, `test_live.py`, `test_readonly.py`, `test_rekordbox_playback.py`
  - `electron-smoke.cjs`, `electron/main.test.mjs`
  - `frontend/{setup.ts, api-metadata.test.ts, app.test.tsx, components-wheel.test.tsx, views-table.test.tsx}`
- `referenzbilder/`:
  - `111111.png`
  - `airdox_rekordbox_ui_prototyp.html`
