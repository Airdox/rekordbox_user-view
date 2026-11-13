# 03 — Feature Parity & Verification Matrix

Status definitions:
- `Tatsächlich implementiert` (Actually implemented in reference)
- `Teilweise implementiert` (Partially implemented in reference)
- `Nur simuliert` (Simulated only)
- `Nur auf synthetischen Daten geprüft` (Verified only on synthetic data)
- `Mit echter Rekordbox-Installation geprüft` (Verified against real Rekordbox)
- `Nicht überprüfbar` (Unverifiable in current Linux sandbox)

| ID | Feature | User Action | Frontend Component | IPC / RPC | Backend Handler | Reference Status | Reconstruction Target |
|---|---|---|---|---|---|---|---|
| F-01 | Library Open (`master.db`, `exportLibrary.db`, `export.pdb`) | Source menu -> Choose file/folder | `App` (`main.tsx`) | `open` | `Core.replace_library` -> `sources.read_source` | Tatsächlich implementiert (mit echter RB-DB nur unter Windows mit `CUEPOINT_VERIFY_REAL=1`) | Implement + Read-only hash tests; `UNVERIFIED_REAL_REKORDBOX` on Linux |
| F-02 | Synthetic 15,500-Track Demo Library | Initial fallback or Source menu -> Demo | `App` (`main.tsx`) | `demoLibrary` | `Core.handle("demoLibrary")` -> `fixtures.demo_tracks` | Tatsächlich implementiert (auf synthetischen Daten geprüft) | Full implementation & verification |
| F-03 | Read-Only Snapshot + SHA-256 + WAL/Journal | Any DB open/reload | `App` (`main.tsx`) | `open`, `bindMedia` | `sources.snapshot` | Tatsächlich implementiert | Full implementation + before/after SHA-256 test |
| F-04 | SQLCipher Decryption | Open encrypted Rekordbox DB | `App` (`main.tsx`) | `open` | `sources._read_sqlite` | Tatsächlich implementiert (benötigt `sqlcipher3` + `pyrekordbox`) | Implemented + explicit `SQLCIPHER_UNAVAILABLE` / `DATABASE_DECRYPT_FAILED` errors |
| F-05 | Live-Match View & Camelot Wheel | Click Live-Match tab / wheel segments / Ctrl+click | `LiveView`, `CamelotWheel` | `query` | `Library.query` + `keys.compatible` | Tatsächlich implementiert | Full implementation + keyboard + multi-select + Vitest/Browser E2E |
| F-06 | Live-Match Quick Filters (BPM %, Genre, Plays ≤ 2, Rating, Search) | Toggle checkboxes, slider, select, search input | `LiveView` | `query` | `Library.query` | Tatsächlich implementiert | Full implementation + boundary checks |
| F-07 | Filter-Studio Nested AND/OR Groups & 7 UI Operators | Add/remove groups/rules, toggle AND/OR, Apply | `FilterView` | `query` | `Library._apply_rule` + `Library.query` | Tatsächlich implementiert (`gt`/`lt` exist in backend, UI offers 7 operators) | Full implementation + 100k combinatorial oracle tests |
| F-08 | Multi-Stage Sort Cascade | Column headers + Sort Designer | `FilterView`, `TrackTable` | `query` (`sorts`) | `Library._sort_positions` | Tatsächlich implementiert (reference lacks DnD & Alt+Arrow on sort rows) | Implement + add DnD & Alt+ArrowUp/Down on `.sortrow` |
| F-09 | Dynamic Facets & BPM Histogram | Returned by `query` (when `facets !== false`) | Backend `Library.query` | `query` | `_group_facet`, `_histogram_from_mask` | Tatsächlich implementiert im Backend (UI ignores `genres`/`keys`/`histogram` arrays) | Preserve exact staged facet computation & verify via tests |
| F-10 | Virtualized Track Table & Context Menu | Scroll, Arrow keys, Right-click row/header | `TrackTable` | `detail`, `rekordboxTransport` | `Library.detail`, `send_track_to_rekordbox` | Tatsächlich implementiert | Full implementation (40px row / 33px header) |
| F-11 | Real ANLZ Waveform vs Synthetic Fallback | Load track detail / Livebar | `LiveWaveform`, `MiniWave` | `detail` | `library.waveform` (`AnlzFile.parse_file`) | Teilweise implementiert (reference does not label synthetic vs real ANLZ) | Distinguish explicitly in UI (`ANLZ-Analyse` vs `Synthetische Vorschau`) |
| F-12 | Set-Builder, Transitions & Exports (CSV/M3U8/XML) | Add/remove/reorder tracks, Export buttons | `SetView`, `App` | Local state + `localStorage` | Frontend (`api.ts`) | Tatsächlich implementiert | Full implementation + export content verification |
| F-13 | Pro DJ Link (UDP 50000/50002) & USB/SD Media Binding | Hardware Modal -> Connect / Bind Media | `HardwareModal` | `interfaces`, `usb`, `linkStart`, `linkStop`, `bindMedia`, `unbindMedia` | `DjLink`, `Core.status`, `Library.match_media` | Tatsächlich implementiert (UDP loop tested; real CDJ hardware unverified) | Full implementation + loopback UDP & multi-media conflict tests |
| F-14 | Local Rekordbox UI Automation & Fader/Crossfader | Automatic when `Master` loaded on Windows | `App`, `HardwareModal` | `live`, `rekordboxTransport` | `RekordboxPlayback`, `send_track_to_rekordbox` | Nur auf Windows UIA / per Mock geprüft | Full implementation + mock WinDLL/UIA tests; `UNVERIFIED_REAL_REKORDBOX` on Linux |
| F-15 | Persistence (`localStorage` + `userData/library.json`) | Reload app / reopen | `App`, `electron/main.cjs` | `open` | `remember()`, `loadColumns()`, `loadSetTracks()`, `loadCustomPresets()` | Tatsächlich implementiert | Full implementation + reload persistence verification |
