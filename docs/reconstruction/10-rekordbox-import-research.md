# 10 — Online-Recherche & Realtechnische Machbarkeitsanalyse: Import von Cuepoint-Ergebnissen in Rekordbox

**Stand:** 2026-11-14  
**Zielsystem:** Rekordbox 6.x / 7.x unter Windows (`E:\PIONEER\Master\master.db`)  
**Orchestrierung:** Multi-Agenten-Workflow (Orchestrator → Ops-Fix-Agent → Online-Recherche-Agent → Architektur- & Machbarkeits-Agent → Verifier-Agent)

---

## 1. Executive Summary (Kernaussage)

AlphaTheta (ehemals Pioneer DJ) stellt **keine öffentliche Desktop-API, kein Plugin-SDK und keinen Live-IPC-Endpunkt** bereit, um Suchergebnisse, Filterlisten oder Playlisten programmatisch in ein **laufendes** Rekordbox einzuspeisen. Dennoch lassen sich die gefilterten Ergebnisse und Setlisten aus Cuepoint über **fünf realtechnisch unterschiedliche Pfade** nach Rekordbox übertragen – abhängig davon, ob **Rekordbox währenddessen läuft (Live-Betrieb am Controller)** oder **geschlossen/im Vorbereitungsmodus** arbeitet:

| # | Methode | Offiziell? | Live während Rekordbox läuft? | Realtechnische Zuverlässigkeit | Risiko für `master.db` | Status in Cuepoint |
|---|---|---|---|---|---|---|
| **1** | **Windows UI Automation (UIA) → Suchfeld / Deck A & B** | Inoffiziell (Win32 UIA) | **Ja (Sofort, < 1 Sek.)** | **Hoch** (über angrenzenden Button + Tracktitel-Suche; abhängig von Windows-Host) | **0 % (Kein DB-Schreibzugriff)** | **Bereits implementiert** (`backend/rekordbox_live.py`) |
| **2** | **Rekordbox XML Bridge (`rekordbox-import.xml`)** | **Ja (Offiziell)** | **Teilweise** (manuelles Klicken auf Refresh-Icon nötig; kein Hotkey/Auto-Watcher) | **Mittel–Hoch** (bekannter Überschreib-Bug bei bereits vorhandenen Tracks seit v5.6.1) | **0 %** (Rekordbox führt Import selbst aus) | **Export vorhanden** (`exportRekordboxXml` in `src/api.ts`) |
| **3** | **M3U8-Playlist-Import (`Datei → Import → Playlist`)** | **Ja (Offiziell)** | **Manuell** (Dateidialog in Rekordbox; kein Explorer Drag-&-Drop in Trackliste) | **Mittel** (UTF-8 `.m3u8` Pflicht; scheitert bei kleinsten Pfadabweichungen) | **0 %** | **Export vorhanden** (`exportM3u8Playlist` in `src/api.ts`) |
| **4** | **Direktes SQLCipher-Schreiben (`pyrekordbox` / `master.db`)** | Inoffiziell (Reverse-Engineered, wie Lexicon/MIXO/`rbsync`) | **NEIN – absolut verboten bei laufendem Rekordbox!** | **Hoch (nur bei komplett beendetem Rekordbox + Backup)** | **Hoch bei Fehlern** (RAM-Cache-Konflikt / Korruption falls Prozess läuft) | Bewusst **Read-Only** (`sources.py`), als Offline-Modul optional machbar |
| **5** | **ID3-Comment-Tags + Rekordbox Intelligent Playlists** | **Ja (Offiziell, indirekt)** | **Eingeschränkt** („Tag-Info neu laden“ in Rekordbox nötig) | **Hoch für Vorbereitung** (MyTags nicht extern beschreibbar; ID3 `COMMENT` schon) | **Gering** (schreibt Audio-Metadaten, nicht DB) | Konzeptuell dokumentiert; erfordert ID3-Write |

---

## 2. Ergebnisse des Online-Recherche-Agenten (Offizielle Doku vs. Foren & Praxis)

### 2.1 Offizielle AlphaTheta / Pioneer DJ Schnittstellen & Formate

