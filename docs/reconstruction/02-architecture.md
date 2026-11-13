# 02 — System Architecture & Multi-Agent Plan

## 1. Process & Communication Architecture

```text
+-------------------------------------------------------------------+
| Presentation Layer (React 19 + TypeScript 5.9 + TanStack Table/   |
| Virtual + Lucide Icons)                                           |
|  - LiveView (CamelotWheel, TrackTable, Live Quick Filters)        |
|  - FilterView (Nested AND/OR Groups, SortDesigner, Set-Korb)      |
|  - SetView (Drag-and-drop Setlist, Transitions, CSV/M3U8/XML)     |
+------------------------------+------------------------------------+
                               | window.cuepoint.request()
                               v
+-------------------------------------------------------------------+
| Bridge Layer                                                      |
|  - Desktop: electron/preload.cjs (contextIsolation, sandbox)      |
|             -> electron/main.cjs (IPC whitelist, worker spawn)    |
|  - Web Preview: server.ts Express /api/cuepoint/request           |
|             -> Persistent Python Worker child process             |
+------------------------------+------------------------------------+
                               | Line-delimited JSON-RPC (stdin/stdout)
                               v
+-------------------------------------------------------------------+
| Python Core Worker (backend/main.py)                              |
|  - sources.py: Read-only snapshot (rb + SHA-256 + WAL/journal),   |
|                SQLCipher (pyrekordbox keys), Master/OneLib/PDB    |
|  - library.py: In-memory SQLite + NumPy masks/lexsort, facets,    |
|                100k+ combo performance, ANLZ PWAV waveform        |
|  - keys.py:    Camelot 1A-12B parser & harmonic neighbors         |
|  - live.py:    Pro DJ Link UDP 50000/50002 listener & decoder     |
|  - rekordbox_live.py: Win32 UIA deck/fader reader & SendInput     |
|  - diagnostics.py: Structured JSONL stderr diagnostics & errors   |
+-------------------------------------------------------------------+
```

## 2. Multi-Agent Role Assignment & Work Packages

Because this environment executes as a single orchestrator, each specialized role is executed as a dedicated phase with an explicit independent review gate before promotion:

| Role | Responsibility |
|---|---|
| `Architektur-Agent` | Phase 1 inventory, contracts, risk register, implementation plan |
| `Datenbank-Agent` | `sources.py`, `fixtures.py`, read-only snapshot + SHA-256 + schema normalization |
| `Query-Agent` | `keys.py`, `library.py`, NumPy vectorized masks (with stdlib fallback), sorts, facets |
| `Live-Agent` | `live.py`, `rekordbox_live.py`, Pro DJ Link UDP, USB media binding, fader math |
| `Electron-Agent` | `electron/main.cjs`, `electron/preload.cjs`, `server.ts` web-worker bridge, `diagnostics.py` |
| `Frontend-Agent` | `src/*.ts`, `src/*.tsx`, `src/style.css`, waveform real/synthetic distinction, sort DnD |
| `Security-Agent` | Read-only hash verification, IPC whitelist, CSP, path traversal protection |
| `Test-Agent` | Python unit/branch/combinatorial/readonly/live tests, Vitest, Electron node:test |
| `Visual-QA-Agent` | Real headless browser verification against port 3000 + screenshot comparison |
| `Build-Agent` | `vite build`, `tsc --noEmit`, CI workflow fix (`quality-gate.yml`), PyInstaller/Windows specs |
| `Review-Agent` | Independent verification of every task contract and final reports |

## 3. Dependency Graph

```text
CP-001 (Phase 1 Docs & Contracts)
  |
  +---> CP-002 (Core Bootstrap: Electron + server.ts + Diagnostics + Error Codes)
  |       |
  +---> CP-003 (Database Integration: sources.py + fixtures.py + Read-Only Snapshot)
  |       |
  |       +---> CP-004 (Query Engine: keys.py + library.py + 15.5k Benchmark)
  |       |
  |       +---> CP-005 (Live Integration: live.py + rekordbox_live.py + main.py Core)
  |
  +---> CP-006 (Frontend UI: React 19 + TanStack Table/Virtual + Wheel + Modals)
          |
          v
        CP-007 (Verification: Python Suites + Vitest + Electron Tests + Browser E2E)
          |
          v
        CP-008 (Build, CI Workflow Fix & Final Reports)
```
