# Visueller & GUI-Vergleichsbericht — Cuepoint v1.1.0 Nachbau vs. Referenz

Status: **`PASS`** (geprüft am `1440x900` Viewport, Scale `1.0`, gegen `referenzbilder/111111.png` sowie DOM-/Geometrie-Assertions aus `tests/electron-smoke.cjs` via Headless Chromium auf `http://127.0.0.1:3000`).

---

## 1. Vorhandene Evidenzdateien

- **Referenz-Screenshot:** `referenzbilder/111111.png` (Filter-Studio mit geöffnetem Sortierdesigner & Preset; Kopie abgelegt unter `reports/evidence/reference/111111.png`)
- **Side-by-Side Vergleich (`1440x900` vs. Referenz):** `reports/evidence/comparisons/filter-studio-vs-reference.png`
- **Nachbau-Screenshots (`reports/evidence/reconstruction/`):**
  - `live-match.png` (`Live-Match`, Camelot `9A`, BPM `±6 %`, Suche `Techno`, Inspector + Set `+1`)
  - `filter-studio.png` (`Filter-Studio`, `Techno / Peak`, Sortierkaskade nach `Alt+ArrowDown`, Inspector + Set `2`)
  - `set-builder.png` (`Set-Builder`, `2` Tracks, Übergang `#1 -> #2`, Reorder + 4 KPI-Kacheln)
  - `hardware-modal.png` (`Hardware, Pro DJ Link & Quellmedien`, `Demo-Link` aktiviert)
- **Viewport-Overlay-Nachweis (`#viewportIndicator`):** Nachgerüstet gemäß Benutzeranforderung (`position: absolute`, oben links, `pointer-events: none`); live in Headless Chromium bei `1280x720` (`"1280 × 720"`) und dynamisch nach Resize auf `1440x900` (`"1440 × 900"`) mit `0` Konsolen-/Seitenfehlern verifiziert.
- **Maschinelle Protokolle:** `reports/evidence/reconstruction/gui-actions.json` & `environment.json`

---

## 2. Gemessene Geometrie & Styling-Übereinstimmung (`1440x900`)

| Merkmal | Referenz-Zielwert (`111111.png` / `electron-smoke.cjs`) | Nachbau (Live Chromium gemessen) | Status |
|---|---|---|---|
| **Hintergrundfarbe (`body`)** | `rgb(17, 20, 24)` (`#111418`) | `rgb(17, 20, 24)` | `PASS` |
| **Aktiver Nav-Tab** | `rgb(32, 75, 121)` (`#204b79`) | `rgb(32, 75, 121)` | `PASS` |
| **Horizontaler Document-Overflow** | `<= 1 px` | `0 px` in allen 3 Ansichten | `PASS` |
| **Header-Schalen (`windowbar / topnav / livebar / footer`)** | `30–38 / 50–60 / 95–120 / 26–36 px` | `34 / 55 / 105 / 31 px` | `PASS` |
| **TrackTable Zeilenhöhe / Headerhöhe** | `40 px` / `33 px` | `40 px` / `33 px` | `PASS` |
| **Virtualisiertes DOM (15.500 Tracks)** | `< 100` Zeilen im DOM | `21` gerenderte Zeilen (`filterVirtDomRows: 21`) | `PASS` |
| **Button-Clipping / Overflow** | `0` abgeschnittene Buttons | `[]` (`0` abgeschnittene Buttons) | `PASS` |
| **Live-Match Pane-Breiten (x=204..1440)** | 3 Spalten + Sidenav | `316 px | 654 px | 266 px` | `PASS` |
| **Filter-Studio Pane-Breiten (x=204..1440)** | 3 Spalten + Sidenav | `353 px | 630 px | 253 px` | `PASS` |
| **Set-Builder Pane-Breiten (x=204..1440)** | 2 Spalten + Sidenav | `908 px | 328 px` | `PASS` |
| **Waveform-Unterscheidung** | Echte ANLZ vs. synthetisch sichtbar trennen | `WAVEFORM-VORSCHAU · SYNTHETISCH (KEINE ANLZ)` (`data-waveform-source="synthetic"`, `226` `<rect>`-Balken) | `PASS` |

---

## 3. Beobachtete visuelle Unterschiede zur Referenz-PNG (`111111.png`)

1. **Topbar Datenquelle & Live-Status:** Statt statischem Demo-Label (`DEMO · simulierte Trackdaten`) zeigt der Nachbau dynamisch die tatsächlich geöffnete Quelle (`Demo · 15.500 Tracks`) sowie im geöffneten Hardware-Dialog `Demo-Modus aktiv` bei `Demo-Link`.
2. **Waveform-Transparenz:** Im Live-Player-Streifen kennzeichnet der Nachbau explizit `WAVEFORM-VORSCHAU · SYNTHETISCH (KEINE ANLZ)` statt generischem `TRACK-ANALYSE / WAVEFORM-VORSCHAU`, sodass keine synthetische Darstellung fälschlicherweise als Rekordbox-ANLZ-Analyse interpretiert werden kann.
3. **Schmale Filter-Studio-Mittelspalte bei geöffneter Sortierkaskade (`630 px` bei `1440x900`):** Nach Klick auf `+ Set` in der rechten Tabellenspalte scrollt der horizontale Tabellencontainer leicht nach rechts (`#`-Spaltenkopf wird um ca. `12 px` nach links verschoben), während alle Buttons und Headerzellen lesbar bleiben (`clippedButtons: []`).
4. **Kurzzeitiges Toast-Overlay:** Unmittelbar nach Klick auf `+ Set` überlagert das temporäre Bottom-Right-Toast (`Zu Set hinzugefügt: ...`, verschwindet automatisch) kurzzeitig die unteren Inspector-/Set-Buttons.

---

## 4. E2E-Benutzerinteraktionen (`reports/evidence/reconstruction/gui-actions.json`)

| Schritt | Aktion | Ergebnis | Status |
|---|---|---|---|
| 1 | Initiales Laden der `15.500`-Track-DB + Livebar + 24 Camelot-Segmente | `15.500` Tracks, `226` Wave-Rects, `0` Console-/Page-Errors | `PASS` |
| 2 | Klick Camelot `9A`, `BPM-Toleranz ±6 %`, Suche `Techno`, Zeile wählen, `+ Set` | `18 Treffer · 15.1 ms`, Set-Zähler `1` | `PASS` |
| 3 | Tab `Filter-Studio`, Preset `Techno / Peak`, Sortierkaskade `+ Sortierstufe` & `Alt+ArrowDown`, 2. Track `+ Set` | `737 Treffer · 10.6 ms`, Sortierstufe `#1` wechselt per `Alt+ArrowDown` von `genre` auf `year`, Set-Zähler `2` | `PASS` |
| 4 | Tab `Set-Builder`, Übergangsprüfung & `Nach unten` | `2` Tracks, `1` Übergangsanalyse, Reihenfolge umgedreht (`Drift`/`Blue Hour` -> `Blue Hour`/`Drift`), BPM `116.2–140.8` | `PASS` |
| 5 | Kompletter `page.reload()` (`localStorage`-Persistenz) | Set-Zähler nach Reload weiterhin `2` | `PASS` |
| 6 | `#liveStatusBtn` -> Hardware-Modal -> `Demo-Link` -> `Escape` | Deck 1 `Dissolve – Kinetic State 07` (`136.63 BPM`, `4B`) angezeigt; `Escape` schließt sauber | `PASS` |
