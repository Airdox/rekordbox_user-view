# Testergebnisse, Coverage & Mutation Testing — Cuepoint v1.1.0

Alle Zahlen stammen ausschließlich aus tatsächlich ausgeführten Test- und Messläufen im Workspace `/app/applet`.

---

## 1. Übersicht aller Testläufe

| Suite / Befehl | Ergebnis | Dauer | Status |
|---|---|---:|---|
| **TypeScript & Vite Build** (`npm run build` / `compile_applet`) | 0 Fehler, Bundle erstellt | ~4 s | `PASS` |
| **TypeScript Lint** (`npm run lint` / `lint_applet`) | 0 Fehler | ~2 s | `PASS` |
| **Frontend Vitest + V8 Coverage** (`npm run test:frontend`) | **4/4** Dateien, **29/29** Tests bestanden (`0` fehlgeschlagen) | ~18 s | `PASS` |
| **Electron Main & Preload + c8 Coverage** (`npm run test:electron`) | **5/5** Subtests bestanden (`0` fehlgeschlagen) · **100 % Lines / 92.78 % Branch** | ~1 s | `PASS` |
| **Python Unit/Live/FilterGroups/Playback/Readonly/Coverage** (`python3 tests/run_backend_tests.py test_readonly test_live test_rekordbox_playback test_filter_groups test_backend_coverage`) | **25** bestanden, **1** übersprungen (`test_encrypted_one_library_export_is_read_only` ohne `sqlcipher3`/`pyrekordbox`), **0** fehlgeschlagen | ~31 s | `PASS` |
| **Kombinatorische Oracle-Stress-Suite** (`CUEPOINT_QA_CASES=5000 python3 tests/run_backend_tests.py test_combinatorial_stress`) | **30** bestanden, **1** übersprungen, **0** fehlgeschlagen (`5.000` eindeutige Pläne, `2.066.942` Treffer, `100 %` Übereinstimmung mit unabhängigem SQL-Oracle) | 52.10 s | `PASS` |
| **Live Browser E2E (Headless Chromium `1440x900` über Port `3000`)** | **6/6** Interaktionsabläufe bestanden + Viewport-Resize-Test, **0** Console-Errors, **0** Page-Errors | ~28 s | `PASS` |
| **StrykerJS Frontend Mutation Testing** (`npx stryker run`) | **`96.49 %`** Mutation Score (`55` gekillt, `2` überlebt, `0` Timeout, `>= 95 %` Schwellenwert bestanden) | ~77 s | `PASS` |
| **Python AST Mutation Testing** (`python3 scripts/mutate_backend.py`) | `167/207` gekillt (`80.68 %` roh / `88.83 %` effektiv exkl. `19` Äquivalente; **100 % Kill-Rate** auf allen ausführbaren Pure-Python-Pfaden; `21` Überlebende nur in `if np is not None:`-Zweigen ohne `numpy`) | ~300 s | `PARTIAL_SUCCESS` (`BLOCKED` für `numpy`-Zweige) |
| **Python Branch Coverage (`pytest-cov`)** | Nicht im Container vorinstalliert (`pytest`/`coverage` fehlen im Basis-Image; Unit-Suite via `run_backend_tests.py` verifiziert) | — | `BLOCKED` |

---

## 2. Frontend V8 Coverage Detail (`reports/coverage-frontend/coverage-summary.json`)

| Datei | Statements | Branches | Functions | Lines | Ziel >= 90% / Kritisch 100% |
|---|---:|---:|---:|---:|---|
| **Global (`src/`)** | **97.10 %** | **91.95 %** | **97.15 %** | **98.40 %** | `PASS` (>= 90 %) |
| `src/api.ts` | **100.00 %** | **100.00 %** | **100.00 %** | **100.00 %** | `PASS` (Kritisch 100 %) |
| `src/camelot-wheel.tsx` | **100.00 %** | **100.00 %** | **100.00 %** | **100.00 %** | `PASS` (Kritisch 100 %) |
| `src/metadata.ts` | **100.00 %** | **100.00 %** | **100.00 %** | **100.00 %** | `PASS` (Kritisch 100 %) |
| `src/components.tsx` | **100.00 %** | **100.00 %** | **100.00 %** | **100.00 %** | `PASS` |
| `src/status-view.tsx` | **100.00 %** | **100.00 %** | **100.00 %** | **100.00 %** | `PASS` |
| `src/hardware-modal.tsx` | 100.00 % | 93.84 % | 100.00 % | 100.00 % | `PASS` |
| `src/set-view.tsx` | 100.00 % | 95.65 % | 100.00 % | 100.00 % | `PASS` |
| `src/track-table.tsx` | 99.20 % | 95.04 % | 100.00 % | 100.00 % | `PASS` |
| `src/filter-view.tsx` | 97.82 % | 90.90 % | 100.00 % | 97.64 % | `PASS` |
| `src/live-view.tsx` | 93.65 % | 90.42 % | 100.00 % | 94.33 % | `PASS` |
| `src/main.tsx` | 95.56 % | 87.63 % | 93.89 % | 97.83 % | `PASS` (Global >= 90 %) |

---

## 3. Electron c8 Coverage Detail (`reports/coverage-electron/coverage-summary.json`)

| Datei | Statements | Branches | Functions | Lines | Ziel >= 90% |
|---|---:|---:|---:|---:|---|
| **Gesamt (`electron/`)** | **100.00 %** | **92.78 %** | **100.00 %** | **100.00 %** | `PASS` (>= 90 %) |
| `electron/main.cjs` | 100.00 % | 92.39 % | 100.00 % | 100.00 % | `PASS` |
| `electron/preload.cjs` | **100.00 %** | **100.00 %** | **100.00 %** | **100.00 %** | `PASS` |

---

## 4. Python AST Mutation Testing (`reports/mutation-python/mutation-report.json`) & StrykerJS (`reports/mutation-frontend/stryker-report.json`)

- **StrykerJS Frontend Mutation:** `96.49 %` (`55/57` gekillt, `>= 95 %` Break-Schwellenwert bestanden).
- **Python AST Mutation:** `207` erzeugte Mutanten, `167` gekillt (`80.68 %` roh), `19` mathematisch/semantisch äquivalent (`88.83 %` effektiv). Alle `21` verbliebenen Überlebenden liegen ausschließlich in `if np is not None:`-Zweigen in `backend/library.py`, da `numpy` im Sandbox-Python nicht installiert ist (`100 %` Kill-Rate auf allen ausführbaren Pure-Python-Pfaden).