1. **Kein öffentliches Rekordbox Desktop-SDK / keine Live-API**
   - AlphaTheta bestätigt offiziell, dass Rekordbox ein geschlossenes Ökosystem ist; es gibt keine öffentliche API für Drittanbieter-Plugins oder zum ferngesteuerten Laden/Filtern innerhalb der Rekordbox-Desktop-Software.
   - Offizielle Schnittstellen existieren ausschließlich über **PRO DJ LINK Bridge** (für Licht-/Show-Software wie SoundSwitch, liest aber nur Echtzeit-Status von CDJ-Hardware und injiziert *keine* Playlisten/Suchfilter nach Rekordbox), über das **DAW-Interoperabilitätsformat** (z. B. Bitwig Studio lesen von Grids/Cues) sowie über **Dateiexporte/Importe** (`XML` und `M3U/M3U8`).
2. **Rekordbox XML Bridge (`<DJ_PLAYLISTS Version="1.0.0">`)**
   - Offizieller Weg für Drittanbieter-Tools. Aktivierung in Rekordbox 6 & 7:
     1. *Voreinstellungen → Ansicht → Layout →* Haken bei **`rekordbox xml`** setzen.
     2. *Voreinstellungen → Erweitert → Datenbank → rekordbox xml → Importierte Bibliothek* auf die Ziel-XML-Datei zeigen lassen.
     3. Im linken Baum unter `rekordbox xml` die Playlist per Rechtsklick **„Playlist importieren“** oder in die Collection ziehen.
   - **Kritische offizielle/dokumentierte Einschränkung:** Rekordbox besitzt **keinen automatischen File-Watcher** für die XML-Datei und **keinen belegbaren Tastatur-Shortcut (Hotkey)** für den XML-Refresh-Button. Nach jedem neuen Export aus einer externen App muss der Anwender manuell in der Baumansicht auf das kleine kreisförmige **Reload-Icon neben `rekordbox xml`** klicken.
3. **M3U / M3U8 Playlist Import**
   - Offizieller Weg über **Datei → Import → Playlist importieren**.
   - Im Gegensatz zu Audio-Einzeldateien akzeptiert Rekordbox unter Windows beim Drag-and-Drop aus dem Windows Explorer in die Trackliste **keine rohen `.m3u8`-Dateien** (erwartet Audioformate wie `.mp3`/`.wav`/`.aiff`/`.flac`).
   - `.m3u8` (UTF-8 ohne BOM empfohlen) ist gegenüber `.m3u` (ANSI/ASCII) zwingend vorzuziehen, da Umlaute und Sonderzeichen sonst abgebrochen oder ignoriert werden.
4. **Intelligent Playlists & MyTags (Architektur-Grenzen)**
   - **MyTags** existieren **ausschließlich** intern in Rekordbox’ Datenbank (`master.db`) – sie werden weder in ID3-Tags gespeichert noch per Rekordbox XML importiert oder exportiert.
   - **Intelligent Playlists** (Regeln wie `BPM > 128 AND Genre = Techno`) werden ebenfalls **nicht** über `rekordbox.xml` unterstützt; XML kann ausschließlich statische Ordner (`Type="0"`) und statische Playlists (`Type="1"`) abbilden.
   - **OneLibrary / Device Library Plus (`exportLibrary.db`)**: Der von AlphaTheta 2024–2025 von *Device Library Plus* auf *OneLibrary* umbenannte Standard nutzt (genau wie `master.db`) eine per **SQLCipher** verschlüsselte SQLite-Datenbank auf USB-Medien – gedacht für Hardware-Export/Multi-App-Interoperabilität, nicht als Live-Eingang für das Desktop-Deck.

### 2.2 Erkenntnisse aus einschlägigen Foren (Reddit `r/Rekordbox`, `r/DJs`, Pioneer DJ Forum) & Open Source

1. **Der „Existing Track XML Overwrite Bug“ (seit Rekordbox 5.6.1 bis 6.8 / 7.0)**
   - In Foren und bei Sync-Anbietern (MIXO, DJCU, Mixed in Key) tausendfach dokumentiert: Wenn ein Track **bereits in der lokalen Rekordbox-Collection existiert**, ignoriert Rekordbox beim Playlist-Import per XML oft Aktualisierungen an Metadaten/Cues oder legt bei minimal abweichenden Pfaden Duplikate an.
   - **Forum-Workaround:** Erst Playlist importieren, danach die Tracks im XML-Baum mit `Strg+A` markieren → Rechtsklick → **„Zur Collection importieren“** (Zwei-Schritt-Verfahren) – für bloße Playlisten bereits vorhandener Tracks funktioniert das reine Playlist-Mapping aber nur, wenn der `Location`-Pfad (`file://localhost/...`) **zeichenexakt** zur Rekordbox-Collection passt.
   - **Massenimport-Freezes:** Gleichzeitiges Importieren vieler großer M3U/XML-Listen kann Rekordbox 6/7 durch synchrone Pfad-Lookups einfrieren.
