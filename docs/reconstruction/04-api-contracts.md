# 04 — IPC & JSON-RPC API Contracts

## 1. Electron Preload Bridge (`window.cuepoint`)

Exposed via `contextBridge.exposeInMainWorld('cuepoint', ...)`:
- `request<T>(method: string, params?: object): Promise<T>` — Invokes `cuepoint:request` (whitelisted methods only)
- `choose(directory: boolean): Promise<string | null>` — Opens native file/folder dialog (`db`, `pdb`)
- `window(action: 'minimize' | 'maximize' | 'close'): Promise<void>` — Window frame controls
- `revealFile?(path: string): Promise<boolean>` — Reveals existing local file in OS explorer

Web Preview Fallback (when `window.cuepoint` is undefined):
- Calls `POST /api/cuepoint/request` with `{ method, params }` -> routed to persistent Python worker over stdio JSON-RPC.

## 2. Whitelisted JSON-RPC Methods (Main <-> Python Worker)

Transport: Newline-delimited JSON on `stdin` / `stdout` (`ensure_ascii=False, allow_nan=False`).
Request: `{"id": <int>, "method": "<name>", "params": <object>}`
Response: `{"id": <int>, "result": <any>}` or `{"id": <int>, "error": "<message>", "errorCode"?: "<CODE>"}`

| Method | Params | Result Schema | Error Codes |
|---|---|---|---|
| `open` | `{ path?: string }` | `Source` (`{ path, kind, total, genres, bpmBounds, withKey }`) | `SOURCE_NOT_FOUND`, `SOURCE_UNREADABLE`, `SNAPSHOT_INCONSISTENT`, `SQLCIPHER_UNAVAILABLE`, `DATABASE_DECRYPT_FAILED`, `DATABASE_SCHEMA_INVALID` |
| `demoLibrary` | `{ path?: string }` | `Source` (`kind: "Demo"`) | `SOURCE_UNREADABLE`, `DATABASE_SCHEMA_INVALID` |
| `query` | `{ search?, rules?, groups?, groupLogic?, excludeId?, genres?, bpmMin?, bpmMax?, keys?, rating?, yearMin?, yearMax?, plays?, sorts?, sort?, desc?, facets?, idsOnly?, fields? }` | `{ rows, counts: [genreCount, bpmCount, keyCount, finalCount], genres: Facet[], keys: Facet[], histogram: {bpm, count}[], ms }` | `SOURCE_NOT_FOUND` (no library loaded) |
| `detail` | `{ id: string }` | `Detail \| null` (`Track` + `album, label, added, created, path, comment, key_raw, plays, bitrate, sample_rate, bytes, waveform: number[]`) | — |
| `interfaces` | `{}` | `{ name: string, ip: string }[]` | — |
| `usb` | `{}` | `string[]` (candidate DB paths on removable/fixed Windows drives) | — |
| `linkStart` | `{ ip: string, announce?: boolean }` | `true` | `NETWORK_INTERFACE_UNAVAILABLE`, `DJ_LINK_PORT_UNAVAILABLE` |
| `linkStop` | `{}` | `true` | — |
| `demoLink` | `{ next?: boolean, index?: number }` | `true` | — |
| `live` | `{ deck?: number, masterSource?: number, tolerance?: number, harmonic?: boolean }` | `{ state, error, decks, anchor, matches, media }` | — |
| `bindMedia` | `{ source: number (1..15), slot: number (2\|3\|7), path: string }` | `true` | `MEDIA_NOT_FOUND`, `DATABASE_SCHEMA_INVALID` |
| `unbindMedia` | `{ source: number (1..15), slot: number (2\|3\|7) }` | `true` | — |
| `rekordboxTransport` | `{ id?: string, action?: 'reveal'\|'deck1'\|'deck2', query?: string, path?: string }` | `{ ok, reason, action, deck, query, path, copied, message }` | `REKORDBOX_NOT_RUNNING` (`ok: false, reason: "no_window"`) |

## 3. Staged Facet Computation Order in `Library.query()`

1. Free-text `search` (all terms must appear in normalized `SEARCH_FIELDS`)
2. Top-level `rules` (AND)
3. Nested `groups` (`groupLogic`: `"AND"` / `"OR"`; within group `mode`: `"AND"` / `"OR"`; empty values ignored except `op: "empty"`)
4. `excludeId`
5. **Compute `genres` facet** from current mask -> Apply `genres` filter -> **`counts[0]` = `genre_count`**
6. **Compute `histogram`** (5-BPM bins) from current mask -> Apply `bpmMin`/`bpmMax` -> **`counts[1]` = `bpm_count`**
7. **Compute `keys` facet** from current mask -> Apply `keys` filter -> **`counts[2]` = `key_count`**
8. Apply `rating`, `yearMin`, `yearMax`, `plays` -> Sort via `_sort_positions` -> **`counts[3]` = `len(rows)`**
