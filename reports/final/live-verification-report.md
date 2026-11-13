# Live-Integrationsbericht (Rekordbox & Pro DJ Link) — Cuepoint v1.1.0

**Ausdrücklicher Verifikationsstatus:** **`UNVERIFIED_REAL_REKORDBOX`**

Gemäß Abschnitt 11.8 der Spezifikation wird unmissverständlich ausgewiesen, dass in dieser Linux-x86_64-Container-Umgebung **keine reale Rekordbox-Desktop-Installation (`rekordbox.exe`)**, keine Windows UI Automation (`UIAutomationCore.dll` / `comtypes`) und **keine physischen Pioneer CDJ-/XDJ-Player** zur Verfügung standen. Synthetische Tests und Mocks ersetzen keine reale Hardware- bzw. Desktop-Prüfung.

---

## 1. Getrennte Betriebsarten (Abschnitt 7.1)

| Modus | Reale Implementierung | Geprüfter Umfang im Nachbau | Kennzeichnung |
|---|---|---|---|
| **Modus A: Demo (`demoLink` / `demoLibrary`)** | `Core.status` + `fixtures.py` | Im Browser (`hardware-modal.png`) & Unit-Tests (`test_backend_coverage.py`) geprüft; UI kennzeichnet ausdrücklich `Demo-Modus aktiv` / `AKTUELLER TRACK (DEMO-LINK)`. | `PASS` (Simulation klar als Demo markiert) |
| **Modus B: Pro DJ Link (`UDP 50000 / 50002`)** | `backend/live.py` (`DjLink`, `decode_status`, `announce_packet`, `interfaces`) | `tests/test_live.py`: Loopback-UDP-Paketdekodierung (`0x0a`-Status, BPM, Pitch, Play/Master, Slot 2/3/7), Ankündigungs-Opt-in-Schutz, Multi-Media Konfliktlösung (`bindMedia`/`unbindMedia`), Timeout alter Decks. Realer CDJ-Netzwerktest nicht möglich. | `PASS` (UDP-Protokoll/Loopback) / `UNVERIFIED` (Hardware-CDJ) |
| **Modus C: Lokales Rekordbox (`UIA` & `SendInput`)** | `backend/rekordbox_live.py` (`RekordboxPlayback`, `send_track_to_rekordbox`, `_crossfader_gain`, `combine_fader_levels`, `_progress`), `backend/main.py` (`_select_anchor`) | `tests/test_rekordbox_playback.py` & `tests/test_backend_coverage.py`: Positions-/Nachbarschaftszuordnung (`_nearest`, `_nearest_x`), Two-Deck Anchor-Stabilisierung & Fader-Hysterese (`>= 0.10`), Crossfader-Linearität, fehlende Fader als `None`, Win32 Transport-Guard (`no_window` bei fehlendem Rekordbox). | **`UNVERIFIED_REAL_REKORDBOX`** (nur per Win32/UIA-Mocks getestet) |

---

## 2. Geprüfte Invarianten in Pro DJ Link & Fader-/Matching-Logik

- **Track-ID-Mehrdeutigkeit auf USB/SD:** Zwei Player mit derselben `Track-ID` (`42`) auf verschiedenen Medien/Slots (`USB 1 Slot 3` vs. `SD Slot 2`) werden anhand des `(source, slot)`-Tupels in `Core.media` korrekt getrennt (`test_live.py`).
- **Metadaten-Disambiguierung (`Core.status`):** Lokale Rekordbox-Decks matchen über normalisierte `(title, artist)`-Identität; bei mehrfachen Treffern verfeinert eine Prüfung auf Original-BPM (`<= 0.05`) und Länge (`<= 2 s`). Bleiben `!= 1` Kandidaten übrig, wird `libraryId = None` gesetzt statt blind zuzuordnen.
- **Sticky-Anchor-Schutz:** Ein kurzzeitig pausiertes oder verdecktes Deck übernimmt bei Fader-Differenz `< 0.10` ohne Masterwechsel nicht fälschlich den Anchor; in `src/main.tsx` verhindert `lastLiveDeck` zudem ein visuelles Springen während kurzer UIA-Aussetzer.
