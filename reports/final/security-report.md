# Sicherheitsbericht — Cuepoint v1.1.0 Nachbau

Status: **`PASS`** (Originaldaten-Schutz, Electron-Sandbox & IPC-Whitelist vollständig geprüft; SQLCipher-Entschlüsselungspfad Code-seitig abgesichert, mangels `sqlcipher3` im Container im Mock verifiziert).

---

## 1. Absoluter Originalschutz (Rekordbox-Datenbanken)

| Kontrolle | Implementierung (`backend/sources.py`) | Testnachweis | Ergebnis |
|---|---|---|---|
| **Nur binäres Lesen der Quelle** | `snapshot()` öffnet Quelldateien ausschließlich mit `.open("rb")`. | `test_readonly.py`, `test_snapshot_reads_committed_wal_without_touching_source` | `PASS` |
| **WAL/Journal-Konsistenz & SHA-256** | Vergleicht Vor-/Nachher-`stat()` (`st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns`) und SHA-256-Prüfsummen über `.db`, `-wal` und `-journal` in maximal 3 Versuchen. Inkonsistente Snapshots werfen `SNAPSHOT_INCONSISTENT`. | `test_backend_coverage.py` (Retry- & Inkonsistenztests) | `PASS` |
| **SQLite Write-Lock verhindern** | Öffnet ausschließlich die temporäre Kopie unter `tempfile.TemporaryDirectory` mit `?mode=ro`, `PRAGMA query_only = ON` und `PRAGMA trusted_schema = OFF`. | `test_readonly.py` (Hash & `mtime_ns` der Quelldateien + Sidecars bleiben bitidentisch) | `PASS` |
| **Keine geheimen Schlüssel in Logs** | `diagnostics.emit_log()` loggt strukturierte JSON-Ereignisse auf `stderr`, niemals SQLCipher-Schlüssel/Passwörter. | Code-Audit `backend/sources.py`, `backend/diagnostics.py` | `PASS` |

---

## 2. Electron-Sicherheit & Web-Bridge

| Kontrolle | Implementierung (`electron/main.cjs`, `preload.cjs`, `server.ts`) | Testnachweis | Ergebnis |
|---|---|---|---|
| **Renderer-Isolation** | `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`, kein Anwendungsmenü (`Menu.setApplicationMenu(null)`). | `tests/electron/main.test.mjs` Subtest 2 | `PASS` |
| **Navigations- & Fenster-Sperre** | `setWindowOpenHandler(() => ({ action: 'deny' }))`, `will-navigate` -> `event.preventDefault()`, `setPermissionRequestHandler(..., false)`. | `tests/electron/main.test.mjs` Subtest 2 (`evil.example`, `media`) | `PASS` |
| **IPC-Methoden-Whitelist & Frame-Prüfung** | `trusted(event)` prüft `sender === webContents && senderFrame === mainFrame`; nur 13 definierte Methoden (`open`, `demoLibrary`, `query`, `detail`, `interfaces`, `usb`, `linkStart`, `linkStop`, `demoLink`, `live`, `bindMedia`, `unbindMedia`, `rekordboxTransport`). Web-Bridge `server.ts` erzwingt exakt dieselbe Whitelist `ALLOWED_METHODS`. | `tests/electron/main.test.mjs` (`evalShell` abgelehnt, gefälschter `senderFrame` abgelehnt) | `PASS` |
| **Explorer-Reveal Validierung (`cuepoint:revealFile`)** | Prüft `trusted(event)`, `typeof filePath === 'string'`, `filePath.length > 0` und `existsSync(filePath)` vor `shell.showItemInFolder`. | `tests/electron/main.test.mjs` Subtest 2 | `PASS` |
| **Worker-JSON-RPC Trennung** | JSON-RPC ausschließlich auf `stdout`; strukturierte Diagnosen und Fehler ausschließlich auf `stderr`. | `backend/diagnostics.py`, `tests/electron/main.test.mjs` Subtest 3 | `PASS` |

---

## 3. Rekordbox-Transport & Pro DJ Link Sicherheitsregeln

| Kontrolle | Implementierung | Testnachweis | Ergebnis |
|---|---|---|---|
| **Keine unkontrollierten Tastatureingaben** | `send_track_to_rekordbox()` sucht aktiv per `EnumWindows`/`GetWindowTextW` das Rekordbox-Hauptfenster (`RekordboxWindow`), bringt es gezielt in den Vordergrund und liefert ohne gefundenes Fenster sauber `ok: false, reason: "no_window"`. | `tests/test_rekordbox_playback.py`, `tests/test_backend_coverage.py` | `PASS` (via Win32 Mocks) |
| **Netzwerk-Schnittstellen-Bindung** | `linkStart` prüft explizit ausgewählte Interface-IP (`NETWORK_INTERFACE_UNAVAILABLE`) und aktiviert virtuellen CDJ-Announce-Modus nur auf expliziten Benutzer-Opt-in. | `tests/test_live.py`, `tests/test_backend_coverage.py` | `PASS` |

---

## 4. Fehlerklassen-Abdeckung (Abschnitt 10.3)

Definiert in `backend/diagnostics.py` (`ERROR_CODES`) und gemappt auf JSON-RPC (`errorCode`):
`SOURCE_NOT_FOUND`, `SOURCE_UNREADABLE`, `SNAPSHOT_INCONSISTENT`, `SQLCIPHER_UNAVAILABLE`, `DATABASE_DECRYPT_FAILED`, `DATABASE_SCHEMA_INVALID`, `TRACK_NOT_FOUND`, `TRACK_AMBIGUOUS`, `ANALYSIS_FILE_MISSING`, `PYTHON_WORKER_UNAVAILABLE`, `IPC_TIMEOUT`, `NETWORK_INTERFACE_UNAVAILABLE`, `DJ_LINK_PORT_UNAVAILABLE`, `REKORDBOX_NOT_RUNNING`, `REKORDBOX_UI_UNAVAILABLE`, `MEDIA_NOT_FOUND`.
