"""Read-only snapshot loader for Rekordbox Master, OneLibrary, and Device Library databases."""

from __future__ import annotations

from contextlib import closing, contextmanager
import ctypes
import hashlib
import os
from pathlib import Path
import sqlite3
import string
import tempfile
import time

from diagnostics import CuepointError, emit_log

DEFAULT_SOURCE = Path.home() / "AppData" / "Roaming" / "Pioneer" / "rekordbox" / "master.db"
DATABASE_NAMES = ("master.db", "exportLibrary.db", "export.pdb")

MASTER_FIELDS = {
    "id": "ID",
    "title": "Title",
    "path": "FolderPath",
    "year": "ReleaseYear",
    "created": "DateCreated",
    "added": "StockDate",
    "comment": "Commnt",
    "rating": "Rating",
    "seconds": "Length",
    "bytes": "FileSize",
    "bitrate": "BitRate",
    "sample_rate": "SampleRate",
    "plays": "DJPlayCount",
    "analysis": "AnalysisDataPath",
    "original_id": "MasterSongID",
    "isrc": "ISRC",
}
MASTER_JOINS = {
    "artist": ("djmdArtist", "ArtistID", "Name"),
    "genre": ("djmdGenre", "GenreID", "Name"),
    "key_raw": ("djmdKey", "KeyID", "ScaleName"),
    "album": ("djmdAlbum", "AlbumID", "Name"),
    "label": ("djmdLabel", "LabelID", "Name"),
}


def candidates(root: Path):
    for directory in (
        root,
        root / "PIONEER" / "rekordbox",
        root / "rekordbox",
        root / "PIONEER" / "Master",
    ):
        for name in DATABASE_NAMES:
            path = directory / name
            if path.is_file():
                yield path


def resolve_source(value=None) -> Path:
    path = Path(value) if value else DEFAULT_SOURCE
    if path.is_file() and path.suffix.lower() in (".db", ".pdb"):
        return path.resolve()
    if path.is_dir():
        database = next(candidates(path), None)
        if database:
            return database.resolve()
    raise CuepointError("SOURCE_NOT_FOUND", f"Keine Rekordbox-Bibliothek gefunden unter {path}.")


def _stamp(path: Path):
    try:
        stat = path.stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
    except FileNotFoundError:
        return None


def _digest(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.digest()


def _copy_digest(source: Path, target: Path) -> bytes:
    digest = hashlib.sha256()
    with source.open("rb") as incoming, target.open("wb") as outgoing:
        while chunk := incoming.read(1024 * 1024):
            outgoing.write(chunk)
            digest.update(chunk)
    return digest.digest()


@contextmanager
def snapshot(source: Path):
    originals = [source]
    if source.suffix.lower() == ".db":
        originals += [Path(str(source) + suffix) for suffix in ("-wal", "-journal")]
    with tempfile.TemporaryDirectory(prefix="cuepoint-") as directory:
        target = Path(directory)
        for attempt in range(3):
            before = [_stamp(path) for path in originals]
            try:
                if not before[0]:
                    raise FileNotFoundError(source)
                pairs = [
                    (path, target / path.name)
                    for path, stamp in zip(originals, before, strict=False)
                    if stamp
                ]
                for local in target.iterdir():
                    local.unlink()
                copies = [(path, _copy_digest(path, local)) for path, local in pairs]
                verified = all(expected == _digest(path) for path, expected in copies)
                after = [_stamp(path) for path in originals]
                if verified and before == after:
                    break
            except (FileNotFoundError, PermissionError) as exc:
                emit_log(
                    "WARN",
                    "sources",
                    "snapshot_retry",
                    f"Attempt {attempt + 1} failed: {exc}",
                    path=str(source),
                )
                if attempt == 2:
                    raise CuepointError(
                        "SOURCE_UNREADABLE",
                        "Die Quelldateien sind gerade nicht lesbar.",
                    ) from None
            time.sleep(0.12 * (attempt + 1))
        else:
            raise CuepointError(
                "SNAPSHOT_INCONSISTENT",
                "Rekordbox schreibt gerade. Bitte die Bibliothek erneut laden.",
            )
        yield target / source.name


def _read_sqlite(copy: Path):
    with copy.open("rb") as stream:
        encrypted = stream.read(16) != b"SQLite format 3\0"
    uri = copy.as_uri() + "?mode=ro"
    if not encrypted:
        return sqlite3.connect(uri, uri=True)
    try:
        from sqlcipher3 import dbapi2
        from pyrekordbox.masterdb.database import BLOB as master_key
        from pyrekordbox.onelibrary.database import BLOB as usb_key
        from pyrekordbox.utils import deobfuscate
    except ImportError as exc:
        raise CuepointError(
            "SQLCIPHER_UNAVAILABLE",
            f"SQLCipher-Entschlüsselung nicht verfügbar ({exc}).",
        ) from exc

    keys = (usb_key, master_key) if copy.name.lower() == "exportlibrary.db" else (master_key, usb_key)
    for blob in keys:
        conn = dbapi2.connect(uri, uri=True)
        try:
            key = deobfuscate(blob).replace("'", "''")
            conn.execute(f"PRAGMA key = '{key}'")
            conn.execute("SELECT count(*) FROM sqlite_schema").fetchone()
            return conn
        except dbapi2.DatabaseError:
            conn.close()
    raise CuepointError(
        "DATABASE_DECRYPT_FAILED",
        "Die SQLCipher-Bibliothek konnte nicht entschlüsselt werden.",
    )


def _columns(conn, table: str) -> set[str]:
    return {row[1].lower() for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _joined(conn, table: str, fields: dict, bpm_column: str, joins: dict) -> list[dict]:
    columns = _columns(conn, table)
    fields_sql = [
        f'c."{source}" AS "{alias}"' if source.lower() in columns else f'NULL AS "{alias}"'
        for alias, source in fields.items()
    ]
    fields_sql.append(
        f'NULLIF(c."{bpm_column}", 0) / 100.0 AS bpm' if bpm_column.lower() in columns else "NULL AS bpm"
    )
    joins_sql = []
    for alias, (other, foreign, field, *primary) in joins.items():
        primary_key = primary[0] if primary else "id"
        other_columns = _columns(conn, other)
        if foreign.lower() in columns and {primary_key.lower(), field.lower()} <= other_columns:
            joins_sql.append(f'LEFT JOIN "{other}" AS {alias} ON c."{foreign}" = {alias}."{primary_key}"')
            fields_sql.append(f'{alias}."{field}" AS "{alias}"')
        else:
            fields_sql.append(f'NULL AS "{alias}"')
    sql = f'SELECT {", ".join(fields_sql)} FROM "{table}" AS c {" ".join(joins_sql)}'  # noqa: S608
    cursor = conn.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=False)) for row in cursor]


