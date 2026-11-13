"""In-memory SQLite + vectorized NumPy (with pure-Python fallback) Rekordbox library engine."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from functools import lru_cache
import math
import operator
from operator import itemgetter
from pathlib import Path
import re
import sqlite3
from time import perf_counter
import unicodedata

try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - sandbox fallback when numpy wheel isn't installed
    np = None  # type: ignore

from keys import camelot, compatible
from sources import read_source, resolve_source

TEXT = (
    "id",
    "title",
    "artist",
    "album",
    "genre",
    "label",
    "key_raw",
    "path",
    "created",
    "added",
    "comment",
    "analysis",
    "original_id",
    "isrc",
)
INTEGER = ("year", "seconds", "bytes", "bitrate", "sample_rate", "plays")
LIST_FIELDS = ("id", "title", "artist", "genre", "bpm", "key", "rating", "seconds", "year")
DETAIL_FIELDS = (*TEXT, *INTEGER, "rating", "key", "bpm")
TEXT_SORTS = tuple(field for field in TEXT if field != "id")
SEARCH_FIELDS = ("title", "artist", "genre", "album", "label", "comment", "path")
SORTS = {field: f"{field}_sort" for field in TEXT_SORTS}
SORTS.update({field: field for field in ("id", *INTEGER, "bpm", "rating")})
SORTS["key"] = "key_sort"

NP_OPS = {
    "eq": operator.eq,
    "neq": operator.ne,
    "gte": operator.ge,
    "lte": operator.le,
    "gt": operator.gt,
    "lt": operator.lt,
}

_NOCASE_TABLE = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def _sqlite_nocase(value: str) -> str:
    return value.translate(_NOCASE_TABLE)


def folded(value) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", str(value if value is not None else "").casefold())
        if not unicodedata.combining(char)
    )


def number(value, minimum: float = 0, maximum: float = 1_000_000_000_000):
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return value if math.isfinite(value) and minimum <= value <= maximum else None


def _parse_range(value):
    parts = [p.strip() for p in re.split(r"\.\.|;|,|\s+bis\s+|\s+[–—-]\s+", str(value or "").strip())]
    if len(parts) != 2:
        return None
    low, high = number(parts[0]), number(parts[1])
    if low is None or high is None:
        return None
    return (low, high) if low <= high else (high, low)


def _track(raw: dict) -> dict:
    track = {field: str(raw[field]).strip() if raw.get(field) is not None else "" for field in TEXT}
    for field in INTEGER:
        minimum = 1 if field == "year" else 0
        value = number(raw.get(field), minimum)
        track[field] = int(value) if value is not None else None
    rating = number(raw.get("rating"), 0, 255) or 0
    track["rating"] = round(rating / 51) if rating > 5 else int(rating)
    track["key"] = camelot(track["key_raw"])
    track["bpm"] = number(raw.get("bpm"), 0.01, 655.34)
    return track


def _key_rank(key: str | None) -> int | None:
    return int(key[:-1]) * 2 + (key[-1] == "B") if key else None


def file_name(path: str) -> str:
    return folded(re.split(r"[/\\]", path)[-1])


def metadata_identity(track: dict) -> tuple[str, str]:
    return folded(track["title"]).strip(), folded(track["artist"]).strip()


class Library:
    def __init__(self, path: Path | None, kind: str, tracks):
        self.path, self.kind = path, kind
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA page_size = 32768")
        text_indexes = ", ".join(f"{field}_sort INTEGER" for field in TEXT_SORTS)
        self.conn.executescript(
            """
            PRAGMA temp_store = MEMORY;
            PRAGMA synchronous = OFF;
            PRAGMA journal_mode = OFF;
            PRAGMA cache_size = -64000;
            CREATE TABLE tracks (
                id TEXT PRIMARY KEY, genre TEXT, year INTEGER, seconds INTEGER, bytes INTEGER,
                bitrate INTEGER, sample_rate INTEGER, plays INTEGER, rating INTEGER, key TEXT,
                bpm REAL, key_sort INTEGER, """
            + text_indexes
            + """
            );
            CREATE TABLE track_search (id TEXT PRIMARY KEY, content TEXT);
        """
        )
        normalized = sorted((_track(row) for row in tracks if row.get("id") is not None), key=itemgetter("id"))
        folded_fields = {field: [folded(track[field]) for track in normalized] for field in TEXT_SORTS}
        self._text_values = {field: sorted(set(values) - {""}) for field, values in folded_fields.items()}
        ranks = {
            field: {value: index for index, value in enumerate(values)}
            for field, values in self._text_values.items()
        }
        base = ("id", "genre", *INTEGER, "rating", "key", "bpm")
        columns = (*base, "key_sort", *(SORTS[field] for field in TEXT_SORTS))
        insert_sql = f"INSERT INTO tracks ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"  # noqa: S608
        self.conn.executemany(
            insert_sql,
            (
                (
                    *[track[field] for field in base],
                    _key_rank(track["key"]),
                    *[ranks[field].get(folded_fields[field][index]) for field in TEXT_SORTS],
                )
                for index, track in enumerate(normalized)
            ),
        )
        search_texts = [
            " ".join(folded_fields[field][index] for field in SEARCH_FIELDS)
            for index in range(len(normalized))
        ]
        self.conn.executemany(
            "INSERT INTO track_search VALUES (?, ?)",
            ((track["id"], search_texts[index]) for index, track in enumerate(normalized)),
        )
        self.conn.executescript("""
            CREATE INDEX track_genre ON tracks(genre);
            CREATE INDEX track_genre_bpm ON tracks(genre,bpm,id);
            CREATE INDEX track_key_bpm ON tracks(key,bpm);
            CREATE INDEX track_key_bpm_asc ON tracks(key,bpm,id);
            CREATE INDEX track_key_bpm_desc ON tracks(key,bpm DESC,id);
            CREATE INDEX track_artist_year_bpm ON tracks(artist_sort,year,bpm DESC,id);
            CREATE INDEX track_artist_year_asc ON tracks(artist_sort,year,id);
            CREATE INDEX track_artist_year_desc ON tracks(artist_sort,year DESC,id);
        """)
        for field, expression in SORTS.items():
            if field in ("id", "original_id", "analysis", "key_raw"):
                continue
            self.conn.execute(f"CREATE INDEX track_{field}_ascending ON tracks({expression},id)")
            self.conn.execute(f"CREATE INDEX track_{field}_descending ON tracks({expression} DESC,id)")
        self.conn.execute("ANALYZE")
        self.conn.row_factory = sqlite3.Row
        self.total = len(normalized)
        stats = self.conn.execute(
            "SELECT count(DISTINCT NULLIF(genre,'')), min(bpm), max(bpm), count(key) FROM tracks"
        ).fetchone()
        self.genre_count, low, high, self.key_count = stats
        self.bpm_bounds = [math.floor(low), math.ceil(high)] if low is not None else [0, 200]
        self._tracks = {track["id"]: track for track in normalized}
        self._list_rows = {track["id"]: {field: track[field] for field in LIST_FIELDS} for track in normalized}
        self._cached_contains_lut = lru_cache(maxsize=128)(self._contains_lut)
        self._init_index(normalized, folded_fields, ranks, search_texts)
        self._projection_fields = ()
        self._projection_rows = {}
        self.by_file = {}
        self.by_metadata = {}
        for track in normalized:
            name = file_name(track["path"])
            if name:
                self.by_file.setdefault(name, []).append(track)
            self.by_metadata.setdefault(metadata_identity(track), []).append(track)

    def _init_index(self, normalized, folded_fields, ranks, search_texts):
        n = len(normalized)
        self._ids = [track["id"] for track in normalized]
        self._id_pos = {track_id: index for index, track_id in enumerate(self._ids)}
        self._search_texts = search_texts
        self._text_null = {}
        self._sort_asc = {}
        self._sort_desc = {}
        for field in TEXT_SORTS:
            m = len(self._text_values[field])
            self._text_null[field] = m
            asc_list = [ranks[field].get(folded_fields[field][i], m) for i in range(n)]
            desc_list = [(m - 1) - v if v < m else m for v in asc_list]
            if np is not None:
                asc = np.array(asc_list, dtype=np.int32)
                self._sort_asc[field] = asc
                self._sort_desc[field] = np.where(asc < m, (m - 1) - asc, m).astype(np.int32)
            else:
                self._sort_asc[field] = asc_list
                self._sort_desc[field] = desc_list

        key_asc_list = [r if (r := _key_rank(t["key"])) is not None else 26 for t in normalized]
        key_desc_list = [25 - v if v < 26 else 26 for v in key_asc_list]
        if np is not None:
            self._pos = np.arange(n, dtype=np.int32)
            key_asc = np.array(key_asc_list, dtype=np.int32)
            self._sort_asc["key"] = key_asc
            self._sort_desc["key"] = np.where(key_asc < 26, 25 - key_asc, 26).astype(np.int32)
        else:
            self._pos = list(range(n))
            self._sort_asc["key"] = key_asc_list
            self._sort_desc["key"] = key_desc_list

        raw_keys = [t["key"] or "" for t in normalized]
        if np is not None:
            self._key_masks = {k: np.array([v == k for v in raw_keys], dtype=bool) for k in set(raw_keys)}
        else:
            self._key_masks = {k: [v == k for v in raw_keys] for k in set(raw_keys)}

        genres = sorted({t["genre"] for t in normalized})
        self._genre_list = genres
        self._genre_nocase = [_sqlite_nocase(g) for g in genres]
        self._genre_vocab = {g: i for i, g in enumerate(genres)}
        genre_idx_list = [self._genre_vocab[t["genre"]] for t in normalized]

        key_vals = sorted({t["key"] or "" for t in normalized})
        self._key_list = key_vals
        self._key_nocase = [_sqlite_nocase(k) for k in key_vals]
        key_vocab = {k: i for i, k in enumerate(key_vals)}
        key_idx_list = [key_vocab[t["key"] or ""] for t in normalized]

        if np is not None:
            self._genre_idx = np.array(genre_idx_list, dtype=np.int32)
            self._key_idx = np.array(key_idx_list, dtype=np.int32)
        else:
            self._genre_idx = genre_idx_list
            self._key_idx = key_idx_list

        self._num_raw = {}
        self._num_valid = {}
        for field in (*INTEGER, "rating", "bpm"):
            vals = [t[field] for t in normalized]
            valid_list = [v is not None for v in vals]
            raw_list = [v if v is not None else 0 for v in vals]
            uniq = sorted({v for v in vals if v is not None})
            m = len(uniq)
            rmap = {v: i for i, v in enumerate(uniq)}
            asc_list = [rmap[v] if v is not None else m for v in vals]
            if np is not None:
                self._num_valid[field] = np.array(valid_list, dtype=bool)
                dtype = np.float64 if field == "bpm" else np.int64
                self._num_raw[field] = np.array(raw_list, dtype=dtype)
                asc = np.array(asc_list, dtype=np.int32)
                self._sort_asc[field] = asc
                self._sort_desc[field] = np.where(asc < m, (m - 1) - asc, m).astype(np.int32)
            else:
                self._num_valid[field] = valid_list
                self._num_raw[field] = raw_list
                self._sort_asc[field] = asc_list
                self._sort_desc[field] = [(m - 1) - v if v < m else m for v in asc_list]

        if np is not None:
            bpm_bins = (self._num_raw["bpm"] / 5.0).astype(np.int32)
            self._bpm_bin = np.where(self._num_valid["bpm"], bpm_bins, -1)
        else:
            self._bpm_bin = [
                int(v / 5.0) if ok else -1
                for v, ok in zip(self._num_raw["bpm"], self._num_valid["bpm"], strict=False)
            ]

    @classmethod
    def load(cls, value=None) -> "Library":
        path = resolve_source(value)
        kind, tracks = read_source(path)
        return cls(path, kind, tracks)

    def close(self) -> None:
        self._cached_contains_lut.cache_clear()
        self.conn.close()

    def info(self) -> dict:
        return {
            "path": str(self.path) if self.path else None,
            "kind": self.kind,
            "total": self.total,
            "genres": self.genre_count,
            "bpmBounds": self.bpm_bounds,
            "withKey": self.key_count,
        }

    @staticmethod
    def _group_facet(idx_arr, vocab_list, nocase_list, mask):
        if np is not None:
            selected = idx_arr[mask]
            if not selected.size:
                return []
            counts = np.bincount(selected)
            nz = np.flatnonzero(counts)
            items = [(int(counts[i]), nocase_list[i], vocab_list[i]) for i in nz.tolist()]
        else:
            counts = Counter(idx_arr[i] for i, flag in enumerate(mask) if flag)
            if not counts:
                return []
            items = [(cnt, nocase_list[i], vocab_list[i]) for i, cnt in counts.items()]
        items.sort(key=lambda item: (-item[0], item[1]))
        return [{"value": val, "count": cnt} for cnt, _, val in items]

    def _histogram_from_mask(self, mask):
        if np is not None:
            bins = self._bpm_bin[mask]
            bins = bins[bins >= 0]
            if not bins.size:
                return []
            counts = np.bincount(bins)
            nz = np.flatnonzero(counts)
            return [{"bpm": int(b) * 5, "count": int(counts[b])} for b in nz.tolist()]
        counts = Counter(b for b, flag in zip(self._bpm_bin, mask, strict=False) if flag and b >= 0)
        return [{"bpm": int(b) * 5, "count": counts[b]} for b in sorted(counts)]

    def _contains_lut(self, field: str, needle: str):
        values = self._text_values[field]
        matches = [index for index, text in enumerate(values) if needle in text]
        if not matches:
            return False
        if len(matches) == len(values):
            return True
        if np is not None:
            lut = np.zeros(len(values) + 1, dtype=bool)
            lut[matches] = True
            return lut
        lut = [False] * (len(values) + 1)
        for index in matches:
            lut[index] = True
        return lut

    def _make_mask(self, fill: bool = True):
        if np is not None:
            return np.ones(self.total, dtype=bool) if fill else np.zeros(self.total, dtype=bool)
        return bytearray([1 if fill else 0] * self.total)

    @staticmethod
    def _and_into(target, cond) -> None:
        if np is not None:
            target &= cond
        else:
            n = len(target)
            target[:] = (int.from_bytes(target, "little") & int.from_bytes(cond, "little")).to_bytes(n, "little")

    @staticmethod
    def _or_into(target, cond) -> None:
        if np is not None:
            target |= cond
        else:
            n = len(target)
            target[:] = (int.from_bytes(target, "little") | int.from_bytes(cond, "little")).to_bytes(n, "little")

    def _apply_rule(self, mask, rule) -> bool:
        if not isinstance(rule, dict):
            return True
        field, operation, value = rule.get("id"), rule.get("op"), rule.get("value")
        if not isinstance(field, str) or field not in SORTS or not isinstance(operation, str):
            return True

        if operation == "empty":
            if field in TEXT_SORTS:
                m = self._text_null[field]
                asc = self._sort_asc[field]
                cond = (asc == m) if np is not None else (v == m for v in asc)
                if np is not None:
                    mask &= cond
                else:
                    for i, v in enumerate(asc):
                        if mask[i] and v != m:
                            mask[i] = 0
            elif field == "key":
                asc = self._sort_asc["key"]
                if np is not None:
                    mask &= (asc == 26)
                else:
                    for i, v in enumerate(asc):
                        if mask[i] and v != 26:
                            mask[i] = 0
            elif field == "id":
                return False
            else:
                valid = self._num_valid[field]
                if np is not None:
                    mask &= ~valid
                else:
                    for i, ok in enumerate(valid):
                        if mask[i] and ok:
                            mask[i] = 0
            return True

        if operation == "range":
            if field in (*INTEGER, "rating", "bpm"):
                bounds = _parse_range(value)
                if not bounds:
                    return False
                lo, hi = bounds
                raw = self._num_raw[field]
                valid = self._num_valid[field]
                if np is not None:
                    mask &= (raw >= lo) & (raw <= hi) & valid
                else:
                    for i in range(self.total):
                        if mask[i] and not (valid[i] and lo <= raw[i] <= hi):
                            mask[i] = 0
                return True
            parts = [p.strip() for p in re.split(r"\.\.|;|,|\s+bis\s+|\s+[–—-]\s+", str(value or "").strip())]
            if len(parts) != 2:
                return False
            if field == "key":
                lo, hi = _key_rank(camelot(parts[0])), _key_rank(camelot(parts[1]))
                if lo is None or hi is None:
                    return False
                lo_r, hi_r = min(lo, hi), max(lo, hi)
                asc = self._sort_asc["key"]
                if np is not None:
                    mask &= (asc >= lo_r) & (asc <= hi_r) & (asc < 26)
                else:
                    for i, v in enumerate(asc):
                        if mask[i] and not (lo_r <= v <= hi_r and v < 26):
                            mask[i] = 0
                return True
            if field == "id":
                lo_i = bisect_left(self._ids, min(parts))
                hi_i = bisect_right(self._ids, max(parts))
                if np is not None:
                    mask &= (self._pos >= lo_i) & (self._pos < hi_i)
                else:
                    for i in range(self.total):
                        if mask[i] and not (lo_i <= i < hi_i):
                            mask[i] = 0
                return True
            values = self._text_values[field]
            lo_t, hi_t = folded(parts[0]), folded(parts[1])
            if lo_t > hi_t:
                lo_t, hi_t = hi_t, lo_t
            lo_r, hi_r = bisect_left(values, lo_t), bisect_right(values, hi_t)
            asc = self._sort_asc[field]
            if np is not None:
                mask &= (asc >= lo_r) & (asc < hi_r)
            else:
                for i, v in enumerate(asc):
                    if mask[i] and not (lo_r <= v < hi_r):
                        mask[i] = 0
            return True

        if operation == "contains" and isinstance(value, (str, int, float)) and str(value):
            if field in TEXT_SORTS:
                lut = self._cached_contains_lut(field, folded(value))
                if lut is False:
                    return False
                m = self._text_null[field]
                asc = self._sort_asc[field]
                if lut is True:
                    if np is not None:
                        mask &= (asc < m)
                    else:
                        for i, v in enumerate(asc):
                            if mask[i] and v >= m:
                                mask[i] = 0
                else:
                    if np is not None:
                        mask &= lut[asc]
                    else:
                        for i, v in enumerate(asc):
                            if mask[i] and not lut[v]:
                                mask[i] = 0
                return True
            column = f"lower({field})" if field in ("key", "id") else SORTS[field]
            query_sql = f"SELECT id FROM tracks WHERE instr({column}, ?) > 0"  # noqa: S608
            rows = self.conn.execute(query_sql, (folded(value),)).fetchall()
            if not rows:
                return False
            hit_pos = {self._id_pos[r[0]] for r in rows}
            if np is not None:
                sub = np.zeros(self.total, dtype=bool)
                sub[list(hit_pos)] = True
                mask &= sub
            else:
                for i in range(self.total):
                    if mask[i] and i not in hit_pos:
                        mask[i] = 0
            return True

        if operation not in NP_OPS:
            return True
        op_fn = NP_OPS[operation]

        if field in TEXT_SORTS:
            values = self._text_values[field]
            m = self._text_null[field]
            asc = self._sort_asc[field]
            text = folded(str(value).strip()) if value is not None else ""
            if text == "":
                if operation == "eq":
                    if np is not None:
                        mask &= (asc == m)
                    else:
                        for i, v in enumerate(asc):
                            if mask[i] and v != m:
                                mask[i] = 0
                elif operation == "neq":
                    if np is not None:
                        mask &= (asc < m)
                    else:
                        for i, v in enumerate(asc):
                            if mask[i] and v >= m:
                                mask[i] = 0
                return True
            first, after = bisect_left(values, text), bisect_right(values, text)
            if operation in ("eq", "neq"):
                if first == after:
                    if operation == "eq":
                        return False
                    if np is not None:
                        mask &= (asc < m)
                    else:
                        for i, v in enumerate(asc):
                            if mask[i] and v >= m:
                                mask[i] = 0
                elif operation == "eq":
                    if np is not None:
                        mask &= (asc == first)
                    else:
                        for i, v in enumerate(asc):
                            if mask[i] and v != first:
                                mask[i] = 0
                else:
                    if np is not None:
                        mask &= (asc != first) & (asc < m)
                    else:
                        for i, v in enumerate(asc):
                            if mask[i] and not (v != first and v < m):
                                mask[i] = 0
                return True
            if operation in ("gte", "gt"):
                t = first if operation == "gte" else after
                if np is not None:
                    mask &= (asc >= t) & (asc < m)
                else:
                    for i, v in enumerate(asc):
                        if mask[i] and not (t <= v < m):
                            mask[i] = 0
                return True
            t = after if operation == "lte" else first
            if np is not None:
                mask &= (asc < t)
            else:
                for i, v in enumerate(asc):
                    if mask[i] and not (v < t):
                        mask[i] = 0
            return True

        if field == "key":
            rank = _key_rank(camelot(value))
            if rank is None:
                return False
            asc = self._sort_asc["key"]
            if np is not None:
                mask &= op_fn(asc, rank) & (asc < 26)
            else:
                for i, v in enumerate(asc):
                    if mask[i] and not (v < 26 and op_fn(v, rank)):
                        mask[i] = 0
            return True

        if field == "id":
            text = str(value).strip() if value is not None else ""
            first, after = bisect_left(self._ids, text), bisect_right(self._ids, text)
            if operation == "eq":
                if first == after:
                    return False
                if np is not None:
                    mask &= (self._pos == first)
                else:
                    for i in range(self.total):
                        if mask[i] and i != first:
                            mask[i] = 0
            elif operation == "neq":
                if first != after:
                    if np is not None:
                        mask &= (self._pos != first)
                    else:
                        mask[first] = 0
            elif operation == "gte":
                if np is not None:
                    mask &= (self._pos >= first)
                else:
                    for i in range(first):
                        mask[i] = 0
            elif operation == "gt":
                if np is not None:
                    mask &= (self._pos >= after)
                else:
                    for i in range(after):
                        mask[i] = 0
            elif operation == "lte":
                if np is not None:
                    mask &= (self._pos < after)
                else:
                    for i in range(after, self.total):
                        mask[i] = 0
            else:
                if np is not None:
                    mask &= (self._pos < first)
                else:
                    for i in range(first, self.total):
                        mask[i] = 0
            return True

        val = number(value)
        if val is None:
            return False
        raw = self._num_raw[field]
        valid = self._num_valid[field]
        if np is not None:
            mask &= op_fn(raw, val) & valid
        else:
            for i in range(self.total):
                if mask[i] and not (valid[i] and op_fn(raw[i], val)):
                    mask[i] = 0
        return True

    def _sort_positions(self, idx, request):
        requested = request.get("sorts")
        if not isinstance(requested, list):
            requested = [{"id": request.get("sort", "title"), "desc": request.get("desc", False)}]
        used, stages = set(), []
        for stage in requested:
            if not isinstance(stage, dict):
                continue
            field = stage.get("id") or stage.get("field")
            if not isinstance(field, str) or field not in SORTS or field in used:
                continue
            used.add(field)
            stages.append((field, stage.get("desc") is True or stage.get("dir") == "desc"))
        if not stages:
            return idx

        if np is not None:
            if len(stages) == 1:
                field, desc = stages[0]
                if field == "id":
                    return idx[::-1] if desc else idx
                col = self._sort_desc[field] if desc else self._sort_asc[field]
                return idx[np.argsort(col[idx], kind="stable")]
            keys = [] if "id" in used else [idx]
            for field, desc in reversed(stages):
                if field == "id":
                    keys.append(-idx if desc else idx)
                else:
                    col = self._sort_desc[field] if desc else self._sort_asc[field]
                    keys.append(col[idx])
            return idx[np.lexsort(tuple(keys))]

        # Pure-Python stable multi-pass Timsort using C-level __getitem__ (matches np.lexsort stability).
        if "id" not in used:
            idx.sort()
        for field, desc in reversed(stages):
            if field == "id":
                idx.sort(reverse=desc)
            else:
                col = self._sort_desc[field] if desc else self._sort_asc[field]
                idx.sort(key=col.__getitem__)
        return idx

    def _project(self, track_ids, fields):
        if not fields:
            return [self._list_rows[track_id] for track_id in track_ids]
        if self._projection_fields != fields:
            self._projection_fields = fields
            self._projection_rows = {}
        cache = self._projection_rows
        columns = LIST_FIELDS + fields
        pick = itemgetter(*columns)
        rows = []
        for track_id in track_ids:
            row = cache.get(track_id)
            if row is None:
                row = dict(zip(columns, pick(self._tracks[track_id]), strict=False))
                cache[track_id] = row
            rows.append(row)
        return rows

    def query(self, request: dict) -> dict:
        start = perf_counter()
        include_facets = request.get("facets") is not False
        mask = self._make_mask(True)
        possible = self.total > 0

        def select_many(field, values):
            nonlocal possible, mask
            if not possible or not isinstance(values, list) or not values:
                return
            values = [v for v in values if isinstance(v, str)]
            if not values:
                return
            if field == "genre":
                g_ids = [self._genre_vocab[v] for v in values if v in self._genre_vocab]
                if not g_ids:
                    possible = False
                elif len(g_ids) == 1:
                    gid = g_ids[0]
                    if np is not None:
                        mask &= (self._genre_idx == gid)
                    else:
                        g_idx = self._genre_idx
                        for i in range(self.total):
                            if mask[i] and g_idx[i] != gid:
                                mask[i] = 0
                else:
                    if np is not None:
                        lut = np.zeros(len(self._genre_vocab), dtype=bool)
                        lut[g_ids] = True
                        mask &= lut[self._genre_idx]
                    else:
                        allowed = set(g_ids)
                        g_idx = self._genre_idx
                        for i in range(self.total):
                            if mask[i] and g_idx[i] not in allowed:
                                mask[i] = 0
            else:
                if np is not None:
                    sub = np.zeros(self.total, dtype=bool)
                    has_any = False
                    for v in values:
                        km = self._key_masks.get(v)
                        if km is not None:
                            sub |= km
                            has_any = True
                    if not has_any:
                        possible = False
                    else:
                        mask &= sub
                else:
                    has_any = any(v in self._key_masks for v in values)
                    if not has_any:
                        possible = False
                    else:
                        masks = [self._key_masks[v] for v in values if v in self._key_masks]
                        if len(masks) == 1:
                            km0 = masks[0]
                            for i in range(self.total):
                                if mask[i] and not km0[i]:
                                    mask[i] = 0
                        else:
                            for i in range(self.total):
                                if mask[i]:
                                    matched = False
                                    for km in masks:
                                        if km[i]:
                                            matched = True
                                            break
                                    if not matched:
                                        mask[i] = 0

        def bound(field, value, op_name):
            nonlocal mask
            if not possible:
                return
            value = number(value)
            if value is not None:
                op_fn = NP_OPS[op_name]
                raw = self._num_raw[field]
                valid = self._num_valid[field]
                if np is not None:
                    mask &= op_fn(raw, value) & valid
                else:
                    for i in range(self.total):
                        if mask[i] and not (valid[i] and op_fn(raw[i], value)):
                            mask[i] = 0

        search = folded(str(request.get("search") or "")[:300]).split()
        if search and possible:
            if np is not None:
                mask &= np.fromiter(
                    (all(term in text for term in search) for text in self._search_texts),
                    dtype=bool,
                    count=self.total,
                )
            else:
                for i, text in enumerate(self._search_texts):
                    if mask[i] and not all(term in text for term in search):
                        mask[i] = 0

        if isinstance(request.get("rules"), list):
            for rule in request["rules"]:
                if possible and not self._apply_rule(mask, rule):
                    possible = False

        if possible and isinstance(request.get("groups"), list) and request["groups"]:
            group_logic = "OR" if request.get("groupLogic") == "OR" else "AND"
            group_masks = []
            for group in request["groups"]:
                if not isinstance(group, dict) or not isinstance(group.get("rules"), list):
                    continue
                active_rules = [
                    rule
                    for rule in group["rules"]
                    if isinstance(rule, dict)
                    and (
                        rule.get("op") == "empty"
                        or str(rule.get("value") if rule.get("value") is not None else "").strip() != ""
                    )
                ]
                if not active_rules:
                    continue
                mode = "OR" if group.get("mode") == "OR" else "AND"
                g_mask = self._make_mask(mode == "AND")
                for rule in active_rules:
                    if mode == "AND":
                        if not self._apply_rule(g_mask, rule):
                            if np is not None:
                                g_mask.fill(False)
                            else:
                                g_mask = bytearray(self.total)
                    else:
                        r_mask = self._make_mask(True)
                        if self._apply_rule(r_mask, rule):
                            self._or_into(g_mask, r_mask)
                group_masks.append(g_mask)
            if group_masks:
                if group_logic == "AND":
                    for g_mask in group_masks:
                        self._and_into(mask, g_mask)
                else:
                    combined = self._make_mask(False)
                    for g_mask in group_masks:
                        self._or_into(combined, g_mask)
                    self._and_into(mask, combined)

        exclude_id = request.get("excludeId")
        if possible and isinstance(exclude_id, str):
            pos = self._id_pos.get(exclude_id)
            if pos is not None:
                mask[pos] = False if np is not None else 0

        genres = (
            self._group_facet(self._genre_idx, self._genre_list, self._genre_nocase, mask)
            if (include_facets and possible)
            else []
        )
        select_many("genre", request.get("genres"))
        if include_facets and possible:
            genre_count = int(np.count_nonzero(mask)) if np is not None else sum(mask)
        else:
            genre_count = 0

        histogram = self._histogram_from_mask(mask) if (include_facets and possible) else []
        bound("bpm", request.get("bpmMin"), "gte")
        bound("bpm", request.get("bpmMax"), "lte")
        if include_facets and possible:
            bpm_count = int(np.count_nonzero(mask)) if np is not None else sum(mask)
        else:
            bpm_count = 0

        keys = (
            self._group_facet(self._key_idx, self._key_list, self._key_nocase, mask)
            if (include_facets and possible)
            else []
        )
        select_many("key", request.get("keys"))
        if include_facets and possible:
            key_count = int(np.count_nonzero(mask)) if np is not None else sum(mask)
        else:
            key_count = 0

        bound("rating", request.get("rating"), "gte")
        bound("year", request.get("yearMin"), "gte")
        bound("year", request.get("yearMax"), "lte")
        bound("plays", request.get("plays"), "gte")

        if possible:
            if np is not None:
                idx = np.flatnonzero(mask)
                if idx.size:
                    idx = self._sort_positions(idx, request)
                    ids = [self._ids[i] for i in idx.tolist()]
                else:
                    ids = []
            else:
                idx = [i for i, flag in enumerate(mask) if flag]
                if idx:
                    idx = self._sort_positions(idx, request)
                    ids = [self._ids[i] for i in idx]
                else:
                    ids = []
        else:
            ids = []

        if request.get("idsOnly") is True:
            rows = ids
        else:
            extra_fields = request.get("fields")
            extra_fields = (
                tuple(dict.fromkeys(field for field in extra_fields if field in DETAIL_FIELDS and field not in LIST_FIELDS))
                if isinstance(extra_fields, list)
                else ()
            )
            rows = self._project(ids, extra_fields)

        return {
            "rows": rows,
            "counts": [genre_count, bpm_count, key_count, len(rows)],
            "genres": genres,
            "keys": keys,
            "histogram": histogram,
            "ms": round((perf_counter() - start) * 1000, 3),
        }

    def detail(self, track_id) -> dict | None:
        track = self._tracks.get(str(track_id))
        return track.copy() if track else None

    def match_media(self, remote):
        if not remote:
            return None
        identity = metadata_identity(remote)
        name = file_name(remote["path"])
        same_file = self.by_file.get(name, []) if name else []
        same_metadata = self.by_metadata.get(identity, []) if all(identity) else []
        file_ids = {row["id"] for row in same_file}
        matching = [track for track in same_metadata if track["id"] in file_ids]
        if len(matching) == 1:
            return matching[0]
        if self.kind == "Master" and (linked := self._tracks.get(remote.get("original_id"))):
            if (
                linked in same_metadata
                and remote["seconds"]
                and linked["seconds"]
                and abs(linked["seconds"] - remote["seconds"]) <= 2
            ):
                return linked
        if len(same_file) == 1 and len(same_metadata) == 1 and same_file[0]["id"] != same_metadata[0]["id"]:
            return None
        for candidates in (matching or same_metadata, same_file if not same_metadata else []):
            valid = [
                track
                for track in candidates
                if remote["seconds"] and track["seconds"] and abs(track["seconds"] - remote["seconds"]) <= 2
            ]
            if len(valid) == 1:
                return valid[0]
        return None

    def recommendations(self, bpm, key, exclude_id, tolerance, harmonic):
        if bpm is None or (harmonic and not key):
            return []
        related = compatible(key)
        statement = "SELECT id FROM tracks WHERE bpm BETWEEN ? AND ? AND id != ?"
        values = [bpm - tolerance, bpm + tolerance, exclude_id or ""]
        if harmonic:
            statement += f" AND key IN ({','.join('?' for _ in related)})"
            values.extend(related)
        rows = [self._list_rows[row[0]].copy() for row in self.conn.execute(statement, values)]
        for row in rows:
            row["delta"] = round(row["bpm"] - bpm, 2)
            row["relation"] = related.get(row["key"], "Tempo")
        rows.sort(key=lambda row: (abs(row["delta"]), row["key"] != key, -row["rating"], row["id"]))
        return rows[:50]


def waveform_with_source(library: Library | None, track: dict | None) -> tuple[list[int], str]:
    """Return (samples, source) where source is 'real' (ANLZ PWAV) or 'none'."""
    if not library or not library.path or not track or not track.get("analysis"):
        return [], "none"
    try:
        from pyrekordbox.anlz import AnlzFile
    except ImportError:
        return [], "none"
    try:
        from construct import ConstructError
    except ImportError:
        ConstructError = OSError
    relative = Path(track["analysis"].lstrip("/\\"))
    parent = library.path.parent
    roots = [parent, parent / "share", parent.parent, parent.parent.parent]
    for root in roots:
        try:
            file = (root / relative).resolve()
            if not file.is_relative_to(root.resolve()) or not file.is_file() or file.stat().st_size > 32_000_000:
                continue
            preview = AnlzFile.parse_file(file).get("PWAV")
            if preview:
                return [int(value) for value in preview[0]], "real"
            return [], "none"
        except (ConstructError, KeyError, OSError, TypeError, ValueError):
            continue
    return [], "none"


def waveform(library: Library | None, track: dict | None) -> list[int]:
    samples, _ = waveform_with_source(library, track)
    return samples
