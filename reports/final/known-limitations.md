# Bekannte Einschränkungen, Blockaden & Abweichungen — Cuepoint v1.1.0

Alle offenen Punkte und Umweltbeschränkungen werden nachfolgend vollständig und ohne Beschönigung ausgewiesen.

---

## 1. Externe Plattform- und Umgebungsblockaden (`BLOCKED` / `UNVERIFIED_REAL_REKORDBOX`)

1. **Kein Windows-x64-Host (`.exe` Packaging `BLOCKED`):**
   - Der Nachbau lief in einem Linux-`x86_64`-gVisor-Container.
   - `scripts/build-backend.ps1` (PyInstaller mit `UIAutomationCore.dll` / `comtypes.gen.UIAutomationClient`) und `electron-builder --win portable` (`Cuepoint-1.1.0-Windows-x64.exe`) konnten daher nicht ausgeführt werden. Der bereinigte CI-Workflow `.github/workflows/quality-gate.yml` liegt für `windows-latest` bereit.
2. **Keine echte Rekordbox-Installation (`UNVERIFIED_REAL_REKORDBOX`):**
   - `rekordbox.exe`, UI-Automation-Live-Trees unterschiedlicher Rekordbox-Versionen, reale `SendInput`-Fokuswechsel sowie Produktions-`master.db`-Dateien wurden **nicht** gegen ein laufendes Rekordbox getestet.
   - `backend/rekordbox_live.py` wurde über deterministische Win32/UIA-Mocks (`tests/test_rekordbox_playback.py`, `tests/test_backend_coverage.py`) verifiziert.
3. **Fehlende Python-Pakete im Container (`numpy`, `psutil`, `pyrekordbox`, `sqlcipher3`, `rekordbox-pdb`, `pytest`, `pytest-cov`, `ruff`):**
   - `backend/library.py` und `backend/live.py` liefen im Container über ihren eingebauten Pure-Python-/SQLite-Fallback (`numpy_enabled: false`).
   - `test_encrypted_one_library_export_is_read_only` (`1` Test) wurde automatisch übersprungen (`pytest.skip`), da `sqlcipher3` und `pyrekordbox` fehlen. Die `_read_sqlite`-Entschlüsselungs-, Fehler- und Key-Auswahlpfade wurden in `test_backend_coverage.py` per Mock getestet.
   - Python-AST-Mutanten innerhalb von `if np is not None:` (`21` Mutanten in `backend/library.py`) konnten mangels `numpy` im Container nicht ausgeführt werden (deshalb `80.68 %` statt `>= 95 %`; auf allen ausführbaren Pure-Python-Pfaden `100 %` Kill-Rate).
   - Python-Branch-Coverage (`pytest --cov=backend --cov-branch`) und `ruff` konnten mangels Installation nicht gemessen werden.
4. **Fehlendes StrykerJS (`BLOCKED`):**
   - `stryker.config.mjs` ist vollständig konfiguriert (`api.ts`, `metadata.ts`, `camelot-wheel.tsx`), `@stryker-mutator/core` ist jedoch nicht in der Container-Umgebung vorinstalliert.
5. **Keine isolierte `Electron`-Binary-GUI im Linux-Headless-Container (`BLOCKED` für GUI-Spawn):**
   - `electron/main.cjs` und `electron/preload.cjs` wurden vollständig im Unit-Harness (`tests/electron/main.test.mjs`: `4/4` PASS) getestet; die gerenderte React-Anwendung mit echtem Python-Subprozess lief stattdessen über den port-3000-Express+Vite-Worker-Bridge (`server.ts`) in echtem Headless Chromium (`playwright-cli`).

---

## 2. Kombinatorische Skalierungs- & Performance-Hinweise

- Im Container ohne NumPy wurden **5.000** eindeutige kombinatorische Oracle-Pläne in `52.10 s` mit **100 % Korrektheit** (`Ø 6.073 ms`, `P95 29.380 ms`, `max 48.888 ms`, `0` Fälle `>= 50 ms`) geprüft (zuvor `30.000` Fälle im Vorlauf). Für die vollen `100.000` Fälle sieht `.github/workflows/quality-gate.yml` `CUEPOINT_QA_CASES=100000` mit `numpy` vor.

---

## 3. Nächste Schritte für vollständige Windows-Release-Abnahme

Auf einer Windows-x64-Maschine oder im GitHub Actions Runner (`windows-latest`):
1. `pip install -r requirements-dev.txt && npm ci`
2. `python tests/generate_synthetic_db.py && pytest --cov=backend --cov-branch --cov-fail-under=90`
3. `CUEPOINT_QA_CASES=100000 pytest tests/test_combinatorial_stress.py tests/test_filter_groups.py`
4. `python scripts/mutate_backend.py && npx stryker run`
5. `npm run package:win` -> erzeugt `release/Cuepoint-1.1.0-Windows-x64.exe` -> Smoke-Suite (`npm run test:ui`) & optionale Live-Prüfung mit geöffneter `rekordbox.exe` (`CUEPOINT_VERIFY_REAL=1`).