def read_source(source: Path):
    with snapshot(source) as copy:
        if source.suffix.lower() == ".pdb":
            return "Device Library", _legacy_rows(copy)
        with closing(_read_sqlite(copy)) as conn:
            conn.execute("PRAGMA query_only = ON")
            conn.execute("PRAGMA trusted_schema = OFF")
            if "id" in _columns(conn, "djmdContent"):
                return "Master", _joined(conn, "djmdContent", MASTER_FIELDS, "BPM", MASTER_JOINS)
            if "content_id" in _columns(conn, "content"):
                return "OneLibrary", _one_library_rows(conn)
    raise CuepointError(
        "DATABASE_SCHEMA_INVALID",
        "Das Datenbankschema gehört zu keiner unterstützten Rekordbox-Bibliothek.",
    )


def _one_library_rows(conn):
    fields = {
        "id": "content_id",
        "title": "title",
        "path": "path",
        "year": "releaseYear",
        "created": "dateCreated",
        "added": "dateAdded",
        "comment": "djComment",
        "rating": "rating",
        "seconds": "length",
        "bytes": "fileSize",
        "bitrate": "bitrate",
        "sample_rate": "samplingRate",
        "plays": "djPlayCount",
        "analysis": "analysisDataFilePath",
        "isrc": "isrc",
        "original_id": "masterContentId",
    }
    joins = {
        "artist": ("artist", "artist_id_artist", "name", "artist_id"),
        "genre": ("genre", "genre_id", "name", "genre_id"),
        "key_raw": ("key", "key_id", "name", "key_id"),
        "album": ("album", "album_id", "name", "album_id"),
        "label": ("label", "label_id", "name", "label_id"),
    }
    return _joined(conn, "content", fields, "bpmx100", joins)


def _legacy_rows(copy: Path):
    try:
        from rekordbox_pdb import Database
    except ImportError as exc:
        raise CuepointError(
            "DATABASE_SCHEMA_INVALID",
            f"Device Library (.pdb) Parser nicht verfügbar ({exc}).",
        ) from exc
    db = Database.from_file(copy)
    names = {
        key: {row.id: row.name for row in getattr(db, key + "s")}
        for key in ("artist", "genre", "album", "label", "key")
    }
    rows = []
    for track in db.tracks:
        row = {
            "id": track.id,
            "title": track.title,
            "path": track.file_path,
            "year": track.year,
            "created": track.release_date,
            "added": track.date_added,
            "comment": track.comment,
            "rating": track.rating,
            "seconds": track.duration,
            "bytes": track.file_size,
            "bitrate": track.bitrate,
            "sample_rate": track.sample_rate,
            "plays": track.play_count,
            "analysis": track.analyze_path,
            "bpm": track.tempo / 100.0,
        }
        for key, entries in names.items():
            row["key_raw" if key == "key" else key] = entries.get(getattr(track, f"{key}_id"))
        rows.append(row)
    return rows


def usb_sources() -> list[str]:
    if os.name != "nt":
        return []
    drive_type = ctypes.windll.kernel32.GetDriveTypeW
    roots = (Path(f"{letter}:\\") for letter in string.ascii_uppercase)
    return [
        str(path)
        for root in roots
        if drive_type(str(root)) in (2, 3)
        for path in candidates(root)
        if path.name.lower() != "master.db"
    ]
