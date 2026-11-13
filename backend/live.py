"""Pro DJ Link UDP 50000/50002 listener, packet decoder, and interface discovery."""

from __future__ import annotations

import ipaddress
import os
import select
import socket
import threading
import time

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - optional in minimal Linux sandbox
    psutil = None  # type: ignore

from diagnostics import CuepointError, emit_log

MAGIC = b"Qspt1WmJOL"
SLOTS = {2: "SD / USB 1", 3: "USB", 4: "Rekordbox", 7: "USB 2"}


def interfaces() -> list[dict]:
    if psutil is None:
        return []
    stats = psutil.net_if_stats()
    result = []
    for name, addresses in psutil.net_if_addrs().items():
        if name not in stats or not stats[name].isup:
            continue
        mac = next((address.address for address in addresses if address.family == psutil.AF_LINK), "")
        for address in addresses:
            if address.family != socket.AF_INET or not address.netmask:
                continue
            ip = ipaddress.IPv4Interface(f"{address.address}/{address.netmask}")
            if not ip.ip.is_loopback and len(mac.replace("-", "").replace(":", "")) == 12:
                result.append({
                    "name": name,
                    "ip": address.address,
                    "mac": mac,
                    "broadcast": str(ip.network.broadcast_address),
                    "network": ip.network,
                })
    return result


def decode_status(packet: bytes) -> dict | None:
    if len(packet) < 0xA0 or not packet.startswith(MAGIC + b"\x0a"):
        return None
    deck = packet[0x21]
    if not 1 <= deck <= 15 or packet[0x24] != deck:
        return None
    name = packet[0x0B:0x1F].split(b"\0")[0].decode("ascii", "replace").strip()
    bpm = int.from_bytes(packet[0x92:0x94], "big")
    multiplier = int.from_bytes(packet[0x8C:0x90], "big") / 0x100000
    effective = round(bpm * multiplier / 100, 2) if bpm not in (0, 0xFFFF) and 0 < multiplier <= 2 else None
    return {
        "deck": deck,
        "name": name,
        "source": packet[0x28],
        "slot": packet[0x29],
        "trackType": packet[0x2A],
        "trackId": str(int.from_bytes(packet[0x2C:0x30], "big")),
        "bpm": effective,
        "playing": bool(packet[0x89] & 0x40),
        "master": bool(packet[0x89] & 0x20),
    }


def announcement(interface: dict, deck: int) -> bytes:
    mac = bytes.fromhex(interface["mac"].replace("-", "").replace(":", ""))
    return (
        MAGIC
        + b"\x06\0"
        + b"Cuepoint".ljust(20, b"\0")
        + bytes((1, 2, 0, 54, deck, 1))
        + mac
        + socket.inet_aton(interface["ip"])
        + b"\x02\x00\x00\x00\x01\x64"
    )


def _listener(host: str, port: int) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if os.name == "nt":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((host, port))
        listener.setblocking(False)
        return listener
    except OSError:
        listener.close()
        raise


class DjLink:
    def __init__(self):
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._decks = {}
        self._devices = {}
        self.state, self.error = "off", None

    def start(self, ip: str, announce: bool) -> None:
        interface = next((item for item in interfaces() if item["ip"] == ip), None)
        if not interface and (announce or ip != "127.0.0.1"):
            raise CuepointError("NETWORK_INTERFACE_UNAVAILABLE", "Diese Netzwerkschnittstelle ist nicht mehr verfügbar.")
        self.stop()
        listeners = []
        try:
            listeners.append(_listener(ip, 50002))
            if announce:
                listeners.append(_listener("", 50000))
                listeners[0].setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except OSError as exc:
            for listener in listeners:
                listener.close()
            raise CuepointError("DJ_LINK_PORT_UNAVAILABLE", f"Pro DJ Link: UDP-Port ist nicht verfügbar ({exc}).") from None
        self._stop.clear()
        with self._lock:
            self._decks.clear()
            self._devices.clear()
            self.state = "discovering" if announce else "listening"
            self.error = None
        self._thread = threading.Thread(
            target=self._run,
            args=(listeners, interface),
            name="pro-dj-link",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.5)
            self._thread = None
        with self._lock:
            self._decks.clear()
            self._devices.clear()
            self.state, self.error = "off", None

    def _run(self, listeners, interface) -> None:
        chosen, next_announcement = 15, 0
        status = listeners[0]
        network = interface["network"] if interface else ipaddress.IPv4Network("127.0.0.1/32")
        try:
            while not self._stop.is_set():
                readable, _, _ = select.select(listeners, [], [], 0.25)
                now = time.monotonic()
                for listener in readable:
                    packet, (sender, _) = listener.recvfrom(4096)
                    if ipaddress.IPv4Address(sender) not in network:
                        continue
                    if len(packet) >= 54 and packet.startswith(MAGIC + b"\x06"):
                        device = packet[0x24]
                        if 1 <= device <= 15 and device != chosen:
                            with self._lock:
                                self._devices[device] = now
                    elif state := decode_status(packet):
                        with self._lock:
                            self._decks[state["deck"]] = (now, state)
                            self.state, self.error = "listening", None
                if len(listeners) > 1 and now >= next_announcement:
                    self._devices = {device: seen for device, seen in self._devices.items() if now - seen < 5}
                    available = [index for index in range(7, 16) if index not in self._devices]
                    if self._devices and available:
                        chosen = chosen if chosen in available else available[0]
                        status.sendto(announcement(interface, chosen), (interface["broadcast"], 50000))
                        with self._lock:
                            self.state, self.error = "listening", None
                    else:
                        with self._lock:
                            self.state = "discovering"
                            self.error = "Alle virtuellen Player-Nummern sind belegt." if self._devices else None
                    next_announcement = now + 1.5
        except OSError as exc:
            emit_log("ERROR", "DJ_LINK", "dj_link_runtime_error", str(exc))
            with self._lock:
                self.state, self.error = "error", f"Pro DJ Link: {exc}"
        finally:
            for listener in listeners:
                listener.close()

    def snapshot(self):
        now = time.monotonic()
        with self._lock:
            decks = [deck for seen, deck in self._decks.values() if now - seen < 4]
            return self.state, self.error, sorted(decks, key=lambda deck: deck["deck"])
