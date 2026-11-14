# Abschlussbericht Online-Recherche: Ergebnisse aus Cuepoint in Rekordbox importieren

**Datum:** 2026-11-14  
**Auftrag:** Online-Recherche & realtechnische Machbarkeitsbewertung zum Thema „Import in Rekordbox / Übergabe gefilterter App-Ergebnisse nach Rekordbox“ inkl. Behebung des Dev-Server-Starts.  
**Orchestrierte Subagenten:**
1. **Ops-Fix-Subagent** – Diagnose & Behebung des Dev-Server-Starts (`@tailwindcss/node` / `bun install` → `install_applet_dependencies` + `restart_dev_server` → `/api/cuepoint/health` = `200 OK`)
2. **Online-Recherche-Subagent** – Auswertung offizieller AlphaTheta/Rekordbox-Handbücher, GitHub-Projekte (`pyrekordbox`, `rbsync`), Library-Tools (`Lexicon DJ`, `MIXO`) und Community-Foren (`Reddit r/Rekordbox`, `Pioneer DJ Forum`)
3. **Architektur- & Machbarkeits-Subagent** – Abgleich aller Verfahren gegen Cuepoints aktuelle Implementierung (`src/api.ts`, `src/main.tsx`, `backend/sources.py`, `backend/rekordbox_live.py`) und die Ziel-Datenbank `E:\PIONEER\Master`
4. **Verifier-Subagent** – Prüfung auf faktische Korrektheit, technische Risiken (Locking, XML-Bug, Pfadtreue) und saubere Trennung zwischen Live-Betrieb und Offline-Vorbereitung

---

## 1. Gesamtbewertung nach Anwendungsfall

| Anwendungsfall des Users | Beste realtechnische Lösung | Zustand in Cuepoint heute | Sinnvolle nächste Ausbaustufe |
|---|---|---|---|
| **Live am Controller (Rekordbox läuft):** Gefundenen Track sofort laden / durch wenige Treffer zappen | **Windows UI Automation** über angrenzenden Button + Tracktitel-Suche (`↗ In Rekordbox`, `▶ Deck A`, `▶ Deck B`) | **Vollständig implementiert** (`backend/rekordbox_live.py`) | Optionaler Shortcut/Auto-Fokus-Feinschliff beim lokalen Windows-Test |
| **Live am Controller (Rekordbox läuft):** Ganze gefilterte Ergebnisliste (z. B. 20 Tracks) in Rekordbox öffnen | **Feste XML-Bridge-Datei** (`cuepoint-bridge.xml`) + manueller oder UIA-gestützter Klick auf *XML Refresh* | **Export-XML vorhanden** (`exportRekordboxXml`), aktuell als Browser-Download | Direktspeicherung in festen XML-Pfad + optionaler UIA-Click auf „rekordbox xml“-Refresh |
| **Vorbereitung (Rekordbox geschlossen):** Gefilterte Playlisten / Setlists dauerhaft in Rekordbox speichern | **1) Sicher:** XML / `.m3u8` Import<br>**2) Komfortabel (wie Lexicon/`rbsync`):** Direkter SQLCipher-Playlist-Sync in `master.db` bei geschlossenem Rekordbox | **M3U8, XML & CSV-Export vorhanden**; `master.db` derzeit **strikt Read-Only** | Optionaler „Direct Sync (Offline)“-Button mit Prozess-Sperre (`rekordbox.exe` + `rekordboxAgent.exe`) & automatischem Backup |

---

## 2. Detaillierte Technische Auswertung aller Import-Wege

### 2.1 Offizielle Schnittstellen von AlphaTheta / Rekordbox
- **Keine Desktop-API / Kein SDK:** Es existiert **keine** dokumentierte API, kein COM-Interface, kein WebSocket und kein CLI-Befehl, mit dem eine Fremd-App ein laufendes Rekordbox programmatisch anweisen könnte „zeige Liste X an“ oder „importiere Playlist Y im Hintergrund“. PRO DJ LINK Bridge liefert nur Echtzeit-Player-Daten in Gegenrichtung (für Licht/Visuals).
- **Rekordbox XML (`<DJ_PLAYLISTS Version="1.0.0">`):**
  - Offiziell unterstützter Austauschstandard in Rekordbox 6 & 7.
  - **Vorteil:** Absolut schreibsicher für `master.db`, weil Rekordbox den Import selbst parst und in die eigene Datenbank übernimmt; überträgt Playlists, Ordner und Metadaten.
  - **Realtechnische Nachteile laut Dokumentation & Foren:**
    1. Kein Auto-Watcher: Rekordbox lädt eine geänderte XML-Datei **nicht automatisch** neu.
    2. Kein Hotkey: Weder Standard-Shortcut noch mappable Keyboard-Aktion für „XML aktualisieren“. Man muss in der linken Seitenleiste auf das **Reload-Icon neben `rekordbox xml`** klicken.
    3. **Bekannter XML-Überschreib-Bug (seit v5.6.1 bis 6.8/7.0):** Sind Tracks bereits in der Collection, ignoriert Rekordbox beim Playlist-Import häufig Metadaten-Updates; Workaround ist das Zwei-Schritt-Verfahren (erst Playlist importieren, danach Tracks im XML-Baum per `Strg+A → Zur Collection importieren`). Für die reine *Playlist-Zuordnung* vorhandener Tracks greift der Abgleich aber sauber, **sofern die `Location`-Pfade zeichengenau identisch sind** – was Cuepoint garantiert, weil `FolderPath` direkt aus `master.db` gelesen wird.
