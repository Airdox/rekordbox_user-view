"""JSON-RPC stdio coordinator for Cuepoint desktop & web preview bridges."""

from __future__ import annotations

import json
import math
import sys
from time import perf_counter

from diagnostics import CuepointError, emit_log, new_correlation_id
from fixtures import demo_tracks
from library import Library, metadata_identity, number, waveform, waveform_with_source
from live import DjLink, SLOTS, interfaces
from rekordbox_live import RekordboxPlayback, send_track_to_rekordbox
from sources import usb_sources


class Core:
    def __init__(self, local_playback=None):
        self.library = None
        self.link = DjLink()
        self.local_playback = local_playback
        self.media = {}
        self.demo = False
        self.demo_index = 0
        self._last_anchor = None

    def replace_library(self, library: Library) -> dict:
        if self.library:
            self.library.close()
        self.library = library
        return library.info()

    def status(self, options: dict) -> dict:
        state, error, decks = self.link.snapshot()
        library = self.library
        local_decks = []
        if self.demo:
            rows = (
                library.conn.execute(
                    "SELECT id,bpm FROM tracks WHERE key IS NOT NULL AND bpm BETWEEN 110 AND 150 "
                    "ORDER BY plays DESC, id LIMIT 24"
                ).fetchall()
                if library
                else []
            )
            row = rows[self.demo_index % len(rows)] if rows else None
            decks = (
                [
                    {
                        "deck": 1,
                        "name": "airdox Demo",
                        "source": 1,
                        "slot": 4,
                        "trackType": 1,
                        "trackId": row["id"],
                        "bpm": row["bpm"],
                        "playing": True,
                        "master": True,
                    }
                ]
                if row
                else []
            )
            state = "demo"
        elif self.local_playback and not decks and library and library.kind == "Master":
            connected, local_decks = self.local_playback.snapshot()
            if connected:
                state = "rekordbox"

        result = {
            "state": state,
            "error": error,
            "decks": [],
            "matches": [],
            "media": [{"source": source, "slot": slot, **media.info()} for (source, slot), media in self.media.items()],
        }

        for deck in decks:
            track, local = None, None
            if deck["trackType"] == 1 and deck["trackId"] != "0":
                is_local_collection = (
                    deck["slot"] == 4
                    and options.get("masterSource") == deck["source"]
                    and library
                    and library.kind == "Master"
                )
                if library and (self.demo or is_local_collection):
                    track = local = library.detail(deck["trackId"])
                elif media := self.media.get((deck["source"], deck["slot"])):
                    track = media.detail(deck["trackId"])
                    if library and track:
                        local = library.match_media(track)
            result["decks"].append({
                **deck,
                "slotName": SLOTS.get(deck["slot"], f"Slot {deck['slot']}"),
                "title": track["title"] if track else None,
                "artist": track["artist"] if track else None,
                "key": track["key"] if track else None,
                "genre": track["genre"] if track else None,
                "seconds": track["seconds"] if track else None,
                "libraryId": local["id"] if local else None,
            })

        for deck in local_decks:
            candidates = library.by_metadata.get(metadata_identity(deck), [])
            if len(candidates) > 1:
                candidates = [
                    track
                    for track in candidates
                    if track["bpm"] is not None
                    and abs(track["bpm"] - deck["original_bpm"]) <= 0.05
                    and (not deck["seconds"] or not track["seconds"] or abs(track["seconds"] - deck["seconds"]) <= 2)
                ]
            track = candidates[0] if len(candidates) == 1 else None
            local_id = track["id"] if track else None
            result["decks"].append({
                "deck": deck["deck"],
                "name": "Rekordbox",
                "source": deck["deck"],
                "slot": 4,
                "slotName": "Rekordbox lokal",
                "trackId": local_id or f"local:{deck['deck']}",
                "trackType": 1,
                "bpm": deck["bpm"],
                "playing": deck["playing"],
                "master": bool(deck.get("master", False)),
                "fader": deck.get("fader"),
                "title": deck["title"],
                "artist": deck["artist"],
                "key": deck["key"] or (track["key"] if track else None),
                "genre": track["genre"] if track else None,
                "seconds": deck["seconds"] or (track["seconds"] if track else None),
                "libraryId": local_id,
            })

        selected = self._select_anchor(result["decks"], state, options.get("deck"))
        result["anchor"] = selected["deck"] if selected else None
        if library and selected and selected["bpm"] is not None and selected["trackType"] and selected["trackId"] != "0":
            percent = number(options.get("tolerance"), 0, 30)
            bpm = selected["bpm"]
            tolerance = bpm * (percent if percent is not None else 3) / 100 + math.ulp(bpm)
            result["matches"] = library.recommendations(
                bpm,
                selected["key"],
                selected["libraryId"],
                tolerance,
                options.get("harmonic", True),
            )
        return result

    def _select_anchor(self, decks: list[dict], state: str, preferred_deck):
        available = [deck for deck in decks if deck["trackId"] != "0" and (state != "rekordbox" or deck["playing"])]
        if preferred_deck is not None:
            selected = next((deck for deck in available if deck["deck"] == preferred_deck), None)
            if selected:
                self._last_anchor = selected["deck"]
            return selected
        if not available:
            return None
        has_faders = any(deck.get("fader") is not None for deck in available)
        if state == "rekordbox" and has_faders:
            audible = [deck for deck in available if deck.get("fader") is None or deck["fader"] > 0.05]
            if audible:
                available = audible

        def level(deck: dict) -> float:
            fader = deck.get("fader")
            return 1.0 if fader is None else float(fader)

        prev = next((deck for deck in available if deck["deck"] == self._last_anchor), None)
        if prev is not None and len(available) > 1:
            prev_lvl = level(prev)
            challenger = max(
                available,
                key=lambda d: (round(level(d), 2), bool(d.get("master")), d["deck"] == self._last_anchor, -d["deck"]),
            )
            if challenger["deck"] != prev["deck"]:
                ch_lvl = level(challenger)
                fader_beat = (ch_lvl - prev_lvl) >= 0.10
                master_beat = abs(ch_lvl - prev_lvl) < 0.05 and challenger.get("master") and not prev.get("master")
                selected = challenger if (fader_beat or master_beat) else prev
            else:
                selected = prev
        else:
            selected = min(
                available,
                key=lambda d: (-round(level(d), 2), not d["playing"], not d.get("master"), d["deck"]),
                default=None,
            )
        if selected:
            self._last_anchor = selected["deck"]
        return selected

    def handle(self, method: str, params: dict):
        if method == "open":
            return self.replace_library(Library.load(params.get("path")))
        if method == "demoLibrary":
            if params.get("path"):
                library = Library.load(params["path"])
                library.kind = "Demo"
                return self.replace_library(library)
            return self.replace_library(Library(None, "Demo", demo_tracks()))
        if method == "query":
            if not self.library:
                raise CuepointError("SOURCE_NOT_FOUND", "Öffne zuerst eine Bibliothek.")
            return self.library.query(params)
        if method == "detail":
            track = self.library.detail(params["id"]) if self.library else None
            if not track:
                return None
            samples, wf_source = waveform_with_source(self.library, track)
            return {**track, "waveform": samples, "waveformSource": wf_source}
        if method == "interfaces":
            return [{"name": item["name"], "ip": item["ip"]} for item in interfaces()]
        if method == "usb":
            return usb_sources()
        if method == "linkStart":
            self.demo = False
            self.link.start(params["ip"], bool(params.get("announce")))
            return True
        if method == "linkStop":
            self.demo = False
            self.link.stop()
            return True
        if method == "demoLink":
            self.link.stop()
            self.demo = True
            if params.get("next"):
                self.demo_index += 1
            elif params.get("index") is not None:
                self.demo_index = int(params["index"])
            return True
        if method == "live":
            return self.status(params)
        if method in ("bindMedia", "unbindMedia"):
            source, slot = int(params["source"]), int(params["slot"])
            if source not in range(1, 16) or slot not in (2, 3, 7):
                raise CuepointError("MEDIA_NOT_FOUND", "Wähle einen Player und einen USB- oder SD-Slot.")
            key = source, slot
            if method == "bindMedia":
                media = Library.load(params["path"])
                if media.kind not in ("OneLibrary", "Device Library"):
                    media.close()
                    raise CuepointError(
                        "DATABASE_SCHEMA_INVALID",
                        "Wähle eine exportLibrary.db oder export.pdb vom USB-Medium.",
                    )
                if key in self.media:
                    self.media[key].close()
                self.media[key] = media
            elif key in self.media:
                self.media.pop(key).close()
            return True
        if method == "rekordboxTransport":
            action = str(params.get("action") or "reveal")
            track = self.library.detail(params["id"]) if (self.library and params.get("id")) else None
            query = str(params.get("query") or (f"{track['title']} {track['artist']}".strip() if track else "")).strip()
            path = str(params.get("path") or (track.get("path") if track else "") or "")
            return send_track_to_rekordbox(action, query, path)
        raise CuepointError("SOURCE_UNREADABLE", "Unbekannter Befehl.")


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    playback = RekordboxPlayback()
    core = Core(local_playback=playback)
    emit_log("INFO", "worker", "started", "Cuepoint Python worker listening on stdio")
    for line in sys.stdin:
        message = {}
        cid = new_correlation_id()
        started = perf_counter()
        try:
            message = json.loads(line)
            method = message["method"]
            result = core.handle(method, message.get("params", {}))
            response = {"id": message["id"], "result": result}
            if method in ("open", "demoLibrary", "linkStart", "bindMedia"):
                emit_log(
                    "INFO",
                    "rpc",
                    f"rpc_{method}",
                    f"Completed {method}",
                    correlation_id=cid,
                    duration_ms=(perf_counter() - started) * 1000,
                )
        except Exception as exc:
            error_code = exc.code if isinstance(exc, CuepointError) else None
            emit_log(
                "ERROR",
                "rpc",
                "rpc_failed",
                str(exc) or exc.__class__.__name__,
                correlation_id=cid,
                duration_ms=(perf_counter() - started) * 1000,
                method=message.get("method"),
                errorCode=error_code or "",
            )
            response = {"id": message.get("id"), "error": str(exc) or exc.__class__.__name__}
            if error_code:
                response["errorCode"] = error_code
        print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)
    core.link.stop()
    playback.close()


if __name__ == "__main__":
    main()