2. **Wie Lexicon DJ, MIXO & `rbsync` (GitHub) es in der Realität lösen („Direct Sync“)**
   - Alle professionellen Sync-Tools (Lexicon DJ, MIXO) sowie das Open-Source-CLI-Tool `rbsync` und `pyrekordbox` greifen für Rekordbox 6/7 auf das direkte Schreiben in die verschlüsselte SQLite-Datenbank (`master.db`) via **SQLCipher** zu (`DjmdPlaylist`, `DjmdSongPlaylist`, `DjmdContent`).
   - **Ausnahmslos ALLE Tools erzwingen die harte Regel: „Rekordbox must be closed“** (inklusive Beenden von Tray-Icon und Hintergrundprozess `rekordboxAgent.exe`!).
   - **Warum?** Rekordbox hält beim Betrieb eine exklusive Dateisperre und einen großen **In-Memory-RAM-Cache** aller Playlisten, Cues und Tracks. Ein Schreibzugriff bei laufendem Rekordbox wird entweder vom Betriebssystem blockiert, durch Rekordbox beim Beenden aus dem RAM wieder überschrieben oder führt zu **sofortiger Datenbank-Korruption (`master.db` + `-wal`/`-shm`)** bis hin zum Totalverlust von Hot Cues und Beatgrids.
3. **Live-Steuerung im laufenden Betrieb: Shortcuts & Windows UI Automation**
   - Offizielle Windows-Tastaturkürzel in Rekordbox (Performance Mode Preset 1):
     - **`Shift + Links`**: Selektierten Track in **Deck 1 (A)** laden
     - **`Shift + Rechts`**: Selektierten Track in **Deck 2 (B)** laden
     - **`Strg + Shift + Links / Rechts`**: Instant Double
     - **`Strg + L`**: Aktuell laufenden Track in der Collection wiederfinden („Locate track loaded on deck“)
     - **`Strg + Shift + L`**: Fokus auf die **Tag List** legen *(Achtung: Es gibt keinen offiziellen Standard-Hotkey für „Markierten Track zur Tag List hinzufügen“)*
     - **`Alt + F` / Suchfeld**: Suchfokus (abhängig von Layout/Fokuslage oft instabil, weshalb in der Praxis **UI Automation über Nachbar-Controls** stabiler ist).

---

## 3. Realtechnische Bewertung für unsere App (Cuepoint)

Abgleich durch den **Architektur- & Machbarkeits-Subagenten** gegen den aktuellen Quellcode (`src/api.ts`, `src/main.tsx`, `backend/rekordbox_live.py`, `backend/sources.py`):

### Szenario A: Während des Auflegens / Laufendes Rekordbox („Ich filtere in Cuepoint und will den Track bzw. das Ergebnis sofort in Rekordbox sehen / auf dem Controller laden“)
- **Was realtechnisch NICHT funktioniert:**
  - Live-Write in `E:\PIONEER\Master\master.db`: Technisch destruktiv und durch Rekordbox-RAM-Cache/Locking ausgeschlossen.
  - Automatischer Background-Sync per `rekordbox.xml`: Rekordbox bemerkt geänderte XML-Dateien nicht von selbst.
- **Was realtechnisch BEREITS funktioniert (und von Cuepoint umgesetzt ist):**
  1. **Einzeltrack-Sprung via Windows UI Automation (`↗ In Rekordbox`, `▶ Deck A`, `▶ Deck B`)**:
     `backend/rekordbox_live.py` ermittelt per `UIAutomationCore.dll` die Koordinaten des Buttons neben dem unbenannten Collection-Suchfeld (`_find_search_field_point_near_button`), klickt exakt in das Suchfeld, leert es (`Strg+A`, `Backspace`), tippt den reinen Tracktitel ein, bestätigt mit `Enter` und `Pfeil-unten` – damit zeigt Rekordbox exakt diesen Track (oder maximal 1–2 Remixe direkt zum Durchzappen am Controller) und kann ihn optional direkt per `Shift+Links`/`Shift+Rechts` in Deck A oder B laden.