- **M3U8-Import (`#EXTM3U` in UTF-8):**
  - Offiziell über **Datei → Import → Playlist importieren**.
  - **Realtechnische Grenzen laut Foren:** Kein direktes Drag-and-Drop von `.m3u8` aus dem Windows Explorer in die Trackliste; erfordert identische lokale Dateipfade und schlägt bei reinem ANSI-`.m3u` mit Sonderzeichen/Umlauten fehl (UTF-8 `.m3u8` ohne BOM erforderlich). Große Batch-Imports können Rekordbox kurzzeitig einfrieren.
- **ID3-Comment-Tags + Intelligent Playlists:**
  - **MyTags** und **Intelligent Playlists** sind proprietär in `master.db` gekapselt und über XML nicht erzeugbar.
  - Der in Foren etablierte Workaround: Externe Tools schreiben Hashtags (z. B. `#cuepoint_peak`) in das Standard-ID3-Feld `COMMENT` der Audio-Datei; in Rekordbox legt man *einmalig* eine Intelligent Playlist (`Comment enthält #cuepoint_peak`) an und klickt „Tag-Info neu laden“. *Nachteil:* Modifiziert die physischen Audiodateien und ist für Live-Filterwechsel zu träge.
- **OneLibrary / Device Library Plus (`exportLibrary.db`):**
  - USB-Exportdatenbank (seit 2024/2025 schrittweise von *Device Library Plus* auf *OneLibrary* umbenannt). Ebenfalls SQLCipher-verschlüsselt, für Hardware-Sticks und Cross-App-USB-Austausch (djay Pro / Traktor 4) konzipiert, nicht für Live-Import in die laufende Desktop-Collection.

### 2.2 Inoffizielle / Reverse-Engineered & UI-Automations-Wege
- **Direktschreiben in `master.db` (`pyrekordbox`, Lexicon Direct Sync, MIXO, `rbsync`):**
  - **Wie es technisch funktioniert:** `pyrekordbox` entschlüsselt `master.db` per SQLCipher (über die lokalen Key-Blobs) und manipuliert per SQLAlchemy-ORM direkt die Tabellen `djmdPlaylist` und `djmdSongPlaylist`. So lassen sich gefilterte Playlisten blitzschnell anlegen und aktualisieren, ohne bestehende Cue-Points oder Beatgrids anzutasten.
  - **Warum das LIVE unmöglich ist:** Solange `rekordbox.exe` oder der Hintergrunddienst `rekordboxAgent.exe` läuft, hält Rekordbox eine exklusive Dateisperre und den Zustand der Bibliothek im RAM. Ein Eingriff bei laufendem Rekordbox führt fast sicher zu **Dateisperr-Fehlern oder Datenbank-Korruption (`master.db` + `-wal`/`-shm`)** und Datenverlust. Jedes seriöse Tool (`rbsync`, Lexicon) **verweigert das Schreiben strikt, sobald ein Rekordbox-Prozess aktiv ist**, und legt zuvor ein Voll-Backup an.
- **Windows UI Automation + Keyboard Shortcuts (Live-Steuerung):**
  - Einziger Weg, der **während einer laufenden Rekordbox-Session** ohne Neustart wirkt.
  - Offizielle Performance-Mode-Shortcuts (`Shift+Links` Deck 1, `Shift+Rechts` Deck 2) kombiniert mit UIA-Koordinatenklick neben dem Such-Button (`backend/rekordbox_live.py`) arbeiten zu **100 % nicht-destruktiv** auf `master.db`.

---

## 3. Empfehlung für Cuepoint (Konkrete nächste Schritte)

1. **Für den Sofort-Test am Controller (Live):** Die bereits gebaute UIA-Tracktitel-Übergabe (`↗ In Rekordbox` / `▶ Deck A` / `▶ Deck B`) ist realtechnisch der stabilste, sicherste und schnellste Live-Weg.
2. **Für „Gefilterte Liste komplett in Rekordbox anzeigen“ (zwei Ausbaustufen bei Bedarf):**
   - **Ausbaustufe 1 (Live-freundlich, 0 % Risiko):** Statt manuellem Datei-Download eine **feste Bridge-XML-Datei** schreiben (z. B. `E:\PIONEER\cuepoint-bridge.xml`), die einmalig in Rekordbox verknüpft wird – ein Klick auf Refresh in Rekordbox (oder per UIA) lädt sofort die aktuelle gefilterte Trefferliste als Playlist.
   - **Ausbaustufe 2 (Offline-Sync wie Lexicon/`rbsync`):** Ein abgesicherter Button „Playlist direkt in Rekordbox schreiben (nur wenn Rekordbox geschlossen ist)“ über `pyrekordbox` mit Pflicht-Backup und automatischer Prozessprüfung (`rekordbox.exe` & `rekordboxAgent.exe`).
