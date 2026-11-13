# 06 — UI Specification (Cuepoint)

## 1. Layout Shell (`#app` CSS Grid)
5-row full-viewport layout (`100vh`, `min-height: 620px`):
1. `.windowbar` (`34px`): Frameless titlebar (`Cuepoint / Rekordbox Pro-Assistant`), active source/read-only summary, minimize/maximize/close window controls.
2. `.topnav` (`55px`): Brand wordmark (`Cuepoint` / `TRACK ANALYSIS & SET PREPARATION`), 3 primary tabs (`Live-Match`, `Filter-Studio`, `Set-Builder` with count), Source menu dropdown (`#sourceButton`), Live status button (`#liveStatusBtn`), Help button (`#helpBtn`).
3. `.livebar` (`105px`): Always-visible active deck/reference strip:
   - Left: Album art disc + status kicker + `#playingName` + artist + tags (BPM, `KeyBadge`, Genre)
   - Center: `LiveWaveform` (48px height, 225 bars) with explicit indicator distinguishing **Rekordbox ANLZ-Analyse** (real PWAV samples) vs **Synthetische Vorschau** (deterministic fallback when ANLZ missing)
   - Right: Source status + `Nächster Demo-Track` (`#changeTrack`) + `Referenz fixieren/lösen` (`#pinTrack`)
4. `.area` (`minmax(0, 1fr)`): Left `.sidenav` (`204px`, `179px` <= 1400px) + `.workspace` (active tab view)
5. `.footer` (`31px`): Active library path/kind, current view, live connection dot + label, `"Originaldaten: unverändert"`.

## 2. Primary Views

### Live-Match (`#view-live`, 3-column grid `316px | minmax(410px,1fr) | 266px`)
- **Left Pane**: `CamelotWheel` (320x320 SVG, 24 interactive `<g role="button" tabindex="0">` wedges for `1A..12A` inner & `1B..12B` outer, click = single key, Ctrl/Shift/Meta+click = multi-select, Enter/Space keyboard support), 4 compatible key chips, `"Alle harmonisch passenden Keys wählen"`, `autoFollow` & `includeCurrent` checkboxes.
- **Center Pane**: Result count & backend query duration (`ms`), search (`#liveSearch`), sort select (`#liveSort` with 10 presets), active filter summary strip, virtualized `TrackTable` (`40px` row height, `33px` sticky header).
- **Right Pane**: Quick live constraints (`useBpm`, `bpmTolerance` slider 0–12%, `sameGenre`, `unplayedLive` ≤ 2, `liveRating`), Selected Track inspector (`+ Set`, `↗ In Rekordbox`, `▶ Deck A`, `▶ Deck B`, `⌕ Details`), footer actions (`Hardware`, `Filter-Studio`, `Setliste`).

### Filter-Studio (`#view-filter`, 3-column grid `353px | minmax(390px,1fr) | 253px`)
- **Left Pane**: Preset selector (`#presetSelect`) + `"Speichern"` (`#savePreset`), global `groupLogic` (`UND`/`ODER`), dynamic nested `.groupbox` list (each with `Alle (UND)`/`Eine (ODER)`, rules over 18 fields & 7 operators `contains|eq|neq|gte|lte|range|empty`), `"Filter aktualisieren"`, `"+ Auswahl zum Set"`.
- **Center Pane**: Search (`#filterSearch`), `"Sortierkaskade"` toggle + `"↓ M3U8"` filtered export, summary strip, `.sortcascade` pill trail, expandable `#sortDesigner` with field/direction/up/down/remove + drag-and-drop + `Alt+ArrowUp`/`Alt+ArrowDown` keyboard reordering, virtualized `TrackTable`.
- **Right Pane**: Synchronized `"Set-Korb"` (preview up to 4 items + remove), Selected Track inspector, `"Set-Builder öffnen"`.

### Set-Builder (`#view-set`, 2-column grid `minmax(490px,1fr) | 328px`)
- **Left Pane**: Toolbar (`+ Tracks suchen`, `↓ M3U8-Playlist`, `↓ Rekordbox XML`, `↓ CSV`), draggable/reorderable `.setrow` list with per-transition harmonic & BPM delta analysis (`.transition`), footer (`Set leeren`, `Rekordbox-Übergabe`).
- **Right Pane**: 4 KPI stat boxes (`Tracks`, `Dauer`, `BPM-Spanne`, `Harmonische Übergänge`), workflow guide, read-only guarantee banner.

## 3. Persistence Keys (`localStorage` & Electron `userData`)
- `airdox.columns` — Visible `TrackTable` columns
- `airdox.setTracks` — Saved Set-Builder track list
- `airdox.customPresets` — User-saved filter presets
- `userData/library.json` (Electron) / `.cuepoint-state.json` (Web server) — Last opened DB path
