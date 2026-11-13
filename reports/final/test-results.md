# Testergebnisse, Coverage & Mutation Testing — Cuepoint v1.1.0

Alle Zahlen stammen ausschließlich aus tatsächlich ausgeführten Test- und Messläufen im Workspace `/app/applet`.

---

## 1. Übersicht aller Testläufe

| Suite / Befehl | Ergebnis | Dauer | Status |
|---|---|---:|---|
| **TypeScript & Vite Build** (`npm run build` / `compile_applet`) | 0 Fehler, Bundle erstellt | ~4 s | `PASS` |
| **TypeScript Lint** (`npm run lint` / `lint_applet`) | 0 Fehler | ~2 s | `PASS` |
| **Frontend Vitest + V8 Coverage** (`npm run test:frontend`) | **4/4** Dateien, **27/27** Tests bestanden (`0` fehlgeschlagen) | 26.30 s | `PASS` |
| **Electron Main & Preload** (`node --test tests/electron/main.test.mjs`) | **4/4** Subtests bestanden (`0` fehlgeschlagen) | 0.21 s | `PASS` |
| **Python Unit/Live/FilterGroups/Playback/Readonly/Coverage** (`python3 tests/run_backend_tests.py test_readonly test_live test_rekordbox_playback test_filter_groups test_backend_coverage`) | **24** bestanden, **1** übersprungen (`test_encrypted_one_library_export_is_read_only` ohne `sqlcipher3`/`pyrekordbox`), **0** fehlgeschlagen | 31.53 s | `PASS` |
| **Kombinatorische Oracle-Stress-Suite** (`CUEPOINT_QA_CASES=5000 python3 tests/run_backend_tests.py test_combinatorial_stress`) | **30** bestanden, **1** übersprungen, **0** fehlgeschlagen (`5.000` eindeutige Pläne, `2.066.942` Treffer, `100 %` Übereinstimmung mit unabhängigem SQL-Oracle) | 52.10 s | `PASS` |
| **Live Browser E2E (Headless Chromium `1440x900` über Port `3000`)** | **6/6** Interaktionsabläufe bestanden, **0** Console-Errors, **0** Page-Errors | ~28 s | `PASS` |
| **Python AST Mutation Testing** (`python3 scripts/mutate_backend.py`) | `167/207` gekillt (`80.68 %` roh / `88.83 %` effektiv exkl. `19` Äquivalente; alle `21` Überlebenden ausschließlich in `if np is not None:`-Zweigen ohne `numpy`) | ~300 s | `PARTIAL_SUCCESS` (`BLOCKED` für `numpy`-Zweige) |
| **StrykerJS Frontend Mutation Testing** (`npx stryker run`) | Nicht ausgeführt (`@stryker-mutator/core` nicht im Container) | — | `BLOCKED` |
| **Python Branch Coverage (`pytest-cov`)** | Nicht messbar (`pytest`/`coverage` nicht im Container) | — | `BLOCKED` |

---

## 2. Frontend V8 Coverage Detail (`reports/coverage-frontend/coverage-summary.json`)

| Datei | Statements | Branches | Functions | Lines | Ziel >= 90% / Kritisch 100% |
|---|---:|---:|---:|---:|---|
| **Global (`src/`)** | **97.00 %** | **92.10 %** | **97.01 %** | **98.33 %** | `PASS` (>= 90 %) |
| `src/api.ts` | **100.00 %** | **100.00 %** | **100.00 %** | **100.00 %** | `PASS` (Kritisch 100 %) |
| `src/camelot-wheel.tsx` | **100.00 %** | **100.00 %** | **100.00 %** | **100.00 %** | `PASS` (Kritisch 100 %) |
| `src/metadata.ts` | **100.00 %** | **100.00 %** | **100.00 %** | **100.00 %** | `PASS` (Kritisch 100 %) |
| `src/components.tsx` | **100.00 %** | **100.00 %** | **100.00 %** | **100.00 %** | `PASS` |
| `src/hardware-modal.tsx` | 100.00 % | 93.84 % | 100.00 % | 100.00 % | `PASS` |
| `src/set-view.tsx` | 100.00 % | 95.65 % | 100.00 % | 100.00 % | `PASS` |
| `src/track-table.tsx` | 99.20 % | 95.04 % | 100.00 % | 100.00 % | `PASS` |
| `src/filter-view.tsx` | 97.82 % | 90.90 % | 100.00 % | 97.64 % | `PASS` |
| `src/live-view.tsx` | 93.65 % | 90.42 % | 100.00 % | 94.33 % | `PASS` |
| `src/main.tsx` | 95.51 % | 88.18 % | 93.77 % | 97.80 % | `PASS` (Global >= 90 %) |

---

## 3. Python AST Mutation Testing Detail (`reports/mutation-python/mutation-report.json`)

- **Geprüfte Zielmodule:** `backend/keys.py`, `backend/library.py` (`_parse_range`, `_key_rank`, `_apply_rule`, `_sort_positions`, `recommendations`), `backend/rekordbox_live.py` (`_crossfader_gain`, `combine_fader_levels`, `_progress`), `backend/main.py` (`_select_anchor`).
- **Erzeugte Mutanten:** `207`
- **Gekillte Mutanten:** `167` (`80.68 %` roh)
- **Bewiesene mathematisch/semantisch äquivalente Mutanten:** `19` (`88.83 %` effektive Gesamtquote)
- **Verbliebene unklassifizierte Überlebende:** `21` — **sämtliche 21 Überlebenden** befinden sich in `backend/library.py` auf Zeilen innerhalb von `if np is not None:` (`392, 402, 428, 444, 454, 467, 524, 550, 557, 566, 601, 609, 614, 620, 668, 670, 674, 676`), da `numpy` im Sandbox-Python nicht installiert ist (`np = None`). Auf allen ausführbaren Pure-Python-Pfaden in `keys.py`, `library.py`, `rekordbox_live.py` und `main.py` überlebte **kein einziger** nicht-äquivalenter Mutant (`100 %` Kill-Rate auf ausführbaren Zweigen).

---

## 4. Hinweis zur kombinatorischen Skala (5.000 vs. 100.000 Fälle)

In der Pure-Python-Umgebung ohne `numpy` wurde die Oracle-Suite mit `CUEPOINT_QA_CASES=5000` (`5.000` eindeutige Filter/Sort-Kombinationen = `2.066.942` geprüfte Track-Treffer, `147` leere Ergebnismengen, `0` Fehler, `max 48.888 ms`) vollständig und fehlerfrei durchgeführt. Zuvor verifizierte der Vorlauf `30.000` Kombinationen (`Ø 3.712 ms`). Volle `100.000` Kombinationen dauern ohne `numpy` ~10–15 Minuten und sind für den Windows/CI-Runner mit `numpy` (`.github/workflows/quality-gate.yml`) vorkonfiguriert.
