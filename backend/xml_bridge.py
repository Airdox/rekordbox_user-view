"""1-Click Rekordbox XML Bridge writer for Cuepoint filtered lists and sets."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from diagnostics import CuepointError, emit_log


def default_bridge_path() -> Path:
    """Resolve the default fixed cuepoint-bridge.xml path for Windows or fallback environments."""
    override = os.environ.get("CUEPOINT_BRIDGE_XML", "").strip()
    if override:
        return Path(override)
    pioneer_root = Path(r"E:\PIONEER")
    if os.name == "nt":
        if pioneer_root.is_dir():
            return pioneer_root / "cuepoint-bridge.xml"
        return Path.home() / "Documents" / "Cuepoint" / "cuepoint-bridge.xml"
    return Path.cwd() / "build" / "cuepoint-bridge.xml"


def to_file_uri(file_path: str) -> str:
    """Convert a local filesystem path into Rekordbox's file://localhost/... URI format."""
    norm = str(file_path or "").replace("\\", "/").strip()
    if not norm:
        return ""
    prefix = "file://localhost" if norm.startswith("/") else "file://localhost/"
    return prefix + quote(norm, safe="/:")


def _attr(value) -> str:
    return escape(str(value if value is not None else ""), {'"': "&quot;", "'": "&apos;"})


def build_rekordbox_xml(
    playlists: dict[str, list[dict]],
    *,
    app_name: str = "Cuepoint Library",
    app_version: str = "1.1.0",
) -> str:
    """Build a valid Rekordbox DJ_PLAYLISTS XML document with deduplicated tracks and named playlists."""
    unique_tracks: list[dict] = []
    key_by_identity: dict[str, int] = {}

    def _identity(track: dict, fallback_idx: int) -> str:
        tid = str(track.get("id") or "").strip()
        path = str(track.get("path") or "").strip()
        if tid:
            return f"id:{tid}"
        if path:
            return f"path:{path}"
        return f"row:{fallback_idx}:{track.get('title', '')}"

    resolved_playlists: list[tuple[str, list[int]]] = []
    counter = 0
    for pl_name, items in playlists.items():
        if not pl_name.strip():
            continue
        track_keys: list[int] = []
        for item in items:
            counter += 1
            ident = _identity(item, counter)
            if ident not in key_by_identity:
                key_num = len(unique_tracks) + 1
                key_by_identity[ident] = key_num
                unique_tracks.append(item)
            track_keys.append(key_by_identity[ident])
        resolved_playlists.append((pl_name.strip(), track_keys))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<DJ_PLAYLISTS Version="1.0.0">',
        f'  <PRODUCT Name="{_attr(app_name)}" Version="{_attr(app_version)}" Company="Cuepoint"/>',
        f'  <COLLECTION Entries="{len(unique_tracks)}">',
    ]
    for idx, track in enumerate(unique_tracks, 1):
        bpm = track.get("bpm")
        bpm_str = f"{float(bpm):.2f}" if isinstance(bpm, (int, float)) else ""
        secs = track.get("seconds")
        total_time = int(secs) if isinstance(secs, (int, float)) else 0
        year = track.get("year")
        year_str = str(int(year)) if isinstance(year, (int, float)) else ""
        rating = track.get("rating")
        rating_val = int(rating) * 51 if isinstance(rating, (int, float)) and 0 <= rating <= 5 else 0
        loc = to_file_uri(str(track.get("path") or ""))
        loc_attr = f' Location="{_attr(loc)}"' if loc else ""
        lines.append(
            f'    <TRACK TrackID="{idx}" Name="{_attr(track.get("title") or "")}" '
            f'Artist="{_attr(track.get("artist") or "")}" '
            f'Album="{_attr(track.get("album") or "")}" '
            f'Genre="{_attr(track.get("genre") or "")}" '
            f'Label="{_attr(track.get("label") or "")}" '
            f'Comments="{_attr(track.get("comment") or "")}" '
            f'TotalTime="{total_time}" Year="{year_str}" '
            f'AverageBpm="{bpm_str}" Tonality="{_attr(track.get("key") or "")}" '
            f'Rating="{rating_val}"{loc_attr}/>'
        )
    lines.append("  </COLLECTION>")
    lines.append("  <PLAYLISTS>")
    lines.append(f'    <NODE Type="0" Name="ROOT" Count="{len(resolved_playlists)}">')
    for pl_name, keys in resolved_playlists:
        lines.append(f'      <NODE Name="{_attr(pl_name)}" Type="1" KeyType="0" Entries="{len(keys)}">')
        for key in keys:
            lines.append(f'        <TRACK Key="{key}"/>')
        lines.append("      </NODE>")
    lines.append("    </NODE>")
    lines.append("  </PLAYLISTS>")
    lines.append("</DJ_PLAYLISTS>")
    return "\n".join(lines) + "\n"


def write_bridge_xml(
    tracks: list[dict],
    playlist_name: str = "Cuepoint Auswahl",
    target_path: str | Path | None = None,
    *,
    secondary_playlists: dict[str, list[dict]] | None = None,
) -> dict:
    """Atomically write the fixed cuepoint-bridge.xml file to disk for 1-click Rekordbox import."""
    dest = Path(str(target_path).strip()) if target_path and str(target_path).strip() else default_bridge_path()
    if dest.suffix.lower() != ".xml":
        dest = dest / "cuepoint-bridge.xml" if dest.is_dir() else dest.with_suffix(".xml")

    playlists: dict[str, list[dict]] = {playlist_name: list(tracks or [])}
    if secondary_playlists:
        for name, items in secondary_playlists.items():
            if name != playlist_name and items:
                playlists[name] = list(items)

    xml_content = build_rekordbox_xml(playlists)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".xml.tmp")
        tmp.write_text(xml_content, encoding="utf-8")
        os.replace(tmp, dest)
    except OSError as exc:
        raise CuepointError(
            "SOURCE_UNREADABLE",
            f"Rekordbox Bridge-XML konnte nicht unter {dest} gespeichert werden ({exc}).",
        ) from exc

    updated_at = datetime.now(timezone.utc).isoformat()
    emit_log(
        "INFO",
        "EXPORT",
        "bridge_xml_written",
        f"Rekordbox Bridge-XML aktualisiert ({len(tracks)} Tracks)",
        path=str(dest),
        playlist=playlist_name,
        trackCount=len(tracks),
    )
    return {
        "ok": True,
        "path": str(dest),
        "playlistName": playlist_name,
        "trackCount": len(tracks),
        "playlists": [{"name": name, "count": len(items)} for name, items in playlists.items()],
        "updatedAt": updated_at,
    }


def bridge_status(target_path: str | Path | None = None) -> dict:
    """Return current bridge XML path and metadata without modifying disk."""
    dest = Path(str(target_path).strip()) if target_path and str(target_path).strip() else default_bridge_path()
    exists = dest.is_file()
    size = dest.stat().st_size if exists else 0
    return {
        "path": str(dest),
        "exists": exists,
        "bytes": size,
    }