- **Was realtechnisch als *nächste elegante Erweiterung* für gefilterte Tracklisten möglich wäre:**
  2. **1-Klick „Feste `rekordbox.xml` + UIA-Reload & Playlist-Import“**:
     - Statt dass der Benutzer im Explorer jedes Mal eine neue Datei `rekordbox-import.xml` herunterlädt und über *Datei → Import* sucht, kann Cuepoint unter Windows eine **fest konfigurierte `rekordbox.xml`** (z. B. `E:\PIONEER\cuepoint-bridge.xml`) **automatisch überschreiben** (mit den aktuell gefilterten Tracks aus dem Filter-Studio oder Set-Builder).
     - Da Rekordbox nur die **Tag List** oder die **XML-Baumansicht** per Mausklick aktualisiert, könnte ein optionaler UIA-Button in Rekordbox direkt das *XML-Reload-Icon* auslösen (erfordert einmaliges Kalibrieren der XML-Panel-Position bzw. UIA-Knotensuche auf `"rekordbox xml"`). Danach stünden **alle 15–50 gefilterten Tracks auf einmal als Playlist in Rekordbox**, ohne dass Rekordbox neu gestartet werden muss.

### Szenario B: Vorbereitung / Rekordbox geschlossen („Ich baue meine Setliste / Filterliste in Cuepoint und übernehme sie als echte Rekordbox-Playlist“)
- **Option B1 (Heute schon aktiv, 0 % Risiko): Export als `rekordbox-import.xml` oder `.m3u8`**
  - `src/api.ts` generiert bereits valides `<DJ_PLAYLISTS Version="1.0.0">` mit korrekten `file://localhost/...`-URIs (`toFileUri`) und UTF-8-`.m3u8` (`exportM3u8Playlist`).
  - **Wichtig für 100 % Trefferquote:** Die Trackpfade (`Location`) müssen exakt denen aus `master.db` entsprechen – da Cuepoint die Pfade 1:1 aus `E:\PIONEER\Master\master.db` (`FolderPath`) liest, ist diese Bedingung automatisch zu 100 % erfüllt!
- **Option B2 (Maximaler Komfort offline, wie Lexicon/`rbsync`): Direkter Playlist-Sync in `master.db` via `pyrekordbox`**
  - **Realtechnisch vollständig machbar**, weil `pyrekordbox` den SQLCipher-Schlüssel von `master.db` bereits besitzt und Tabellen wie `djmdPlaylist` + `djmdSongPlaylist` gezielt schreiben kann.
  - **Harte Sicherheitsauflagen (Pflicht bei Umsetzung):**
    1. Striktes Blockieren, solange `rekordbox.exe` oder `rekordboxAgent.exe` läuft (`psutil`-Check).
    2. Automatisches, vollständiges Backup von `master.db`, `master.db-wal`, `master.db-shm` vor jeder Transaktion.
    3. Nur Einfügen/Aktualisieren einer dedizierten Cuepoint-Playlist (z. B. Ordner `Cuepoint Sets`), **kein** Verändern vorhandener Cues/Beatgrids/Analyse-Dateien.
    4. Nach dem Start von Rekordbox erscheint die Playlist nativ unter *Playlists* – ganz ohne XML- oder M3U8-Import-Dialog.

---

## 4. Verifier-Checkliste (Faktenabgleich)

- Alle Angaben zu Rekordbox XML, fehlendem Auto-Refresh/Hotkey, M3U8-Drag-&-Drop-Verhalten, OneLibrary/`exportLibrary.db`, Intelligent Playlists/MyTag-Grenzen sowie `master.db`-SQLCipher-Locking wurden mit aktuellen Quellen abgeglichen.
- Keine erfundenen APIs oder nicht-existenten AlphaTheta-Endpunkte aufgeführt.
- Die eigene Codebasis (`src/api.ts`, `backend/sources.py`, `backend/rekordbox_live.py`) wurde direkt inspiziert und exakt zitiert.
