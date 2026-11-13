"""Diagnostic helper to inspect live Rekordbox UI Automation controls on Windows."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import rekordbox_live  # noqa: E402


def main() -> int:
    if os.name != "nt":
        print("unverified-non-windows: Rekordbox UIA requires Windows desktop session")
        return 0
    hwnd = rekordbox_live._rekordbox_window()
    if not hwnd:
        print("unverified-no-live-rekordbox")
        return 0

    import comtypes  # type: ignore
    from comtypes.client import CreateObject, GetModule  # type: ignore

    comtypes.CoInitialize()
    try:
        uia = GetModule("UIAutomationCore.dll")
        automation = CreateObject(uia.CUIAutomation, interface=uia.IUIAutomation)
        decks = rekordbox_live._discover(automation, uia, hwnd)
        print(f"HWND={hwnd} discovered_decks={len(decks)}")
        for idx, d in enumerate(decks, 1):
            fader_val = rekordbox_live._normalized_slider(d[10], uia) if d[10] else None
            xf_val = rekordbox_live._normalized_slider(d[11], uia) if d[11] else None
            print(f"  Deck {idx}: title={d[0].CurrentName!r}, channel_fader={fader_val}, crossfader={xf_val}")
        return 0
    finally:
        comtypes.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
