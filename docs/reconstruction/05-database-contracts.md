# 05 — Database & Read-Only Snapshot Contracts

## 1. Supported Database Formats & Discovery Order

Candidate directory search order (`sources.candidates(root)`):
1. `<root>/`
2. `<root>/PIONEER/rekordbox/`
3. `<root>/rekordbox/`
4. `<root>/PIONEER/Master/`

Filename priority:
1. `master.db` (Rekordbox Master Database — SQLite / SQLCipher)
2. `exportLibrary.db` (Rekordbox OneLibrary USB Export — SQLite / SQLCipher)
3. `export.pdb` (Legacy Pioneer Device Library — binary PDB parsed via `rekordbox-pdb`)

Default startup path: `E:\PIONEER\Master` (falls back gracefully to saved path or synthetic `Demo` library when missing).

## 2. Read-Only Snapshot Protocol (`sources.snapshot`)

1. Identify primary file + sidecars (`-wal`, `-journal` when `.db`).
2. Retry up to 3 times with backoff (`0.12s`, `0.24s`, `0.36s`):
   - Record `_stamp(path)` (`st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns`) before copy.
   - Open originals exclusively in binary read-only mode (`open(..., "rb")`) and stream copy + SHA-256 digest to a fresh `tempfile.TemporaryDirectory(prefix="cuepoint-")`.
   - Recompute SHA-256 on original and compare `_stamp(path)` after copy.
   - Only if all digests match AND `before == after` is the snapshot accepted.
3. Open SQLite/SQLCipher ONLY on the temporary copy with `?mode=ro`, `PRAGMA query_only = ON`, `PRAGMA trusted_schema = OFF`.
4. Never delete, migrate, reindex, or write to source files or source WAL/journal files.

## 3. Schema Mapping

### Master (`djmdContent`)
- Columns: `ID`->`id`, `Title`->`title`, `FolderPath`->`path`, `ReleaseYear`->`year`, `DateCreated`->`created`, `StockDate`->`added`, `Commnt`->`comment`, `Rating`->`rating`, `Length`->`seconds`, `FileSize`->`bytes`, `BitRate`->`bitrate`, `SampleRate`->`sample_rate`, `DJPlayCount`->`plays`, `AnalysisDataPath`->`analysis`, `MasterSongID`->`original_id`, `ISRC`->`isrc`, `NULLIF(BPM, 0) / 100.0`->`bpm`.
- Joins: `djmdArtist` (`ArtistID`), `djmdGenre` (`GenreID`), `djmdKey` (`KeyID` -> `ScaleName`), `djmdAlbum` (`AlbumID`), `djmdLabel` (`LabelID`).

### OneLibrary (`content`)
- Columns: `content_id`->`id`, `title`, `path`, `releaseYear`->`year`, `dateCreated`->`created`, `dateAdded`->`added`, `djComment`->`comment`, `rating`, `length`->`seconds`, `fileSize`->`bytes`, `bitrate`, `samplingRate`->`sample_rate`, `djPlayCount`->`plays`, `analysisDataFilePath`->`analysis`, `masterContentId`->`original_id`, `isrc`, `NULLIF(bpmx100, 0) / 100.0`->`bpm`.
- Joins: `artist` (`artist_id_artist`->`artist_id`), `genre` (`genre_id`), `key` (`key_id`), `album` (`album_id`), `label` (`label_id`).

### Normalization Rules (`library._track`)
- `rating`: If `> 5` (Master `0..255` scale), `round(rating / 51)`, else `int(rating)`, clamped `[0..5]`.
- `bpm`: Validated in `(0.01 .. 655.34)`, else `None`.
- `year`: Minimum `1`, else `None`.
- `key`: Normalized to Camelot `1A..12B` via `keys.camelot(key_raw)`.
