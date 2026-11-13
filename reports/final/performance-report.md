# Performance-Bericht — Cuepoint v1.1.0 (15.500-Track Referenzbibliothek)

## 1. Testumgebung & Datenbasis

- **Umgebung:** Linux `4.19.0` (`x86_64` gVisor Sandbox, 2 vCPUs), Python `3.10.12` (Pure-Python `C-BigInt` Bitmasks + `C-Timsort` `__getitem__` Modus, `numpy_enabled: false`), Node `v22.23.2`.
- **Testbibliothek:** `build/synthetic_test_master.db` — **15.500 Tracks**, `2.40 MiB` (`163 Byte/Track`), Generierungszeit `0.22 s` (`tests/generate_synthetic_db.py`).

---

## 2. Backend Query-Engine Messreihen (Isoliert, ohne NumPy)

### A. Kontrollierte Messreihe (3 Warm-up + 30 Wiederholungen pro Szenario)

| Szenario | Treffer | Min (ms) | P50 / Median (ms) | P95 (ms) | Max (ms) | Ziel <= 50 ms |
|---|---:|---:|---:|---:|---:|---|
| **Cold Load (`Library.load` 15.500 Tracks inkl. Indexbau)** | 15.500 | — | — | — | `2436.45` | Einmaliger Start (`2.44 s`) |
| **Live-Match (4 Keys `7A/8A/8B/9A`, BPM ±4 %, Rating ≥ 3, Sort `bpm ↑`)** | 426 | `7.770` | `8.226` | `16.183` | `48.948` | `PASS` (< 50 ms) |
| **Filter-Studio (Verschachtelte `AND`/`OR` Gruppen + Staged Facets + 3-stufiger Sort)** | 737 | `6.859` | `7.060` | `11.931` | `21.308` | `PASS` (< 50 ms) |
| **Unicode-Freitextsuche (`nachtflug`) + 4-stufiger Sort (`idsOnly`)** | 196 | `8.292` | `13.789` | `40.890` | `41.756` | `PASS` (< 50 ms) |

### B. Kombinatorischer Stress-Lauf (`5.000` eindeutige Filter/Sort-Pläne gegen SQL-Oracle)

- **SQL + ID-Projektion (`5.000` Anfragen):** `Ø 6.073 ms` | `P95 29.380 ms` | `max 48.888 ms` | **Abfragen `>= 50 ms`: `0`** (`PASS`).
- **Query-Thread CPU-Zeit (`thread_time`):** `Ø 5.708 ms` | `max 50.000 ms` | CPU bei längster Laufzeit: `30.000 ms`.
- **Vollständige Abfragen inkl. Facetten & Zeilen (`6` Stichproben):** `Ø 4.818 ms` | `max 9.334 ms` | **`>= 50 ms`: `0`** (`PASS`).

### C. Rohe SQLite-Baseline zum Vergleich (`tests/profile_query_breakdown.py`)

| SQLite-Messschritt | Zeit (ms) |
|---|---:|
| Execute + 1 Fetch (`LIMIT 1`) | `39.22` |
| Execute + `fetchall()` | `53.23` |
| `json_group_array` | `48.74` |
| `json_group_array` + `json.loads()` | `47.66` |

> **Erkenntnis:** Durch Vorindizierung im In-Memory-`Library`-Objekt (C-Bitmask-Operationen `int.from_bytes` + Multi-Pass C-Timsort `list.sort(key=col.__getitem__)`) schlägt der Engine-Durchschnitt (`~6–8 ms` P50) rohe SQLite-`ORDER BY`-Abfragen (`~53 ms`) selbst **ohne NumPy** deutlich um Faktor ~6–8x. Mit installiertem `numpy` (Zielplattform Windows CI) sind nochmals ~3–5x schnellere Vektoroperationen zu erwarten.

---

## 3. End-to-End GUI-Reaktionszeit & Virtualisierung (Headless Chromium auf Port `3000`)

Gemessen über echte Benutzeraktionen in `playwright-cli` (`reports/evidence/reconstruction/gui-actions.json`):

| Aktion | Sichtbare Backend-/UI-Anzeige | Beobachtetes DOM | Status |
|---|---|---|---|
| **Filter-Studio Preset `Techno / Peak` (über 15.500 Tracks)** | `737 Treffer · 10.6 ms` | `21` gerenderte DOM-Zeilen (von `15.500` total vor Filter) | `PASS` |
| **Live-Match (`9A` + BPM ±6 % + Suche `Techno`)** | `18 Treffer · 15.1 ms` | `0 px` horizontaler Overflow | `PASS` |
| **Scroll-Virtualisierung (Zeilenhöhe `40 px`, Header `33 px`)** | `@tanstack/react-virtual` aktiv | Konstant `21` DOM-Knoten bei 15.500 Tracks | `PASS` |
